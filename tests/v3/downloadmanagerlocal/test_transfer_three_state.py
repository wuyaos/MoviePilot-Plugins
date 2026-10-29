"""P2-1e 三态继承：真实解析、配置生命周期、API 投影及删除决策，外部 IO 替身。"""
import copy
import importlib.util
import json
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from test_transfer_tasks_engine import tt, tr  # noqa: F401
from test_transfer_pipeline import runtime, cycle  # noqa: F401
from test_gating import gating  # noqa: F401
from test_manual_run_endpoints import endpoints, _transfer_status_stubs, PLUGIN, PREFIX  # noqa: F401

MISSING = object()
VALUES = [True, False, "inherit", MISSING, "False", "false", "0", 0, 1, None, [], {}]
FIELDS = [("delete_source", False), ("delete_duplicate", True)]


@pytest.fixture
def delete_defaults_runtime(monkeypatch, request):
    # 既有全套夹具有残留同名适配器替身；此处隔离后再调用真实配置夹具。
    for name in list(sys.modules):
        if name.startswith(PREFIX + "."):
            monkeypatch.delitem(sys.modules, name)
    return request.getfixturevalue("gating")


@pytest.mark.parametrize("field,legacy", FIELDS)
@pytest.mark.parametrize("global_default", [False, True])
@pytest.mark.parametrize("value", VALUES)
def test_resolve_task_flag_matrix(tt, field, legacy, global_default, value):
    task = {} if value is MISSING else {field: value}
    expected = ((value, "task") if type(value) is bool else
                (global_default, "global") if value == "inherit" else
                (legacy, "legacy-default"))
    before = copy.deepcopy(task)
    assert tt.resolve_task_flag(task, field, global_default) == expected
    assert task == before
    tt.logger.warning.assert_not_called()  # 解析本身纯函数，日志在输入规范化边界。


@pytest.mark.parametrize("field,legacy", FIELDS)
def test_only_inherit_follows_global_flip(tt, field, legacy):
    for value in VALUES:
        task = {} if value is MISSING else {field: value}
        before = tt.resolve_task_flag(task, field, False)
        after = tt.resolve_task_flag(task, field, True)
        if value == "inherit":
            assert before == (False, "global") and after == (True, "global")
        else:
            assert before == after
    assert tt.resolve_task_flag({}, field, False) == (legacy, "legacy-default")


@pytest.mark.parametrize("field,legacy", FIELDS)
@pytest.mark.parametrize("value", ["False", "false", "0", 0, 1, None, [], {}])
def test_invalid_value_warns_once_and_preserves_raw(tt, field, legacy, value):
    task = tt._normalize_task(dict(name="风险测试", from_downloader="A", to_downloader="B", **{field: value}), 0)
    assert task[field] == value
    assert tt.resolve_task_flag(task, field, False) == (legacy, "legacy-default")
    tt.logger.warning.assert_called_once()
    message = tt.logger.warning.call_args.args[0]
    assert "风险测试" in message and repr(value) in message and field in message


def test_storage_roundtrip_missing_and_new_template(tt):
    old = dict(name="旧任务", from_downloader="A", to_downloader="B")
    plugin = SimpleNamespace(_transfer_tasks=json.dumps([old]), _transfer_tasks_migrated=True)
    tasks = tt.load_transfer_tasks(plugin)
    assert "delete_source" not in tasks[0] and "delete_duplicate" not in tasks[0]
    plugin._transfer_tasks = json.dumps(tasks)
    assert isinstance(plugin._transfer_tasks, str)
    saved = tt.load_transfer_tasks(plugin)[0]
    assert "delete_source" not in saved and "delete_duplicate" not in saved
    assert tt.resolve_task_flag(saved, "delete_source", True) == (False, "legacy-default")
    assert tt.resolve_task_flag(saved, "delete_duplicate", False) == (True, "legacy-default")
    for field, _ in FIELDS:
        assert tt._TASK_DEFAULTS[field] == "inherit"
        assert tt.resolve_task_flag(tt._TASK_DEFAULTS, field, False) == (False, "global")


@pytest.mark.parametrize("old", [False, True])
@pytest.mark.parametrize("explicit", [MISSING, False, True])
def test_global_defaults_migrate_without_overwriting_explicit(delete_defaults_runtime, old, explicit):
    gating = delete_defaults_runtime
    config = {"deletesource": old, "deleteduplicate": old}
    keys = ["transfer_delete_source_default", "transfer_delete_duplicate_default"]
    if explicit is not MISSING:
        config.update(dict.fromkeys(keys, explicit))
    plugin = SimpleNamespace()
    result = gating.service.initialize_runtime_config(plugin, config)
    expected = old if explicit is MISSING else explicit
    for key in keys:
        assert result[key] is expected
        assert getattr(plugin, "_" + key) is expected
    assert result["deletesource"] is old and result["deleteduplicate"] is old
    assert gating.service.initialize_runtime_config(SimpleNamespace(), result) == result


def test_fresh_defaults_and_invalid_global_not_truthy(delete_defaults_runtime):
    gating = delete_defaults_runtime
    plugin = SimpleNamespace()
    assert gating.service.initialize_runtime_config(plugin, {}) == {}
    assert plugin._transfer_delete_source_default is False
    assert plugin._transfer_delete_duplicate_default is False
    assert gating.utils.transfer_delete_defaults({"deletesource": "false", "deleteduplicate": 1}) == {
        "transfer_delete_source_default": False, "transfer_delete_duplicate_default": False,
    }


def test_legacy_task_migration_keeps_explicit_overrides(tt):
    plugin = SimpleNamespace(_fromdownloader="A", _todownloader="B", _deletesource=False, _deleteduplicate=True)
    task = tt.load_transfer_tasks(plugin)[0]
    assert tt.resolve_task_flag(task, "delete_source", True) == (False, "task")
    assert tt.resolve_task_flag(task, "delete_duplicate", False) == (True, "task")


@pytest.mark.parametrize("global_default", [False, True])
def test_transfer_status_additive_raw_and_effective(endpoints, monkeypatch, global_default):
    _transfer_status_stubs(monkeypatch, {})
    name = PREFIX + ".modules.transfer.tasks"
    spec = importlib.util.spec_from_file_location(name, PLUGIN / "modules/transfer/tasks.py")
    tasks_module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, tasks_module)
    spec.loader.exec_module(tasks_module)
    raw = [dict(name=str(i), from_downloader="A", to_downloader="B", **(
        {} if value is MISSING else {"delete_source": value, "delete_duplicate": value}))
        for i, value in enumerate(VALUES)]
    serialized = json.dumps(raw)
    plugin = SimpleNamespace(_transfer_tasks=serialized, _transfer_tasks_migrated=True,
                             _transfer_delete_source_default=global_default,
                             _transfer_delete_duplicate_default=global_default,
                             get_data=lambda key=None: None if key else {})
    status = endpoints.handlers.api_transfer_status(plugin)["status"]
    for row, original in zip(status["tasks"], raw):
        for field, _ in FIELDS:
            assert row[field] == original.get(field)
            effective, origin = tasks_module.resolve_task_flag(original, field, global_default)
            assert row[field + "_effective"] is effective
            assert row[field + "_origin"] == origin
    assert status["tasks"][3]["delete_duplicate"] is None
    assert status["tasks"][3]["delete_duplicate_effective"] is True
    assert status["tasks"][3]["delete_duplicate_origin"] == "legacy-default"
    assert plugin._transfer_tasks == serialized
    assert status["total"] == 0 and status["page_size"] == 20


def _service_case(tr, monkeypatch, value, global_default, duplicate):
    source, target = Mock(), Mock()
    source.get_completed_torrents.return_value = [{"hash": "abc", "state": "pausedUP"}]
    target.get_torrents.return_value = ([{"state": "pausedUP"}] if duplicate else [], None)
    services = {"A": SimpleNamespace(name="A", type="qbittorrent", instance=source),
                "B": SimpleNamespace(name="B", type="qbittorrent", instance=target)}
    plugin = SimpleNamespace(service_info=services.get, _scan_limit=500,
                             _transfer_delete_source_default=global_default,
                             _transfer_delete_duplicate_default=global_default,
                             get_hash=lambda *a: "abc", get_save_path=lambda *a: "/data",
                             get_label=lambda *a: [], get_category=lambda *a: "",
                             get_data=lambda *a: {}, convert_save_path=lambda *a: "/data")
    task = dict(name="决策", from_downloader="A", to_downloader="B", no_paths="",
                include_category="", include_labels="", exclude_labels="", empty_label_ok=True,
                from_path="", to_path="")
    if value is not MISSING:
        task.update(delete_source=value, delete_duplicate=value)
    monkeypatch.setattr(tr, "_transfer_stopped", lambda *a: False)
    monkeypatch.setattr(tr, "_transfer_delay_status", lambda *a: (False, 0, 0))
    monkeypatch.setattr(tr, "get_torrent_payloads", Mock(return_value={"abc": b"payload"}))
    monkeypatch.setattr(tr, "delete_source", Mock(return_value="deleted"))
    monkeypatch.setattr(tr, "begin_transfer", Mock(return_value=True))
    totals = dict(success=0, fail=0, skip=0, del_dup=0)
    tr._run_task(plugin, task, "手动", 0, totals)
    return totals


@pytest.mark.parametrize("value", VALUES[:10])
@pytest.mark.parametrize("global_default", [False, True])
def test_service_duplicate_branch_uses_effective(tr, monkeypatch, value, global_default):
    totals = _service_case(tr, monkeypatch, value, global_default, duplicate=True)
    expected = value if type(value) is bool else global_default if value == "inherit" else True
    assert tr.delete_source.call_count == int(expected)
    assert totals["del_dup"] == int(expected)
    if expected:
        tr.delete_source.assert_called_once_with(tr.delete_source.call_args.args[0], "A", "abc")


@pytest.mark.parametrize("value", VALUES[:10])
@pytest.mark.parametrize("global_default", [False, True])
def test_service_submission_passes_resolved_bool(tr, monkeypatch, value, global_default):
    totals = _service_case(tr, monkeypatch, value, global_default, duplicate=False)
    expected = value if type(value) is bool else global_default if value == "inherit" else False
    assert tr.begin_transfer.call_args.kwargs["delete_source"] is expected
    assert totals["success"] == 1


@pytest.mark.parametrize("value", VALUES[:10])
@pytest.mark.parametrize("global_default", [False, True])
def test_pipeline_delete_decision_uses_resolved_snapshot(runtime, tt, value, global_default):
    r = runtime
    task = {} if value is MISSING else {"delete_source": value}
    effective, _ = tt.resolve_task_flag(task, "delete_source", global_default)
    assert r.pipeline.begin_transfer(r.plugin, r.services["source"], r.services["target"],
                                     "abc", {"state": "uploading"}, lambda: "abc", lambda: False,
                                     delete_source=effective)
    assert r.data["queue"]["target::abc"]["delete_source_requested"] is effective
    # 完整目标通过真实事务的校验/启动确认后，才可能进入删除。
    cycle(r)
    cycle(r, "checkingUP")
    cycle(r)
    cycle(r, "stalledUP")
    assert r.source.delete_torrents.call_count == int(effective)
    if effective:
        r.source.delete_torrents.assert_called_once_with(delete_file=False, ids=["abc"])
