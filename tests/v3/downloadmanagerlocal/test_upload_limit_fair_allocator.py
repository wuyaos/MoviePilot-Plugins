"""Pure fair allocator and rule config contract tests."""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[3] / "plugins.v3/downloadmanagerlocal"


@pytest.fixture
def allocator(monkeypatch):
    package = "dml_allocator_test"
    root = types.ModuleType(package)
    root.__path__ = [str(PLUGIN)]
    monkeypatch.setitem(sys.modules, package, root)
    model = types.ModuleType(package + ".model")
    model.__path__ = []
    monkeypatch.setitem(sys.modules, package + ".model", model)
    upload_model = types.ModuleType(package + ".model.upload_limit")
    upload_model.UploadPool = type("UploadPool", (), {})
    monkeypatch.setitem(sys.modules, package + ".model.upload_limit", upload_model)
    modules = types.ModuleType(package + ".modules")
    modules.__path__ = []
    monkeypatch.setitem(sys.modules, package + ".modules", modules)
    uplimit = types.ModuleType(package + ".modules.uploadlimit")
    uplimit.__path__ = []
    monkeypatch.setitem(sys.modules, package + ".modules.uploadlimit", uplimit)
    path = PLUGIN / "modules/uploadlimit/allocator.py"
    spec = importlib.util.spec_from_file_location(package + ".modules.uploadlimit.allocator", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def tasks(*entries):
    return {
        key: {"downloader_id": downloader, "site_key": site, "single_limit_kib": single}
        for key, downloader, site, single in entries
    }


def test_equal_split_ignores_current_upload_speed(allocator):
    torrent_tasks = tasks(("a", "qb", "site", 0), ("b", "qb", "site", 0))
    result = allocator.allocate_fair_task_limits(
        torrent_tasks, {"qb": 45 * 1024}, {"site": 45 * 1024}
    )
    assert result == {"a": 45 * 1024 // 2, "b": 45 * 1024 // 2}
    # Speed is intentionally not an input; a 0.22 MiB/s task gets the same share.


def test_cross_downloader_site_budget_is_shared(allocator):
    torrent_tasks = tasks(("a", "qb", "site", 0), ("b", "tr", "site", 0))
    result = allocator.allocate_fair_task_limits(
        torrent_tasks, {"qb": 40, "tr": 40}, {"site": 45}
    )
    assert result == {"a": 23, "b": 22}
    assert sum(result.values()) == 45


def test_single_torrent_caps_release_unused_share(allocator):
    torrent_tasks = tasks(("a", "qb", "site", 10), ("b", "qb", "site", 0))
    result = allocator.allocate_fair_task_limits(
        torrent_tasks, {"qb": 100}, {"site": 100}
    )
    assert result == {"a": 10, "b": 90}


def test_single_only_without_site_budget_uses_single_caps(allocator):
    torrent_tasks = tasks(("a", "qb", "site", 12), ("b", "qb", "site", 0))
    assert allocator.allocate_fair_task_limits(torrent_tasks, {"qb": 100}, {}) == {
        "a": 12, "b": 88
    }


def test_zero_and_missing_budgets_never_create_negative_values(allocator):
    torrent_tasks = tasks(("a", "qb", "s", 0), ("b", "qb", "s", 10))
    assert allocator.allocate_fair_task_limits(torrent_tasks, {"qb": 0}, {"s": 5}) == {
        "a": 0, "b": 0
    }
    assert allocator.allocate_fair_task_limits(torrent_tasks, {"qb": 8}, {}) == {
        "a": 4, "b": 4
    }


def test_integer_remainder_is_stable_and_within_budgets(allocator):
    torrent_tasks = tasks(("c", "d", "s", 0), ("a", "d", "s", 0), ("b", "d", "s", 0))
    first = allocator.allocate_fair_task_limits(torrent_tasks, {"d": 8}, {"s": 8})
    second = allocator.allocate_fair_task_limits(torrent_tasks, {"d": 8}, {"s": 8})
    assert first == second == {"a": 3, "b": 3, "c": 2}


def test_config_site_rule_keeps_single_only_and_legacy_total_limit():
    import ast

    path = PLUGIN / "utils/config.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {"_normalize_upload_site_rules", "normalize_upload_limit_config", "safe_int", "_positive_integer_mapping"}
    selected = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
    namespace = {}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), namespace)
    normalize = namespace["normalize_upload_limit_config"]

    normalized = normalize({
        "upload_limit_site_rules": {
            "total": {"limit_kib": 100},
            "single": {"torrent_limit_kib": 25},
        }
    })
    assert normalized["upload_limit_site_rules"] == {
        "total": {"limit_kib": 100, "torrent_limit_kib": 0},
        "single": {"limit_kib": 0, "torrent_limit_kib": 25},
    }
    assert normalized["upload_limit_notify"] is True
    assert normalize({"upload_limit_notify": ""})["upload_limit_notify"] is False


def test_explicit_zero_site_budget_is_exhausted_but_missing_is_unconstrained(allocator):
    torrent_tasks = tasks(("a", "qb", "site", 0))
    assert allocator.allocate_fair_task_limits(torrent_tasks, {"qb": 10}, {"site": 0}) == {"a": 0}
    assert allocator.allocate_fair_task_limits(torrent_tasks, {"qb": 10}, {}) == {"a": 10}


def test_fractional_waterline_does_not_discard_other_constraint_headroom(allocator):
    torrent_tasks = tasks(
        ("a", "qb1", "site", 0),
        ("b", "qb2", "site", 0),
        ("c", "qb2", "other", 0),
    )
    result = allocator.allocate_fair_task_limits(
        torrent_tasks, {"qb1": 100, "qb2": 100}, {"site": 1}
    )
    assert result == {"a": 1, "b": 0, "c": 100}
    assert result["b"] + result["c"] == 100


def test_zero_budget_site_does_not_starve_other_sites(allocator):
    """显式 0 预算站点只冻结本站成员，其余站点/下载器照常分配。"""
    torrent_tasks = tasks(
        ("a", "qb1", "frozen", 0),
        ("b", "qb2", "healthy", 0),
    )
    result = allocator.allocate_fair_task_limits(
        torrent_tasks, {"qb1": 100, "qb2": 100}, {"frozen": 0, "healthy": 100}
    )
    assert result == {"a": 0, "b": 100}
