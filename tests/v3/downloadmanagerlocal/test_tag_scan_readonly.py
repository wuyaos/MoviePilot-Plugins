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


def test_scan_reads_global_definitions_and_never_writes(tag_service):
    service = fake_service([{"hash": "a", "tags": ["used", "DML_TMP_x"]}])
    service.instance.qbc = SimpleNamespace(torrents_tags=lambda: ["used", "DML_TMP_x", "empty", "H&R"])
    result = tag_service.scan_tag_candidates(fake_plugin(service), ["qb"])
    tags = {item["tag"]: item for item in result["downloaders"][0]["tags"]}
    assert result["auto_removed"] == []
    assert tags["empty"]["removable"] and tags["H&R"]["removable"]
    assert not tags["used"]["removable"] and not tags["DML_TMP_x"]["removable"]
    assert tags["empty"]["count"] == 0


def ready(tag_service, torrents=None):
    from unittest.mock import Mock
    service = fake_service(torrents or [])
    service.instance.qbc = SimpleNamespace(torrents_tags=lambda: ["empty"])
    service.instance.delete_torrents_tag = Mock(return_value=True)
    service.instance.remove_torrents_tag = Mock(side_effect=AssertionError("must not strip torrent tags"))
    plugin = fake_plugin(service)
    scan = tag_service.scan_tag_candidates(plugin, ["qb"])
    return plugin, service, scan["scan_id"]


def test_execute_empty_definition_only(tag_service):
    plugin, service, scan_id = ready(tag_service)
    result = tag_service.execute_tag_cleanup(plugin, [{"downloader": "qb", "tag": "empty"}], scan_id)
    assert result["code"] == 0 and len(result["removed"]) == 1
    service.instance.delete_torrents_tag.assert_called_once_with(ids=None, tag="empty")
    service.instance.remove_torrents_tag.assert_not_called()


@pytest.mark.parametrize("change", ["in_use", "read_error", "active", "outside", "old", "no_id", "hashes"])
def test_execute_rechecks_live_state_and_snapshot(tag_service, change):
    plugin, service, scan_id = ready(tag_service)
    item = {"downloader": "qb", "tag": "empty"}
    if change == "in_use":
        service.instance.get_torrents = lambda: ([{"hash": "new", "tags": ["empty"]}], None)
    elif change == "read_error":
        service.instance.get_torrents = lambda: ([], "offline")
    elif change == "active":
        plugin._active_temporary_tags.add("empty")
    elif change == "outside":
        item["tag"] = "unknown"
    elif change == "old":
        scan_id = "old"
    elif change == "no_id":
        scan_id = None
    else:
        item["hashes"] = ["a"]
    result = tag_service.execute_tag_cleanup(plugin, [item], scan_id)
    assert result["code"] == 1 and not result["removed"]
    service.instance.delete_torrents_tag.assert_not_called()


def test_observe_mode_does_not_delete(tag_service, monkeypatch):
    plugin, service, scan_id = ready(tag_service)
    monkeypatch.setattr(sys.modules[PREFIX + ".utils.config"], "observe_skip", lambda *a: True)
    result = tag_service.execute_tag_cleanup(plugin, [{"downloader": "qb", "tag": "empty"}], scan_id)
    assert result["observed"] == 1 and result["code"] == 0
    service.instance.delete_torrents_tag.assert_not_called()


@pytest.mark.parametrize("definitions", [None, "empty", [None]])
def test_scan_invalid_definition_response_fails_closed(tag_service, definitions):
    service = fake_service([])
    service.instance.qbc = SimpleNamespace(torrents_tags=lambda: definitions)
    result = tag_service.scan_tag_candidates(fake_plugin(service), ["qb"])
    assert result["code"] == 1 and not result["downloaders"]


def test_scan_id_round_trip_and_persisted_fallback(tag_service):
    plugin, _, scan_id = ready(tag_service)
    saved = plugin._tag_cleanup_status
    plugin._tag_cleanup_status = None
    plugin.get_data = lambda key: saved
    assert tag_service.get_cleanup_status(plugin)["scan_id"] == scan_id


def test_execute_truncation_is_explicit(tag_service):
    plugin, _, scan_id = ready(tag_service)
    result = tag_service.execute_tag_cleanup(plugin, [{"downloader": "qb", "tag": "outside"}] * 1001, scan_id)
    assert result["truncated"] and result["requested"] == 1001 and result["processed"] == 1000


def test_unavailable_and_non_qb_are_errors(tag_service):
    plugin = fake_plugin(None)
    plugin.service_info = lambda name: None if name == "missing" else SimpleNamespace(type="transmission")
    result = tag_service.scan_tag_candidates(plugin, ["missing", "tr"])
    assert len(result["errors"]) == 2 and result["code"] == 1
