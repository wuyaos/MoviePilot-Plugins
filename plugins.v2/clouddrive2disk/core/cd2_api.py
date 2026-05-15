# input: CloudDrive2 gRPC 地址、API 令牌、disk_name、upload_mode、MoviePilot FileItem 操作请求
# output: Cd2Api — MoviePilot 存储适配器，委托给 Cd2Client / DirectUploader / RemoteUploadManager
# pos: clouddrive2disk 的 MP 存储适配器；薄层，不含 gRPC 连接或上传逻辑
from pathlib import Path, PurePosixPath
from typing import List, Optional
from urllib.request import Request, urlopen

import grpc

from app.core.config import settings
from app.log import logger
from app.schemas import FileItem, StorageUsage

from .cd2_client import Cd2Client
from .cd2_helpers import (
    human_size,
    is_success,
    join_path,
    normalize_path,
    result_paths,
    root_item,
    to_file_item,
)
from .cd2_upload import DirectUploader
from .cd2_remote_upload import RemoteUploadManager
from ..proto import cd2_pb2 as pb2


class Cd2Api:
    """MoviePilot 存储适配器：委托给 Cd2Client、DirectUploader 或 RemoteUploadManager。"""

    def __init__(self, cd2_url: str, api_key: str, disk_name: str, upload_mode: str = "direct_write"):
        self._disk_name = disk_name
        self._client = Cd2Client(cd2_url, api_key)
        if upload_mode == "remote_upload":
            self._uploader = RemoteUploadManager(self._client)
        else:
            self._uploader = DirectUploader(self._client)
        logger.info(
            f"【CloudDrive2Disk】Cd2Api 初始化完成: host={self._client.host}, "
            f"token_root={self._client.token_root}, storage={disk_name}, mode={upload_mode}"
        )

    def close(self):
        self._client.close()

    def __del__(self):
        self.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _to_item(self, cloud_file) -> FileItem:
        return to_file_item(cloud_file, self._disk_name)

    def _root(self) -> FileItem:
        return root_item(self._disk_name)

    # ------------------------------------------------------------------
    # Browse
    # ------------------------------------------------------------------
    def list(self, fileitem: FileItem) -> List[FileItem]:
        if fileitem.type == "file":
            item = self.get_item(Path(fileitem.path))
            return [item] if item else []
        path = self._client.norm_dir(fileitem.path)
        try:
            return [self._to_item(f) for f in self._client.list_files(path)]
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.UNAUTHENTICATED:
                self._client.log_auth_error_once("浏览目录", path, e)
            else:
                logger.error(f"【CloudDrive2Disk】浏览目录失败: {path}, {e.details()}")
            return []

    def iter_files(self, fileitem: FileItem) -> Optional[List[FileItem]]:
        if fileitem.type == "file":
            item = self.get_item(Path(fileitem.path))
            return [item] if item else []
        root = self._client.norm_dir(fileitem.path)
        result, pending, visited = [], [root], set()
        try:
            while pending:
                current = pending.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                for cf in self._client.list_files(current):
                    item = self._to_item(cf)
                    result.append(item)
                    if item.type == "dir":
                        pending.append(self._client.norm_dir(item.path))
            return result
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.UNAUTHENTICATED:
                self._client.log_auth_error_once("递归遍历目录", root, e)
            else:
                logger.error(f"【CloudDrive2Disk】递归遍历失败: {root}, {e.details()}")
            return None

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def get_item(self, path: Path) -> Optional[FileItem]:
        target = normalize_path(path.as_posix())
        if target == "/":
            return self._root()
        try:
            cf = self._client.call(
                "FindFileByPath",
                pb2.FindFileByPathRequest(path=self._client.norm_file(target)),
            )
            if not getattr(cf, "name", "") and not getattr(cf, "fullPathName", ""):
                return None
            return self._to_item(cf)
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.UNAUTHENTICATED:
                self._client.log_auth_error_once("获取文件详情", target, e)
            return None
        except Exception:
            return None

    def get_parent(self, fileitem: FileItem) -> Optional[FileItem]:
        src = self._client.norm_file(fileitem.path)
        if src == "/":
            return None
        parent = str(PurePosixPath(src).parent)
        return self.get_item(Path("/" if parent in ("", ".") else parent))

    def create_folder(self, fileitem: FileItem, name: str) -> Optional[FileItem]:
        parent = self._client.norm_dir(fileitem.path)
        target = join_path(parent, name)
        try:
            resp = self._client.call(
                "CreateFolder", pb2.CreateFolderRequest(parentPath=parent, folderName=name)
            )
            if hasattr(resp, "result") and not is_success(resp.result):
                logger.error(
                    f"【CloudDrive2Disk】创建目录失败: {target}, "
                    f"{getattr(resp.result, 'errorMessage', '')}"
                )
                return None
            folder = getattr(resp, "folderCreated", None)
            if folder and (getattr(folder, "fullPathName", None) or getattr(folder, "name", None)):
                return self._to_item(folder)
            return self.get_item(Path(target))
        except Exception as e:
            logger.error(f"【CloudDrive2Disk】创建目录失败: {target}, {e}")
            return None

    def _get_folder(self, path: Path) -> Optional[FileItem]:
        """Get or recursively create a directory."""
        target = normalize_path(path.as_posix())
        item = self.get_item(path)
        if item and item.type == "dir":
            return item
        current, current_item = "/", None
        for part in PurePosixPath(target).parts[1:]:
            next_path = join_path(current, part)
            existing = self.get_item(Path(next_path))
            if existing and existing.type == "dir":
                current, current_item = next_path, existing
                continue
            created = self.create_folder(current_item or self._root(), part)
            if not created:
                logger.error(f"【CloudDrive2Disk】创建目录失败: {next_path}")
                return None
            current, current_item = next_path, created
        return current_item

    def delete(self, fileitem: FileItem) -> bool:
        path = normalize_path(fileitem.path)
        try:
            resp = self._client.call("DeleteFile", pb2.FileRequest(path=path))
            if not is_success(resp):
                logger.error(f"【CloudDrive2Disk】删除失败: {path}")
                return False
            return True
        except Exception as e:
            logger.error(f"【CloudDrive2Disk】删除失败: {path}, {e}")
            return False

    def rename(self, fileitem: FileItem, name: str) -> bool:
        src = self._client.norm_file(fileitem.path)
        if src == "/":
            return False
        try:
            resp = self._client.call(
                "RenameFile", pb2.RenameFileRequest(theFilePath=src, newName=name)
            )
            if not is_success(resp):
                logger.error(f"【CloudDrive2Disk】重命名失败: {src} -> {name}")
                return False
            return True
        except Exception as e:
            logger.error(f"【CloudDrive2Disk】重命名失败: {src} -> {name}, {e}")
            return False

    def move(self, fileitem: FileItem, path: Path, new_name: str) -> bool:
        src = self._client.norm_file(fileitem.path)
        dst_dir = self._client.norm_dir(path.as_posix())
        src_name = PurePosixPath(src).name
        target_name = new_name or src_name
        try:
            resp = self._client.call(
                "MoveFile",
                pb2.MoveFileRequest(
                    theFilePaths=[src],
                    destPath=dst_dir,
                    conflictPolicy=pb2.MoveFileRequest.Overwrite,
                ),
            )
            if not is_success(resp):
                logger.error(f"【CloudDrive2Disk】移动失败: {src} -> {dst_dir}")
                return False
            if target_name != src_name:
                paths = result_paths(resp)
                moved = paths[0] if paths else join_path(dst_dir, src_name)
                rr = self._client.call(
                    "RenameFile", pb2.RenameFileRequest(theFilePath=moved, newName=target_name)
                )
                if not is_success(rr):
                    logger.error(f"【CloudDrive2Disk】移动后重命名失败: {moved} -> {target_name}")
                    return False
            return True
        except Exception as e:
            logger.error(f"【CloudDrive2Disk】移动失败: {src} -> {dst_dir}, {e}")
            return False

    def copy(self, fileitem: FileItem, path: Path, new_name: str) -> bool:
        src = self._client.norm_file(fileitem.path)
        dst_dir = self._client.norm_dir(path.as_posix())
        src_name = PurePosixPath(src).name
        target_name = new_name or src_name
        try:
            resp = self._client.call(
                "CopyFile",
                pb2.CopyFileRequest(
                    theFilePaths=[src],
                    destPath=dst_dir,
                    conflictPolicy=pb2.CopyFileRequest.Overwrite,
                ),
            )
            if not is_success(resp):
                logger.error(f"【CloudDrive2Disk】复制失败: {src} -> {dst_dir}")
                return False
            if target_name != src_name:
                paths = result_paths(resp)
                copied = paths[0] if paths else join_path(dst_dir, src_name)
                rr = self._client.call(
                    "RenameFile", pb2.RenameFileRequest(theFilePath=copied, newName=target_name)
                )
                if not is_success(rr):
                    logger.error(f"【CloudDrive2Disk】复制后重命名失败: {copied} -> {target_name}")
                    return False
            return True
        except Exception as e:
            logger.error(f"【CloudDrive2Disk】复制失败: {src} -> {dst_dir}, {e}")
            return False

    # ------------------------------------------------------------------
    # Download / Upload
    # ------------------------------------------------------------------
    def download(self, fileitem: FileItem, path: Optional[Path] = None) -> Optional[Path]:
        if fileitem.type != "file":
            return None
        remote = self._client.norm_file(fileitem.path)
        local = Path(path or settings.TEMP_PATH / fileitem.name)
        local.parent.mkdir(parents=True, exist_ok=True)
        try:
            url, headers = self._client.resolve_download_url(remote)
            req = Request(url=url, headers=headers)
            with urlopen(req) as resp, open(local, "wb") as f:
                while True:
                    chunk = resp.read(8 * 1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
            return local
        except Exception as e:
            logger.error(f"【CloudDrive2Disk】下载失败: {remote} -> {local}, {e}")
            local.unlink(missing_ok=True)
            return None

    def upload(
        self, target_dir: FileItem, local_path: Path, new_name: Optional[str] = None
    ) -> Optional[FileItem]:
        if not local_path.exists() or not local_path.is_file():
            logger.error(f"【CloudDrive2Disk】上传失败，本地文件不存在: {local_path}")
            return None
        target_name = new_name or local_path.name
        remote_dir = self._client.norm_dir(target_dir.path)
        remote_path = join_path(remote_dir, target_name)

        if not self._get_folder(Path(remote_dir)):
            logger.error(f"【CloudDrive2Disk】上传失败，目标目录创建失败: {remote_dir}")
            return None
        existed = self.get_item(Path(remote_path))
        if existed and not self.delete(existed):
            logger.error(f"【CloudDrive2Disk】上传失败，无法覆盖已有文件: {remote_path}")
            return None

        ok = self._uploader.upload(remote_dir, target_name, local_path)
        return self.get_item(Path(remote_path)) if ok else None

    # ------------------------------------------------------------------
    # Storage info
    # ------------------------------------------------------------------
    def usage(self) -> Optional[StorageUsage]:
        base = self._client.token_root or "/"
        entries = []
        try:
            for one in self._client.list_files(base):
                if not getattr(one, "isCloudRoot", False):
                    continue
                full = getattr(one, "fullPathName", "") or f"/{getattr(one, 'name', '')}"
                norm = self._client.norm_dir(full)
                if not norm or norm == "/":
                    continue
                try:
                    sp = self._client.call("GetSpaceInfo", pb2.FileRequest(path=norm))
                    t = int(getattr(sp, "totalSpace", 0) or 0)
                    u = int(getattr(sp, "usedSpace", 0) or 0)
                    f = int(getattr(sp, "freeSpace", 0) or 0)
                    if t > 0 or u > 0 or f > 0:
                        entries.append((t, u, f))
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"【CloudDrive2Disk】枚举空间统计路径失败: {base}, {e}")

        if not entries:
            try:
                sp = self._client.call("GetSpaceInfo", pb2.FileRequest(path=base))
                t = int(getattr(sp, "totalSpace", 0) or 0)
                u = int(getattr(sp, "usedSpace", 0) or 0)
                f = int(getattr(sp, "freeSpace", 0) or 0)
                if t > 0 or u > 0 or f > 0:
                    avail = f if f > 0 else max(t - u, 0)
                    return StorageUsage(total=t, available=avail)
            except Exception:
                pass
            return None

        seen, unique = set(), []
        for t, u, f in entries:
            if (t, u) not in seen:
                seen.add((t, u))
                unique.append((t, u, f))

        total = sum(t for t, _, _ in unique)
        used = sum(u for _, u, _ in unique)
        free = sum(f for _, _, f in unique)
        if total <= 0 and used <= 0 and free <= 0:
            return None
        avail = free if free > 0 else max(total - used, 0)
        logger.info(
            f"【CloudDrive2Disk】空间统计: {len(unique)} 云盘, "
            f"total={human_size(total)}, used={human_size(used)}, available={human_size(avail)}"
        )
        return StorageUsage(total=total, available=avail)

    def is_support_transtype(self, transtype: str) -> bool:
        return transtype in ("move", "copy")
