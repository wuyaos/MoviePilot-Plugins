from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.config import BrushConfig
from core.filtering import matches_final_filters, prefilter_candidates
from core.models import BakaBTTorrent


NOW = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)


def _item(
    torrent_id: str, *, age_minutes: int | None, size_mb: float,
    free: bool = True, added_text: str = "",
) -> BakaBTTorrent:
    published_at = NOW - timedelta(minutes=age_minutes) if age_minutes is not None else None
    return BakaBTTorrent(
        torrent_id=torrent_id,
        title=torrent_id,
        detail_url=f"https://bakabt.me/torrent/{torrent_id}/example",
        size_mb=size_mb,
        published_at=published_at,
        added_text=added_text,
        is_freeleech=free,
    )


def test_prefilter_keeps_only_today_freeleech_and_size_candidates():
    config = BrushConfig.from_mapping({
        "publish_age_range_minutes": "10-60",
        "size_range_mb": "500-1000",
    })
    result = prefilter_candidates([
        _item("fresh", age_minutes=5, size_mb=600, added_text="today"),
        _item("good", age_minutes=30, size_mb=600, added_text="today"),
        _item("old", age_minutes=30, size_mb=600, added_text="yesterday"),
        _item("small", age_minutes=30, size_mb=100, added_text="today"),
        _item("paid", age_minutes=30, size_mb=600, free=False, added_text="today"),
        _item("unknown", age_minutes=None, size_mb=600, added_text="today"),
    ], config)

    # 发布时间窗口只在详情页精确时间取得后过滤。
    assert [item.torrent_id for item in result] == ["fresh", "good", "unknown"]


def test_final_filter_requires_detail_time_only_when_time_constraint_is_enabled():
    no_time_limit = BrushConfig.from_mapping({})
    time_limited = BrushConfig.from_mapping({"publish_age_range_minutes": "60"})
    item = _item("unknown", age_minutes=None, size_mb=500, added_text="today")

    assert matches_final_filters(item, no_time_limit, NOW) is True
    assert matches_final_filters(item, time_limited, NOW) is False


def test_prefilter_preserves_browse_order_until_detail_time_is_available():
    config = BrushConfig.from_mapping({})
    result = prefilter_candidates([
        _item("old-large", age_minutes=20, size_mb=1000, added_text="today"),
        _item("new-small", age_minutes=10, size_mb=500, added_text="today"),
        _item("new-large", age_minutes=10, size_mb=900, added_text="today"),
    ], config)

    assert [item.torrent_id for item in result] == ["old-large", "new-small", "new-large"]
