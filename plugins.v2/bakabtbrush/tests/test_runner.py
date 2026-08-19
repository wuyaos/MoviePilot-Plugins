from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.config import BrushConfig
from core.models import BakaBTTorrent
from core.runner import matches_final_filters, prefilter_candidates


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


def test_prefilter_only_uses_freeleech_size_and_known_time():
    config = BrushConfig.from_mapping({
        "min_publish_age_minutes": 10,
        "max_publish_age_minutes": 60,
        "min_size_mb": 500,
        "max_size_mb": 1000,
    })
    result = prefilter_candidates([
        _item("fresh", age_minutes=5, size_mb=600),
        _item("good", age_minutes=30, size_mb=600),
        _item("small", age_minutes=30, size_mb=100),
        _item("paid", age_minutes=30, size_mb=600, free=False),
        _item("unknown", age_minutes=None, size_mb=600, added_text="today"),
    ], config, NOW)

    assert [item.torrent_id for item in result] == ["unknown", "good"]


def test_final_filter_requires_detail_time_only_when_time_constraint_is_enabled():
    no_time_limit = BrushConfig.from_mapping({})
    time_limited = BrushConfig.from_mapping({"max_publish_age_minutes": 60})
    item = _item("unknown", age_minutes=None, size_mb=500, added_text="today")

    assert matches_final_filters(item, no_time_limit, NOW) is True
    assert matches_final_filters(item, time_limited, NOW) is False


def test_sort_prefers_newer_then_larger_candidates():
    config = BrushConfig.from_mapping({})
    result = prefilter_candidates([
        _item("old-large", age_minutes=20, size_mb=1000),
        _item("new-small", age_minutes=10, size_mb=500),
        _item("new-large", age_minutes=10, size_mb=900),
    ], config, NOW)

    assert [item.torrent_id for item in result] == ["new-large", "new-small", "old-large"]
