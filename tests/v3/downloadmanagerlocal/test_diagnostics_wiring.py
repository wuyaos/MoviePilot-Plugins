"""诊断端点接线守卫：`run` 参数必须从路由穿透到 handler。

背景（真实缺陷，2026-10-30 本地 MP 实测）：
1. `controller/api.py` 曾把 `/diagnostics` 写成 `partial(plugin.api_diagnostics)`，
   partial 隐藏签名 → FastAPI 无法绑定 `run` 查询参数；
2. `__init__.py` 的插件方法包装层 `api_diagnostics(self, detail_limit=20)` 不接受也不转发
   `run` → 即使路由正确，参数也会在第二层被丢掉（特性静默失效）。
两者都不会被任何离线单测发现（本机无 fastapi，HTTP 级测试被 importorskip 跳过），
因此这里用 AST 做**接线契约**断言：只保证「参数能穿过每一层」，不替代真实 HTTP 验收。
"""
import ast
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3] / "plugins.v3" / "downloadmanagerlocal"


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _func(tree: ast.Module, name: str):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"未找到函数 {name}")


def test_plugin_method_forwards_run_to_handler():
    """插件方法包装层必须接受并转发 run，否则特性静默失效。"""
    method = _func(_parse(PLUGIN_ROOT / "__init__.py"), "api_diagnostics")
    params = [arg.arg for arg in method.args.args] + [arg.arg for arg in method.args.kwonlyargs]
    assert "run" in params, "插件方法 api_diagnostics 未声明 run 参数"
    forwarded = [
        keyword.arg
        for node in ast.walk(method)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
    ]
    assert "run" in forwarded, "插件方法 api_diagnostics 未把 run 转发给 handler"


def test_handler_accepts_run_keyword():
    """controller.handlers.api_diagnostics 必须接受 run。"""
    handler = _func(_parse(PLUGIN_ROOT / "controller" / "handlers.py"), "api_diagnostics")
    params = [arg.arg for arg in handler.args.args] + [arg.arg for arg in handler.args.kwonlyargs]
    assert "run" in params, "handlers.api_diagnostics 未声明 run 参数"


def test_diagnostics_route_is_not_wrapped_by_partial():
    """partial 会隐藏签名，导致 detail_limit / run 查询参数无法绑定。"""
    source = (PLUGIN_ROOT / "controller" / "api.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        values = [value for value in node.values if isinstance(value, ast.Constant)]
        if "/diagnostics" not in [value.value for value in values]:
            continue
        endpoint_values = [
            value
            for key, value in zip(node.keys, node.values)
            if isinstance(key, ast.Constant) and key.value == "endpoint"
        ]
        assert endpoint_values, "/diagnostics 路由缺少 endpoint"
        endpoint = endpoint_values[0]
        assert not (
            isinstance(endpoint, ast.Call)
            and isinstance(endpoint.func, ast.Name)
            and endpoint.func.id == "partial"
        ), "/diagnostics 的 endpoint 不得使用 partial（会隐藏签名，查询参数失效）"
        return
    raise AssertionError("未找到 /diagnostics 路由声明")
