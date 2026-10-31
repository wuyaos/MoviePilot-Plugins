"""F10 过时清理防回归契约：已删除符号不得复活，RENAME_QNAP_CONFIG 不得回到 __all__。

来源：risk-auditor「Outdated」#1/#4/#5/#6 与 code-scout O1/O3/O4（见
.ralph/dml-review-fixes.md F10）。删除型修复用源码文本断言防回归；
文本而非 AST 是因为 `_BRACKET_PREFIX_RE`/`_path_exists` 是模块私有名，
跨文件只需保证「不再出现」。
"""

from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3] / "plugins.v3" / "downloadmanagerlocal"

CASES = [
    # 精确模式：子串断言会误伤 _LEADING_BRACKET_PREFIX_RE / source_path_exists 这类合法名。
    (
        PLUGIN / "utils" / "name_cleaner.py",
        ["collect_retry_rename_hashes", "\n_BRACKET_PREFIX_RE = "],
    ),
    (
        PLUGIN / "model" / "state.py",
        ["PERSISTED_STATE_KEYS"],
    ),
    (
        PLUGIN / "modules" / "diagnostics" / "service.py",
        ["def _path_exists"],
    ),
]


def test_removed_symbols_stay_removed():
    for path, symbols in CASES:
        source = path.read_text(encoding="utf-8")
        for symbol in symbols:
            assert symbol not in source, f"{path.name} 不应再出现 {symbol}"


def test_transfer_tasks_default_declared_once():
    source = (PLUGIN / "utils" / "config.py").read_text(encoding="utf-8")
    occurrences = source.count('"transfer_tasks": "[]"')
    assert occurrences == 1, f"transfer_tasks 默认值应只声明一次，实际 {occurrences} 次"


def test_transfer_pipeline_docstring_points_to_current_path():
    source = (PLUGIN / "controller" / "handlers.py").read_text(encoding="utf-8")
    assert "modules/transfer_pipeline" not in source, "旧模块路径 transfer_pipeline 不应再被引用"
    assert "modules/transfer/pipeline.py" in source


def test_rename_qnap_config_not_exported():
    source = (PLUGIN / "modules" / "rename" / "service.py").read_text(encoding="utf-8")
    all_start = source.index("__all__ = (")
    all_block = source[all_start:source.index(")", all_start)]
    assert "RENAME_QNAP_CONFIG" not in all_block, "RENAME_QNAP_CONFIG 是行为证据常量，不应随 __all__ 发布"
    assert 'RENAME_QNAP_CONFIG = {' in source, "常量本体保留在模块内（仅退出导出面）"


def test_config_vue_has_no_legacy_subtab_watcher():
    source = (
        Path(__file__).resolve().parents[3]
        / "frontend.v3" / "downloadmanagerlocal" / "src" / "components" / "Config.vue"
    ).read_text(encoding="utf-8")
    assert "legacySubTabs" not in source, "旧子页迁移 watcher 已删除，不应复活"
