"""API 请求体注解审计。

V3 宿主用 FastAPI 装配插件端点：`__init__.py` 里 `payload` 参数**没有类型注解**时，
FastAPI 把它当 query 参数，JSON body 永远解析不到——表现为「端点永远收到空 body」。
本地 MP 实测踩到：`/cleanup_module_data` 无论传什么都回 400
「module Field required, input_value={}」，而单元测试因为直接调用函数看不出问题。

本文件做纯静态校验：所有 `def api_*(self, payload ...)` 的 payload 必须有注解。
"""

import ast
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3] / "plugins.v3/downloadmanagerlocal"
INIT = PLUGIN_ROOT / "__init__.py"


def _payload_params(tree: ast.AST):
    """收集 (函数名, 行号, 参数节点) —— 名字恰为 payload 或以此开头。"""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        args = node.args.args
        for arg in args:
            if arg.arg == "payload" or arg.arg.startswith("payload"):
                found.append((node.name, arg.lineno, arg))
    return found


def test_api_payload_params_are_annotated():
    """所有 payload 参数必须带注解，否则宿主收不到 JSON body。"""
    tree = ast.parse(INIT.read_text(encoding="utf-8"))
    missing = [
        f"{name}:{line}"
        for name, line, arg in _payload_params(tree)
        if arg.annotation is None
    ]
    assert missing == [], (
        "以下端点 payload 参数缺少类型注解，宿主会丢弃 JSON body：\n"
        + "\n".join(missing)
    )


def test_audit_detects_missing_annotation():
    """回归：无注解的 payload 必须被判定为缺失。"""
    tree = ast.parse(
        "class P:\n"
        "    def api_x(self, payload=None):\n"
        "        return payload\n"
        "    def api_y(self, payload: dict | None = None):\n"
        "        return payload\n"
    )
    missing = [name for name, _, arg in _payload_params(tree) if arg.annotation is None]
    assert missing == ["api_x"]
