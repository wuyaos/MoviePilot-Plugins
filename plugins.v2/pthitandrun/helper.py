# input: 下载器实例（Qbittorrent / Transmission）
# output: 统一的种子信息查询、标签操作、站点识别接口
# pos: 适配层，屏蔽 QB/TR 差异，供 checker 和 __init__ 调用
"""下载器适配 + 站点识别 + 格式化工具。"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import parse_qs, unquote, urlparse

from app.helper.sites import SitesHelper
from app.log import logger
from app.utils.string import StringUtils

siteshelper = SitesHelper()

# tracker 域名特殊映射
_TRACKER_MAPPINGS = {
    "chdbits.xyz": "ptchdbits.co",
    "agsvpt.trackers.work": "agsvpt.com",
    "tracker.cinefiles.info": "audiences.me",
}


class TorrentHelper:
    """下载器种子操作统一接口。"""

    def __init__(self, downloader: Any):
        self.downloader = downloader
        self.dl_type = "qbittorrent" if hasattr(downloader, "qbc") else "transmission" if downloader else None

    # ---- 站点识别 ----

    @staticmethod
    def get_site_by_torrent(torrent: Any) -> Tuple[int, Optional[str]]:
        """通过 tracker URL 识别站点，返回 (site_id, site_name)。"""
        trackers: List[str] = []
        try:
            tracker_url = torrent.get("tracker") if isinstance(torrent, dict) else getattr(torrent, "tracker", "")
            if tracker_url:
                trackers.append(tracker_url)
            magnet = torrent.get("magnet_uri") if isinstance(torrent, dict) else getattr(torrent, "magnet_uri", "")
            if magnet:
                params = parse_qs(urlparse(magnet).query)
                trackers.extend(unquote(u) for u in params.get("tr", []))
        except Exception as e:
            logger.debug(f"解析 tracker 失败: {e}")

        for tracker in trackers:
            if not tracker:
                continue
            domain = None
            for key, mapped in _TRACKER_MAPPINGS.items():
                if key in tracker:
                    domain = mapped
                    break
            if not domain:
                domain = StringUtils.get_url_domain(tracker)
            if not domain:
                continue
            site_info = siteshelper.get_indexer(domain)
            if site_info:
                return site_info.get("id", 0), site_info.get("name")
        return 0, None

    # ---- 种子信息 ----

    def get_torrent_info(self, torrent: Any) -> Dict[str, Any]:
        """统一提取种子运行时信息。"""
        now = int(time.time())
        if self.dl_type == "qbittorrent":
            return self._qb_info(torrent, now)
        return self._tr_info(torrent, now)

    def _qb_info(self, t: Any, now: int) -> Dict[str, Any]:
        added = t.get("added_on", 0)
        done = t.get("completion_on", 0)
        seeding_time = (now - done) if done > 0 else 0
        return {
            "hash": t.get("hash"),
            "title": t.get("name"),
            "seeding_time": seeding_time,
            "ratio": t.get("ratio", 0),
            "uploaded": t.get("uploaded", 0),
            "downloaded": t.get("downloaded", 0),
            "total_size": t.get("total_size", 0),
            "add_on": added,
            "tags": t.get("tags", ""),
            "category": t.get("category", ""),
            "tracker": t.get("tracker", ""),
            "state": t.get("state", ""),
        }

    def _tr_info(self, t: Any, now: int) -> Dict[str, Any]:
        done_ts = int(t.date_done.timestamp()) if t.date_done and t.date_done.timestamp() > 1 else 0
        seeding_time = (now - done_ts) if done_ts > 0 else 0
        downloaded = int(t.total_size * t.progress / 100)
        uploaded = int(downloaded * t.ratio) if t.ratio else 0
        return {
            "hash": t.hashString,
            "title": t.name,
            "seeding_time": seeding_time,
            "ratio": t.ratio or 0,
            "uploaded": uploaded,
            "downloaded": downloaded,
            "total_size": t.total_size,
            "add_on": int(t.date_added.timestamp()) if t.date_added else 0,
            "tags": getattr(t, "labels", []) or [],
            "category": "",
            "tracker": (t.trackers[0].get("announce", "") if t.trackers else ""),
            "state": "",
        }

    # ---- 种子列表 ----

    def get_torrents(self, hashes: Optional[Union[str, List[str]]] = None) -> Optional[List[Any]]:
        """获取下载器种子，支持按 hash 过滤。"""
        ids = [hashes] if isinstance(hashes, str) else hashes
        torrents, err = self.downloader.get_torrents(ids=ids)
        if err:
            logger.warning("连接下载器出错")
            return None
        return torrents

    def get_torrent_hash(self, torrent: Any) -> str:
        if self.dl_type == "qbittorrent":
            return torrent.get("hash", "") if isinstance(torrent, dict) else ""
        return getattr(torrent, "hashString", "")

    def get_torrent_category(self, torrent: Any) -> str:
        if self.dl_type == "qbittorrent" and isinstance(torrent, dict):
            return torrent.get("category", "") or ""
        return ""

    # ---- 标签操作 ----

    def get_torrent_tags(self, torrent: Any) -> List[str]:
        try:
            if self.dl_type == "qbittorrent":
                raw = torrent.get("tags", "") if isinstance(torrent, dict) else ""
                return [t.strip() for t in raw.split(",") if t.strip()]
            return list(set(t.strip() for t in (getattr(torrent, "labels", []) or []) if t.strip()))
        except Exception:
            return []

    def set_torrent_tag(self, torrent_hash: str, tags: List[str]):
        try:
            unique = list(set(tags))
            if self.dl_type == "qbittorrent":
                self.downloader.set_torrents_tag(ids=torrent_hash, tags=unique)
            else:
                self.downloader.set_torrent_tag(ids=torrent_hash, tags=unique)
        except Exception as e:
            logger.error(f"设置标签失败 {torrent_hash}: {e}")

    def remove_torrent_tag(self, torrent_hash: str, tags: List[str]):
        try:
            unique = list(set(tags))
            if self.dl_type == "qbittorrent":
                self.downloader.remove_torrents_tag(ids=torrent_hash, tag=unique)
            else:
                torrent_list = self.get_torrents(hashes=torrent_hash)
                if not torrent_list:
                    return
                current = self.get_torrent_tags(torrent_list[0])
                updated = [t for t in current if t not in unique]
                self.downloader.set_torrent_tag(ids=torrent_hash, tags=updated)
        except Exception as e:
            logger.error(f"移除标签失败 {torrent_hash}: {e}")


class FormatHelper:
    """格式化工具。"""

    @staticmethod
    def format_value(value: float, precision: int = 1, default: str = "N/A") -> str:
        if value:
            return f"{value:.{precision}f}".rstrip("0").rstrip(".") or "0"
        return default

    @staticmethod
    def format_hour(seconds: float) -> str:
        return FormatHelper.format_value(seconds / 3600)

    @staticmethod
    def format_size(value: float) -> str:
        return StringUtils.str_filesize(value) if str(value).replace(".", "", 1).isdigit() else str(value)
