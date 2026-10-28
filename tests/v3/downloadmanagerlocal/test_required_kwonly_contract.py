# -*- coding: utf-8 -*-
"""调用点契约：函数签名的「必填 keyword-only 参数」必须在每个调用点显式传入。

离线运行：
    micromamba run -n base python -m pytest tests/v3/downloadmanagerlocal/test_required_kwonly_contract.py -q

背景（真实事故）：modules/transfer/pipeline.py 的完成分支调用
`record_transfer_success(plugin, 1)` 时漏掉了 `model/state.py` 中声明为必填
keyword-only 的 `fallback`，运行到「转移完成」才抛
`TypeError: record_transfer_success() missing 1 required keyword-only argument: 'fallback'`。
既有 pipeline 测试把该函数整体替身成 Mock()，Signature 不参与校验，因此漏检。

本测试用真实签名（通过加载真实源码取得）+ AST 静态扫描双重校验，
覆盖插件内所有「必填 keyword-only 参数」的调用点，避免同类问题再次漏网。
"""
import ast
import importlib.machinery
import importlib.util
import sys
import types
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[3] / "plugins.v3" / "downloadmanagerlocal"
PREFIX = "app.plugins.downloadmanagerlocal"


def _module(name: str) -> types.ModuleType:
    """建带 __spec__ 的替身模块。

    无 spec 的替身一旦被写进 sys.modules（本文件在导入期就写），pytest 渲染
    任何失败回溯时会调用 importlib.resources.files() 解析父包并抛 INTERNALERROR，
    把真实失败掩盖成「no tests ran」。
    """
    module = types.ModuleType(name)
    module.__spec__ = importlib.machinery.ModuleSpec(name, None)
    return module


def _bootstrap():
    """桩掉外部边界，真实加载 model/state.py 以取得权威签名。"""
    sys.modules.setdefault("app", _module("app"))
    sdk = sys.modules.setdefault("app.sdk", _module("app.sdk"))
    logging_mod = _module("app.sdk.logging")
    logging_mod.logger = types.SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        error=lambda *a, **k: None,
        debug=lambda *a, **k: None,
    )
    sys.modules["app.sdk.logging"] = logging_mod
    sdk.logging = logging_mod

    pkg = _module(PREFIX)
    pkg.__path__ = [str(PLUGIN)]
    sys.modules[PREFIX] = pkg
    for name in ("model", "modules", "modules.hr", "core"):
        mod = _module(f"{PREFIX}.{name}")
        mod.__path__ = []
        sys.modules[f"{PREFIX}.{name}"] = mod
    hr_constants = _module(f"{PREFIX}.modules.hr.constants")
    hr_constants.HR_NOTIFY_EVENTS_DATA_KEY = "hr_notify_events"
    hr_constants.HR_TASKS_DATA_KEY = "hr_tasks"
    sys.modules[f"{PREFIX}.modules.hr.constants"] = hr_constants

    spec = importlib.util.spec_from_file_location(
        f"{PREFIX}.model.state", PLUGIN / "model" / "state.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"{PREFIX}.model.state"] = module
    spec.loader.exec_module(module)
    return module


_STATE = _bootstrap()


def _required_kwonly(func) -> set:
    """返回必须在调用点显式传入的 keyword-only 参数名集合。"""
    import inspect

    sig = inspect.signature(func)
    return {
        name
        for name, param in sig.parameters.items()
        if param.kind is inspect.Parameter.KEYWORD_ONLY and param.default is inspect.Parameter.empty
    }


def _plugin_sources():
    return sorted(PLUGIN.rglob("*.py"))


def _iter_calls():
    """遍历插件源码，产出调用点元组。

    产出：(文件, 被调函数名, 传入的关键字参数名集合, 行号, 是否属性调用, 是否用 ** 展开)

    属性调用（`x.update(...)`）与内建容器方法同名是常态，仅凭名字无法区分，
    因此属性调用只在「显式传了关键字参数」时才纳入契约校验：内建
    `dict.update({...})` 这类调用不传关键字参数，而漏传必填 kwarg 的真实
    调用几乎总会以关键字形式传入其余参数。
    """
    for path in _plugin_sources():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - 语法错误由 ast 测试兜底
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name):
                name, is_attr = func.id, False
            elif isinstance(func, ast.Attribute):
                name, is_attr = func.attr, True
            else:
                continue
            kwargs = {kw.arg for kw in node.keywords if kw.arg}
            has_unpack = any(kw.arg is None for kw in node.keywords)
            yield path, name, kwargs, node.lineno, is_attr, has_unpack


def _collect_contracts():
    """收集插件内所有「含必填 keyword-only 参数」的函数/方法。"""
    contracts = {}
    for path in _plugin_sources():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            required = {
                arg.arg for arg in node.args.kwonlyargs
                if not _has_kwonly_default(node, arg.arg)
            }
            if required:
                contracts[node.name] = (required, path, node.lineno)
    return contracts


def _has_kwonly_default(node: ast.FunctionDef, arg_name: str) -> bool:
    """keyword-only 参数是否带默认值（带默认值即非必填）。"""
    # ast 的 kw_defaults 与 kwonlyargs 按下标对齐：None 表示无默认值。
    for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
        if arg.arg == arg_name:
            return default is not None
    return False


CONTRACTS = _collect_contracts()


def test_record_transfer_success_requires_fallback():
    """事故函数的契约本身保持必填，防止「把 fallback 改成默认值」的方式绕过修复。"""
    assert _required_kwonly(_STATE.record_transfer_success) == {"fallback"}


def test_every_call_site_passes_required_kwonly_args():
    """插件内所有调用点必须显式传入被调函数的必填 keyword-only 参数。"""
    violations = []
    for path, name, kwargs, lineno, is_attr, has_unpack in _iter_calls():
        entry = CONTRACTS.get(name)
        if not entry:
            continue
        required, _defpath, _defline = entry
        if name in ("__init__", "super"):
            continue
        missing = required - kwargs
        if not missing:
            continue
        # 属性调用（如 x.update(...)）的名字与内建 dict/set 方法完全撞名，
        # 静态无法区分接收者，故不纳入通用校验；HrGuard.update 由专用测试锁定。
        if is_attr:
            continue
        # 该调用点用 ** 展开时静态无法判定，跳过（由运行时测试兜底）。
        if has_unpack:
            continue
        rel = path.relative_to(PLUGIN.parent.parent)
        violations.append(f"{rel}:{lineno} -> {name}() 缺必填 kwarg {sorted(missing)}")
    assert not violations, "调用点漏传必填 keyword-only 参数：\n" + "\n".join(violations)


def _guard_receiver(node: ast.Call):
    """若调用形如 `self._guard.update(...)`，返回接收者名（`_guard`）；否则 None。"""
    func = node.func
    if not (isinstance(func, ast.Attribute) and func.attr == "update"):
        return None
    target = func.value
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return target.attr
    return None


def test_hr_guard_update_call_sites_pass_required_kwargs():
    """HrGuard.update 是本仓库唯一的必填 kwonly 实例方法，单独锁定其调用点。

    通用校验只处理裸函数调用（属性调用的名字与内建 dict/set.update 撞名，
    静态无法区分接收者），因此这里用接收者名字精确定位 `…_guard.update(...)`。
    """
    guard_source = (PLUGIN / "modules" / "hr" / "guard.py").read_text(encoding="utf-8")
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "update"
        and {arg.arg for arg in node.args.kwonlyargs} == {"enabled", "protected"}
        for node in ast.walk(ast.parse(guard_source))
    ), "HrGuard.update 的必填 keyword-only 契约发生漂移"

    found, violations = [], []
    for path in PLUGIN.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or _guard_receiver(node) != "_guard":
                continue
            kwargs = {kw.arg for kw in node.keywords if kw.arg}
            rel = path.relative_to(PLUGIN.parent.parent)
            found.append(f"{rel}:{node.lineno}")
            missing = {"enabled", "protected"} - kwargs
            if missing:
                violations.append(f"{rel}:{node.lineno} -> update() 缺 {sorted(missing)}")
    assert found, "未找到任何 HrGuard.update 调用点，接收者名字可能已改动"
    assert not violations, "HrGuard.update 调用点漏传必填参数：\n" + "\n".join(violations)


def test_pipeline_completion_path_passes_fallback():
    """事故的精确回归：完成分支必须把 fallback 传给统计函数。"""
    source = (PLUGIN / "modules" / "transfer" / "pipeline.py").read_text(encoding="utf-8")
    assert "record_transfer_success(plugin, 1, fallback=" in source, (
        "transfer_pipeline 完成分支必须传 fallback=…，否则完成时抛 TypeError"
    )


def test_begin_transfer_records_fallback_flag():
    """begin_transfer 必须把兜底标记落盘，否则统计无法区分兜底成功。"""
    source = (PLUGIN / "modules" / "transfer" / "pipeline.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    begin = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "begin_transfer"
    )
    kwonly = {arg.arg for arg in begin.args.kwonlyargs}
    assert "fallback" in kwonly, "begin_transfer 需要接受 fallback 关键字参数"
    assert '"fallback": bool(fallback)' in source, "begin_transfer 应把 fallback 写入事务记录"
