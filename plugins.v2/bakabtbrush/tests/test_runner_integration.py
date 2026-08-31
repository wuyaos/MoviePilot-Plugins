from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import core.runner as runner_module
from core.config import BrushConfig
from core.models import AccountSnapshot, BakaBTTorrent, BrowsePage, DetailPage, RssFeed
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
        self.account_calls = 0
        self.detail_calls = 0
        self.torrent_calls = 0

    def fetch_browse(self):
        self.browse_calls += 1
        return BrowsePage([self.item], "https://bakabt.me/user/1/example")

    def fetch_account(self, _):
        self.account_calls += 1
        return AccountSnapshot(2048, 1024, "2.00")

    def fetch_detail(self, _):
        self.detail_calls += 1
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


def _rss_item(torrent_id: str, *, age_minutes: int = 30, size_mb: float = 1024):
    return BakaBTTorrent(
        torrent_id=torrent_id,
        title=f"RSS {torrent_id}",
        detail_url=f"https://bakabt.me/torrent/{torrent_id}/example",
        size_mb=size_mb,
        published_at=NOW - timedelta(minutes=age_minutes),
        added_text="rss",
        is_freeleech=False,
    )


def _install_rss_client(monkeypatch, items_holder):
    calls = []

    class FakeRssClient:
        def __init__(self, timeout=20):
            self.timeout = timeout

        def fetch_rss(self, rss_url):
            calls.append(rss_url)
            return RssFeed(list(items_holder["items"]))

    monkeypatch.setattr(runner_module, "BakaBTRssClient", FakeRssClient)
    return calls


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


def test_rss_mode_keeps_automatic_cleanup_before_discovery(monkeypatch):
    holder = {"items": [_rss_item("360858")]}
    _install_rss_client(monkeypatch, holder)
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
    state["added"]["360857"] = {
        "infohash": "b" * 40,
        "title": "existing",
        "detail_url": "https://bakabt.me/torrent/360857/example",
        "added_at": (NOW - timedelta(hours=30)).isoformat(),
    }
    instance = FakeQBInstance([existing])
    client = FakeClient(_item())

    result = run_once(
        _config(
            rss_url="https://bakabt.me/rss.php?uid=1&v=2&key=private",
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

    assert result.status == "no_candidate"
    assert result.deleted[0]["title"] == "existing"
    assert instance.delete_calls == [{"delete_file": False, "ids": ["b" * 40]}]
    assert client.browse_calls == 0


def test_rss_first_run_builds_baseline_without_cookie_or_html(monkeypatch):
    holder = {"items": [_rss_item("360858")]}
    rss_calls = _install_rss_client(monkeypatch, holder)
    state = default_state()
    client = FakeClient(_item())
    cookie_lookups = []

    result = run_once(
        _config(rss_url="https://bakabt.me/rss.php?uid=1&v=2&key=private"),
        lambda: cookie_lookups.append(True) or "cookie",
        state,
        FakeQBInstance(),
        now=NOW,
        client=client,
    )

    assert result.status == "no_candidate"
    assert "基线" in result.detail
    assert len(rss_calls) == 1
    assert client.browse_calls == 0
    assert client.detail_calls == 0
    assert cookie_lookups == []
    assert state["rss"]["seen_ids"] == ["360858"]
    assert "private" not in str(state)


def test_unchanged_rss_uses_cache_and_never_accesses_html(monkeypatch):
    holder = {"items": [_rss_item("360858")]}
    _install_rss_client(monkeypatch, holder)
    state = default_state()
    client = FakeClient(_item())
    config = _config(rss_url="https://bakabt.me/rss.php?uid=1&v=2&key=private")

    run_once(config, "cookie", state, FakeQBInstance(), now=NOW, client=client)
    result = run_once(config, "cookie", state, FakeQBInstance(), now=NOW, client=client)

    assert result.status == "no_candidate"
    assert "未发现新种" in result.detail
    assert client.browse_calls == 0
    assert client.account_calls == 0
    assert client.detail_calls == 0


def test_rss_new_item_prefilters_size_before_single_browse_request(monkeypatch):
    baseline = _rss_item("360858")
    holder = {"items": [baseline]}
    _install_rss_client(monkeypatch, holder)
    state = default_state()
    client = FakeClient(_item())
    config = _config(rss_url="https://bakabt.me/rss.php?uid=1&v=2&key=private")
    run_once(config, "cookie", state, FakeQBInstance(), now=NOW, client=client)

    holder["items"] = [_rss_item("360860", size_mb=100), baseline]
    result = run_once(config, "cookie", state, FakeQBInstance(), now=NOW, client=client)

    assert result.status == "no_candidate"
    assert client.browse_calls == 0
    assert client.detail_calls == 0
    assert state["rss"]["pending"] == {}


def test_rss_matching_new_item_uses_one_browse_then_detail_and_adds(monkeypatch):
    baseline = _rss_item("360858")
    candidate = _rss_item("360860")
    holder = {"items": [baseline]}
    _install_rss_client(monkeypatch, holder)
    state = default_state()
    config = _config(rss_url="https://bakabt.me/rss.php?uid=1&v=2&key=private")
    instance = FakeQBInstance()
    browser_item = _rss_item("360860")
    browser_item.is_freeleech = True
    client = FakeClient(browser_item)
    run_once(config, "cookie", state, instance, now=NOW, client=client)

    holder["items"] = [candidate, baseline]
    result = run_once(config, "cookie", state, instance, now=NOW, client=client)

    assert result.status == "success"
    assert [item.torrent_id for item in result.added] == ["360860"]
    assert client.browse_calls == 1
    assert client.detail_calls == 1
    assert client.torrent_calls == 1
    assert state["rss"]["pending"] == {}
    assert state["rss"]["promotions"]["360860"]["is_freeleech"] is True


def test_rss_dry_run_keeps_cached_candidate_for_next_normal_run(monkeypatch):
    baseline = _rss_item("360858")
    candidate = _rss_item("360860")
    holder = {"items": [baseline]}
    _install_rss_client(monkeypatch, holder)
    state = default_state()
    config = _config(rss_url="https://bakabt.me/rss.php?uid=1&v=2&key=private")
    browser_item = _rss_item("360860")
    browser_item.is_freeleech = True
    client = FakeClient(browser_item)
    instance = FakeQBInstance()
    run_once(config, "cookie", state, instance, now=NOW, client=client)

    holder["items"] = [candidate, baseline]
    preview = run_once(
        config,
        "cookie",
        state,
        instance,
        dry_run=True,
        now=NOW,
        client=client,
    )
    added = run_once(config, "cookie", state, instance, now=NOW, client=client)

    assert preview.status == "dry_run"
    assert [item.torrent_id for item in preview.previewed] == ["360860"]
    assert added.status == "success"
    assert client.browse_calls == 1
    assert client.detail_calls == 1
    assert client.torrent_calls == 1


def test_rss_account_snapshot_cache_skips_fresh_account_page(monkeypatch):
    baseline = _rss_item("360858")
    candidate = _rss_item("360860")
    holder = {"items": [baseline]}
    _install_rss_client(monkeypatch, holder)
    state = default_state()
    state["account"]["updated_at"] = NOW.isoformat().replace("+00:00", "Z")
    config = _config(rss_url="https://bakabt.me/rss.php?uid=1&v=2&key=private")
    browser_item = _rss_item("360860")
    browser_item.is_freeleech = False
    client = FakeClient(browser_item)
    run_once(config, "cookie", state, FakeQBInstance(), now=NOW, client=client)

    holder["items"] = [candidate, baseline]
    run_once(config, "cookie", state, FakeQBInstance(), now=NOW, client=client)

    assert client.browse_calls == 1
    assert client.account_calls == 0


def test_rss_waiting_age_uses_cache_until_time_matches(monkeypatch):
    baseline = _rss_item("360858")
    candidate = _rss_item("360860", age_minutes=2)
    holder = {"items": [baseline]}
    _install_rss_client(monkeypatch, holder)
    state = default_state()
    config = _config(rss_url="https://bakabt.me/rss.php?uid=1&v=2&key=private")
    browser_item = _rss_item("360860", age_minutes=2)
    browser_item.is_freeleech = True
    client = FakeClient(browser_item)
    instance = FakeQBInstance()
    run_once(config, "cookie", state, instance, now=NOW, client=client)

    holder["items"] = [candidate, baseline]
    waiting = run_once(config, "cookie", state, instance, now=NOW, client=client)
    assert waiting.status == "no_candidate"
    assert state["rss"]["pending"]["360860"]["status"] == "waiting_age"
    assert client.browse_calls == 0

    ready = run_once(
        config,
        "cookie",
        state,
        instance,
        now=NOW + timedelta(minutes=8),
        client=client,
    )
    assert ready.status == "success"
    assert client.browse_calls == 1


def test_rss_candidate_waits_in_cache_while_qb_is_full(monkeypatch):
    baseline = _rss_item("360858")
    candidate = _rss_item("360860")
    holder = {"items": [baseline]}
    _install_rss_client(monkeypatch, holder)
    state = default_state()
    config = _config(
        rss_url="https://bakabt.me/rss.php?uid=1&v=2&key=private",
        max_bakabt_downloading=1,
    )
    browser_item = _rss_item("360860")
    browser_item.is_freeleech = True
    client = FakeClient(browser_item)
    run_once(config, "cookie", state, FakeQBInstance(), now=NOW, client=client)

    existing = SimpleNamespace(
        hash="b" * 40, name="existing", category="刷流", tags="bakabt,刷流",
        state="downloading", progress=0, uploaded=0, downloaded=0,
    )
    holder["items"] = [candidate, baseline]
    blocked = run_once(
        config,
        "cookie",
        state,
        FakeQBInstance([existing]),
        now=NOW,
        client=client,
    )

    assert blocked.status == "no_qb_slot"
    assert state["rss"]["pending"]["360860"]["status"] == "waiting_slot"
    assert client.browse_calls == 0

    resumed = run_once(
        config,
        "cookie",
        state,
        FakeQBInstance(),
        now=NOW,
        client=client,
    )
    assert resumed.status == "success"
    assert client.browse_calls == 1


def test_rss_unlimited_publish_age_does_not_apply_hidden_24h_limit(monkeypatch):
    baseline = _rss_item("360858")
    old_candidate = _rss_item("360860", age_minutes=2000)
    holder = {"items": [baseline]}
    _install_rss_client(monkeypatch, holder)
    state = default_state()
    config = _config(
        rss_url="https://bakabt.me/rss.php?uid=1&v=2&key=private",
        publish_age_range_minutes="0",
    )
    browser_item = _rss_item("360860", age_minutes=2000)
    browser_item.is_freeleech = True
    client = FakeClient(browser_item)
    instance = FakeQBInstance()
    run_once(config, "cookie", state, instance, now=NOW, client=client)

    holder["items"] = [old_candidate, baseline]
    result = run_once(config, "cookie", state, instance, now=NOW, client=client)

    assert result.status == "success"
    assert client.browse_calls == 1


def test_rss_missing_browse_row_retries_three_times_then_stops(monkeypatch):
    baseline = _rss_item("360858")
    candidate = _rss_item("360860")
    holder = {"items": [baseline]}
    _install_rss_client(monkeypatch, holder)
    state = default_state()
    config = _config(rss_url="https://bakabt.me/rss.php?uid=1&v=2&key=private")

    class MissingRowClient(FakeClient):
        def fetch_browse(self):
            self.browse_calls += 1
            return BrowsePage([], None)

    client = MissingRowClient(candidate)
    run_once(config, "cookie", state, FakeQBInstance(), now=NOW, client=client)
    holder["items"] = [candidate, baseline]

    for minute in (0, 10, 20):
        run_once(
            config,
            "cookie",
            state,
            FakeQBInstance(),
            now=NOW + timedelta(minutes=minute),
            client=client,
        )
    final = run_once(
        config,
        "cookie",
        state,
        FakeQBInstance(),
        now=NOW + timedelta(minutes=30),
        client=client,
    )

    assert final.status == "no_candidate"
    assert client.browse_calls == 3
    assert state["rss"]["pending"] == {}
    assert state["rss"]["promotions"]["360860"]["is_freeleech"] is None


def test_rss_non_freeleech_result_is_cached_and_not_rechecked(monkeypatch):
    baseline = _rss_item("360858")
    candidate = _rss_item("360860")
    holder = {"items": [baseline]}
    _install_rss_client(monkeypatch, holder)
    state = default_state()
    config = _config(rss_url="https://bakabt.me/rss.php?uid=1&v=2&key=private")
    browser_item = _rss_item("360860")
    browser_item.is_freeleech = False
    client = FakeClient(browser_item)
    run_once(config, "cookie", state, FakeQBInstance(), now=NOW, client=client)

    holder["items"] = [candidate, baseline]
    first = run_once(config, "cookie", state, FakeQBInstance(), now=NOW, client=client)
    second = run_once(config, "cookie", state, FakeQBInstance(), now=NOW, client=client)

    assert first.status == "no_candidate"
    assert second.status == "no_candidate"
    assert client.browse_calls == 1
    assert client.detail_calls == 0
    assert state["rss"]["pending"] == {}
    assert state["rss"]["promotions"]["360860"]["is_freeleech"] is False
