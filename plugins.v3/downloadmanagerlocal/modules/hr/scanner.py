"""H&R 任务扫描：下载器读取、种子统计归一、站点识别与标签读写。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional

from app.sdk.logging import logger

from ...adapter.downloader import (
    downloader_type as _downloader_type,
    read_torrents as _query_torrents,
)
from ...adapter.moviepilot import get_downloader_services, get_site_indexer, get_url_domain
from ...utils.torrent_adapter import (
    get_category,
    get_hash,
    get_label,
    get_torrent_size,
    get_tracker_urls,
)
from .constants import HR_LOG_PREFIX
from .models import HrTask

QBITTORRENT = "qbittorrent"


@dataclass(frozen=True)
class HrTorrentSnapshot:
    """下载器无关的 H&R 采样快照。"""

    downloader: str
    downloader_type: str
    torrent_hash: str
    title: str
    size: int
    added_on: float
    seeding_time: float
    ratio: float
    uploaded: float
    downloaded: float
    state: str
    tags: tuple[str, ...]
    category: str
    trackers: tuple[str, ...]

    completed_on: float = 0.0

    downloader_seeding_time: Optional[float] = None
def downloader_services(names: Iterable[str]) -> dict[str, Any]:
    """按名称读取可用下载器服务，跳过未连接或缺少实例的下载器。"""
    selected: list[str] = []
    for name in names or []:
        text = str(name or "").strip()
        if text and text not in selected:
            selected.append(text)
    if not selected:
        return {}
    services = get_downloader_services(name_filters=selected) or {}
    active: dict[str, Any] = {}
    for name, service in services.items():
        instance = getattr(service, "instance", None)
        if instance is None or instance.is_inactive():
            logger.warning(f"{HR_LOG_PREFIX}下载器 {name} 不可用，已跳过")
            continue
        active[name] = service
    return active


def downloader_type(service: Any) -> str:
    """返回下载器类型标识（qbittorrent / transmission）。"""
    return _downloader_type(service)


def read_torrents(service: Any, ids: Optional[Iterable[str]] = None) -> tuple[list, str]:
    """读取下载器任务；返回 (任务列表, 错误信息)，查询失败与成功空列表区分。"""
    id_list = [str(item) for item in ids] if ids is not None else None
    result = _query_torrents(service, ids=id_list)
    if result.success:
        return list(result.items), ""
    return [], result.error or "下载器查询失败"


def torrent_snapshot(
    torrent: Any,
    downloader_id: str,
    downloader_type_name: str,
    now: float,
) -> HrTorrentSnapshot:
    """把 qBittorrent 字典或 Transmission 对象归一为 H&R 采样快照。"""
    dl_type = str(downloader_type_name or "").lower()
    size = int(get_torrent_size(torrent, dl_type) or 0)
    raw_seeding_time = _field(torrent, "seeding_time", "seconds_seeding", "secondsSeeding")
    downloader_seeding_time = _number(raw_seeding_time) if raw_seeding_time is not None else None
    if dl_type == QBITTORRENT:
        completed_at = _number(_field(torrent, "completion_on"))
        seeding_time = now - completed_at if completed_at > 0 else 0.0
        completed_on = completed_at
        ratio = _number(_field(torrent, "ratio"))
        downloaded = _number(_field(torrent, "downloaded"))
        uploaded = _number(_field(torrent, "uploaded"))
        added_on = _number(_field(torrent, "added_on"))
        state = str(_field(torrent, "state", default="") or "")
    else:
        done_at = _timestamp(_field(torrent, "done_date", "date_done", "doneDate"))
        seeding_time = now - done_at if done_at > 0 else 0.0
        completed_on = done_at
        ratio = _number(_field(torrent, "upload_ratio", "uploadRatio", "ratio"))
        percent = _number(_field(torrent, "percent_done", "percentDone", "progress"))
        downloaded = _number(_field(torrent, "downloaded_ever", "downloadedEver")) or size * percent
        uploaded = _number(_field(torrent, "uploaded_ever", "uploadedEver")) or downloaded * ratio
        added_on = _timestamp(_field(torrent, "added_date", "date_added", "addedDate"))
        state = str(getattr(torrent, "status", "") or "")

    return HrTorrentSnapshot(
        downloader=str(downloader_id or ""),
        downloader_type=dl_type,
        torrent_hash=str(get_hash(torrent, dl_type) or "").strip().lower(),
        title=str(_field(torrent, "name", default="") or ""),
        size=size,
        added_on=added_on,
        seeding_time=max(seeding_time, 0.0),
        ratio=ratio,
        uploaded=uploaded,
        downloaded=downloaded,
        state=state,
        tags=tuple(get_label(torrent, dl_type)),
        category=str(get_category(torrent, dl_type) or ""),
        trackers=tuple(get_tracker_urls(torrent, dl_type)),
        completed_on=completed_on,
        downloader_seeding_time=downloader_seeding_time,
    )


def apply_snapshot(task: HrTask, snapshot: HrTorrentSnapshot) -> None:
    """把下载器采样写入任务，补全缺失的种子体积。"""
    task.seeding_time = snapshot.seeding_time
    task.completed_on = snapshot.completed_on or None
    if snapshot.downloader_seeding_time is not None:
        task.downloader_seeding_time = snapshot.downloader_seeding_time
    if task.hr_use_downloader_seeding_time:
        task.seeding_time = task.downloader_seeding_time or 0.0
    task.ratio = snapshot.ratio
    task.uploaded = snapshot.uploaded
    task.downloaded = snapshot.downloaded
    task.state = snapshot.state
    if not task.size and snapshot.size:
        task.size = float(snapshot.size)


def resolve_site(
    tracker_mappings: Optional[dict],
    trackers: Iterable[str],
    site_rules: Optional[dict] = None,
) -> tuple[Optional[int], Optional[str]]:
    """按 tracker 解析站点 ID 与名称：用户域名映射优先，其次 MoviePilot 站点库，
    最后按站点规则条目的 trackers 字段兜底（覆盖 MP 站点库未收录的自定义站点）。"""
    rule_trackers = _rule_domain_map(site_rules)
    mappings = tracker_mappings if isinstance(tracker_mappings, dict) else {}
    for tracker in trackers or []:
        if not tracker:
            continue
        domain = ""
        for key, mapped in mappings.items():
            if key and key in tracker:
                domain = str(mapped or "").strip()
                break
        if not domain:
            domain = get_url_domain(tracker)
        if not domain:
            continue
        rule_name = rule_trackers.get(domain)
        if rule_name:
            return None, rule_name
        try:
            indexer = get_site_indexer(domain) or {}
        except Exception as error:
            logger.debug(f"{HR_LOG_PREFIX}站点索引查询失败 domain={domain}: {error}")
            continue
        site_id = indexer.get("id")
        site_name = indexer.get("name")
        if site_id or site_name:
            return (int(site_id) if site_id else None), (str(site_name) if site_name else None)
    return None, None


def _rule_domain_map(site_rules: Optional[dict]) -> dict[str, str]:
    """把站点规则条目的 trackers 字段归一化为 域名→站点名 映射（仅启用条目参与）。"""
    result: dict[str, str] = {}
    for name, rule in (site_rules or {}).items():
        if not getattr(rule, "enabled", True):
            continue
        for item in getattr(rule, "trackers", None) or []:
            domain = get_url_domain(str(item or "").strip())
            if domain and domain not in result:
                result[domain] = str(name)
    return result


def is_excluded(
    snapshot: HrTorrentSnapshot,
    exclude_tags: Iterable[str],
    exclude_categories: Iterable[str],
) -> tuple[bool, str]:
    """按排除标签与排除分类判断是否跳过纳管，分类仅 qBittorrent 生效。"""
    tags = {str(tag).strip().casefold() for tag in exclude_tags or [] if str(tag).strip()}
    if tags:
        for tag in snapshot.tags:
            if str(tag).strip().casefold() in tags:
                return True, f"标签={tag}"
    categories = {str(item).strip().casefold() for item in exclude_categories or [] if str(item).strip()}
    if categories and snapshot.downloader_type == QBITTORRENT:
        category = str(snapshot.category or "").strip()
        if category and category.casefold() in categories:
            return True, f"分类={category}"
    return False, ""


def torrent_labels(service: Any, torrent_hash: str, *, strict: bool = False) -> list[str]:
    """读取单个任务的最新标签列表，读取失败返回空列表。"""
    torrents, error = read_torrents(service, ids=[torrent_hash])
    if error or not torrents:
        if strict:
            raise RuntimeError(error or "torrent not found")
        return []
    return get_label(torrents[0], downloader_type(service))


def set_hr_tag(service: Any, torrent_hash: str, tag: str, *, strict: bool = False) -> None:
    """给任务追加 H&R 标签，Transmission 保留原有标签。"""
    if not torrent_hash or not tag:
        return
    try:
        if downloader_type(service) == QBITTORRENT:
            result = service.instance.set_torrents_tag(ids=torrent_hash, tags=[tag])
        else:
            result = service.instance.set_torrent_tag(
                ids=torrent_hash,
                tags=[tag],
                org_tags=torrent_labels(service, torrent_hash, strict=strict),
            )
        if strict and result is False:
            raise RuntimeError("tag write rejected")
    except Exception as error:
        if strict:
            raise
        logger.warning(f"{HR_LOG_PREFIX}设置 H&R 标签失败 hash={torrent_hash}: {error}")


def remove_hr_tag(service: Any, torrent_hash: str, tag: str, *, strict: bool = False) -> None:
    """达标后移除 H&R 标签；Transmission 先读最新标签再回写，避免覆盖其他模块写入的标签。"""
    if not torrent_hash or not tag:
        return
    try:
        if downloader_type(service) == QBITTORRENT:
            result = service.instance.remove_torrents_tag(ids=torrent_hash, tag=tag)
            if strict and result is False:
                raise RuntimeError("tag removal rejected")
            return
        remaining = [item for item in torrent_labels(service, torrent_hash, strict=strict) if item != tag]
        if remaining:
            result = service.instance.set_torrent_tag(ids=torrent_hash, tags=remaining)
            if strict and result is False:
                raise RuntimeError("tag removal rejected")
            return
        client = getattr(service.instance, "trc", None)
        if client is None:
            if strict:
                raise RuntimeError("Transmission client unavailable")
            logger.warning(f"{HR_LOG_PREFIX}Transmission 客户端不可用，无法清空 H&R 标签 hash={torrent_hash}")
            return
        result = client.change_torrent(ids=[torrent_hash], labels=[])
        if strict and result is False:
            raise RuntimeError("tag removal rejected")
    except Exception as error:
        if strict:
            raise
        logger.warning(f"{HR_LOG_PREFIX}移除 H&R 标签失败 hash={torrent_hash}: {error}")


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
    "HrTorrentSnapshot",
    "apply_snapshot",
    "downloader_services",
    "downloader_type",
    "is_excluded",
    "read_torrents",
    "remove_hr_tag",
    "resolve_site",
    "set_hr_tag",
    "torrent_snapshot",
)
