"""BakaBT Today、Freeleech、体积和发布时间筛选。"""

from __future__ import annotations

from datetime import datetime, timezone

from .config import BrushConfig
from .models import BakaBTTorrent


def prefilter_candidates(
    torrents: list[BakaBTTorrent], config: BrushConfig,
) -> list[BakaBTTorrent]:
    """详情请求前仅使用浏览页可靠字段粗筛。"""
    return [
        item for item in torrents
        if item.is_freeleech and matches_size(item, config) and is_today_listing(item)
    ]


def matches_final_filters(
    item: BakaBTTorrent, config: BrushConfig, now: datetime,
) -> bool:
    """详情页复核后的最终判断；启用时间限制却无时间时安全跳过。"""
    now = _utc(now)
    if not item.is_freeleech or not matches_size(item, config):
        return False
    if config.publish_age_minimum == 0 and config.publish_age_maximum == 0:
        return True
    if item.published_at is None:
        return False
    age_minutes = max(0, (now - _utc(item.published_at)).total_seconds() / 60)
    if config.publish_age_minimum > 0 and age_minutes < config.publish_age_minimum:
        return False
    if config.publish_age_maximum > 0 and age_minutes > config.publish_age_maximum:
        return False
    return True


def sort_key(item: BakaBTTorrent, now: datetime) -> tuple[float, float]:
    """发布时间新优先；同一时间使用较大体积打破平局。"""
    if item.published_at is not None:
        published_at = _utc(item.published_at).timestamp()
    elif is_today_listing(item):
        published_at = _utc(now).timestamp()
    else:
        published_at = 0
    return published_at, item.size_mb


def is_today_listing(item: BakaBTTorrent) -> bool:
    added = " ".join((item.added_text or "").lower().split())
    return added == "today" or added.startswith("today ")


def matches_size(item: BakaBTTorrent, config: BrushConfig) -> bool:
    if item.size_mb < 0:
        return False
    if config.size_minimum_mb > 0 and item.size_mb < config.size_minimum_mb:
        return False
    if config.size_maximum_mb > 0 and item.size_mb > config.size_maximum_mb:
        return False
    return True


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
