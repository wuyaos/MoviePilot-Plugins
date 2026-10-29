"""模块×页签 2x2 矩阵（方案 §6.2 D）。

转移做种页签上的联动语义：关联模块（种子重命名/站点标签）的开关状态决定
联动动作是否发生；模块本体执行/观察边界由 test_observe_boundaries* 覆盖，
门控解析四态由 test_gating 覆盖，本文件不重复。
"""

import importlib.machinery
import importlib.util
import sys
import threading
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

PLUGIN = Path(__file__).resolve().parents[3] / "plugins.v3/downloadmanagerlocal"
SERVICE = PLUGIN / "modules" / "transfer"
UTILS = PLUGIN / "utils"
PREFIX = "app.plugins.downloadmanagerlocal.modules.transfer"


def _module(monkeypatch, name, **attrs):
    """替身模块必须带 __spec__，否则 pytest 回溯渲染会 INTERNALERROR 掩盖真实失败。

    __path__ 不 pop、随 attrs 进 __dict__：相对导入的包判定读该属性，
    pop 后漏赋会把桩变成非包，触发 "is not a package" 导入失败。
    """
    result = types.ModuleType(name)
    result.__spec__ = importlib.machinery.ModuleSpec(
        name, None, is_package="__path__" in attrs)
    result.__dict__.update(attrs)
    monkeypatch.setitem(sys.modules, name, result)
    return result


def _load_real(monkeypatch, name):
    spec = importlib.util.spec_from_file_location(PREFIX + "." + name, SERVICE / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, result)
    spec.loader.exec_module(result)
    return result


def _load_util(monkeypatch, name):
    """按真实路径加载 utils 子模块，供 transfer/service 的相对导入使用。"""
    full = "app.plugins.downloadmanagerlocal.utils." + name
    spec = importlib.util.spec_from_file_location(full, UTILS / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, full, result)
    spec.loader.exec_module(result)
    return result


@pytest.fixture
def tt(monkeypatch):
    """transfer_tasks 真模块。"""
    _module(monkeypatch, "app")
    _module(monkeypatch, "app.sdk")
    _module(monkeypatch, "app.sdk.logging", logger=Mock())
    return _load_real(monkeypatch, "tasks")


@pytest.fixture
def pe(monkeypatch):
    """payload_export 真模块。"""
    _module(monkeypatch, "app")
    _module(monkeypatch, "app.sdk")
    _module(monkeypatch, "app.sdk.logging", logger=Mock())
    return _load_real(monkeypatch, "payload_export")


@pytest.fixture
def svc(monkeypatch):
    """transfer.py 真模块，同级重依赖存根化。"""
    _module(monkeypatch, "app")
    _module(monkeypatch, "app.sdk")
    _module(monkeypatch, "app.sdk.logging", logger=Mock())
    _module(monkeypatch, "app.schemas", ServiceInfo=Mock())
    _module(monkeypatch, "app.schemas.types", MessageType=Mock())
    _module(monkeypatch, "app.sdk.config", settings=Mock())
    _module(monkeypatch, "app.plugins")
    _module(monkeypatch, "app.plugins.downloadmanagerlocal")
    _module(monkeypatch, "app.plugins.downloadmanagerlocal.modules",
            __path__=[str(PLUGIN / "modules")])
    _module(monkeypatch, PREFIX, __path__=[str(SERVICE)])
    _module(monkeypatch, "app.plugins.downloadmanagerlocal.adapter", __path__=[])
    _module(monkeypatch, "app.plugins.downloadmanagerlocal.adapter.moviepilot",
            is_downloader_type=Mock(return_value=False))
    _module(monkeypatch, "app.plugins.downloadmanagerlocal.utils", __path__=[str(UTILS)])
    _module(monkeypatch, "app.plugins.downloadmanagerlocal.utils.name_cleaner",
            is_dirty_renamed_torrent_name=Mock(return_value=False))
    # 适配层按真实实现加载：转移管线的跨类型状态判定依赖真实语义。
    _load_util(monkeypatch, "torrent_adapter")
    _module(monkeypatch, "app.plugins.downloadmanagerlocal.model", __path__=[])
    _module(monkeypatch, "app.plugins.downloadmanagerlocal.model.state",
            SEED_RECHECK_QUEUE_KEY="queue", record_transfer_success=Mock())
    # 真加载轻模块，供 transfer.py 的 from-import 使用
    _load_real(monkeypatch, "tasks")
    _load_real(monkeypatch, "payload_export")
    _module(monkeypatch, PREFIX + ".recheck",
            _queue_lock=Mock(), _queue_key=Mock(return_value="queue"),
            load_seed_recheck_queue=Mock(return_value={}),
            save_seed_recheck_queue=Mock(),
            ensure_seed_recheck_worker=Mock(), seed_is_checking=Mock(return_value=False),
            seed_is_ready=Mock(return_value=True), seed_is_error=Mock(return_value=False),
            seed_is_timeout=Mock(return_value=False))
    # hr.guard 显式桩：pipeline/service 的导入链需要它；依赖文件序的
    # namespace-package 侥幸会在全量运行时被前序文件残留的空 hr 包破坏。
    guard = Mock()
    guard.HrGuard = Mock()
    _module(monkeypatch, "app.plugins.downloadmanagerlocal.modules.hr",
            __path__=[str(PLUGIN / "modules" / "hr")])
    _module(monkeypatch, "app.plugins.downloadmanagerlocal.modules.hr.guard",
            HrGuard=guard.HrGuard, SKIP_PATH_TRANSFER_SOURCE="transfer_source")
    _module(monkeypatch, "app.plugins.downloadmanagerlocal.modules.rename.service",
            _get_torrent_content_name=Mock(return_value=""),
            build_rename_config=Mock(return_value={"enabled": True, "downloader": []}),
            resolve_retry_original_name=Mock(return_value=""))
    _module(monkeypatch, "app.plugins.downloadmanagerlocal.modules.sitetag.service",
            create_temporary_tag=Mock(), forget_temporary_tag=Mock(),
            release_temporary_tag=Mock())
    return _load_real(monkeypatch, "service")


def _post_plugin(rename_enabled, tag_enabled, transfer_rename_enabled=True):
    """post_transfer_process 所需的最小插件快照（联动开关即矩阵变量）。"""
    return SimpleNamespace(
        _transfer_stop_generation=0,
        _event=threading.Event(),
        _transfer_rename_enabled=transfer_rename_enabled,
        _rename_enabled=rename_enabled,
        _tag_enabled=tag_enabled,
        _rename_torrent=Mock(),
        _tag_torrent=Mock(return_value=True),
    )


def _post_target():
    dl = Mock()
    dl.get_torrents.return_value = ([{
        "hash": "h1", "name": "种子A", "tags": "", "category": "",
        "save_path": "/downloads", "trackers": [],
    }], None)
    return SimpleNamespace(name="目标下载器", type="qbittorrent", instance=dl)


def _run_post(service, plugin):
    target = _post_target()
    ok = service.post_transfer_process(plugin, target, "h1")
    return ok, plugin, target


def test_transfer_pane_rename_disabled_skips_followup(svc):
    """关联模块关闭：rename 关 → 转移后补刀不发生，站点标签联动不受影响。"""
    plugin = _post_plugin(rename_enabled=False, tag_enabled=True)
    ok, plugin, _ = _run_post(svc, plugin)
    assert ok is True
    plugin._rename_torrent.assert_not_called()
    plugin._tag_torrent.assert_called_once()


def test_transfer_pane_rename_enabled_runs_followup(svc):
    """关联模块开启：rename 开 → 转移后补刀按快照执行。"""
    plugin = _post_plugin(rename_enabled=True, tag_enabled=False)
    ok, plugin, _ = _run_post(svc, plugin)
    assert ok is True
    plugin._rename_torrent.assert_called_once()
    plugin._tag_torrent.assert_not_called()


def test_transfer_pane_both_enabled_runs_both(svc):
    """关联模块全开：改名与标签联动互不阻断，各自执行一次。"""
    plugin = _post_plugin(rename_enabled=True, tag_enabled=True)
    ok, plugin, _ = _run_post(svc, plugin)
    assert ok is True
    plugin._rename_torrent.assert_called_once()
    plugin._tag_torrent.assert_called_once()


def test_transfer_pane_transfer_rename_off_gates_followup(svc):
    """页签开关优先：transfer_rename_enabled=False 时即使 rename 开也不补刀。"""
    plugin = _post_plugin(rename_enabled=True, tag_enabled=False,
                          transfer_rename_enabled=False)
    ok, plugin, _ = _run_post(svc, plugin)
    assert ok is True
    plugin._rename_torrent.assert_not_called()


def test_transfer_pane_retry_followup_skipped_when_rename_disabled(svc):
    """一键补刀与转移后补刀同一门控：rename 关 → 明确回执跳过。"""
    plugin = _post_plugin(rename_enabled=False, tag_enabled=True)
    result = svc.retry_pending_renames(plugin)
    assert result["code"] == 1
    assert "未启用" in result["msg"]
    assert result["total"] == 0


def test_transfer_pane_retry_followup_proceeds_when_rename_enabled(svc):
    """一键补刀在 rename 开时走过门控（无下载器配置走到下一层回执）。"""
    plugin = _post_plugin(rename_enabled=True, tag_enabled=False)
    result = svc.retry_pending_renames(plugin)
    assert result["code"] == 1
    assert result["msg"] != "种子重命名模块未启用，已跳过补刀"
