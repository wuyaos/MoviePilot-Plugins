from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.cleanup import evaluate_deletions, execute_cleanup
from core.config import BrushConfig
from core.models import DetailPage, QBTorrentSnapshot
from core.state import default_state


NOW = datetime(2026, 8, 20, 8, 0, tzinfo=timezone.utc)
INFOHASH = "a" * 40


def _torrent(**overrides):
    values = dict(
        infohash=INFOHASH,
        name="Example",
        category="刷流",
        tags=("bakabt", "刷流"),
        state="uploading",
        progress=1.0,
        uploaded=3 * 1024**3,
        downloaded=1024**3,
        added_on=int((NOW - timedelta(hours=30)).timestamp()),
        last_activity=int((NOW - timedelta(minutes=10)).timestamp()),
        seeding_time=25 * 3600,
        ratio=3.0,
    )
    values.update(overrides)
    return QBTorrentSnapshot(**values)


def _state():
    state = default_state()
    state["added"]["1"] = {
        "infohash": INFOHASH,
        "title": "Example",
        "detail_url": "https://bakabt.me/torrent/1/example",
        "added_at": (NOW - timedelta(hours=30)).isoformat(),
    }
    return state


def test_any_enabled_condition_matches_only_managed_unexcluded_task():
    config = BrushConfig.from_mapping({
        "auto_delete": True,
        "delete_seed_hours": 24,
        "delete_ratio": 10,
        "delete_protection_minutes": 60,
    })
    decisions = evaluate_deletions(config, [_torrent()], _state(), NOW)

    assert len(decisions) == 1
    assert "做种达到 25 小时" in decisions[0].reasons

    unmanaged = default_state()
    assert evaluate_deletions(config, [_torrent()], unmanaged, NOW) == []
    excluded = _torrent(tags=("bakabt", "保留"))
    assert evaluate_deletions(config, [excluded], _state(), NOW) == []


def test_protection_period_blocks_early_low_speed_deletion():
    config = BrushConfig.from_mapping({
        "auto_delete": True,
        "delete_avg_upload_kbps": 100,
        "delete_protection_minutes": 60,
    })
    fresh = _torrent(
        state="downloading",
        progress=0.2,
        uploaded=0,
        added_on=int((NOW - timedelta(minutes=30)).timestamp()),
    )
    assert evaluate_deletions(config, [fresh], _state(), NOW) == []


def test_expired_freeleech_deletes_only_after_successful_live_confirmation():
    class FakeInstance:
        def __init__(self):
            self.calls = []

        def delete_torrents(self, **kwargs):
            self.calls.append(kwargs)

    class FakeClient:
        @staticmethod
        def fetch_detail(_):
            return DetailPage(False, NOW, None, INFOHASH)

    config = BrushConfig.from_mapping({
        "auto_delete": True,
        "delete_expired_freeleech_incomplete": True,
        "delete_protection_minutes": 0,
    })
    incomplete = _torrent(state="downloading", progress=0.5)
    state = _state()
    instance = FakeInstance()

    records, notes = execute_cleanup(
        config, state, instance, [incomplete], NOW,
        client=FakeClient(), freeleech_only=True,
    )

    assert notes == []
    assert records[0]["reason"] == "Freeleech 已过期且下载未完成"
    assert instance.calls == [{"delete_file": False, "ids": [INFOHASH]}]


def test_expired_freeleech_does_not_delete_when_detail_structure_is_unconfirmed():
    class FakeInstance:
        def __init__(self):
            self.calls = []

        def delete_torrents(self, **kwargs):
            self.calls.append(kwargs)

    class EmptyClient:
        @staticmethod
        def fetch_detail(_):
            return DetailPage(False, None, None, None)

    config = BrushConfig.from_mapping({
        "auto_delete": True,
        "delete_expired_freeleech_incomplete": True,
        "delete_protection_minutes": 0,
    })
    instance = FakeInstance()
    records, notes = execute_cleanup(
        config, _state(), instance, [_torrent(state="downloading", progress=0.5)], NOW,
        client=EmptyClient(), freeleech_only=True,
    )

    assert records == []
    assert instance.calls == []
    assert "无法确认" in notes[0]


def test_execute_cleanup_uses_moviepilot_delete_wrapper_and_records_history():
    class FakeInstance:
        def __init__(self):
            self.calls = []

        def delete_torrents(self, **kwargs):
            self.calls.append(kwargs)

    config = BrushConfig.from_mapping({
        "auto_delete": True,
        "delete_ratio": 2,
        "delete_files": False,
        "delete_protection_minutes": 0,
    })
    state = _state()
    instance = FakeInstance()

    records, notes = execute_cleanup(config, state, instance, [_torrent()], NOW)

    assert notes == []
    assert instance.calls == [{"delete_file": False, "ids": [INFOHASH]}]
    assert records[0]["reason"] == "分享率达到 3"
    assert records[0]["detail_url"].endswith("/1/example")
    assert state["deletions"][0]["title"] == "Example"
