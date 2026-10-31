# -*- coding: utf-8 -*-
"""展示历史基础能力（B03）行为测试。

运行：
  C:/app/scoop/apps/micromamba/2.9.0-0/base/envs/mp3/python.exe -m pytest tests/v3/downloadmanagerlocal/test_execution_history.py -q

覆盖：并发追加、追加/清理交替、按流独立裁剪、稳定分页与非法参数、未初始化
状态、clear 不碰业务/保护/恢复键、保存失败无下载器副作用、白名单外 module
拒绝、result 白名单拒绝、深拷贝隔离。
"""

import copy
import importlib.machinery
import importlib.util
import sys
import threading
import types
from pathlib import Path
from unittest.mock import Mock

import pytest

from test_manual_run_endpoints import endpoints, PREFIX, FakeHTTPException

PLUGIN = Path(__file__).resolve().parents[3] / "plugins.v3/downloadmanagerlocal"


def _mk_module(monkeypatch, name, **attrs):
    result = types.ModuleType(name)
    path = attrs.get("__path__")
    result.__spec__ = importlib.machinery.ModuleSpec(name, None, is_package=path is not None)
    result.__dict__.update(attrs)
    monkeypatch.setitem(sys.modules, name, result)
    return result


def _load(monkeypatch, relpath, name):
    spec = importlib.util.spec_from_file_location(name, PLUGIN / relpath)
    result = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, result)
    spec.loader.exec_module(result)
    return result


class FakePlugin:
    """最小插件桩：内存存储 + 保存调用记录 + 可注入保存失败。"""

    def __init__(self, data=None, fail_save=False):
        self._data = dict(data or {})
        self.save_calls = []
        self.fail_save = fail_save
        self.downloader = Mock()

    def get_data(self, key=None):
        if key is None:
            return dict(self._data)
        return self._data.get(key)

    def save_data(self, key, value):
        if self.fail_save:
            raise RuntimeError("save failed")
        self.save_calls.append(key)
        self._data[key] = value


def _record(**overrides):
    base = {
        "trigger": "定时",
        "occurred_at": 1000.0,
        "action": "delete",
        "result": "success",
        "reason": "ok",
    }
    base.update(overrides)
    return base


@pytest.fixture
def history(monkeypatch):
    """加载真实 execution_history.py，仅桩掉 model.state 的依赖符号。"""
    _mk_module(monkeypatch, PREFIX, __path__=[str(PLUGIN)])
    _mk_module(monkeypatch, PREFIX + ".model", __path__=[str(PLUGIN / "model")])
    _mk_module(
        monkeypatch,
        PREFIX + ".model.state",
        EXECUTION_HISTORY_KEY="execution_history",
        EXECUTION_HISTORY_SCHEMA_VERSION=1,
        _HISTORY_LOCK=threading.RLock(),
    )
    return _load(monkeypatch, "model/execution_history.py", PREFIX + ".model.execution_history")


@pytest.fixture
def history_api(endpoints, monkeypatch):
    """在 endpoints 桩上补 execution-history 符号，加载真实 helper 供 handler 调用。"""
    state = sys.modules[PREFIX + ".model.state"]
    monkeypatch.setattr(state, "EXECUTION_HISTORY_KEY", "execution_history", raising=False)
    monkeypatch.setattr(state, "EXECUTION_HISTORY_SCHEMA_VERSION", 1, raising=False)
    monkeypatch.setattr(state, "_HISTORY_LOCK", threading.RLock(), raising=False)
    exec_history = _load(monkeypatch, "model/execution_history.py", PREFIX + ".model.execution_history")
    records = sys.modules[PREFIX + ".controller.records"]
    # 全量跑时 records/handlers 可能已被其它测试桩绑定到各自的 FakeHTTPException；
    # 这里统一到本文件导入的异常类，避免跨文件类不一致导致 pytest.raises 漏接。
    monkeypatch.setattr(records, "HTTPException", FakeHTTPException, raising=False)
    monkeypatch.setattr(endpoints.handlers, "HTTPException", FakeHTTPException, raising=False)
    return types.SimpleNamespace(
        handlers=endpoints.handlers,
        routes=endpoints.routes,
        exec_history=exec_history,
        records=records,
    )


# ── 存储层：并发 / 交替 / 裁剪 / 白名单 / 深拷贝 ──────────────────────

def test_concurrent_append_no_loss_no_dup(history):
    """并发追加 N 条后计数正确、record_id 无重复。"""
    plugin = FakePlugin()
    n = 250

    def worker(i):
        history.append(plugin, "autoremove", _record(occurred_at=float(i), action=f"w{i}"))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    items = history.query(plugin, "autoremove")["items"]
    assert len(items) == n
    ids = {item["record_id"] for item in items}
    assert len(ids) == n


def test_append_clear_interleaving_consistent(history):
    """交替追加/清理后数据自洽，清理只影响目标流。"""
    plugin = FakePlugin()
    history.append(plugin, "tag", _record(action="first"))
    assert history.clear(plugin, "tag") == 1
    history.append(plugin, "tag", _record(action="second"))
    snap = history.query(plugin, "tag")
    assert snap["initialized"] is True
    assert len(snap["items"]) == 1
    assert snap["items"][0]["action"] == "second"


def test_trim_1001_to_1000_independent_per_stream(history):
    """1001 条裁成 1000 条，且按流独立裁剪。"""
    plugin = FakePlugin()
    for i in range(1001):
        history.append(plugin, "autoremove", _record(occurred_at=float(i), action=f"a{i}"))
    for i in range(1001):
        history.append(plugin, "failclean", _record(occurred_at=float(i), action=f"f{i}"))

    ar = history.query(plugin, "autoremove")["items"]
    fc = history.query(plugin, "failclean")["items"]
    assert len(ar) == 1000
    assert len(fc) == 1000
    assert {item["occurred_at"] for item in ar} == set(range(1, 1001))
    assert {item["occurred_at"] for item in fc} == set(range(1, 1001))
    assert all(item["action"].startswith("a") for item in ar)
    assert all(item["action"].startswith("f") for item in fc)


def test_unknown_module_rejected(history):
    """白名单外的 module 必须被拒绝（明确错误，不静默接受）。"""
    plugin = FakePlugin()
    with pytest.raises(history.HistoryRecordError):
        history.append(plugin, "bogus", _record())
    with pytest.raises(history.HistoryRecordError):
        history.query(plugin, "bogus")
    with pytest.raises(history.HistoryRecordError):
        history.clear(plugin, "bogus")


def test_invalid_result_rejected(history):
    """result 非白名单值被拒绝，不得静默改语义。"""
    plugin = FakePlugin()
    with pytest.raises(history.HistoryRecordError):
        history.append(plugin, "tag", _record(result="verifying"))
    with pytest.raises(history.HistoryRecordError):
        history.append(plugin, "tag", _record(result="回滚中"))


def test_invalid_occurred_at_rejected(history):
    """occurred_at 非数值必须拒绝：不得静默存成 0（页面会显示成 1970）。"""
    plugin = FakePlugin()
    with pytest.raises(history.HistoryRecordError):
        history.append(plugin, "tag", _record(occurred_at="昨天"))
    with pytest.raises(history.HistoryRecordError):
        history.append(plugin, "tag", _record(occurred_at=None))
    with pytest.raises(history.HistoryRecordError):
        history.append(plugin, "tag", _record(occurred_at=""))


def test_return_values_are_deepcopied(history):
    """调用方改写返回值后存储不受影响。"""
    plugin = FakePlugin()
    appended = history.append(plugin, "autoremove", _record(reason="original"))
    appended["reason"] = "MUTATED"

    snap = history.query(plugin, "autoremove")
    assert snap["items"][0]["reason"] == "original"

    snap["items"][0]["reason"] = "MUTATED2"
    assert history.query(plugin, "autoremove")["items"][0]["reason"] == "original"


def test_deepcopy_nested_extra_field(history):
    """额外嵌套字段同样深拷贝，不共享可变对象。"""
    plugin = FakePlugin()
    history.append(plugin, "tag", _record(detail={"nested": [1, 2]}))
    snap = history.query(plugin, "tag")
    snap["items"][0]["detail"]["nested"].append(3)
    assert history.query(plugin, "tag")["items"][0]["detail"]["nested"] == [1, 2]


def test_clear_preserves_protected_keys(history):
    """clear 只影响新展示历史，不碰业务/保护/恢复键。"""
    protected = {
        "seed_recheck_queue": {"QB": {"h": {"phase": "verifying"}}},
        "transfer_schedule": {"queue": ["x"]},
        "hr_tasks": {"a": {}},
        "upload_limit_state": {"original": {"q": 1}, "last_written": 2},
        "transfer_stats": {"success_total": 3},
        "rename_records": {"h": {"original_name": "a"}},
    }
    plugin = FakePlugin(data={
        "execution_history": {"schema_version": 1, "streams": {"tag": [_record()]}},
        **protected,
    })
    before = copy.deepcopy(plugin._data)

    removed = history.clear(plugin, "tag")

    assert removed == 1
    for key in protected:
        assert plugin._data[key] == before[key], key
    assert plugin._data["execution_history"]["streams"]["tag"] == []
    assert plugin.save_calls == ["execution_history"]


def test_save_failure_no_downloader_action_and_no_side_effects(history):
    """save_data 抛错时无任何下载器调用、存储无副作用，异常原样上抛。"""
    plugin = FakePlugin(
        data={"execution_history": {"schema_version": 1, "streams": {"tag": []}}},
        fail_save=True,
    )
    before = copy.deepcopy(plugin._data)

    with pytest.raises(RuntimeError):
        history.append(plugin, "tag", _record())

    assert plugin.downloader.method_calls == []
    assert plugin._data == before


# ── 端点层：分页 / 三态 / 清理 / 路由 ──────────────────────────────

def test_query_endpoint_stable_pagination(history_api):
    """跨页不重不漏、时间倒序、总数与 total_pages 正确。"""
    plugin = FakePlugin()
    eh = history_api.exec_history
    for i in range(105):
        eh.append(plugin, "autoremove", _record(
            occurred_at=1000 + i,
            result="success" if i % 2 == 0 else "failed",
        ))

    page1 = history_api.handlers.api_execution_history(plugin, "autoremove", page=1, page_size=50)
    page2 = history_api.handlers.api_execution_history(plugin, "autoremove", page=2, page_size=50)
    page3 = history_api.handlers.api_execution_history(plugin, "autoremove", page=3, page_size=50)

    assert page1["total"] == 105
    assert page1["total_pages"] == 3
    assert len(page1["items"]) == 50
    assert len(page2["items"]) == 50
    assert len(page3["items"]) == 5

    combined = page1["items"] + page2["items"] + page3["items"]
    ids = [row["record_id"] for row in combined]
    assert len(ids) == 105
    assert len(set(ids)) == 105

    times = [row["occurred_at"] for row in combined]
    assert times == sorted(times, reverse=True)

    assert page1["initialized"] is True
    assert page1["note"] == ""
    assert page1["stream"] == "autoremove"


def test_query_endpoint_rejects_illegal_params(history_api):
    """page=0 / page_size=30 / 未知 result_filter / 未知 module → 400。"""
    plugin = FakePlugin()
    handler = history_api.handlers.api_execution_history

    with pytest.raises(FakeHTTPException) as exc:
        handler(plugin, "autoremove", page=0)
    assert exc.value.status_code == 400

    with pytest.raises(FakeHTTPException) as exc:
        handler(plugin, "autoremove", page=1, page_size=30)
    assert exc.value.status_code == 400

    with pytest.raises(FakeHTTPException) as exc:
        handler(plugin, "autoremove", page=1, page_size=20, result_filter="unknown")
    assert exc.value.status_code == 400

    with pytest.raises(FakeHTTPException) as exc:
        handler(plugin, "bogus", page=1, page_size=20)
    assert exc.value.status_code == 400
    assert "未知历史流" in exc.value.detail


def test_query_endpoint_uninitialized_vs_empty(history_api):
    """未初始化返回「尚无新记录」；清理后为空则是已初始化空结果。"""
    uninitialized = history_api.handlers.api_execution_history(FakePlugin(), "autoremove")
    assert uninitialized["items"] == []
    assert uninitialized["total"] == 0
    assert uninitialized["initialized"] is False
    assert uninitialized["note"] == "尚无新记录"

    plugin = FakePlugin()
    eh = history_api.exec_history
    eh.append(plugin, "autoremove", _record())
    eh.clear(plugin, "autoremove")
    empty = history_api.handlers.api_execution_history(plugin, "autoremove")
    assert empty["items"] == []
    assert empty["initialized"] is True
    assert empty["note"] == ""


def test_route_wrapper_get_post_precedence_and_unknown_field(history_api):
    """GET/POST 等价、显式 query 优先、未知 body 字段拒绝。"""
    plugin = FakePlugin()
    eh = history_api.exec_history
    for i in range(30):
        eh.append(plugin, "autoremove", _record(occurred_at=1000 + i))

    handler = history_api.handlers.api_execution_history
    endpoint = history_api.records.record_history_endpoint(handler, plugin)

    get = endpoint(module="autoremove", page="2", page_size="20")
    post = endpoint(payload={"module": "autoremove", "page": 2, "page_size": 20})
    assert get == post

    mixed = endpoint(module="autoremove", page="1", page_size="20", payload={"page": 2, "page_size": 50})
    assert mixed["page"] == 1
    assert mixed["page_size"] == 20

    with pytest.raises(FakeHTTPException) as exc:
        endpoint(payload={"module": "autoremove", "bogus": 1})
    assert exc.value.status_code == 400
    assert "未知字段" in exc.value.detail

    with pytest.raises(FakeHTTPException) as exc:
        endpoint(payload={"page": 1})
    assert exc.value.status_code == 400
    assert "module 必填" in exc.value.detail


def test_clear_endpoint_rejects_unknown_module(history_api):
    plugin = FakePlugin()
    with pytest.raises(FakeHTTPException) as exc:
        history_api.handlers.api_execution_history_clear(plugin, {"module": "bogus"})
    assert exc.value.status_code == 400
    assert "未知历史流" in exc.value.detail


def test_clear_endpoint_clears_only_history(history_api):
    plugin = FakePlugin(data={
        "execution_history": {"schema_version": 1, "streams": {"tag": [_record()]}},
        "seed_recheck_queue": {"keep": {}},
    })
    response = history_api.handlers.api_execution_history_clear(plugin, {"module": "tag"})
    assert response.success is True
    assert response.data.removed == 1
    assert response.data.module == "tag"
    assert plugin._data["seed_recheck_queue"] == {"keep": {}}
    assert plugin._data["execution_history"]["streams"]["tag"] == []


def test_new_routes_registered(history_api):
    """两条新路由齐全：GET/POST 查询 + POST 清理，auth=bear。"""
    routes = history_api.routes.build_api_routes(Mock())
    assert len(routes) == 42
    by_path = {route["path"]: route for route in routes}

    query = by_path["/execution_history"]
    assert query["methods"] == ["GET", "POST"]
    assert query["auth"] == "bear"
    assert query["summary"] == "获取模块展示历史"

    clear = by_path["/execution_history_clear"]
    assert clear["methods"] == ["POST"]
    assert clear["auth"] == "bear"
    assert clear["summary"] == "清空模块展示历史"
