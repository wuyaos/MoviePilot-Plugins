"""数据页模块明细（P7-2 用户需求 m18492：每个模块面展示明细，失败清理不再只有数字）。

覆盖：
1. 明细覆盖七个模块，标题/行/列表/错误字段齐全；
2. 失败清理把「本轮 / 事件 / 累计」三段计数与保留期、跳过统计展开成行；
3. 自动删种候选列表按 MODULE_DETAIL_ITEM_LIMIT 截断；
4. 单模块读取失败只在该模块记 error，其他模块明细不受影响（模块隔离）；
5. 重命名明细带最近失败原因列表；
6. build_diagnostics payload 带出 module_details；
7. 明细条数上限（P7-2c 需求③）：detail_limit 白名单归一、total/limit/truncated 元信息、
   重命名按请求上限取失败样本且 total 用真实失败总数、异常模块的错误块同样带元信息。

加载方式仿 test_module_isolation：插件根挂为带 __path__ 的假包，
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
    """任意未知属性返回 Mock，避免为每个依赖枚举符号。"""

    def __getattr__(self, item):
        if item.startswith("__"):
            raise AttributeError(item)
        return Mock(name=f"{self.__name__}.{item}")


def _register_package(monkeypatch, name, path=None, **attrs):
    result = _StubModule(name) if path is None else types.ModuleType(name)
    result.__spec__ = importlib.machinery.ModuleSpec(name, None, is_package=path is not None)
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
    for sub in ("utils", "core", "modules", "model"):
        _register_package(monkeypatch, f"{PREFIX}.{sub}", __path__=[str(PLUGIN / sub)])
    _register_package(monkeypatch, f"{PREFIX}.model.state", RENAME_RECORDS_KEY="rename_records")
    _register_package(
        monkeypatch,
        f"{PREFIX}.utils.name_cleaner",
        is_dirty_renamed_torrent_name=lambda name: False,
    )
    _register_package(monkeypatch, f"{PREFIX}.utils.config")

    def load(relpath: str, name: str = ""):
        dotted = ".".join(Path(relpath).with_suffix("").parts)
        spec = importlib.util.spec_from_file_location(f"{PREFIX}.{dotted}", PLUGIN / relpath)
        result = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, spec.name, result)
        spec.loader.exec_module(result)
        return result

    return load


def _rows(detail: dict) -> dict:
    """把明细行转成 {标签: 值} 便于断言。"""
    return {row["label"]: row["value"] for row in detail["rows"]}


@pytest.fixture
def service(env, monkeypatch):
    """加载诊断服务，并把模块级状态访问替换成可变桩。"""
    config_stub = sys.modules[f"{PREFIX}.utils.config"]
    config_stub.module_faults = lambda plugin: {}
    config_stub.module_observe_flags = lambda plugin: {}
    config_stub.observe_previews = lambda plugin: {}
    module = env("modules/diagnostics/service.py")
    state = sys.modules[f"{PREFIX}.model.state"]
    state.TRANSFER_SKIP_STATS_KEY = "transfer_skip_stats"
    state.load_transfer_stats = lambda plugin: {
        "today_success": 3,
        "success_total": 120,
        "today_fallback": 1,
        "fallback_success": 9,
    }
    rename = _register_package(monkeypatch, f"{PREFIX}.modules.rename.service")
    rename.get_module_status = lambda plugin: {"renamed": 2, "failed": 1, "skipped": 0, "last_run": "2026-10-29 10:00:00"}
    sitetag = _register_package(monkeypatch, f"{PREFIX}.modules.sitetag.service")
    sitetag.get_module_status = lambda plugin: {"completed": 7, "skipped": 1, "matched": {"pt.example": 4},
                                                   "round": {"checked": 10, "success": 4, "no_update": 5, "failed": 1}}
    uploadlimit = _register_package(monkeypatch, f"{PREFIX}.modules.uploadlimit.service")
    uploadlimit.get_upload_limit_status = lambda plugin: {
        "service_status": "running",
        "mode": "site_policy",
        "managed_torrents": 6,
        "cycle": 12,
        "sites": [],
        "errors": [],
    }
    return module


def _plugin(**overrides):
    base = {
        "_module_observe_only": {"transfer": False, "rename": False, "tag": False, "hr": False,
                                 "autoremove": False, "failclean": False, "upload_limit": False},
        "_transfer_enabled": True,
        "_transfer_active": True,
        "_transfer_fallback_enabled": False,
        "_rename_enabled": True,
        "_tag_enabled": True,
        "_hr_enabled": False,
        "_remover_enabled": True,
        "_failcleanup_enabled": True,
        "_upload_limit_enabled": True,
        "_hr_service": None,
        "_autoremove_service": None,
        "_failclean_service": None,
        "get_data": lambda key: {},
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_module_details_covers_seven_modules(service):
    """七个模块都要有明细块，字段齐全且无错误。"""
    details = service._module_details(_plugin(), {"total": 5}, {"archived": 2, "threshold": 3})

    assert set(details) == {"transfer", "rename", "tag", "tagcleanup", "hr", "autoremove", "failclean", "upload_limit"}
    for key, detail in details.items():
        assert detail["title"], key
        assert detail["error"] == "", key
        assert set(detail) == {"title", "rows", "items", "error", "total", "limit", "truncated"}
        assert detail["limit"] == service.MODULE_DETAIL_ITEM_LIMIT == 20, "默认上限保持 20"
        assert detail["truncated"] is False and detail["total"] >= len(detail["items"])
    assert _rows(details["transfer"])["累计成功"] == "120"
    assert _rows(details["tag"])["命中站点数"] == "1"
    assert [_rows(details["tag"])[label] for label in ("本轮检查", "成功", "无需更新", "失败")] == ["10", "4", "5", "1"]
    assert _rows(details["hr"])["状态"] == "未启用或初始化失败", "服务被隔离时要给出显式提示"


def test_tagcleanup_detail_projects_latest_scan(service):
    """标签清理明细聚合最近扫描结果，并保持标签名与任务数。"""
    plugin = _plugin(_tag_cleanup_status={
        "downloaders": [{"name": "qb", "tags": [
            {"tag": "DML_TMP_old", "hashes": ["a", "b"]},
            {"tag": "manual", "hashes": ["b"], "cleanup_error": "失败"},
        ]}],
        "auto_removed": [{"tag": "DML_TMP_done", "removed": 1}],
        "errors": [{"downloader": "missing"}],
    })
    detail = service._tagcleanup_detail(plugin)
    rows = _rows(detail)
    assert rows == {"候选标签": "2", "涉及任务": "2", "成功": "1", "失败": "2"}
    assert [(item["title"], item["meta"]) for item in detail["items"]] == [
        ("DML_TMP_old", "2 个任务"), ("manual", "1 个任务")
    ]


def test_failclean_detail_breaks_counters_into_three_sections(service):
    """失败清理明细：本轮/事件/累计三段计数、保留期与跳过统计都要展开成可读行。"""
    status = {
        "enabled": True,
        "retain_hours": 6,
        "last_scan_time": 1793263474.61,
        "last_scan_trigger": "手动",
        "scan": {"scanned": 12, "cleaned": 3, "failed": 1, "skipped": 8},
        "event": {"deleted": 4, "failed": 0, "skipped": 5},
        "total": {"cleaned": 30, "failed": 2, "skipped": 11},
        "skip_stats": {"transfer_source": 2, "auto_remove": 0, "transfer_failure": 1, "sync_delete": 0},
    }
    plugin = _plugin(_failclean_service=SimpleNamespace(get_module_status=lambda: status))

    detail = service._failclean_detail(plugin)
    rows = _rows(detail)

    assert rows["本轮扫描 / 清理 / 失败 / 跳过"] == "12 / 3 / 1 / 8"
    assert rows["事件删除 / 失败 / 跳过"] == "4 / 0 / 5"
    assert rows["累计清理 / 失败 / 跳过"] == "30 / 2 / 11"
    assert rows["保留期（小时）"] == "6"
    assert rows["巡检触发"] == "手动"
    assert rows["最近巡检"] != "尚未运行", "有时间戳时要显示可读时间"
    assert rows["跳过（转移源种子）"] == "2" and rows["跳过（整理失败）"] == "1"
    assert detail["error"] == ""


def test_autoremove_detail_lists_candidates_with_limit(service):
    """自动删种明细：观察开关与候选列表（按 MODULE_DETAIL_ITEM_LIMIT 截断）。"""
    candidates = [
        {
            "name": f"dml-{index}.bin",
            "site": "pt.example",
            "state": "stalledUP",
            "size_text": "2.02KB",
            "reason": "平均上传0.0KB/s",
        }
        for index in range(service.MODULE_DETAIL_ITEM_LIMIT + 5)
    ]
    status = {"observe_only": True, "candidates": len(candidates), "candidate_list": candidates}
    plugin = _plugin(_autoremove_service=SimpleNamespace(get_module_status=lambda: status))

    detail = service._autoremove_detail(plugin)

    assert _rows(detail)["观察模式"] == "已开启"
    assert _rows(detail)["候选"] == "25"
    assert len(detail["items"]) == service.MODULE_DETAIL_ITEM_LIMIT
    assert detail["total"] == 25, "total 是真实候选数，不是截断后的条数"
    assert detail["limit"] == 20 and detail["truncated"] is True
    assert detail["items"][0]["title"] == "dml-0.bin"
    assert "平均上传0.0KB/s" in detail["items"][0]["meta"]


def test_module_details_isolates_failing_module(service):
    """单模块读取抛异常只在该模块记 error，其他模块明细照常返回（模块隔离）。"""

    def boom():
        raise RuntimeError("服务未初始化")

    plugin = _plugin(_failclean_service=SimpleNamespace(get_module_status=boom))
    details = service._module_details(plugin, {}, {})

    assert details["failclean"]["rows"] == []
    assert details["failclean"]["error"].startswith("RuntimeError")
    assert details["transfer"]["error"] == "" and details["transfer"]["rows"], "其他模块不受影响"
    assert details["upload_limit"]["error"] == ""


def test_rename_detail_lists_recent_failures(service):
    """重命名明细：归档水位与最近失败原因列表。"""
    history = {
        "total": 37,
        "recent_failures": [
            {"name": "dml-a.bin", "reason": "媒体识别失败", "time": "2026-10-29 10:00:00"},
            {"name": "dml-b.bin", "reason": "媒体识别失败", "time": "2026-10-29 09:00:00"},
        ],
    }
    detail = service._rename_detail(_plugin(), history, {"archived": 34, "threshold": 3})

    assert _rows(detail)["失败归档"] == "34 / 阈值 3"
    assert _rows(detail)["历史记录"] == "37"
    assert [item["title"] for item in detail["items"]] == ["dml-a.bin", "dml-b.bin"]
    assert "媒体识别失败" in detail["items"][0]["meta"]


def test_build_diagnostics_payload_includes_module_details(service, monkeypatch):
    """诊断 payload 必须带出 module_details，供数据页渲染模块明细。"""
    sentinel = {"transfer": {"title": "转移做种", "rows": [], "items": [], "error": ""}}
    monkeypatch.setattr(service, "_module_details", lambda *args, **kwargs: sentinel)
    # 诊断项依赖的模块常量走懒导入，注册成桩即可（真实导入由 test_relative_imports 覆盖）
    _register_package(monkeypatch, f"{PREFIX}.modules.autoremove.constants", REMOVER_STATE_DATA_KEY="remover_state")
    _register_package(monkeypatch, f"{PREFIX}.modules.failclean.constants", FAILCLEAN_STATUS_DATA_KEY="failclean_status")
    _register_package(monkeypatch, f"{PREFIX}.modules.transfer.tasks", load_transfer_tasks=lambda plugin: [])

    plugin = SimpleNamespace(
        plugin_name="下载中心",
        plugin_version="3.9.12",
        get_state=lambda: True,
        get_data=lambda key: {},
        service_info=lambda name: SimpleNamespace(instance=True, type="qbittorrent"),
        rename_archive_stats=lambda: {"archived": 0, "threshold": 3},
        _enabled=True,
        _transfer_enabled=True,
        _transfer_active=True,
        _transfer_fallback_enabled=False,
        _rename_enabled=True,
        _tag_enabled=True,
        _seed_autostart=True,
        _seed_skipverify=True,
        _frompath="/downloads",
        _topath="/downloads",
        _fromtorrentpath="",
    )

    payload = service.build_diagnostics(plugin)

    assert payload["module_details"] == sentinel
    assert "cleanup_data" in payload and "checks" in payload


def test_resolve_detail_limit_normalizes_to_whitelist(service):
    """条数上限只接受白名单值，缺失/非法/越界一律回到默认 20。"""
    assert service.MODULE_DETAIL_LIMIT_CHOICES == (20, 50, 100, 200)
    for value in (20, 50, 100, 200, "50"):
        assert service.resolve_detail_limit(value) == int(value)
    for value in (0, 21, -5, 999, "abc", None, 20.5):
        assert service.resolve_detail_limit(value) == 20, value


def test_detail_limit_truncates_items_and_reports_metadata(service):
    """20/50/100/200 四档截断正确，total 是截断前真实条数，truncated 按需为真。"""
    rows = [{"label": "计数", "value": "1"}]
    items = [{"title": f"第{index}条", "meta": ""} for index in range(230)]
    for limit in service.MODULE_DETAIL_LIMIT_CHOICES:
        detail = service._detail("示例", rows, items, detail_limit=limit)
        assert detail["limit"] == limit
        assert len(detail["items"]) == min(limit, 230)
        assert detail["total"] == 230
        assert detail["truncated"] is (limit < 230)
    assert service._detail("示例", rows, items, detail_limit=200)["items"][-1]["title"] == "第199条"


def test_detail_ignores_invalid_items_and_keeps_caller_total(service):
    """先过滤非字典条目再计总数；调用方给的 total 更大时以真实条数为准。"""
    detail = service._detail("示例", [], ["x", {"title": "a", "meta": ""}, None], total=7)
    assert len(detail["items"]) == 1 and detail["total"] == 7 and detail["truncated"] is True
    assert service._detail("示例", [], None)["total"] == 0


def test_rename_history_stats_excludes_hidden_records(service):
    """诊断与清理计数只统计可见记录，恢复隐藏标记后计数回升。"""
    records = {
        "visible": {"success": True, "original_name": "a", "after_name": "b"},
        "hidden": {"success": False, "history_hidden": True, "original_name": "c"},
    }
    plugin = _plugin(get_data=lambda key: records if key == "rename_records" else {})
    assert service._rename_history_stats(plugin)["total"] == 1
    records["hidden"].pop("history_hidden")
    assert service._rename_history_stats(plugin)["total"] == 2


def test_rename_history_sample_follows_requested_limit(service):
    """重命名失败样本按请求上限取，不再固定截五条。"""
    records = {
        f"hash{index}": {"success": False, "original_name": f"dml-{index}.bin",
                         "reason": "媒体识别失败", "time": f"2026-10-29 10:{index:02d}:00"}
        for index in range(12)
    }
    plugin = _plugin(get_data=lambda key: records if key == "rename_records" else {})

    assert len(service._rename_history_stats(plugin)["recent_failures"]) == 5, "默认 5 条供诊断摘要"
    wide = service._rename_history_stats(plugin, recent_limit=50)
    assert len(wide["recent_failures"]) == 12 and wide["failed"] == 12


def test_rename_detail_reports_real_failure_total(service):
    """重命名明细给请求上限内的样本，total 用真实失败总数。"""
    history = {
        "total": 37,
        "failed": 34,
        "recent_failures": [
            {"name": f"dml-{index}.bin", "reason": "媒体识别失败", "time": "2026-10-29 10:00:00"}
            for index in range(20)
        ],
    }
    detail = service._rename_detail(_plugin(), history, {"archived": 34, "threshold": 3}, detail_limit=20)

    assert len(detail["items"]) == 20
    assert detail["total"] == 34 and detail["limit"] == 20 and detail["truncated"] is True


def test_module_details_apply_limit_and_error_block_metadata(service):
    """detail_limit 贯穿七个 builder；异常模块的错误块同样带 total/limit/truncated。"""
    def boom():
        raise RuntimeError("服务未初始化")

    plugin = _plugin(_failclean_service=SimpleNamespace(get_module_status=boom))
    details = service._module_details(plugin, {}, {}, detail_limit=50)

    assert details["failclean"]["error"].startswith("RuntimeError")
    assert (details["failclean"]["total"], details["failclean"]["limit"],
            details["failclean"]["truncated"]) == (0, 50, False)
    for key, detail in details.items():
        assert detail["limit"] == 50, key


def test_build_diagnostics_passes_detail_limit_through(service, monkeypatch):
    """真实链路：build_diagnostics 按 detail_limit 取失败样本并透传给明细块。"""
    seen = {}

    def fake_stats(plugin, recent_limit=5):
        seen["recent_limit"] = recent_limit
        return {"total": 1, "failed": 3, "recent_failures": []}

    monkeypatch.setattr(service, "_rename_history_stats", fake_stats)
    _register_package(monkeypatch, f"{PREFIX}.modules.autoremove.constants", REMOVER_STATE_DATA_KEY="remover_state")
    _register_package(monkeypatch, f"{PREFIX}.modules.failclean.constants", FAILCLEAN_STATUS_DATA_KEY="failclean_status")
    _register_package(monkeypatch, f"{PREFIX}.modules.transfer.tasks", load_transfer_tasks=lambda plugin: [])
    plugin = SimpleNamespace(
        plugin_name="下载中心",
        plugin_version="3.9.12",
        get_state=lambda: True,
        get_data=lambda key: {},
        service_info=lambda name: SimpleNamespace(instance=True, type="qbittorrent"),
        rename_archive_stats=lambda: {"archived": 0, "threshold": 3},
        _enabled=True,
        _transfer_enabled=True,
        _transfer_active=True,
        _transfer_fallback_enabled=False,
        _rename_enabled=True,
        _tag_enabled=True,
        _seed_autostart=True,
        _seed_skipverify=True,
        _frompath="/downloads",
        _topath="/downloads",
        _fromtorrentpath="",
    )

    payload = service.build_diagnostics(plugin, detail_limit=100)

    assert seen["recent_limit"] == 100
    assert payload["module_details"]["upload_limit"]["limit"] == 100


def test_diagnostics_check_contract(service):
    item = service._check("测试", "warn", "legacy")
    assert item["status"] == "warn"
    assert item["state"] == "pending"
    assert set(("time", "reason", "suggestion", "target")) <= item.keys()


def test_remote_path_check_stays_pending_with_target(service):
    item = service._check(
        "种子文件目录", "warn", "无法核实", state="pending",
        reason="无法确认该路径归属本机还是远端下载器，未做存在性判定",
        suggestion="请在该路径所属的下载器/主机上自行核对；本诊断不做跨主机存在性判定",
        target="/remote/not-present",
    )
    assert service._path_exists("/remote/not-present") is False
    assert item["state"] == "pending" and item["target"] == "/remote/not-present"
    assert item["status"] == "warn"


def test_diagnostics_snapshot_starts_unchecked(service):
    plugin = object()
    assert service.diagnostics_snapshot(plugin) == {"code": 0, "checked": False, "time": "", "checks": []}


@pytest.mark.parametrize(
    ("from_available", "to_available"),
    ((False, True), (True, False), (False, False), (True, True)),
)
def test_downloader_diagnostics_states_and_remote_path(service, monkeypatch,
                                                         from_available, to_available):
    """下载器连接问题为异常；下载器侧路径存在性保持未知。"""
    monkeypatch.setattr(service, "_first_enabled_task", lambda plugin: {
        "from_downloader": "源", "to_downloader": "目标",
    })
    statuses = {
        "源": {"available": from_available, "message": "源状态", "type": "qbittorrent"},
        "目标": {"available": to_available, "message": "目标状态", "type": "qbittorrent"},
    }
    monkeypatch.setattr(service, "_service_status", lambda plugin, name: statuses[name])
    monkeypatch.setattr(service, "_module_details", lambda *args, **kwargs: {})
    monkeypatch.setattr(service, "_rename_history_stats", lambda *args, **kwargs: {
        "total": 0, "failed": 0, "recent_failures": [],
    })

    plugin = SimpleNamespace(
        plugin_name="下载中心", plugin_version="3.9.12", get_state=lambda: True,
        get_data=lambda key: {}, rename_archive_stats=lambda: {"archived": 0, "threshold": 3},
        _enabled=True, _transfer_enabled=True, _transfer_active=True,
        _transfer_fallback_enabled=False, _rename_enabled=True, _tag_enabled=True,
        _seed_autostart=True, _seed_skipverify=True, _frompath="/downloads",
        _topath="/downloads", _fromtorrentpath="/remote/torrents",
    )

    payload = service.build_diagnostics(plugin)
    checks = {item["label"]: item for item in payload["checks"]}
    expected_state = "ok" if from_available else "error"
    assert checks["源下载器"]["state"] == expected_state
    assert checks["源下载器"]["status"] == expected_state
    expected_state = "ok" if to_available else "error"
    assert checks["目标下载器"]["state"] == expected_state
    assert checks["目标下载器"]["status"] == expected_state
    assert "paths" in payload
    assert payload["paths"]["fromtorrentpath_exists"] is None
