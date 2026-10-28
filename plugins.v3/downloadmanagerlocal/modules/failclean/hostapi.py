"""整理失败清理的宿主能力边界：存储链、整理/下载历史、下载目录与媒体扩展名。

隔离测试不覆盖真实存储模块与宿主下载目录配置，因此把宿主导入集中在本模块，
接线核对时只需确认这里的导入路径与调用契约。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.application.directory import DirectoryHelper
from app.chain.storage import StorageChain
from app.db.oper.downloadhistory import DownloadHistoryOper
from app.db.oper.transferhistory import TransferHistoryOper
from app.schemas.types import EventType
from app.sdk.config import settings
from app.sdk.events import eventmanager


def media_extensions() -> set[str]:
    """返回宿主配置的视频、字幕与音频扩展名集合（统一为带点小写形式）。"""
    extensions: set[str] = set()
    for group in (settings.RMT_MEDIAEXT, settings.RMT_SUBEXT, settings.RMT_AUDIOEXT):
        for extension in group or []:
            text = str(extension or "").strip().lower()
            if not text:
                continue
            extensions.add(text if text.startswith(".") else f".{text}")
    return extensions


def local_download_paths() -> list[Path]:
    """返回宿主配置的本地下载目录路径。"""
    paths: list[Path] = []
    for directory in DirectoryHelper().get_local_download_dirs():
        download_path = str(getattr(directory, "download_path", "") or "").strip()
        if download_path:
            paths.append(Path(download_path))
    return paths


def get_success_transfer_history(src: str) -> Any:
    """按源路径读取成功的整理记录，未命中时返回 None。"""
    return TransferHistoryOper().get_success_by_src(src, storage="local")


def dest_file_exists(dest_storage: str, dest: str) -> bool:
    """判断整理记录的目标文件在当前存储中是否仍存在。"""
    if not dest_storage or not dest:
        return False
    return bool(StorageChain().get_file_item(storage=dest_storage, path=Path(dest)))


def get_local_file_item(path: Path) -> Any:
    """读取本地文件的存储文件项，供存储链删除使用。"""
    return StorageChain().get_file_item(storage="local", path=path)


def delete_media_file(fileitem: Any) -> bool:
    """通过存储链删除媒体文件并清理不含媒体文件的目录。"""
    return bool(StorageChain().delete_media_file(fileitem))


def get_download_hash_by_fullpath(fullpath: str) -> str:
    """按完整路径反查下载历史 hash。"""
    return str(DownloadHistoryOper().get_hash_by_fullpath(fullpath) or "").strip()


def delete_download_history_file(fullpath: str) -> None:
    """删除该完整路径对应的下载历史文件记录。"""
    DownloadHistoryOper().delete_file_by_fullpath(fullpath)


def send_download_file_deleted(src: str, download_hash: str) -> None:
    """广播下载源文件删除事件，供同步删除等模块继续处理。"""
    eventmanager.send_event(EventType.DownloadFileDeleted, {"src": src, "hash": download_hash})


__all__ = (
    "delete_download_history_file",
    "delete_media_file",
    "dest_file_exists",
    "get_download_hash_by_fullpath",
    "get_local_file_item",
    "get_success_transfer_history",
    "local_download_paths",
    "media_extensions",
    "send_download_file_deleted",
)
