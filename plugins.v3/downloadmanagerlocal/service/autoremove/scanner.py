"""自动删种下载器读取：任务采样与 qBittorrent / Transmission 字段归一。"""

from __future__ import annotations

from typing import Any

from ...adapter.moviepilot import get_url_domain
from ...utils.torrent_adapter import (
    get_category,
    get_hash,
    get_label,
    get_save_path,
    get_torrent_size,
    get_tracker_urls,
)
from .models import RemoveSnapshot

QBITTORRENT = "qbittorrent"
TRANSMISSION = "transmission"


def downloader_type(service: Any) -> str:
    """返回下载器类型标识（qbittorrent / transmission）。"""
    return str(getattr(service, "type", "") or "").strip().lower()


def read_torrents(instance: Any) -> tuple[list, str]:
    """读取下载器全部任务；返回 (任务列表, 错误信息)，查询失败与成功空列表区分。"""
    try:
        response = instance.get_torrents()
    except Exception as error:
        return [], str(error)
    if isinstance(response, tuple) and len(response) == 2:
        items, failed = response
    else:
        items, failed = response, None
    if failed:
        return [], "下载器查询失败"
    return list(items or []), ""


def torrent_hash(torrent: Any, downloader_type_name: str) -> str:
    """返回归一化后的种子 hash。"""
    return str(get_hash(torrent, downloader_type_name) or "").strip().lower()


def build_snapshot(
    torrent: Any,
    downloader_id: str,
    downloader_type_name: str,
    now: float,
) -> RemoveSnapshot:
    """把 qBittorrent 字典或 Transmission 对象归一为删种采样快照。

    做种时间取完成时间（qB completion_on / TR date_done），为 0 时回退添加时间；
    平均上传速度由上传量除以做种时长得到，不是实时速度。
    """
    dl_type = str(downloader_type_name or "").lower()
    size = int(get_torrent_size(torrent, dl_type) or 0)
    if dl_type == QBITTORRENT:
        completed_at = _number(_field(torrent, "completion_on"))
        added_at = _number(_field(torrent, "added_on"))
        ratio = _number(_field(torrent, "ratio"))
        uploaded = _number(_field(torrent, "uploaded"))
        current_tracker = str(_field(torrent, "tracker", default="") or "")
        site = get_url_domain(current_tracker)
        error_string = ""
    else:
        completed_at = _timestamp(_field(torrent, "done_date", "date_done", "doneDate"))
        added_at = _timestamp(_field(torrent, "added_date", "date_added", "addedDate"))
        ratio = _number(_field(torrent, "upload_ratio", "uploadRatio", "ratio"))
        uploaded = _number(_field(torrent, "uploaded_ever", "uploadedEver")) or ratio * size
        current_tracker = ""
        site = _transmission_site(torrent)
        error_string = str(_field(torrent, "error_string", "errorString", default="") or "")

    reference = completed_at if completed_at > 0 else added_at
    return RemoveSnapshot(
        downloader=str(downloader_id or ""),
        downloader_type=dl_type,
        torrent_hash=torrent_hash(torrent, dl_type),
        name=str(_field(torrent, "name", default="") or ""),
        size=size,
        ratio=ratio,
        seeding_seconds=max(now - reference, 0.0) if reference > 0 else 0.0,
        uploaded=uploaded,
        save_path=str(get_save_path(torrent, dl_type) or ""),
        current_tracker=current_tracker,
        trackers=tuple(get_tracker_urls(torrent, dl_type)),
        site=site,
        state=str(_field(torrent, "state", "status", default="") or ""),
        category=str(get_category(torrent, dl_type) or ""),
        tags=tuple(get_label(torrent, dl_type)),
        error_string=error_string,
    )


def _transmission_site(torrent: Any) -> str:
    """读取 Transmission 首个 tracker 的站点名，缺失时回退首个 announce 域名。"""
    trackers = _field(torrent, "trackers", default=[]) or []
    if trackers:
        name = str(_field(trackers[0], "sitename", default="") or "").strip()
        if name:
            return name
    urls = get_tracker_urls(torrent, TRANSMISSION)
    return get_url_domain(urls[0]) if urls else ""


def _field(torrent: Any, *names: str, default: Any = None) -> Any:
    """按字段名读取字典键或对象属性，兼容 qBittorrent 与 Transmission 字段差异。"""
    for name in names:
        if isinstance(torrent, dict) and name in torrent:
            return torrent.get(name)
        if hasattr(torrent, name):
            return getattr(torrent, name)
    return default


def _number(value: Any) -> float:
    """把下载器数值字段转换为非负浮点数。"""
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


def _timestamp(value: Any) -> float:
    """把时间戳或 datetime 对象转换为 Unix 秒。"""
    if hasattr(value, "timestamp"):
        try:
            return _number(value.timestamp())
        except (TypeError, ValueError, OSError):
            return 0.0
    return _number(value)


__all__ = (
    "build_snapshot",
    "downloader_type",
    "read_torrents",
    "torrent_hash",
)
