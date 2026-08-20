from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from core.config import BrushConfig
from core.models import AccountSnapshot, BakaBTTorrent, BrowsePage, DetailPage
from core.runner import run_once
from core.scraper import BakaBTError
from core.state import default_state


NOW = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
INFOHASH = "a" * 40


class FakeQBC:
    def __init__(self, torrents=None):
        self.torrents = list(torrents or [])

    def torrents_info(self, category=None, torrent_hashes=None):
        if torrent_hashes:
            return [item for item in self.torrents if item.hash == torrent_hashes]
        return [item for item in self.torrents if item.category == category]


class FakeQBInstance:
    def __init__(self, torrents=None):
        self.qbc = FakeQBC(torrents)
        self.add_calls = []
        self.delete_calls = []

    def add_torrent(self, **kwargs):
        self.add_calls.append(kwargs)
        self.qbc.torrents.append(SimpleNamespace(
            hash=INFOHASH,
            name="Example",
            category=kwargs["category"],
            tags=",".join(kwargs["tag"]),
            state="downloading",
            progress=0,
            uploaded=0,
            downloaded=0,
        ))
        return True, [INFOHASH]

    def delete_torrents(self, **kwargs):
        self.delete_calls.append(kwargs)
        deleted = set(kwargs.get("ids") or [])
        self.qbc.torrents = [item for item in self.qbc.torrents if item.hash not in deleted]


class FakeClient:
    def __init__(self, item):
        self.item = item
        self.browse_calls = 0
        self.torrent_calls = 0

    def fetch_browse(self):
        self.browse_calls += 1
        return BrowsePage([self.item], "https://bakabt.me/user/1/example")

    def fetch_account(self, _):
        return AccountSnapshot(2048, 1024, "2.00")

    def fetch_detail(self, _):
        return DetailPage(True, self.item.published_at, "https://bakabt.me/download/x.torrent", INFOHASH)

    def fetch_torrent(self, _):
        self.torrent_calls += 1
        return b"d4:infodummy"


def _config(**overrides):
    values = {
        "publish_age_range_minutes": "10-60",
        "size_range_mb": "500-2000",
        "max_bakabt_downloading": 2,
        "save_path": "/downloads/bakabt",
    }
    values.update(overrides)
    return BrushConfig.from_mapping(values)


def _item():
    return BakaBTTorrent(
        torrent_id="360859",
        title="Example",
        detail_url="https://bakabt.me/torrent/360859/example",
        size_mb=1024,
        published_at=NOW - timedelta(minutes=30),
        added_text="today",
        is_freeleech=True,
    )


def test_no_qb_slot_stops_before_any_bakabt_request():
    existing = SimpleNamespace(
        hash="b" * 40, name="existing", category="刷流", tags="bakabt,刷流",
        state="downloading", progress=0, uploaded=0, downloaded=0,
    )
    client = FakeClient(_item())
    cookie_lookups = []
    result = run_once(
        _config(max_bakabt_downloading=1),
        lambda: cookie_lookups.append(True) or "cookie",
        default_state(),
        FakeQBInstance([existing]),
        now=NOW,
        client=client,
    )

    assert result.status == "no_qb_slot"
    assert client.browse_calls == 0
    assert cookie_lookups == []


def test_auto_cleanup_runs_before_slot_check_and_records_deletion():
    existing = SimpleNamespace(
        hash="b" * 40,
        name="existing",
        category="刷流",
        tags="bakabt,刷流",
        state="uploading",
        progress=1,
        uploaded=3 * 1024**3,
        downloaded=1024**3,
        ratio=3,
        added_on=int((NOW - timedelta(hours=30)).timestamp()),
        seeding_time=25 * 3600,
        last_activity=int(NOW.timestamp()),
    )
    state = default_state()
    state["added"]["360859"] = {
        "infohash": "b" * 40,
        "title": "existing",
        "detail_url": "https://bakabt.me/torrent/existing/example",
        "added_at": (NOW - timedelta(hours=30)).isoformat(),
    }
    instance = FakeQBInstance([existing])
    client = FakeClient(_item())
    result = run_once(
        _config(
            max_bakabt_downloading=1,
            auto_delete=True,
            delete_ratio=2,
            delete_protection_minutes=0,
        ),
        "cookie",
        state,
        instance,
        now=NOW,
        client=client,
    )

    assert instance.delete_calls == [{"delete_file": False, "ids": ["b" * 40]}]
    assert result.deleted[0]["title"] == "existing"
    assert result.status == "no_candidate"


def test_finally_rejected_today_item_is_not_shown_as_selected_torrent():
    state = default_state()
    client = FakeClient(_item())

    result = run_once(
        _config(publish_age_range_minutes="10"),
        "cookie",
        state,
        FakeQBInstance(),
        dry_run=True,
        now=NOW,
        client=client,
    )

    assert result.status == "dry_run"
    assert result.previewed == ()
    assert state["last_run"]["torrent"] == "-"
    assert state["last_run"]["torrent_links"] == []


def test_empty_cookie_after_slot_check_fails_without_bakabt_request():
    client = FakeClient(_item())
    result = run_once(_config(), lambda: "", default_state(), FakeQBInstance(), now=NOW, client=client)

    assert result.status == "failed"
    assert client.browse_calls == 0
    assert "Cookie" in result.detail


def test_detail_failure_does_not_block_later_candidate():
    first = _item()
    first.torrent_id = "first"
    first.title = "First"
    second = _item()
    second.torrent_id = "second"
    second.title = "Second"
    second.published_at = NOW - timedelta(minutes=31)

    class FlakyClient(FakeClient):
        def __init__(self):
            super().__init__(first)
            self.detail_calls = 0

        def fetch_browse(self):
            self.browse_calls += 1
            return BrowsePage([first, second], "https://bakabt.me/user/1/example")

        def fetch_detail(self, _):
            self.detail_calls += 1
            if self.detail_calls == 1:
                raise BakaBTError("detail unavailable")
            return DetailPage(True, second.published_at, "https://bakabt.me/download/x.torrent", INFOHASH)

    result = run_once(_config(), "cookie", default_state(), FakeQBInstance(), now=NOW, client=FlakyClient())

    assert result.status == "success"
    assert [item.title for item in result.added] == ["Second"]
    assert result.failed_titles == ("First",)


def test_dry_run_records_candidate_without_downloading_or_adding_to_qb():
    state = default_state()
    instance = FakeQBInstance()
    client = FakeClient(_item())

    result = run_once(
        _config(),
        "cookie",
        state,
        instance,
        dry_run=True,
        now=NOW,
        client=client,
    )

    assert result.status == "dry_run"
    assert [item.torrent_id for item in result.previewed] == ["360859"]
    assert result.added == ()
    assert instance.add_calls == []
    assert client.torrent_calls == 0
    assert state["added"] == {}
    assert state["history"][-1]["push"] == "试运行，未推送 1 个"




def test_today_candidates_use_detail_time_then_download_slot_order():
    older = _item()
    older.torrent_id, older.title = "older", "Older"
    older.detail_url = "https://bakabt.me/torrent/older/example"
    older.added_text = "today"
    older.published_at = NOW - timedelta(minutes=50)
    newer = _item()
    newer.torrent_id, newer.title = "newer", "Newer"
    newer.detail_url = "https://bakabt.me/torrent/newer/example"
    newer.added_text = "today"
    newer.published_at = NOW - timedelta(minutes=15)

    class DetailOrderingClient(FakeClient):
        def __init__(self):
            super().__init__(older)

        def fetch_browse(self):
            return BrowsePage([older, newer], "https://bakabt.me/user/1/example")

        def fetch_detail(self, detail_url):
            item = newer if "/newer/" in detail_url else older
            return DetailPage(True, item.published_at, "https://bakabt.me/download/x.torrent", INFOHASH)

    result = run_once(
        _config(max_bakabt_downloading=1),
        "cookie",
        default_state(),
        FakeQBInstance(),
        dry_run=True,
        now=NOW,
        client=DetailOrderingClient(),
    )

    assert result.status == "dry_run"
    assert [item.torrent_id for item in result.previewed] == ["newer"]

    state = default_state()
    instance = FakeQBInstance()
    item = _item()
    result = run_once(_config(), "cookie", state, instance, now=NOW, client=FakeClient(item))

    assert result.status == "success"
    assert [torrent.torrent_id for torrent in result.added] == ["360859"]
    assert "360859" in state["added"]
    assert state["account"]["ratio"] == "2.00"
    assert state["history"][-1]["push"] == "已推送 1 个"
    assert instance.add_calls[0]["category"] == "刷流"
    assert instance.add_calls[0]["tag"] == ["bakabt", "刷流"]
