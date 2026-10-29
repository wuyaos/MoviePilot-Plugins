# -*- coding: utf-8 -*-
"""自动删种 run_cycle 观察分支隔离测试（阶段三 P3-3 预览与状态隔离）。

运行：micromamba 环境的 pytest tests/v3/downloadmanagerlocal/test_observe_isolation_autoremove.py -q

锁定语义（与 docs/downloadmanagerlocal-optimization-plan.md §5 对齐）：
1. 观察期 run_cycle 不调用 _execute（不暂停/不删除、不查 H&R 保护）；
2. 观察期落盘的 remover_state 记录观察结果本身：observe_only=True、候选数保留、
   paused/deleted/deleted_files/failed 全为 0 —— 即不增加成功数；
3. _collect 与 _execute 以替身注入，聚焦 run_cycle 的分支与落盘契约。
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


@pytest.fixture
def autoremove(monkeypatch):
    """加载真实 AutoRemoveService 与真实 utils.config，扫描器/守卫用替身。"""

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
    module("app.sdk.logging", logger=Mock())
    module("app.sdk.config", settings=Mock())
    module("app.schemas")
    module("app.schemas.types", MessageType=Mock())
    module("app.modules")
    module("app.modules.qbittorrent", Qbittorrent=type("Qbittorrent", (), {}))
    module("app.modules.transmission", Transmission=type("Transmission", (), {}))
    module("app.plugins")
    module(PREFIX, __path__=[str(PLUGIN)])

    # hr.guard 替身：观察分支不触达 H&R 查询，仅需可导入
    module(PREFIX + ".modules", __path__=[str(PLUGIN / "modules")])
    module(PREFIX + ".modules.hr", __path__=[str(PLUGIN / "modules/hr")])
    module(PREFIX + ".modules.hr.constants",
           build_hr_config_defaults=Mock(return_value={}))
    guard_stub = module(
        PREFIX + ".modules.hr.guard",
        HrGuard=Mock, SKIP_PATH_AUTO_REMOVE="auto_remove")
    # 扫描器/规则解析替身：run_cycle 观察分支不依赖其行为
    module(PREFIX + ".modules.autoremove", __path__=[str(PLUGIN / "modules/autoremove")])
    module(PREFIX + ".modules.autoremove.rules", parse_remover_config=Mock())
    scanner = module(
        PREFIX + ".modules.autoremove.scanner",
        build_snapshot=Mock(), downloader_type=Mock(),
        read_torrents=Mock(), torrent_hash=Mock())

    def stub_constants(name, **attrs):
        return module(name, **attrs)

    stub_constants(PREFIX + ".modules.failclean.constants",
                   build_failclean_config_defaults=Mock(return_value={}))
    module(PREFIX + ".modules.rename.service",
           build_rename_flat_defaults=Mock(return_value={}))
    module(PREFIX + ".modules.sitetag.service", DEFAULT_TAG_CONFIG={
        "interval_cron": "0 3 * * *", "enable_media_tag": False,
        "enable_tag": True, "enable_category": False, "enable_del_tags": False,
        "downloaders": [], "all_cat": [], "all_cat_rename": [],
        "rename_type": "movie", "path_rename": False, "catprefix": "",
    })

    module(PREFIX + ".adapter", __path__=[str(PLUGIN / "adapter")])
    module(PREFIX + ".utils", __path__=[str(PLUGIN / "utils")])
    utils_config = load("utils/config.py", ".config", PREFIX + ".utils")

    ar_pkg = PREFIX + ".modules.autoremove"
    ar_constants = load("modules/autoremove/constants.py", ".constants", ar_pkg)
    ar_models = load("modules/autoremove/models.py", ".models", ar_pkg)
    ar_criteria = load("modules/autoremove/criteria.py", ".criteria", ar_pkg)
    service = load("modules/autoremove/service.py", ".service", ar_pkg)
    return SimpleNamespace(service=service, scanner=scanner,
                           config=utils_config, constants=ar_constants,
                           models=ar_models, criteria=ar_criteria)


def _observe_result(candidates=3):
    """构造 _collect 返回的观察期结果（候选>0、执行计数全 0）。"""
    return {
        "trigger": "test",
        "enabled": True,
        "observe_only": True,
        "action": "delete",
        "downloaders": [],
        "candidates": candidates,
        "paused": 0,
        "deleted": 0,
        "deleted_files": 0,
        "skipped_protected": 0,
        "skipped_missing": 0,
        "failed": 0,
        "config_error": "",
        "candidate_list": [
            {"downloader": "QB1", "name": f"seed-{i}", "size": 1024}
            for i in range(candidates)
        ],
        "details": [],
    }


def test_run_cycle_observed_records_status_without_execute(autoremove):
    """观察期：不执行任何下载器动作，落盘状态记录观察结果且成功计数全 0。"""
    plugin = SimpleNamespace(
        get_data=Mock(return_value=None), save_data=Mock(), post_message=Mock())
    service = autoremove.service.AutoRemoveService(plugin)
    service._config = SimpleNamespace(enabled=True, action="delete",
                                      downloaders=[], cron="", notify=False)
    service._observe_only = True
    service._config_error = ""

    result = _observe_result(candidates=3)
    service._collect = Mock(return_value=SimpleNamespace(
        result=result, candidates={}, conditions=None))
    service._execute = Mock()

    out = service.run_cycle("test")

    assert out is result
    assert out["observe_only"] is True
    service._execute.assert_not_called()
    plugin.save_data.assert_called_once()
    state_key, status = plugin.save_data.call_args.args
    assert state_key == "remover_state"
    assert status["observe_only"] is True
    assert status["candidates"] == 3
    assert status["paused"] == 0
    assert status["deleted"] == 0
    assert status["deleted_files"] == 0
    assert status["failed"] == 0


def test_run_cycle_unobserved_executes(autoremove):
    """未观察时照常进入执行路径（_execute 被调用）。"""
    plugin = SimpleNamespace(
        get_data=Mock(return_value=None), save_data=Mock(), post_message=Mock())
    service = autoremove.service.AutoRemoveService(plugin)
    service._config = SimpleNamespace(enabled=True, action="delete",
                                      downloaders=[], cron="", notify=False)
    service._observe_only = False
    service._config_error = ""

    result = _observe_result(candidates=0)
    result["observe_only"] = False
    service._collect = Mock(return_value=SimpleNamespace(
        result=result, candidates={}, conditions=None))
    service._execute = Mock()

    out = service.run_cycle("test")

    assert out is result
    assert out["observe_only"] is False
    service._execute.assert_called_once()
