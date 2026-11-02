# -*- coding: utf-8 -*-
"""重命名 / 站点标签模块观察模式写边界测试（阶段三 P3-2 后半）。

运行：micromamba 环境的 pytest tests/v3/downloadmanagerlocal/test_observe_boundaries_rename_tag.py -q

锁定语义（与 docs/downloadmanagerlocal-optimization-plan.md §5 对齐）：
1. 观察模式下重命名漏斗（rename_candidate）不写下载器、按 skipped 计、登记预览样本；
2. 未观察时重命名漏斗照常进入真实写路径（rename_torrent 被调用）；
3. 观察模式下站点标签写入（_apply_metadata）不改下载器、changed=False、带 observe_only 标记；
4. 未观察时站点标签照常写入；
5. 观察模式下人工标签清理（execute_tag_cleanup）直接返回预览回执，不触达下载器。

宿主（app / 下载器 / 媒体识别 / 历史库）全部替身；加载真实
`modules/rename/service.py`、`modules/sitetag/service.py` 与 `utils/config.py`。
"""
import importlib.machinery
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

PLUGIN = Path(__file__).resolve().parents[3] / "plugins.v3" / "downloadmanagerlocal"
PREFIX = "app.plugins.downloadmanagerlocal"

HASH_A = "a" * 40
HASH_B = "b" * 40
HASH_C = "c" * 40


@pytest.fixture
def mods(monkeypatch):
    """加载真实 rename/sitetag 服务与真实观察模式解析器，宿主全部替身。"""

    def module(name, **attrs):
        path = attrs.pop("__path__", None)
        result = types.ModuleType(name)
        result.__spec__ = importlib.machinery.ModuleSpec(
            name, None, is_package=path is not None)
        if path is not None:
            result.__path__ = path
        result.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, result)
        return result

    def load(relpath, name, pkg):
        spec = importlib.util.spec_from_file_location(
            pkg + name, PLUGIN / relpath)
        result = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = result
        spec.loader.exec_module(result)
        return result

    module("app")
    module("app.sdk")
    module("app.plugins")
    module("app.plugins.downloadmanagerlocal", __path__=[str(PLUGIN)])
    module("app.sdk.logging", logger=Mock())
    module("app.application")
    module("app.application.torrent")
    module("app.application.torrent.download", TorrentHelper=Mock())
    module("app.db")
    module("app.db.oper")
    module("app.db.oper.downloadhistory", DownloadHistoryOper=Mock())
    module("app.db.oper.site", SiteOper=Mock())
    module("app.modules.qbittorrent", Qbittorrent=type("Qbittorrent", (), {}))
    module("app.modules.transmission", Transmission=type("Transmission", (), {}))
    module("app.sdk.network", RequestUtils=Mock(), SitesHelper=Mock())
    module("app.sdk.services", DownloaderHelper=Mock())
    module("app.sdk.utilities", StringUtils=Mock())
    module("app.sdk.media", MetaBase=object, MetaInfo=Mock, resolve_media_identity=Mock())
    module("app.sdk.config", settings=Mock())
    module("app.modules")
    module("app.modules.filemanager")
    module("app.modules.filemanager.transhandler", TransHandler=Mock())
    module("app.schemas")
    module("app.schemas.types", MediaType=Mock(), MessageType=Mock())
    module("bencode", bdecode=Mock(), bencode=Mock())

    module(PREFIX + ".utils", __path__=[str(PLUGIN / "utils")])
    module(PREFIX + ".model", __path__=[str(PLUGIN / "model")])
    module(PREFIX + ".model.state", RENAME_RECORDS_KEY="rename_records",
           RENAME_RETRY_STATE_KEY="rename_retry")
    module(PREFIX + ".modules", __path__=[str(PLUGIN / "modules")])
    module(PREFIX + ".adapter", __path__=[str(PLUGIN / "adapter")])
    module(
        PREFIX + ".adapter.moviepilot",
        get_download_history_by_hash=Mock(return_value=None),
        get_url_domain=Mock(return_value=""),
        get_site_indexer=Mock(return_value=None),
        list_site_dicts=Mock(return_value=[]),
        generate_random_tag=Mock(return_value="tmp_tag"),
    )

    pkg = PREFIX + ".modules"
    rename_mod = load("modules/rename/service.py", ".rename.service", pkg)
    sitetag_mod = load("modules/sitetag/service.py", ".sitetag.service", pkg)
    utils_config = load("utils/config.py", ".config", PREFIX + ".utils")
    return SimpleNamespace(rename=rename_mod, tag=sitetag_mod, config=utils_config)


def _torrent(torrent_hash):
    return {
        "hash": torrent_hash,
        "name": "Show.S01E01.2024.mkv",
        "save_path": "/data/show/",
        "labels": [],
    }


def test_rename_funnel_blocked_when_observed(mods):
    """观察模式下重命名漏斗跳过写操作：skipped、下载器零调用、登记预览。"""
    plugin = SimpleNamespace(_module_observe_only={"rename": True}, _observe_previews={}, get_data=lambda key: {})
    dl = Mock()
    service = SimpleNamespace(type="qbittorrent", name="QB1", instance=dl)
    result = mods.rename.rename_candidate(
        plugin, service, mods.rename.build_rename_config({}), _torrent(HASH_A))

    assert result == "skipped"
    assert dl.mock_calls == []
    previews = mods.config.observe_previews(plugin)
    assert previews["rename"]["count"] == 1
    assert "重命名种子" in previews["rename"]["samples"][0]
    assert HASH_A[:8] in previews["rename"]["samples"][0]


def test_rename_funnel_executes_when_not_observed(mods, monkeypatch):
    """未观察时重命名漏斗照常进入真实写路径。"""
    plugin = SimpleNamespace(_module_observe_only={"rename": False}, _observe_previews={}, get_data=lambda key: {})
    service = SimpleNamespace(type="qbittorrent", name="QB1", instance=Mock())
    rename_mock = Mock(return_value=True)
    monkeypatch.setattr(mods.rename, "rename_torrent", rename_mock)

    result = mods.rename.rename_candidate(
        plugin, service, mods.rename.build_rename_config({}), _torrent(HASH_A))

    assert result == "renamed"
    rename_mock.assert_called_once()
    assert mods.config.observe_previews(plugin) == {}


def _tag_config():
    return {
        "enable_tag": False,
        "siteprefix": "",
        "enable_media_tag": True,
        "enable_category": False,
        "tracker_mappings": {},
        "custom_site_labels": {},
    }


def test_tag_apply_metadata_blocked_when_observed(mods, monkeypatch):
    """观察模式下标签写入不触达下载器：changed=False、observe_only 标记、登记预览。"""
    plugin = SimpleNamespace(_module_observe_only={"tag": True}, _observe_previews={})
    set_tags = Mock()
    service = SimpleNamespace(type="qbittorrent", name="QB1",
                              instance=SimpleNamespace(set_torrents_tag=set_tags))
    monkeypatch.setattr(mods.tag, "_history_for_hash",
                        Mock(return_value=SimpleNamespace(title="某剧")))
    outcome = mods.tag._apply_metadata(plugin, service, _torrent(HASH_B), _tag_config())

    assert outcome.get("observe_only") is True
    assert outcome.get("changed") is False
    set_tags.assert_not_called()
    previews = mods.config.observe_previews(plugin)
    assert previews["tag"]["count"] == 1
    assert "写入站点标签" in previews["tag"]["samples"][0]


def test_tag_apply_metadata_executes_when_not_observed(mods, monkeypatch):
    """未观察时标签写入照常执行并报告 changed=True。"""
    plugin = SimpleNamespace(_module_observe_only={"tag": False}, _observe_previews={})
    set_tags = Mock()
    service = SimpleNamespace(type="qbittorrent", name="QB1",
                              instance=SimpleNamespace(set_torrents_tag=set_tags))
    monkeypatch.setattr(mods.tag, "_history_for_hash",
                        Mock(return_value=SimpleNamespace(title="某剧")))
    outcome = mods.tag._apply_metadata(plugin, service, _torrent(HASH_B), _tag_config())

    assert outcome.get("changed") is True
    assert outcome.get("observe_only") is None
    set_tags.assert_called_once()
    assert "某剧" in set_tags.call_args.kwargs.get("tags", [])
    assert mods.config.observe_previews(plugin) == {}


def test_retry_failed_renames_observed_skips_without_retry(mods):
    """观察模式下补刀扫描不消耗重试：skipped 计数、不触达下载器、不写记录。"""
    dl = Mock()
    to_service = SimpleNamespace(type="qbittorrent", instance=dl)
    dl.get_torrents.return_value = ([_torrent(HASH_A)], None)
    plugin = SimpleNamespace(
        _rename_enabled=True, _tag_enabled=False,
        _module_observe_only={"rename": True}, _observe_previews={},
        get_data=lambda key: ({HASH_A: {"after_name": "Show.S01E01.2024.mkv",
                                        "success": False}}
                              if key == "rename_records" else None),
        save_data=Mock(),
    )

    summary = mods.rename.retry_failed_renames(plugin, to_service)

    assert summary["skipped"] == 1
    assert summary["attempted"] == 0
    plugin.save_data.assert_not_called()
    assert dl.rename_torrent.call_count == 0
    previews = mods.config.observe_previews(plugin)
    assert previews["rename"]["count"] == 1
    assert "补刀重命名" in previews["rename"]["samples"][0]


def test_retry_failed_renames_unobserved_attempts_retry(mods, monkeypatch):
    """未观察时补刀照常进入尝试路径（attempted 计数、rename_torrent 被调用）。"""
    dl = Mock()
    to_service = SimpleNamespace(type="qbittorrent", instance=dl)
    dl.get_torrents.return_value = ([_torrent(HASH_A)], None)
    plugin = SimpleNamespace(
        _rename_enabled=True, _tag_enabled=False,
        _module_observe_only={"rename": False}, _observe_previews={},
        get_data=lambda key: ({HASH_A: {"after_name": "Show.S01E01.2024.mkv",
                                        "success": False}}
                              if key == "rename_records" else None),
        save_data=Mock(),
    )
    rename_mock = Mock(return_value=False)
    monkeypatch.setattr(mods.rename, "rename_torrent", rename_mock)

    summary = mods.rename.retry_failed_renames(plugin, to_service)

    assert summary["attempted"] == 1
    assert summary["skipped"] == 0
    rename_mock.assert_called_once()
    assert mods.config.observe_previews(plugin) == {}


def test_tag_cleanup_execute_blocked_when_observed(mods):
    """观察模式下人工标签清理直接返回预览回执，不触达下载器。"""
    dl = SimpleNamespace(get_torrents=lambda: ([], None))
    plugin = SimpleNamespace(_module_observe_only={"tag": True}, _observe_previews={},
        _active_temporary_tags=set(),
        _tag_cleanup_status={"scan_id": "s", "downloaders": [{"name": "QB1", "tags": [{"tag": "legacy", "count": 0, "removable": True}]}]},
        service_info=lambda name: SimpleNamespace(type="qbittorrent", instance=dl))
    result = mods.tag.execute_tag_cleanup(plugin, [{"downloader": "QB1", "tag": "legacy"}], "s")

    assert "观察模式" in result["msg"]
    assert result.get("observed") == 1
    assert result.get("removed") == []


def test_transfer_linked_site_tag_respects_observe_mode(mods):
    plugin = SimpleNamespace(_module_observe_only={"tag": True}, _observe_previews={})
    dl = Mock()
    assert mods.tag.tag_torrent(plugin, dl, "qbittorrent", HASH_A, [], []) is None
    assert dl.mock_calls == []
    assert mods.config.observe_previews(plugin)["tag"]["count"] == 1


def test_transmission_rename_tag_preserves_existing_labels(mods):
    dl = Mock()
    result = mods.rename.add_rename_tag(SimpleNamespace(), dl, "transmission", HASH_A, ["keep"], {"add_tag_after_rename": True})
    assert result is True
    assert set(dl.set_torrent_tag.call_args.kwargs["tags"]) == {"keep", mods.rename.RENAME_TAG}


def test_transmission_metadata_merges_labels_as_set(mods, monkeypatch):
    plugin = SimpleNamespace(_module_observe_only={"tag": False})
    dl = Mock()
    dl.get_trackers.return_value = []
    monkeypatch.setattr(mods.tag, "_history_for_hash", lambda *a, **k: SimpleNamespace(title="media"))
    torrent = {**_torrent(HASH_B), "labels": ["keep"]}
    result = mods.tag._apply_metadata(plugin, SimpleNamespace(type="transmission", instance=dl), torrent, _tag_config())
    assert result["changed"] is True
    assert set(dl.set_torrent_tag.call_args.kwargs["tags"]) == {"keep", "media"}



@pytest.mark.parametrize("write_result", [True, False])
def test_transfer_site_tag_preserves_business_and_existing_labels(mods, monkeypatch, write_result):
    plugin = SimpleNamespace(_module_observe_only={"tag": False}, _tracker_mappings={},
                             _custom_site_labels={}, _tag_siteprefix="🏠")
    monkeypatch.setattr(mods.tag, "find_site_by_domain", lambda domain: "PTS")
    monkeypatch.setattr(mods.tag, "get_url_domain", lambda url: "tracker.example")
    dl = Mock()
    dl.set_torrent_tag.return_value = write_result
    result = mods.tag.tag_torrent(plugin, dl, "transmission", HASH_A,
                                  ["收藏", "已转移"], ["https://tracker.example/announce"])
    assert result is write_result
    assert set(dl.set_torrent_tag.call_args.kwargs["tags"]) == {"收藏", "已转移", "🏠PTS"}

def test_path_category_does_not_require_download_history(mods, monkeypatch):
    plugin = SimpleNamespace(_module_observe_only={"tag": False})
    dl = Mock()
    dl.get_trackers.return_value = []
    monkeypatch.setattr(mods.tag, "_history_for_hash", lambda *a, **k: None)
    config = {**_tag_config(), "enable_category": True, "rename_type": True, "path_rename": "/data/show#series"}
    class QbTorrent(dict):
        setCategory = Mock()
    torrent = QbTorrent(_torrent(HASH_B))
    result = mods.tag._apply_metadata(plugin, SimpleNamespace(type="qbittorrent", instance=dl), torrent, config)
    assert result["changed"] is True
    torrent.setCategory.assert_called_once_with(category="series")


@pytest.mark.parametrize("stop_at", ["recognition", "query", "after_first_write"])
def test_rename_scan_old_generation_never_resumes_after_reload(mods, monkeypatch, stop_at):
    from threading import Event
    data = {}
    dl = Mock()
    plugin = SimpleNamespace(
        _event=Event(), _transfer_stop_generation=0, _module_observe_only={"rename": False},
        _rename_config={"enabled": True, "downloader": ["qb"], "add_tag_after_rename": True},
        _rename_exclude_dirs=None, _rename_tv_format="name", _rename_movie_format="name",
        get_data=lambda key: data.get(key, {}), save_data=lambda key, value: data.__setitem__(key, value),
        chain=SimpleNamespace(recognize_media=Mock()),
    )
    plugin.service_info = lambda name: SimpleNamespace(name=name, type="qbittorrent", instance=dl)
    def reload_plugin():
        plugin._event.set()
        plugin._transfer_stop_generation += 1
        plugin._event.clear()  # 新配置已启动，旧调用仍不得写。
    def query():
        if stop_at == "query": reload_plugin()
        return [_torrent(HASH_A), _torrent(HASH_B)], None
    dl.get_torrents.side_effect = query
    def recognize(**kwargs):
        if stop_at == "recognition": reload_plugin()
        return SimpleNamespace(type="movie")
    plugin.chain.recognize_media.side_effect = recognize
    monkeypatch.setattr(mods.rename, "get_download_history_by_hash", lambda h: None)
    monkeypatch.setattr(mods.rename, "format_torrent_name", lambda *a: "New")
    if stop_at == "after_first_write": dl.qbc.torrents_rename.side_effect = lambda **kwargs: reload_plugin()

    result = mods.rename.scan_renames(plugin)

    assert dl.qbc.torrents_rename.call_count == (1 if stop_at == "after_first_write" else 0)
    dl.set_torrents_tag.assert_not_called()
    assert result["failed"] == 0
