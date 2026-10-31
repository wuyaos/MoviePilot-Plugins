# -*- coding: utf-8 -*-
"""静态契约：annotation 引用的名字必须在模块导入时已可解析。

pipeline.py 曾在签名中使用 Optional 却未导入；Python 3.14 惰性注解掩盖了该
错误（import 不炸），但 ≤3.13 会在函数定义时立即求值注解并抛 NameError。
此测试不依赖解释器版本：直接 ast 扫描，保证「签名中引用的注解名字都有来源」。
"""
import ast
import builtins
import pathlib
import sys

PLUGIN = pathlib.Path(__file__).resolve().parents[3] / "plugins.v3" / "downloadmanagerlocal"

BUILTIN_NAMES = set(dir(builtins))


def _module_import_names(tree: ast.Module) -> set:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
    return names


def _assigned_names(tree: ast.Module) -> set:
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                names.add(sub.id)
            elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(sub.name)
    return names


def _annotation_names(node):
    out = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            out.add(sub.id)
        elif isinstance(sub, ast.Attribute):
            cur = sub
            while isinstance(cur, ast.Attribute):
                cur = cur.value
            if isinstance(cur, ast.Name):
                out.add(cur.id)
    return out


def test_annotation_names_are_resolvable_at_import():
    """模块内所有函数签名注解引用的名字必须来自 import/模块赋值/内建。"""
    failures = []
    py_files = sorted(PLUGIN.rglob("*.py"))
    assert py_files, "plugin directory missing"
    for path in py_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        available = _module_import_names(tree) | _assigned_names(tree) | BUILTIN_NAMES
        # typing 模块属性形式（typing.Optional）按 Attribute 处理，取根名 typing 判定
        for node in ast.walk(tree):
            args = []
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = list(node.args.args) + list(node.args.kwonlyargs)
                if node.args.vararg:
                    args.append(node.args.vararg)
                if node.args.kwarg:
                    args.append(node.args.kwarg)
                returns = [node.returns] if node.returns else []
            elif isinstance(node, ast.AnnAssign):
                args, returns = [], [node.annotation]
            else:
                continue
            for a in args:
                if a.annotation is not None:
                    for name in _annotation_names(a.annotation):
                        if name not in available:
                            failures.append(f"{path.name}:{a.lineno} arg '{a.arg}' uses unresolved '{name}'")
            for r in returns:
                if r is not None:
                    for name in _annotation_names(r):
                        if name not in available:
                            failures.append(f"{path.name}:{node.lineno} return uses unresolved '{name}'")
    assert not failures, "unresolved annotation names:\n" + "\n".join(failures)


if __name__ == "__main__":
    sys.exit(0)
