from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.config import BrushConfig
from core.filtering import matches_final_filters, sort_key
from core.models import BakaBTTorrent
from core.runner import _rss_age_state


NOW = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)


def _item(
    torrent_id: str, *, age_minutes: int | None, size_mb: float,
    free: bool = True,
) -> BakaBTTorrent:
    published_at = NOW - timedelta(minutes=age_minutes) if age_minutes is not None else None
    return BakaBTTorrent(
        torrent_id=torrent_id,
        title=torrent_id,
        detail_url=f"https://bakabt.me/torrent/{torrent_id}/example",
        size_mb=size_mb,
        published_at=published_at,
        is_freeleech=free,
    )


def test_final_filter_requires_detail_time_only_when_time_constraint_is_enabled():
    no_time_limit = BrushConfig.from_mapping({})
    time_limited = BrushConfig.from_mapping({"publish_age_range_minutes": "60"})
    item = _item("unknown", age_minutes=None, size_mb=500)

    assert matches_final_filters(item, no_time_limit, NOW) is True
    assert matches_final_filters(item, time_limited, NOW) is False


def test_rss_age_state_respects_minimum_maximum_and_unlimited_boundaries():
    limited = BrushConfig.from_mapping({"publish_age_range_minutes": "10-60"})

    assert _rss_age_state(_item("too-new", age_minutes=9, size_mb=500), limited, NOW) == "waiting"
    assert _rss_age_state(_item("minimum", age_minutes=10, size_mb=500), limited, NOW) == "ready"
    assert _rss_age_state(_item("maximum", age_minutes=60, size_mb=500), limited, NOW) == "ready"
    assert _rss_age_state(_item("expired", age_minutes=61, size_mb=500), limited, NOW) == "expired"
    assert _rss_age_state(
        _item("unlimited", age_minutes=2000, size_mb=500),
        BrushConfig.from_mapping({"publish_age_range_minutes": "0"}),
        NOW,
    ) == "ready"


def test_sort_key_prefers_newest_then_larger_size_and_handles_unknown_time():
    newest = _item("newest", age_minutes=10, size_mb=100)
    older_large = _item("older-large", age_minutes=20, size_mb=900)
    unknown = BakaBTTorrent(
        torrent_id="unknown",
        title="unknown",
        detail_url="https://bakabt.me/torrent/unknown/example",
        size_mb=9999,
        published_at=None,
    )

    ordered = sorted([unknown, older_large, newest], key=lambda item: sort_key(item, NOW), reverse=True)

    assert [item.torrent_id for item in ordered] == ["newest", "older-large", "unknown"]