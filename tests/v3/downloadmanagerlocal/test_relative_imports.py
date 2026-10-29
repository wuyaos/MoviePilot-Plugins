"""相对导入路径审计。

本地 MP 真实调用暴露过一类单元测试桩掩盖的错误：写了
`from ..modules.autoremove.constants import ...`（在 `modules/diagnostics/` 里
`..` 已经指向 `modules`，多写一层 `.modules` 就变成不存在的 `modules.modules`），
桩测试因为 sys.modules 里恰好装了同名桩而不报错，线上接口直接 500。

本文件做纯静态校验，不依赖运行期 app 包：解析每个源文件的相对导入，
按 PEP 328 还原目标模块路径，确认磁盘上真实存在对应 `.py` 或包目录。
"""

import ast
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3] / "plugins.v3/downloadmanagerlocal"

SKIP_DIRS = {"dist", "__pycache__", "node_modules"}


def _iter_sources(root: Path):
    for path in sorted(root.rglob("*.py")):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        yield path


def _package_parts(root: Path, source: Path):
    """返回源文件所在包的相对路径段（不含文件名）。"""
    return list(source.relative_to(root).parent.parts)


def _target_module_path(root: Path, source: Path, node: ast.ImportFrom) -> Path | None:
    """按 level 还原 `from ...a.b import c` 的模块磁盘路径；越界返回 None。"""
    package = _package_parts(root, source)
    up = node.level - 1
    if up > len(package):
        return None
    base = package[: len(package) - up]
    if node.module:
        base = base + node.module.split(".")
    return root.joinpath(*base) if base else root


def _exists(root: Path, target: Path) -> bool:
    if target is None:
        return False
    return target.is_dir() or target.with_suffix(".py").exists()


def _scan(root: Path):
    """返回 [(相对文件名, 行号, 原文目标, 解析路径)] 形式的损坏导入列表。"""
    broken = []
    for source in _iter_sources(root):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.level:
                continue
            target = _target_module_path(root, source, node)
            if not _exists(root, target):
                broken.append(
                    (
                        str(source.relative_to(root)).replace("\\", "/"),
                        node.lineno,
                        "." * node.level + (node.module or ""),
                        str(target.relative_to(root)).replace("\\", "/") if target else "<越界>",
                    )
                )
    return broken


def test_no_broken_relative_imports():
    """插件内所有相对导入都必须指向真实存在的模块或包。"""
    broken = _scan(PLUGIN_ROOT)
    detail = "\n".join(
        f"{name}:{line}  {written}  ->  {resolved}" for name, line, written, resolved in broken
    )
    assert broken == [], f"发现无法解析的相对导入：\n{detail}"


def test_scanner_detects_missing_subpackage(tmp_path):
    """回归：`modules/<a>/x.py` 里写 `from ..modules.<b>...` 必须被判定为损坏。"""
    root = tmp_path / "plug"
    (root / "modules" / "alpha").mkdir(parents=True)
    (root / "modules" / "__init__.py").write_text("", encoding="utf-8")
    source = root / "modules" / "alpha" / "service.py"
    source.write_text(
        "def f():\n    from ..modules.beta.constants import KEY\n",
        encoding="utf-8",
    )
    broken = _scan(root)
    assert len(broken) == 1
    assert broken[0][2] == "..modules.beta.constants"
    assert broken[0][3] == "modules/modules/beta/constants"


def test_scanner_accepts_correct_levels(tmp_path):
    """回归：同级模块用 `..`、顶层包用 `...` 都必须通过。"""
    root = tmp_path / "plug"
    (root / "modules" / "alpha").mkdir(parents=True)
    (root / "modules" / "beta").mkdir(parents=True)
    (root / "model").mkdir()
    for path in (root / "modules" / "__init__.py", root / "modules" / "beta" / "__init__.py"):
        path.write_text("", encoding="utf-8")
    (root / "model" / "state.py").write_text("KEY = 1\n", encoding="utf-8")
    (root / "modules" / "alpha" / "service.py").write_text(
        "def f():\n"
        "    from ..beta import constants\n"
        "    from ...model.state import KEY\n",
        encoding="utf-8",
    )
    (root / "modules" / "beta" / "constants.py").write_text("", encoding="utf-8")
    assert _scan(root) == []
