# -*- coding: utf-8 -*-
"""重命名幂等守卫测试。

运行：micromamba 环境的 pytest tests/v3/downloadmanagerlocal/test_rename_idempotent.py -q

锁定语义（对应线上「FX战士久留美」被改名两次的问题）：
1. 当前名称已等于本插件上一次成功改名的结果时，重命名漏斗按 skipped 返回且不调用下载器；
2. 同一 hash 但当前名称与记录不一致（例如被其它工具改过）时仍照常重命名；
3. 无记录或记录 success=False 时照常重命名；
4. 手动补刀（直接调用 rename_torrent）不受该守卫限制。

宿主（app / 下载器 / 媒体识别 / 历史库）全部替身；加载真实 modules/rename/service.py。
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
RENAMED = "Show (2024) - S01E01 - Show.S01E01.2024.mkv"


@pytest.fixture
def mods(monkeypatch):
    """加载真实 rename 服务，宿主全部替身。"""

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
        spec = importlib.util.spec_from_file_location(pkg + name, PLUGIN / relpath)
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

    return SimpleNamespace(
        rename=load("modules/rename/service.py", ".rename.service", PREFIX + ".modules"))


def _plugin(records=None, **kwargs):
    """构造带 rename_records 的最小插件替身。"""
    data = {"rename_records": records if records is not None else {}}
    return SimpleNamespace(
        _module_observe_only={"rename": False},
        _observe_previews={},
        get_data=lambda key: data.get(key, {}),
        save_data=lambda key, value: data.__setitem__(key, value),
        **kwargs,
    )


def _torrent(torrent_hash, name):
    return {
        "hash": torrent_hash,
        "name": name,
        "save_path": "/data/show/",
        "labels": [],
    }


def test_skips_when_current_name_is_recorded_result(mods, monkeypatch):
    """当前名称已是本插件重命名结果 → skipped，下载器零调用。"""
    plugin = _plugin({HASH_A: {"after_name": RENAMED, "success": True}})
    dl = Mock()
    service = SimpleNamespace(type="qbittorrent", name="QB1", instance=dl)
    rename_mock = Mock(return_value=True)
    monkeypatch.setattr(mods.rename, "rename_torrent", rename_mock)

    result = mods.rename.rename_candidate(
        plugin, service, mods.rename.build_rename_config({}), _torrent(HASH_A, RENAMED))

    assert result == "skipped"
    assert rename_mock.mock_calls == []


def test_executes_when_recorded_name_differs(mods, monkeypatch):
    """记录存在但当前名称不同（外部改名）→ 仍执行重命名。"""
    plugin = _plugin({HASH_A: {"after_name": "Other.Name.mkv", "success": True}})
    service = SimpleNamespace(type="qbittorrent", name="QB1", instance=Mock())
    rename_mock = Mock(return_value=True)
    monkeypatch.setattr(mods.rename, "rename_torrent", rename_mock)

    result = mods.rename.rename_candidate(
        plugin, service, mods.rename.build_rename_config({}), _torrent(HASH_A, RENAMED))

    assert result == "renamed"
    assert rename_mock.call_count == 1


def test_executes_when_no_record(mods, monkeypatch):
    """无记录 → 照常重命名。"""
    plugin = _plugin()
    service = SimpleNamespace(type="qbittorrent", name="QB1", instance=Mock())
    rename_mock = Mock(return_value=True)
    monkeypatch.setattr(mods.rename, "rename_torrent", rename_mock)

    result = mods.rename.rename_candidate(
        plugin, service, mods.rename.build_rename_config({}), _torrent(HASH_A, RENAMED))

    assert result == "renamed"
    assert rename_mock.call_count == 1


def test_executes_when_record_not_success(mods, monkeypatch):
    """记录 success=False（上次失败）→ 不算已重命名。"""
    plugin = _plugin({HASH_A: {"after_name": RENAMED, "success": False}})
    service = SimpleNamespace(type="qbittorrent", name="QB1", instance=Mock())
    rename_mock = Mock(return_value=True)
    monkeypatch.setattr(mods.rename, "rename_torrent", rename_mock)

    result = mods.rename.rename_candidate(
        plugin, service, mods.rename.build_rename_config({}), _torrent(HASH_A, RENAMED))

    assert result == "renamed"
    assert rename_mock.call_count == 1


def test_guard_only_lives_in_rename_candidate(mods, monkeypatch):
    """守卫只在重命名漏斗生效：直接调用 rename_torrent（手动补刀）不读该判断。"""
    guard = Mock(return_value=True)
    monkeypatch.setattr(mods.rename, "_is_already_renamed", guard)
    plugin = _plugin(
        {HASH_A: {"after_name": RENAMED, "success": True}},
        _rename_config={},
        _rename_exclude_dirs=None,
        _rename_movie_format=None,
        _rename_tv_format=None,
    )
    dl = Mock()

    mods.rename.rename_torrent(plugin, dl, "qbittorrent", HASH_A, RENAMED, "/data/show/")

    assert guard.call_count == 0
