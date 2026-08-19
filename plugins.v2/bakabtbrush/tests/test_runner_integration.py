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


class FakeClient:
    def __init__(self, item):
        self.item = item
        self.browse_calls = 0

    def fetch_browse(self):
        self.browse_calls += 1
        return BrowsePage([self.item], "https://bakabt.me/user/1/example")

    def fetch_account(self, _):
        return AccountSnapshot(2048, 1024, "2.00")

    def fetch_detail(self, _):
        return DetailPage(True, self.item.published_at, "https://bakabt.me/download/x.torrent", INFOHASH)

    def fetch_torrent(self, _):
        return b"d4:infodummy"


def _config(**overrides):
    values = {
        "min_publish_age_minutes": 10,
        "max_publish_age_minutes": 60,
        "min_size_mb": 500,
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


def test_successful_round_adds_only_eligible_torrent_and_records_state():
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
