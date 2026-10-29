"""P4 标签扫描只读、快照范围和截断契约测试。"""
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3] / "plugins.v3" / "downloadmanagerlocal"
PREFIX = "app.plugins.downloadmanagerlocal"


@pytest.fixture
def tag_service(mp_stubs, monkeypatch):
    adapter = types.ModuleType(PREFIX + ".adapter.moviepilot")
    adapter.generate_random_tag = lambda length=10: "x"
    adapter.get_site_indexer = lambda domain: None
    adapter.get_url_domain = lambda value: ""
    adapter.list_site_dicts = lambda: []
    monkeypatch.setitem(sys.modules, adapter.__name__, adapter)
    state = types.ModuleType(PREFIX + ".model.state")
    state.SITE_TAG_STATUS_KEY = "sitetag_status"
    state.TAG_CLEANUP_STATUS_KEY = "tag_cleanup_status"
    monkeypatch.setitem(sys.modules, state.__name__, state)
    config = types.ModuleType(PREFIX + ".utils.config")
    config.observe_skip = lambda *args: False
    monkeypatch.setitem(sys.modules, config.__name__, config)
    load = mp_stubs("utils/tag_cleanup.py", "utils.tag_cleanup")
    monkeypatch.setitem(sys.modules, PREFIX + ".utils.tag_cleanup", load)
    torrent = mp_stubs("utils/torrent_adapter.py", "utils.torrent_adapter")
    monkeypatch.setitem(sys.modules, PREFIX + ".utils.torrent_adapter", torrent)
    spec = importlib.util.spec_from_file_location(PREFIX + ".modules.sitetag.service", ROOT / "modules/sitetag/service.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.settings.TORRENT_TAG = ""
    return module


def fake_plugin(service):
    return SimpleNamespace(service_info=lambda name: service, _tag_cleanup_status=None,
                           _active_temporary_tags=set(), _torrent_tags=[], _tag_siteprefix="",
                           save_data=lambda key, value: None, get_data=lambda key: None)


def fake_service(torrents):
    class Download:
        type = "qbittorrent"
        instance = SimpleNamespace(get_torrents=lambda ids=None: (torrents, None))
    return Download()


def test_scan_is_readonly_and_keeps_auto_candidate(tag_service, monkeypatch):
    writes = []
    service = fake_service([{"hash": "a", "tags": ["DML_TMP_x"]}])
    plugin = fake_plugin(service)
    monkeypatch.setattr(tag_service, "_read_qb_torrents", lambda service: ([{"hash": "a", "tags": ["DML_TMP_x"]}], None))
    monkeypatch.setattr(tag_service, "_remove_tag_snapshot", lambda *args: writes.append(args))
    result = tag_service.scan_tag_candidates(plugin, ["qb"])
    assert writes == []
    assert result["auto_removed"] == []
    assert result["downloaders"][0]["tags"][0]["auto_removable"] is True


def test_scan_id_round_trip_and_persisted_fallback(tag_service, monkeypatch):
    service = fake_service([])
    plugin = fake_plugin(service)
    monkeypatch.setattr(tag_service, "_read_qb_torrents", lambda service: ([], None))
    result = tag_service.scan_tag_candidates(plugin, ["qb"])
    plugin._tag_cleanup_status = None
    plugin.get_data = lambda key: result
    assert tag_service.get_cleanup_status(plugin)["scan_id"] == result["scan_id"]


def test_wrong_scan_id_rejects_batch_without_delete(tag_service):
    calls = []
    plugin = fake_plugin(fake_service([]))
    plugin._tag_cleanup_status = {"scan_id": "current", "downloaders": []}
    tag_service._remove_tag_snapshot = lambda *args: calls.append(args)
    result = tag_service.execute_tag_cleanup(plugin, [{"downloader": "qb", "tag": "x", "hashes": ["a"]}], "old")
    assert result["code"] == 1 and calls == []


def test_outside_snapshot_is_failed(tag_service):
    plugin = fake_plugin(fake_service([]))
    plugin._tag_cleanup_status = {"scan_id": "s", "downloaders": [{"name": "qb", "tags": [{"tag": "x", "hashes": ["a"]}]}]}
    result = tag_service.execute_tag_cleanup(plugin, [{"downloader": "qb", "tag": "x", "hashes": ["b"]}], "s")
    assert "不在扫描快照内" in result["failed"][0]["message"]


def test_new_candidate_after_scan_is_not_added(tag_service):
    plugin = fake_plugin(fake_service([]))
    plugin._tag_cleanup_status = {"scan_id": "s", "downloaders": [{"name": "qb", "tags": []}]}
    result = tag_service.execute_tag_cleanup(plugin, [{"downloader": "qb", "tag": "new", "hashes": ["b"]}], "s")
    assert result["failed"] and not result["removed"]


def test_managed_tag_is_protected(tag_service):
    plugin = fake_plugin(fake_service([{"hash": "a", "tags": ["managed"]}]))
    plugin._tag_cleanup_status = {"scan_id": "s", "downloaders": [{"name": "qb", "tags": [{"tag": "managed", "hashes": ["a"]}]}]}
    plugin._torrent_tags = ["managed"]
    result = tag_service.execute_tag_cleanup(plugin, [{"downloader": "qb", "tag": "managed", "hashes": ["a"]}], "s")
    assert "保护标签" in result["failed"][0]["message"]


def test_execute_truncation_is_explicit(tag_service):
    plugin = fake_plugin(fake_service([]))
    plugin._tag_cleanup_status = {"scan_id": "s", "downloaders": []}
    removals = [{"downloader": "missing", "tag": "x", "hashes": ["a"]}] * 1001
    result = tag_service.execute_tag_cleanup(plugin, removals, "s")
    assert result["truncated"] is True and result["requested"] == 1001 and result["processed"] == 1000


def test_unavailable_and_non_qb_are_errors(tag_service, monkeypatch):
    plugin = fake_plugin(None)
    plugin.service_info = lambda name: None if name == "missing" else SimpleNamespace(type="transmission")
    monkeypatch.setattr(tag_service, "_read_qb_torrents", lambda service: ([], None))
    result = tag_service.scan_tag_candidates(plugin, ["missing", "tr"])
    assert len(result["errors"]) == 2 and result["code"] == 1
