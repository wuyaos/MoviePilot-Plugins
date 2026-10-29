"""模块独立性回归（2026-10-28，Goal: 单模块故障不拖垮其它模块）。

三个隔离点：
1. core/lifecycle.py::_init_service_isolated —— hr/autoremove/failclean 任一
   构造或 init_module 抛异常只标记该模块运行异常（plugin._module_faults），不改插件
   总开关、不落盘改写用户开关，初始化链继续；
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
        f"{PREFIX}.modules.hr.guard",
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


def _stub_fault_recording(lifecycle):
    """把隔离测试的异常记录换成列表记录器（真实实现由 test_gating.py 覆盖）。"""
    faults = []
    lifecycle.record_module_fault = lambda plugin, module, reason: faults.append((module, str(reason)))
    lifecycle.clear_module_fault = lambda plugin, module: None
    return faults



def _stub_module_faults(scheduler, faults=None):
    """隔离测试里 utils.config 被整体替换为 Mock，这里换成可控的故障快照。"""
    scheduler.module_faults = lambda plugin: dict(faults or {})

def test_init_service_isolated_marks_fault_and_continues(env):
    """P2-2：模块初始化失败只标记该模块运行异常，不关插件总开关、不落盘改写用户开关。"""
    lifecycle = env("core/lifecycle.py")
    calls = []
    faults = _stub_fault_recording(lifecycle)

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

    written = []
    plugin = SimpleNamespace(update_config=lambda config: written.append(dict(config)))
    config = {"enabled": True, "hr_enabled": True}

    hr = lifecycle._init_service_isolated(plugin, "H&R", "hr", Boom, config)
    ok = lifecycle._init_service_isolated(plugin, "自动删种", "autoremove", Ok, config)

    assert hr is None, "失败的模块应返回 None"
    assert ok is not None, "后续模块不受失败影响"
    assert calls == ["boom", "ok"], "后续模块仍被初始化"
    assert faults == [("hr", "未配置下载器")], "只标记该模块运行异常"
    assert config["hr_enabled"] is True, "用户模块开关不被改写"
    assert written == [], "不落盘改写配置"

def test_init_service_isolated_leaves_disabled_module_switch_untouched(env):
    """模块本来就没开的时候初始化失败，同样只记运行异常、不写回配置。"""
    lifecycle = env("core/lifecycle.py")
    faults = _stub_fault_recording(lifecycle)

    class Boom:
        def __init__(self, plugin):
            pass

        def init_module(self, config):
            raise RuntimeError("未配置下载器")

    written = []
    plugin = SimpleNamespace(update_config=lambda config: written.append(dict(config)))
    config = {"enabled": True, "hr_enabled": False}

    assert lifecycle._init_service_isolated(plugin, "H&R", "hr", Boom, config) is None
    assert written == [], "开关本来就是关的，不应写回配置"
    assert faults == [("hr", "未配置下载器")]

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
    _stub_module_faults(scheduler)
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


def test_init_service_isolated_isolates_constructor_failure(env):
    """P2-3：service 构造期异常也纳入模块边界，后续模块照常初始化。"""
    lifecycle = env("core/lifecycle.py")
    faults = _stub_fault_recording(lifecycle)

    class BoomCtor:
        def __init__(self, plugin):
            raise RuntimeError("构造期缺少依赖")

    class Ok:
        def __init__(self, plugin):
            pass

        def init_module(self, config):
            pass

    plugin = SimpleNamespace()
    config = {"enabled": True}

    assert lifecycle._init_service_isolated(plugin, "H&R", "hr", BoomCtor, config) is None
    assert lifecycle._init_service_isolated(plugin, "自动删种", "autoremove", Ok, config) is not None
    assert faults == [("hr", "构造期缺少依赖")]


def test_mark_transfer_config_invalid_keeps_plugin_switch(env):
    """P2-2：转移配置错误只标记运行异常，不关插件总开关、不落盘改写配置。"""
    lifecycle = env("core/lifecycle.py")
    faults = _stub_fault_recording(lifecycle)
    written = []
    plugin = SimpleNamespace(
        _enabled=True, update_config=lambda config: written.append(dict(config))
    )

    lifecycle._mark_transfer_config_invalid(plugin)

    assert plugin._enabled is True, "插件总开关不被改写"
    assert written == [], "不写回用户配置"
    assert faults and faults[0][0] == "transfer"
    assert "转移配置" in faults[0][1]


def test_init_upload_limit_isolated_records_fault(env):
    """P2-2：上传限速初始化失败只标记该模块，不向外抛异常。"""
    lifecycle = env("core/lifecycle.py")
    faults = _stub_fault_recording(lifecycle)
    lifecycle.clear_module_fault = lambda plugin, module: None

    def boom(_plugin):
        raise RuntimeError("状态读取失败")

    lifecycle.load_upload_limit_state = boom
    lifecycle.is_upload_limit_active = lambda _plugin: False

    lifecycle._init_upload_limit_isolated(SimpleNamespace())

    assert faults == [("upload_limit", "状态读取失败")]


def test_init_upload_limit_isolated_clears_fault_on_success(env):
    """P2-2：上传限速初始化成功时清除历史运行异常标记。"""
    lifecycle = env("core/lifecycle.py")
    cleared = []
    lifecycle.record_module_fault = lambda plugin, module, reason: None
    lifecycle.clear_module_fault = lambda plugin, module: cleared.append(module)
    lifecycle.load_upload_limit_state = lambda _plugin: {}
    lifecycle.is_upload_limit_active = lambda _plugin: False

    lifecycle._init_upload_limit_isolated(SimpleNamespace())

    assert cleared == ["upload_limit"]


def test_stop_plugin_service_isolates_failing_stop(env):
    """P2-3：单个模块停止失败不阻断其余模块的后台组件停止。"""
    lifecycle = env("core/lifecycle.py")
    calls = []

    def boom(_plugin):
        calls.append("hr")
        raise RuntimeError("H&R 停止失败")

    lifecycle._stop_hr_service = boom
    lifecycle._stop_autoremove_service = lambda _plugin: calls.append("autoremove")
    lifecycle._stop_failclean_service = lambda _plugin: calls.append("failclean")
    lifecycle.stop_seed_recheck_worker = lambda _plugin: calls.append("recheck")
    lifecycle.stop_upload_limit_worker = lambda _plugin: calls.append("upload_limit")
    plugin = SimpleNamespace(
        _transfer_stop_generation=0,
        _event=None,
        _scheduler=None,
        _hr_service=None,
        _autoremove_service=None,
        _failclean_service=None,
    )

    lifecycle.stop_plugin_service(plugin)

    assert calls == ["recheck", "hr", "autoremove", "failclean", "upload_limit"], (
        "H&R 停止抛异常后，其余模块仍逐个执行停止"
    )


def test_scheduler_skips_faulted_module_declaration(env):
    """P2-3：已标记运行异常的模块不再注册定时任务声明，其余模块照常注册。"""
    scheduler = env("core/scheduler.py")
    _stub_module_faults(scheduler, {"hr": "初始化失败"})
    plugin = SimpleNamespace()

    scheduler._build_transfer_fallback_services = lambda p: [{"id": "TorrentTransferFallback"}]
    scheduler._build_hr_services = lambda p: [{"id": "HitAndRunCheck"}]
    scheduler._build_autoremove_services = lambda p: [{"id": "AutoRemove"}]
    scheduler._build_failclean_services = lambda p: []
    scheduler._build_site_tag_services = lambda p: []
    scheduler._build_rename_services = lambda p: []

    services = scheduler.build_plugin_services(plugin)

    assert [item["id"] for item in services] == [
        "TorrentTransferFallback",
        "AutoRemove",
    ], "故障模块的声明被跳过，其余模块正常注册"



class _GuardRecorder:
    """记录保护预期登记的替身闸门。"""

    def __init__(self):
        self.calls = []

    def expect(self, *, enabled):
        self.calls.append(enabled)


def test_hr_protection_intent_follows_module_gate(env, monkeypatch):
    """P2-4：H&R 模块关闭时撤销保护预期；启用但服务不可用时登记无法确认。"""
    lifecycle = env("core/lifecycle.py")
    guard = _GuardRecorder()
    monkeypatch.setattr(lifecycle, "get_guard", lambda: guard)

    closed = SimpleNamespace(_hr_enabled=False, _hr_service=None)
    lifecycle._sync_hr_guard_intent(closed, {"hr_protection_enabled": True})
    assert guard.calls == [False], "模块关闭必须撤销保护预期，不得继续拦截删除"

    broken = SimpleNamespace(_hr_enabled=True, _hr_service=None)
    lifecycle._sync_hr_guard_intent(broken, {"hr_protection_enabled": True})
    assert guard.calls[-1] is True, "服务不可用时登记保护预期，危险删除保守跳过"


def test_hr_protection_intent_respects_protection_switch(env, monkeypatch):
    """保护开关关闭时登记 enabled=False，关闭的保护不得拦截删除。"""
    lifecycle = env("core/lifecycle.py")
    guard = _GuardRecorder()
    monkeypatch.setattr(lifecycle, "get_guard", lambda: guard)

    plugin = SimpleNamespace(_hr_enabled=True, _hr_service=None)
    lifecycle._sync_hr_guard_intent(plugin, {"hr_protection_enabled": False})

    assert guard.calls == [False]


def test_hr_protection_intent_defers_to_running_service(env, monkeypatch):
    """服务已在运行时由 _refresh_guard 写快照，生命周期不重复覆盖保护预期。"""
    lifecycle = env("core/lifecycle.py")
    guard = _GuardRecorder()
    monkeypatch.setattr(lifecycle, "get_guard", lambda: guard)

    plugin = SimpleNamespace(_hr_enabled=True, _hr_service=object())
    lifecycle._sync_hr_guard_intent(plugin, {"hr_protection_enabled": True})

    assert guard.calls == []


def test_diagnostics_reports_module_fault_as_error(env):
    """P2-5：模块运行异常在诊断项里是 error，页面据此区分「关闭」与「故障」。"""
    service = env("modules/diagnostics/service.py")
    service.module_faults = lambda plugin: {"hr": "初始化失败"}

    checks = service._module_fault_checks(SimpleNamespace())

    assert [item["label"] for item in checks] == ["模块运行异常"]
    assert checks[0]["status"] == "error"
    assert "hr" in checks[0]["detail"]
    assert "初始化失败" in checks[0]["detail"]


def test_diagnostics_omits_fault_check_when_no_fault(env):
    """没有故障记录时不产生空诊断项，关闭的模块只体现为「未启用」。"""
    service = env("modules/diagnostics/service.py")
    service.module_faults = lambda plugin: {}

    assert service._module_fault_checks(SimpleNamespace()) == []
