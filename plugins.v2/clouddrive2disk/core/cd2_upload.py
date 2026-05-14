# input: Cd2Client instance, local file Path, remote dir path
# output: DirectUploader (gRPC write), RemoteUploadManager (server-pull flow)
# pos: upload strategies for cd2_api.py; keeps upload logic out of the main adapter
import time
import uuid
from pathlib import Path
from typing import Optional

from app.log import logger

from ..proto import cd2_pb2 as pb2
from .cd2_helpers import human_size, is_success, normalize_path
from .cd2_client import Cd2Client

_CHUNK = 3 * 1024 * 1024  # 3 MB per WriteToFile call


class DirectUploader:
    """CreateFile → WriteToFile chunks → CloseFile, then wait for CD2 cloud upload."""

    def __init__(self, client: Cd2Client):
        self._c = client

    def upload(self, remote_dir: str, target_name: str, local_path: Path) -> bool:
        remote_path = f"{remote_dir}/{target_name}" if remote_dir != "/" else f"/{target_name}"
        fh = 0
        try:
            resp = self._c.call(
                "CreateFile",
                pb2.CreateFileRequest(parentPath=remote_dir, fileName=target_name),
            )
            fh = int(getattr(resp, "fileHandle", 0) or 0)
            if fh <= 0:
                logger.error(f"【CloudDrive2Disk】上传失败，获取文件句柄失败: {remote_path}")
                return False

            offset = 0
            with open(local_path, "rb") as f:
                while True:
                    data = f.read(_CHUNK)
                    if not data:
                        break
                    wr = self._c.call(
                        "WriteToFile",
                        pb2.WriteFileRequest(
                            fileHandle=fh,
                            startPos=offset,
                            length=len(data),
                            buffer=data,
                            closeFile=False,
                        ),
                    )
                    written = int(getattr(wr, "bytesWritten", len(data)) or 0)
                    if written != len(data):
                        logger.error(
                            f"【CloudDrive2Disk】写入长度不匹配: {remote_path}, "
                            f"expect={len(data)}, actual={written}"
                        )
                        return False
                    offset += written

            cr = self._c.call("CloseFile", pb2.CloseFileRequest(fileHandle=fh))
            fh = 0
            if not is_success(cr):
                logger.error(f"【CloudDrive2Disk】CloseFile 失败: {remote_path}")
                return False

            return _wait_upload_complete(self._c, remote_path)
        except Exception as e:
            logger.error(f"【CloudDrive2Disk】直接上传失败: {remote_path}, {e}")
            return False
        finally:
            if fh > 0:
                try:
                    self._c.call("CloseFile", pb2.CloseFileRequest(fileHandle=fh))
                except Exception:
                    pass


class RemoteUploadManager:
    """
    Server-pull upload: tell CD2 to fetch a local HTTP URL.

    Protocol: StartRemoteUpload → RemoteUploadChannel (server-streaming)
              → RemoteReadData (client provides data on demand) or track RemoteUploadStatusChanged.
    """

    def __init__(self, client: Cd2Client):
        self._c = client
        self._device_id = str(uuid.uuid4())

    def upload(self, remote_dir: str, target_name: str, local_path: Path) -> bool:
        """
        Currently falls back to DirectUploader — RemoteUploadChannel requires a server
        that can push data back on demand (bidirectional stream) which is complex to host
        from within MoviePilot. The protocol skeleton is retained for future use.
        """
        logger.info(
            "【CloudDrive2Disk】远程上传回退到直接上传 (RemoteUploadChannel 需要本地 HTTP 服务端)"
        )
        return DirectUploader(self._c).upload(remote_dir, target_name, local_path)


# ---------------------------------------------------------------------------
# Shared wait helper
# ---------------------------------------------------------------------------

def _wait_upload_complete(
    client: Cd2Client,
    remote_path: str,
    timeout: int = 3600,
    interval: int = 5,
    stall_timeout: int = 600,
) -> bool:
    """Poll GetUploadFileList (paginated) until the file reaches a terminal state."""
    terminal = {
        pb2.UploadFileInfo.Finish,
        pb2.UploadFileInfo.Error,
        pb2.UploadFileInfo.FatalError,
        pb2.UploadFileInfo.Cancelled,
        pb2.UploadFileInfo.Skipped,
        pb2.UploadFileInfo.Ignored,
    }

    normalized = normalize_path(remote_path)
    deadline = time.monotonic() + timeout
    found_ever = False
    last_bytes = -1
    last_progress_t = time.monotonic()

    while time.monotonic() < deadline:
        try:
            page, all_files = 0, []
            while True:
                resp = client.call(
                    "GetUploadFileList",
                    pb2.GetUploadFileListRequest(itemsPerPage=50, pageNumber=page),
                )
                batch = list(getattr(resp, "uploadFiles", []) or [])
                all_files.extend(batch)
                if len(batch) < 50:
                    break
                page += 1

            found = False
            for uf in all_files:
                dest = normalize_path(getattr(uf, "destPath", "") or "")
                if dest.rstrip("/") != normalized.rstrip("/"):
                    continue
                found = found_ever = True
                status_enum = getattr(uf, "statusEnum", None)
                status_str = getattr(uf, "status", "")
                transferred = int(getattr(uf, "transferedBytes", 0) or 0)
                total = int(getattr(uf, "size", 0) or 0)

                if status_enum in terminal:
                    if status_enum == pb2.UploadFileInfo.Finish:
                        logger.info(f"【CloudDrive2Disk】云端上传完成: {remote_path}")
                    else:
                        logger.warning(
                            f"【CloudDrive2Disk】云端上传终态非成功: {remote_path}, status={status_str}"
                        )
                    return status_enum == pb2.UploadFileInfo.Finish

                now = time.monotonic()
                if transferred > last_bytes:
                    last_progress_t, last_bytes = now, transferred
                if now - last_progress_t >= stall_timeout:
                    logger.warning(
                        f"【CloudDrive2Disk】云端上传停滞 {stall_timeout}s: {remote_path}, "
                        f"{human_size(transferred)}/{human_size(total)}"
                    )
                    return False

                pct = f"{transferred / total * 100:.1f}%" if total > 0 else "N/A"
                logger.debug(
                    f"【CloudDrive2Disk】等待云端上传: {remote_path}, {status_str}, "
                    f"{pct} ({human_size(transferred)}/{human_size(total)})"
                )
                break

            if not found and found_ever:
                logger.info(f"【CloudDrive2Disk】上传任务已从队列消失，视为完成: {remote_path}")
                return True
        except Exception as e:
            logger.debug(f"【CloudDrive2Disk】查询上传状态失败: {remote_path}, {e}")

        time.sleep(interval)

    logger.warning(f"【CloudDrive2Disk】等待云端上传超时 ({timeout}s): {remote_path}")
    return False
