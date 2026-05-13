# input: MoviePilot DownloaderHelper service instance, torrent 文件
# output: hash 检查、种子提交（支持 qBittorrent / Transmission）
# pos: 下载器操作层，使用 MP 下载器已连接实例

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


def dl_has_hash(instance: Any, infohash: str) -> bool:
    """检查下载器是否已有该 infohash"""
    try:
        # qBittorrent
        qbc = getattr(instance, "qbc", None)
        if qbc:
            return len(qbc.torrents_info(torrent_hashes=infohash)) > 0
        # Transmission
        trc = getattr(instance, "trc", None)
        if trc:
            torrents, _ = trc.get_torrents(ids=[infohash])
            return len(torrents) > 0
        logger.warning(f"不支持的下载器类型: {type(instance).__name__}")
    except Exception as e:
        logger.warning(f"检查 hash 失败: {e}")
    return False


def dl_add_torrent(
    instance: Any, torrent_path: Path, category: str = "", tags: str = ""
) -> bool:
    """提交 .torrent 文件到下载器"""
    try:
        # qBittorrent
        qbc = getattr(instance, "qbc", None)
        if qbc:
            with torrent_path.open("rb") as f:
                result = qbc.torrents_add(
                    torrent_files=f, category=category, tags=tags
                )
            ok = result and "OK" in str(result).upper()
            if ok:
                logger.info(f"种子已提交 qBittorrent: {torrent_path.name}")
            else:
                logger.warning(f"qB 提交结果: {result}")
            return ok
        # Transmission
        trc = getattr(instance, "trc", None)
        if trc:
            with torrent_path.open("rb") as f:
                torrent_data = f.read()
            import base64
            b64 = base64.b64encode(torrent_data).decode()
            kwargs = {}
            if category:
                kwargs["labels"] = [category]
            result = trc.add_torrent(metainfo=b64, **kwargs)
            if result:
                logger.info(f"种子已提交 Transmission: {torrent_path.name}")
                return True
            logger.warning("Transmission 提交失败")
            return False
        logger.warning(f"不支持的下载器类型: {type(instance).__name__}")
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


def dl_list_category(instance: Any, category: str) -> list[dict[str, Any]]:
    """列出下载器中指定分类的种子"""
    result = []
    try:
        qbc = getattr(instance, "qbc", None)
        if qbc:
            torrents = qbc.torrents_info(category=category)
            for t in torrents:
                result.append({"name": t.name, "size": t.size, "state": t.state,
                               "progress": t.progress, "hash": t.hash,
                               "seeding_time": getattr(t, "seeding_time", 0) or 0})
            return result
        trc = getattr(instance, "trc", None)
        if trc:
            torrents, _ = trc.get_torrents()
            for t in torrents:
                labels = getattr(t, "labels", []) or []
                if category in labels:
                    result.append({"name": t.name, "size": getattr(t, "total_size", 0),
                                   "state": t.status, "progress": t.progress / 100,
                                   "hash": t.hashString,
                                   "seeding_time": getattr(t, "secondsSeeding", 0) or 0})
    except Exception as e:
        logger.warning(f"查询下载器种子失败: {e}")
    return result
