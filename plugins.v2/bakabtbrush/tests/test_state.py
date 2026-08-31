from __future__ import annotations

from datetime import datetime, timezone

from core.models import AccountSnapshot, BakaBTTorrent
from core.state import (
    MAX_HISTORY,
    cache_rss_pending,
    completed_hashes,
    default_state,
    initialize_rss_cache,
    normalize_state,
    record_run,
    remember_added,
    remember_completed,
    remember_rss_feed,
    remember_rss_promotion,
    rss_cache_initialized,
    rss_pending_torrents,
    rss_source_hash,
    unseen_rss_torrents,
    update_account,
    update_qb,
    was_added,
)


def _item() -> BakaBTTorrent:
    return BakaBTTorrent(
        torrent_id="360859",
        title="Example",
        detail_url="https://bakabt.me/torrent/360859/example",
        size_mb=512,
        is_freeleech=True,
    )


def test_state_tracks_added_completed_and_snapshots_without_cookie():
    state = default_state()
    item = _item()

    remember_added(state, item, "A" * 40)
    remember_completed(state, {"A" * 40})
    update_account(state, AccountSnapshot(1024.5, 512.0, "2.00"))
    update_qb(state, uploaded_mb=100, downloaded_mb=50, downloading_count=1, max_downloading=2)

    assert was_added(state, "360859")
    assert completed_hashes(state) == {"a" * 40}
    assert state["account"]["uploaded_mb"] == 1024.5
    assert state["qb"]["downloading_count"] == 1
    assert "cookie" not in str(state).lower()


def test_rss_cache_persists_only_public_candidate_fields_and_source_hash():
    state = default_state()
    now = datetime(2026, 8, 19, 12, tzinfo=timezone.utc)
    rss_url = "https://bakabt.me/rss.php?uid=1&v=2&key=private-secret"
    baseline = _item()
    baseline.published_at = now
    source_hash = rss_source_hash(rss_url)

    initialize_rss_cache(state, source_hash, [baseline], now)
    assert rss_cache_initialized(state, source_hash)
    assert unseen_rss_torrents(state, [baseline]) == []

    candidate = _item()
    candidate.torrent_id = "360860"
    candidate.published_at = now
    cache_rss_pending(state, candidate, "waiting_promotion", now)
    remember_rss_promotion(state, candidate.torrent_id, True, now)
    remember_rss_feed(state, [candidate, baseline], now)

    restored = normalize_state(state)
    assert [item.torrent_id for item in rss_pending_torrents(restored)] == ["360860"]
    assert restored["rss"]["promotions"]["360860"]["is_freeleech"] is True
    restored["rss"]["seen_ids"] = []
    assert unseen_rss_torrents(restored, [candidate]) == []
    assert "private-secret" not in str(restored)
    assert rss_url not in str(restored)


def test_history_is_trimmed_to_recent_entries():
    state = default_state()
    for index in range(MAX_HISTORY + 3):
        record_run(state, {"status": "success", "torrent": str(index)})

    assert len(state["history"]) == MAX_HISTORY
    assert state["history"][-1]["torrent"] == str(MAX_HISTORY + 2)


def test_normalize_state_keeps_valid_old_data_only():
    state = normalize_state({"history": [{"status": "success"}, "bad"], "completed_hashes": ["ABC", "abc"]})

    assert len(state["history"]) == 1
    assert state["completed_hashes"] == ["abc"]
