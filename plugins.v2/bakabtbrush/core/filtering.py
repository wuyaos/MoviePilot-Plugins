"""BakaBT Freeleech、体积和发布时间筛选。"""

from __future__ import annotations

from datetime import datetime, timezone

from .config import BrushConfig
from .models import BakaBTTorrent


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
    published_at = (
        _utc(item.published_at).timestamp() if item.published_at is not None else 0
    )
    return published_at, item.size_mb


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
