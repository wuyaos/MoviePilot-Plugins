# input: MoviePilot DownloaderHelper service instance, torrent 文件
# output: qB hash 检查、种子提交
# pos: qBittorrent 操作层，使用 MP 下载器已连接实例

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.log import logger


def get_downloader_instance(downloader_name: str) -> Any | None:
    """从 MoviePilot 获取已连接的下载器实例"""
    if not downloader_name:
        return None
    try:
        from app.helper.downloader import DownloaderHelper
        svc = DownloaderHelper().get_service(name=downloader_name)
        if not svc or not svc.instance:
            logger.warning(f"下载器 {downloader_name} 不可用")
            return None
        return svc.instance
    except Exception as e:
        logger.warning(f"获取下载器失败: {e}")
        return None


def qb_has_hash(instance: Any, infohash: str) -> bool:
    """检查 qBittorrent 是否已有该 infohash"""
    try:
        qbc = getattr(instance, "qbc", None)
        if qbc is None:
            logger.warning("下载器实例无 qbc 属性")
            return False
        torrents = qbc.torrents_info(torrent_hashes=infohash)
        return len(torrents) > 0
    except Exception as e:
        logger.warning(f"检查 hash 失败: {e}")
        return False


def qb_add_torrent(
    instance: Any, torrent_path: Path, category: str = "", tags: str = ""
) -> bool:
    """提交 .torrent 文件到 qBittorrent"""
    try:
        qbc = getattr(instance, "qbc", None)
        if qbc is None:
            logger.warning("下载器实例无 qbc 属性")
            return False
        with torrent_path.open("rb") as f:
            result = qbc.torrents_add(
                torrent_files=f, category=category, tags=tags
            )
        if result and result.upper() == "OK.":
            logger.info(f"种子已提交 qBittorrent: {torrent_path.name}")
            return True
        logger.warning(f"qB 提交结果: {result}")
        return result is not None
    except Exception as e:
        logger.error(f"提交种子失败: {e}")
        return False


def torrent_infohash(torrent_path: Path) -> str:
    """从 .torrent 文件解析 infohash"""
    try:
        from torf import Torrent
    except ImportError:
        raise RuntimeError("缺少依赖: torf")
    t = Torrent.read(torrent_path)
    return str(t.infohash).lower()
