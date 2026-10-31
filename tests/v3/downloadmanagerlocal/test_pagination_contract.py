# -*- coding: utf-8 -*-
"""静态契约：插件层分页默认值与死接口清理。

- api_* 分页包装默认 page_size 必须为 20（与 handler 层一致，前端统一 20/页）。
- list_rename_archive 只作为 modules/rename/archive.py 的模块函数存在；
  插件类上不得再有同名转发包装（无任何调用方，handlers 自行分页）。
"""
import ast
import pathlib
import sys

PLUGIN = pathlib.Path(__file__).resolve().parents[3] / "plugins.v3" / "downloadmanagerlocal"


def _plugin_tree():
    return ast.parse(
        (PLUGIN / "__init__.py").read_text(encoding="utf-8"),
        filename="__init__.py",
    )


def test_api_wrappers_default_page_size_20():
    tree = _plugin_tree()
    defaults = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("api_"):
            args = node.args.args
            fn_defaults = node.args.defaults
            # defaults 与 args 尾部对齐：无默认值的前段不在 defaults 里
            offset = len(args) - len(fn_defaults)
            for i, arg in enumerate(args):
                if arg.arg == "page_size" and i >= offset:
                    defaults[node.name] = ast.literal_eval(fn_defaults[i - offset])
    assert defaults, "no api_* pagination wrappers found"
    bad = {name: value for name, value in defaults.items() if value != 20}
    assert not bad, f"page_size default must be 20, got: {bad}"


def test_plugin_class_has_no_list_rename_archive_wrapper():
    tree = _plugin_tree()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "list_rename_archive":
            raise AssertionError("plugin-level list_rename_archive wrapper must stay deleted")
    src = (PLUGIN / "__init__.py").read_text(encoding="utf-8")
    assert "_list_rename_archive_impl" not in src, "stale import alias remains"


if __name__ == "__main__":
    sys.exit(0)
