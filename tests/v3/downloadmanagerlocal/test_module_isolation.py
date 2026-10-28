"""模块独立性回归（2026-10-28，Goal: 单模块故障不拖垮其它模块）。

三个隔离点：
1. core/lifecycle.py::_init_service_isolated —— hr/autoremove/failclean 任一
   init_module 抛异常只禁用该模块，初始化链继续；
2. core/lifecycle.py::stop_plugin_service —— 服务为 None（隔离禁用态）可安全停止；
3. modules/transfer/events.py::_event_step —— download_added 事件的各分支
   （站点标签/重命名补刀/H&R/限速唤醒）逐个隔离，单个分支炸不阻断后续分支。

加载方式仿 test_transfer_pipeline：把插件根挂为带 __path__ 的假包，
真实模块经 spec_from_file_location 挂到假包命名空间下，相对导入可解析。
"""

from __future__ import annotations

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


class _StubModule(types.ModuleType):
    """任意未知属性返回 Mock，避免为每个被隔离依赖枚举符号。"""

    def __getattr__(self, item):
        if item.startswith("__"):
            raise AttributeError(item)
        return Mock(name=f"{self.__name__}.{item}")


def _register_package(monkeypatch, name, path=None, **attrs):
    result = _StubModule(name) if path is None else types.ModuleType(name)
    result.__spec__ = importlib.machinery.ModuleSpec(
        name, None, is_package=path is not None
    )
    if path is not None:
        result.__path__ = path
    result.__dict__.update(attrs)
    monkeypatch.setitem(sys.modules, name, result)
    return result


@pytest.fixture
def env(monkeypatch):
    """最小宿主替身 + 真实插件包结构，返回 load(relpath) 加载器。"""
    for name in ("app", "app.sdk", "app.plugins"):
        _register_package(monkeypatch, name)
    _register_package(monkeypatch, PREFIX, __path__=[str(PLUGIN)])
    _register_package(monkeypatch, "app.sdk.logging", logger=Mock())
    _register_package(monkeypatch, "app.sdk.config", settings=Mock())
    _register_package(monkeypatch, "app.model", __path__=[str(PLUGIN / "model")])
    _register_package(monkeypatch, "app.modules", __path__=[])
    for msub in ("qbittorrent", "transmission"):
        _register_package(monkeypatch, f"app.modules.{msub}")
    for sub in ("utils", "core", "modules", "model"):
        _register_package(monkeypatch, f"{PREFIX}.{sub}", __path__=[str(PLUGIN / sub)])
    # lifecycle/events 的深层依赖在隔离测试中全部替换为 Mock，避免整树加载
    for deep in (
        f"{PREFIX}.core.config",
        f"{PREFIX}.utils.config",
        f"{PREFIX}.modules.autoremove.service",
        f"{PREFIX}.modules.transfer.events",
        f"{PREFIX}.modules.failclean.service",
        f"{PREFIX}.modules.hr.service",
        f"{PREFIX}.modules.transfer.recheck",
        f"{PREFIX}.modules.transfer.service",
        f"{PREFIX}.modules.uploadlimit.worker",
        f"{PREFIX}.modules.uploadlimit.service",
        f"{PREFIX}.model.state",
        f"{PREFIX}.modules.hr.models",
        f"{PREFIX}.modules.rename.events",
        f"{PREFIX}.modules.sitetag.service",
        f"{PREFIX}.modules.transfer.tasks",
        f"{PREFIX}.modules.rename.service",
    ):
        _register_package(monkeypatch, deep)
    # events.py 通过 app.modules.hr.models 引用（三段相对导入解析到宿主 app.modules）
    _register_package(monkeypatch, "app.modules.hr", __path__=[])
    _register_package(monkeypatch, "app.modules.hr.constants")
    _register_package(monkeypatch, "app.modules.hr.models")

    def load(relpath: str, name: str = ""):
        # 模块名必须完整反映相对路径（core.lifecycle），否则相对导入会解析偏离
        dotted = ".".join(Path(relpath).with_suffix("").parts)
        spec = importlib.util.spec_from_file_location(
            f"{PREFIX}.{dotted}", PLUGIN / relpath
        )
        result = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, spec.name, result)
        spec.loader.exec_module(result)
        return result

    return load


def test_init_service_isolated_disables_and_continues(env):
    lifecycle = env("core/lifecycle.py")
    calls = []

    class Boom:
        def __init__(self, plugin):
            pass

        def init_module(self, config):
            calls.append("boom")
            raise RuntimeError("未配置下载器")

    class Ok:
        def __init__(self, plugin):
            pass

        def init_module(self, config):
            calls.append("ok")

    lifecycle.HrService = Boom
    lifecycle.AutoRemoveService = Ok
    lifecycle.FailCleanService = Ok
    # 开关注册表在隔离测试里被替身化，这里显式给出真实口径
    lifecycle.MODULE_SWITCHES = {"hr": ("hr_enabled", "_hr_enabled")}
    lifecycle.module_switch_on = lambda config, module: bool(
        config.get(lifecycle.MODULE_SWITCHES[module][0], False)
    )

    written = []
    plugin = SimpleNamespace(update_config=lambda config: written.append(dict(config)))
    config = {"enabled": True, "hr_enabled": True}

    hr = lifecycle._init_service_isolated(plugin, "H&R", "hr", Boom, config)
    ok = lifecycle._init_service_isolated(plugin, "自动删种", "autoremove", Ok, config)

    assert hr is None, "失败的模块应返回 None"
    assert ok is not None, "后续模块不受失败影响"
    assert calls == ["boom", "ok"], "后续模块仍被初始化"
    assert config["hr_enabled"] is False, "失败模块的开关被关闭"
    assert written and written[-1]["hr_enabled"] is False, "关闭结果已落盘"


def test_init_service_isolated_leaves_disabled_module_switch_untouched(env):
    """模块本来就没开的时候初始化失败，不应改动配置（避免无谓落盘）。"""
    lifecycle = env("core/lifecycle.py")

    class Boom:
        def __init__(self, plugin):
            pass

        def init_module(self, config):
            raise RuntimeError("未配置下载器")

    written = []
    plugin = SimpleNamespace(update_config=lambda config: written.append(dict(config)))
    config = {"enabled": True, "hr_enabled": False}
    lifecycle.MODULE_SWITCHES = {"hr": ("hr_enabled", "_hr_enabled")}
    lifecycle.module_switch_on = lambda config, module: False

    assert lifecycle._init_service_isolated(plugin, "H&R", "hr", Boom, config) is None
    assert written == [], "开关本来就是关的，不应写回配置"


def test_event_step_isolates_failing_branch(env):
    events = env("modules/transfer/events.py")
    ran = []

    def bad(plugin, event):
        raise ValueError("站点标签炸了")

    def good(plugin, event):
        ran.append("good")

    # bad 抛异常不向外传播
    events._event_step(SimpleNamespace(), "坏分支", bad, object())
    events._event_step(SimpleNamespace(), "好分支", good, object())
    assert ran == ["good"], "后续分支继续执行"


def test_stop_plugin_service_tolerates_none_services(env):
    lifecycle = env("core/lifecycle.py")
    plugin = SimpleNamespace(
        _transfer_stop_generation=0,
        _event=None,
        _scheduler=None,
        _hr_service=None,
        _autoremove_service=None,
        _failclean_service=None,
    )
    # 不抛异常即通过（服务为 None 是隔离后的合法状态）
    lifecycle.stop_plugin_service(plugin)


def test_scheduler_services_isolates_failing_module(env):
    """单个模块构造定时任务失败，只丢该模块的声明，其余模块照常注册。"""
    scheduler = env("core/scheduler.py")
    plugin = SimpleNamespace()

    scheduler._build_transfer_fallback_services = lambda p: [
        {"id": "TorrentTransferFallback"}
    ]

    def boom(_plugin):
        raise AttributeError("config.cron 缺失")

    scheduler._build_hr_services = boom
    scheduler._build_autoremove_services = lambda p: [{"id": "AutoRemove"}]
    scheduler._build_failclean_services = lambda p: []
    scheduler._build_site_tag_services = lambda p: [{"id": "SiteTagHistory"}]
    scheduler._build_rename_services = lambda p: []

    services = scheduler.build_plugin_services(plugin)

    assert [item["id"] for item in services] == [
        "TorrentTransferFallback",
        "AutoRemove",
        "SiteTagHistory",
    ], "坏模块的声明被丢弃，其余模块的正常注册"
