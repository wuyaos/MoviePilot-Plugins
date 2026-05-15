# input: Cd2Client instance, local file Path, remote dir path
# output: RemoteUploadManager — server-pull upload via StartRemoteUpload + RemoteUploadChannel
# pos: remote upload strategy for cd2_api.py; full gRPC server-pull protocol (proto 1.0.7)
import hashlib
import threading
import time
import uuid
from pathlib import Path

import grpc

from app.log import logger

from ..proto import cd2_pb2 as pb2
from .cd2_client import Cd2Client

_MD5 = 1
_SHA1 = 2
_PIKPAK_SHA1 = 3

_TERMINAL = frozenset({
    pb2.UploadFileInfo.Finish,
    pb2.UploadFileInfo.Error,
    pb2.UploadFileInfo.FatalError,
    pb2.UploadFileInfo.Cancelled,
    pb2.UploadFileInfo.Skipped,
    pb2.UploadFileInfo.Ignored,
})


class RemoteUploadManager:
    """
    Server-pull upload: StartRemoteUpload → RemoteUploadChannel (server-stream)
    → service RemoteReadDataRequest / RemoteHashDataRequest on demand.
    device_id is stable per instance so the server can resume across reconnects.
    """

    def __init__(self, client: Cd2Client):
        self._c = client
        self._device_id = str(uuid.uuid4())

    def upload(self, remote_dir: str, target_name: str, local_path: Path) -> bool:
        remote_path = f"{remote_dir}/{target_name}" if remote_dir != "/" else f"/{target_name}"
        file_size = local_path.stat().st_size

        try:
            started = self._c.call(
                "StartRemoteUpload",
                pb2.StartRemoteUploadRequest(file_path=remote_path, file_size=file_size),
            )
        except Exception as e:
            logger.error(f"【CloudDrive2Disk】StartRemoteUpload 失败: {remote_path}, {e}")
            return False

        upload_id = getattr(started, "upload_id", "") or ""
        if not upload_id:
            logger.error(f"【CloudDrive2Disk】StartRemoteUpload 未返回 upload_id: {remote_path}")
            return False
        logger.info(f"【CloudDrive2Disk】远程上传已启动: {remote_path}, upload_id={upload_id}")

        cancel = threading.Event()
        final_status: list = [None]
        hash_threads: list = []

        try:
            stream = self._c.stub.RemoteUploadChannel(
                pb2.RemoteUploadChannelRequest(device_id=self._device_id),
                metadata=self._c._metadata,
            )
            for msg in stream:
                which = msg.WhichOneof("request")
                if which == "read_data":
                    self._do_read(upload_id, msg.read_data, local_path, file_size)
                elif which == "hash_data":
                    t = threading.Thread(
                        target=self._do_hash,
                        args=(upload_id, msg.hash_data, local_path, file_size, cancel),
                        daemon=True,
                    )
                    hash_threads.append(t)
                    t.start()
                elif which == "status_changed":
                    sc = msg.status_changed
                    status = getattr(sc, "status", None)
                    if status in _TERMINAL:
                        final_status[0] = status
                        if status == pb2.UploadFileInfo.Finish:
                            logger.info(f"【CloudDrive2Disk】远程上传完成: {remote_path}")
                        elif status == pb2.UploadFileInfo.Skipped:
                            logger.info(f"【CloudDrive2Disk】远程上传已秒传: {remote_path}")
                        else:
                            logger.warning(
                                f"【CloudDrive2Disk】远程上传终态非成功: {remote_path}, "
                                f"status={status}, err={getattr(sc, 'error_message', '')}"
                            )
                        cancel.set()
                        break
        except grpc.RpcError as e:
            logger.error(f"【CloudDrive2Disk】RemoteUploadChannel gRPC 错误: {remote_path}, {e.details()}")
            cancel.set()
            return False
        except Exception as e:
            logger.error(f"【CloudDrive2Disk】远程上传异常: {remote_path}, {e}")
            cancel.set()
            return False
        finally:
            cancel.set()
            for t in hash_threads:
                t.join(timeout=10)

        fs = final_status[0]
        return fs in (pb2.UploadFileInfo.Finish, pb2.UploadFileInfo.Skipped)

    def _do_read(self, upload_id: str, req, local_path: Path, file_size: int) -> None:
        offset = int(getattr(req, "offset", 0) or 0)
        length = int(getattr(req, "length", 0) or 0)
        try:
            with open(local_path, "rb") as f:
                f.seek(offset)
                data = f.read(length)
            self._c.call(
                "RemoteReadData",
                pb2.RemoteReadDataUpload(
                    upload_id=upload_id,
                    offset=offset,
                    length=len(data),
                    data=data,
                    is_last_chunk=(offset + len(data)) >= file_size,
                ),
            )
        except Exception as e:
            logger.error(f"【CloudDrive2Disk】RemoteReadData 失败: uid={upload_id}, off={offset}, {e}")

    def _do_hash(
        self,
        upload_id: str,
        req,
        local_path: Path,
        file_size: int,
        cancel: threading.Event,
    ) -> None:
        hash_type = int(getattr(req, "hash_type", 0) or 0)
        block_size = int(getattr(req, "block_size", 0) or 0)
        last_t: list = [0.0]

        def report(bh: int, hv: str = "", blk=None) -> None:
            try:
                self._c.call(
                    "RemoteHashProgress",
                    pb2.RemoteHashProgressUpload(
                        upload_id=upload_id,
                        bytes_hashed=bh,
                        total_bytes=file_size,
                        hash_type=hash_type,
                        hash_value=hv,
                        block_hashes=blk or [],
                    ),
                )
            except Exception as ex:
                logger.debug(f"【CloudDrive2Disk】RemoteHashProgress 失败: {ex}")

        def tick(bh: int) -> None:
            now = time.time()
            if now - last_t[0] >= 0.25:
                report(bh)
                last_t[0] = now

        try:
            with open(local_path, "rb") as f:
                bh = 0
                if hash_type == _MD5:
                    md5_f, blocks, cs = hashlib.md5(), [], block_size or (1 << 20)
                    while not cancel.is_set():
                        chunk = f.read(cs)
                        if not chunk:
                            break
                        md5_f.update(chunk)
                        if block_size > 0:
                            blocks.append(hashlib.md5(chunk).hexdigest())
                        bh += len(chunk)
                        tick(bh)
                    if cancel.is_set():
                        report(bh)
                        return
                    report(bh, md5_f.hexdigest(), blocks if block_size > 0 else [])

                elif hash_type == _PIKPAK_SHA1:
                    seg = (256 << 10) if file_size <= (128 << 20) else \
                          (512 << 10) if file_size <= (256 << 20) else \
                          (1024 << 10) if file_size <= (512 << 20) else (2048 << 10)
                    segs = []
                    while not cancel.is_set():
                        chunk = f.read(seg)
                        if not chunk:
                            break
                        segs.append(hashlib.sha1(chunk).digest())
                        bh += len(chunk)
                        tick(bh)
                    if cancel.is_set():
                        report(bh)
                        return
                    report(bh, hashlib.sha1(b"".join(segs)).hexdigest().upper())

                else:  # SHA1 or unknown
                    dig = hashlib.sha1()
                    while not cancel.is_set():
                        chunk = f.read(1 << 20)
                        if not chunk:
                            break
                        dig.update(chunk)
                        bh += len(chunk)
                        tick(bh)
                    if cancel.is_set():
                        report(bh)
                        return
                    report(bh, dig.hexdigest())

        except Exception as e:
            logger.error(f"【CloudDrive2Disk】哈希计算失败: uid={upload_id}, {e}")
            try:
                report(0)
            except Exception:
                pass
