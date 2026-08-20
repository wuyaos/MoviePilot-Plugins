"""BakaBTBrush 自动删种条件评估；仅处理插件自己登记的 qB 任务。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .config import BrushConfig
from .downloader import COMPLETE_STATES, DownloaderError, delete_torrent
from .models import QBTorrentSnapshot
from .scraper import BakaBTError
from .state import record_deletions


@dataclass(frozen=True)
class DeletionCandidate:
    torrent: QBTorrentSnapshot
    reasons: tuple[str, ...]
    managed: dict[str, Any]


def evaluate_deletions(
    config: BrushConfig,
    torrents: list[QBTorrentSnapshot],
    state: dict[str, Any],
    now: datetime,
) -> list[DeletionCandidate]:
    """普通模式：任一已启用条件命中即返回；不执行实际删除。"""
    if not config.auto_delete:
        return []
    now_ts = int(_utc(now).timestamp())
    managed_by_hash = _managed_by_hash(state)
    excluded = {tag.casefold() for tag in config.delete_exclude_tags}
    results: list[DeletionCandidate] = []

    for torrent in torrents:
        managed = managed_by_hash.get(torrent.infohash.lower())
        if not managed:
            continue
        if excluded.intersection(tag.casefold() for tag in torrent.tags):
            continue
        age_seconds = _age_seconds(torrent, managed, now_ts)
        if config.delete_protection_minutes > 0:
            if age_seconds < config.delete_protection_minutes * 60:
                continue

        complete = torrent.progress >= 0.999999 or torrent.state.lower() in COMPLETE_STATES
        reasons: list[str] = []
        if config.delete_seed_hours > 0 and complete:
            seeded_seconds = max(0, torrent.seeding_time)
            if seeded_seconds >= config.delete_seed_hours * 3600:
                reasons.append(f"做种达到 {_number_text(seeded_seconds / 3600)} 小时")
        if config.delete_ratio > 0 and torrent.ratio >= config.delete_ratio:
            reasons.append(f"分享率达到 {_number_text(torrent.ratio)}")
        uploaded_gb = torrent.uploaded / (1024 ** 3)
        if config.delete_uploaded_gb > 0 and uploaded_gb >= config.delete_uploaded_gb:
            reasons.append(f"上传量达到 {_number_text(uploaded_gb)} GB")
        if config.delete_download_timeout_hours > 0 and not complete:
            if age_seconds >= config.delete_download_timeout_hours * 3600:
                reasons.append(f"下载达到 {_number_text(age_seconds / 3600)} 小时仍未完成")
        if config.delete_inactive_minutes > 0 and torrent.last_activity > 0:
            inactive_seconds = max(0, now_ts - torrent.last_activity)
            if inactive_seconds >= config.delete_inactive_minutes * 60:
                reasons.append(f"未活动达到 {_number_text(inactive_seconds / 60)} 分钟")
        if config.delete_avg_upload_kbps > 0 and age_seconds > 0:
            average_kbps = torrent.uploaded / age_seconds / 1024
            if average_kbps <= config.delete_avg_upload_kbps:
                reasons.append(f"平均上传速度仅 {_number_text(average_kbps)} KB/s")

        if reasons:
            results.append(DeletionCandidate(torrent, tuple(reasons), managed))
    return results


def managed_incomplete_for_freeleech_check(
    config: BrushConfig,
    torrents: list[QBTorrentSnapshot],
    state: dict[str, Any],
    now: datetime,
) -> list[DeletionCandidate]:
    """返回需要实时确认促销状态的未完成任务，不复用当天详情缓存。"""
    if not config.auto_delete or not config.delete_expired_freeleech_incomplete:
        return []
    now_ts = int(_utc(now).timestamp())
    managed_by_hash = _managed_by_hash(state)
    excluded = {tag.casefold() for tag in config.delete_exclude_tags}
    results: list[DeletionCandidate] = []
    for torrent in torrents:
        if torrent.progress >= 0.999999 or torrent.state.lower() in COMPLETE_STATES:
            continue
        managed = managed_by_hash.get(torrent.infohash.lower())
        if not managed or not managed.get("detail_url"):
            continue
        if excluded.intersection(tag.casefold() for tag in torrent.tags):
            continue
        age_seconds = _age_seconds(torrent, managed, now_ts)
        if config.delete_protection_minutes > 0:
            if age_seconds < config.delete_protection_minutes * 60:
                continue
        results.append(DeletionCandidate(torrent, (), managed))
    return results


def execute_cleanup(
    config: BrushConfig,
    state: dict[str, Any],
    qb_instance: Any,
    torrents: list[QBTorrentSnapshot],
    now: datetime,
    *,
    client: Any = None,
    freeleech_only: bool = False,
    excluded_hashes: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """执行已严格限定范围的删除；详情读取失败时安全跳过。"""
    excluded_hashes = {value.lower() for value in excluded_hashes or set()}
    candidates = (
        managed_incomplete_for_freeleech_check(config, torrents, state, now)
        if freeleech_only
        else evaluate_deletions(config, torrents, state, now)
    )
    records: list[dict[str, Any]] = []
    notes: list[str] = []
    for candidate in candidates:
        torrent = candidate.torrent
        if torrent.infohash.lower() in excluded_hashes:
            continue
        reasons = list(candidate.reasons)
        if freeleech_only:
            if client is None:
                continue
            try:
                detail = client.fetch_detail(str(candidate.managed.get("detail_url")))
            except BakaBTError:
                notes.append(f"{torrent.name}：促销状态读取失败，未删除")
                continue
            if not detail.published_at and not detail.download_url and not detail.infohash:
                notes.append(f"{torrent.name}：促销状态无法确认，未删除")
                continue
            if detail.is_freeleech:
                continue
            reasons = ["Freeleech 已过期且下载未完成"]
        try:
            delete_torrent(qb_instance, torrent.infohash, delete_files=config.delete_files)
        except DownloaderError:
            notes.append(f"{torrent.name}：qB 删除失败")
            continue
        records.append({
            "time": _utc(now).isoformat().replace("+00:00", "Z"),
            "infohash": torrent.infohash,
            "title": torrent.name,
            "detail_url": str(candidate.managed.get("detail_url") or ""),
            "reason": "；".join(reasons),
            "delete_files": config.delete_files,
            "uploaded_gb": round(torrent.uploaded / (1024 ** 3), 3),
            "ratio": round(max(0.0, torrent.ratio), 3),
        })
    record_deletions(state, records)
    return records, notes


def _managed_by_hash(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in (state.get("added") or {}).values():
        if not isinstance(record, dict):
            continue
        infohash = str(record.get("infohash") or "").lower()
        if infohash:
            result[infohash] = record
    return result


def _age_seconds(torrent: QBTorrentSnapshot, managed: dict[str, Any], now_ts: int) -> int:
    if torrent.added_on > 0:
        return max(0, now_ts - torrent.added_on)
    try:
        added_at = datetime.fromisoformat(str(managed.get("added_at") or "").replace("Z", "+00:00"))
        return max(0, now_ts - int(_utc(added_at).timestamp()))
    except (TypeError, ValueError):
        return 0


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _number_text(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")
