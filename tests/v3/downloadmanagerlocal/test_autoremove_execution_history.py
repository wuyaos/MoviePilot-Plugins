# -*- coding: utf-8 -*-
"""自动删种接入展示历史（B04）行为测试。

运行：
  C:/app/scoop/apps/micromamba/2.9.0-0/base/envs/mp3/python.exe -m pytest tests/v3/downloadmanagerlocal/test_autoremove_execution_history.py -q

覆盖：pause/delete/deletefile 成功逐条记录、假值/异常失败、H&R 保护跳过、
回读缺失跳过、下载器级失败只记一条、预览不写记录、历史写入失败不影响业务、
轮次统计与记录可解释、clear 不触发下载器动作。
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
import threading
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

PLUGIN = Path(__file__).resolve().parents[3] / "plugins.v3" / "downloadmanagerlocal"
PREFIX = "app.plugins.downloadmanagerlocal"


class FakePlugin:
    """最小插件桩：内存存储 + 保存调用记录 + 可注入保存失败 + 下载器服务表。"""

    def __init__(self, data=None, fail_save=False):
        self._data = dict(data or {})
        self.fail_save = fail_save
        self.save_calls = []
        self.services = {}

    def get_data(self, key=None):
        if key is None:
            return dict(self._data)
        return self._data.get(key)

    def save_data(self, key, value):
        if self.fail_save:
            raise RuntimeError("save failed")
        self.save_calls.append(key)
        self._data[key] = value

    def service_info(self, name):
        return self.services.get(name)


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
def autoremove(monkeypatch):
    """加载真实 service.py 与真实 execution_history.py；model.state/扫描器/守卫用替身。"""

    def module(name, **attrs):
        path = attrs.pop("__path__", None)
        result = types.ModuleType(name)
        result.__spec__ = importlib.machinery.ModuleSpec(
            name, None, is_package=path is not None)
        if path is not None:
            result.__path__ = [str(path)]
        result.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, result)
        return result

    def load(relpath, name):
        spec = importlib.util.spec_from_file_location(name, PLUGIN / relpath)
        result = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, result)
        spec.loader.exec_module(result)
        return result

    logger = Mock()
    module("app")
    module("app.sdk")
    module("app.sdk.logging", logger=logger)
    module("app.sdk.config", settings=Mock())
    module("app.schemas")
    module("app.schemas.types", MessageType=Mock())
    module("app.modules")
    module("app.modules.qbittorrent", Qbittorrent=type("Qbittorrent", (), {}))
    module("app.modules.transmission", Transmission=type("Transmission", (), {}))
    module("app.plugins")
    module(PREFIX, __path__=[str(PLUGIN)])

    module(PREFIX + ".modules", __path__=[str(PLUGIN / "modules")])
    module(PREFIX + ".modules.hr", __path__=[str(PLUGIN / "modules/hr")])
    module(PREFIX + ".modules.hr.guard",
           HrGuard=Mock(return_value=SimpleNamespace(should_skip=Mock(return_value=False))),
           SKIP_PATH_AUTO_REMOVE="auto_remove")

    # model：真实 execution_history（B03 交付）+ 替身 state
    module(PREFIX + ".model", __path__=[str(PLUGIN / "model")])
    module(PREFIX + ".model.state",
           EXECUTION_HISTORY_KEY="execution_history",
           EXECUTION_HISTORY_SCHEMA_VERSION=1,
           _HISTORY_LOCK=threading.RLock())
    exec_history = load("model/execution_history.py", PREFIX + ".model.execution_history")

    module(PREFIX + ".utils", __path__=[str(PLUGIN / "utils")])
    module(PREFIX + ".utils.config",
           module_active=Mock(return_value=True),
           module_observe_only=Mock(return_value=False))
    module(PREFIX + ".utils.torrent_adapter", delete_torrent_with_files=Mock())

    package = PREFIX + ".modules.autoremove"
    module(package, __path__=[str(PLUGIN / "modules/autoremove")])
    module(package + ".rules", parse_remover_config=Mock())
    scanner = module(package + ".scanner",
                     build_snapshot=Mock(), downloader_type=Mock(),
                     read_torrents=Mock(), torrent_hash=Mock())
    constants = load("modules/autoremove/constants.py", package + ".constants")
    models = load("modules/autoremove/models.py", package + ".models")
    criteria = load("modules/autoremove/criteria.py", package + ".criteria")
    history = load("modules/autoremove/history.py", package + ".history")
    service = load("modules/autoremove/service.py", package + ".service")

    return SimpleNamespace(
        service=service, scanner=scanner, constants=constants,
        models=models, criteria=criteria, exec_history=exec_history,
        history=history, logger=logger,
    )


def _snapshot(models, downloader="QB1", hash_="abc", name="seed", site="test"):
    return models.RemoveSnapshot(
        downloader=downloader,
        downloader_type="qbittorrent",
        torrent_hash=hash_,
        name=name,
        size=1024,
        ratio=0.0,
        seeding_seconds=0.0,
        uploaded=0.0,
        save_path="/data",
        current_tracker="https://tracker.test/a",
        trackers=("https://tracker.test/a",),
        site=site,
        state="seeding",
        category="",
        tags=(),
        error_string="",
    )


def _candidate(models, hash_="abc", name="seed", site="test"):
    return models.RemoveCandidate(
        snapshot=_snapshot(models, hash_=hash_, name=name, site=site), reason="命中")


def _detail():
    return {
        "downloader": "QB1",
        "candidates": 0,
        "paused": 0,
        "deleted": 0,
        "deleted_files": 0,
        "skipped_protected": 0,
        "skipped_missing": 0,
        "skipped": 0,
        "failed": 0,
        "failed_operations": 0,
        "error": "",
    }


def _configure(autoremove, plugin, *, instance, torrents=(), read_error=None):
    plugin.services["QB1"] = SimpleNamespace(type="qbittorrent", instance=instance)
    autoremove.scanner.downloader_type.return_value = "qbittorrent"
    autoremove.scanner.torrent_hash.side_effect = lambda torrent, dl_type: torrent["hash"]
    autoremove.scanner.read_torrents.return_value = (list(torrents), read_error or "")
    service = autoremove.service.AutoRemoveService(plugin)
    service._stopped = False
    return service

def _run_downloader(service, *args, **kwargs):
    """按 run_cycle 的方式调用 _execute_downloader：收集后锁外落库，测试共用同一出口。"""
    records: list[dict] = []
    executed = service._execute_downloader(*args, records, **kwargs)
    service._flush_history(records)
    return executed


# ── 逐条记录：真实动作出口的五分支 + 下载器级失败 ──────────────────────

@pytest.mark.parametrize("action,method", [
    ("pause", "stop_torrents"),
    ("delete", "delete_torrents"),
])
def test_success_action_records_success(autoremove, action, method):
    plugin = FakePlugin()
    instance = Mock()
    getattr(instance, method).return_value = True
    service = _configure(autoremove, plugin, instance=instance, torrents=[{"hash": "abc"}])

    detail = _detail()
    candidate = _candidate(autoremove.models, hash_="abc", name="seed", site="test")
    executed = _run_downloader(service,
        "QB1", [candidate], detail, SimpleNamespace(action=action), "手动")

    assert executed == [candidate]
    items = autoremove.exec_history.query(plugin, "autoremove")["items"]
    assert len(items) == 1
    record = items[0]
    assert record["result"] == "success"
    assert record["action"] == action
    assert record["trigger"] == "手动"
    assert record["downloader_id"] == "QB1"
    assert record["torrent_hash"] == "abc"
    assert record["name"] == "seed"
    assert record["site"] == "test"
    assert record["occurred_at"] > 0


def test_deletefile_success_records_action_deletefile(autoremove):
    plugin = FakePlugin()
    instance = Mock()
    service = _configure(autoremove, plugin, instance=instance, torrents=[{"hash": "abc"}])

    detail = _detail()
    candidate = _candidate(autoremove.models, hash_="abc", name="seed", site="test")
    executed = _run_downloader(service,
        "QB1", [candidate], detail, SimpleNamespace(action="deletefile"), "手动")

    assert executed == [candidate]
    assert detail["deleted"] == 1
    assert detail["deleted_files"] == 1
    autoremove.service.delete_torrent_with_files.assert_called_once_with(
        instance, "abc", delete_file=True)
    items = autoremove.exec_history.query(plugin, "autoremove")["items"]
    assert len(items) == 1
    assert items[0]["result"] == "success"
    assert items[0]["action"] == "deletefile"


def test_falsy_action_result_records_failed(autoremove):
    plugin = FakePlugin()
    instance = Mock()
    instance.delete_torrents.return_value = False  # 字面 False = 未获确认（_apply_action 用 is not False 判真）
    service = _configure(autoremove, plugin, instance=instance, torrents=[{"hash": "abc"}])

    detail = _detail()
    candidate = _candidate(autoremove.models, hash_="abc", name="seed")
    executed = _run_downloader(service,
        "QB1", [candidate], detail, SimpleNamespace(action="delete"), "手动")

    assert executed == []
    assert detail["failed"] == 1
    instance.delete_torrents.assert_called_once_with(delete_file=False, ids=["abc"])
    items = autoremove.exec_history.query(plugin, "autoremove")["items"]
    assert len(items) == 1
    assert items[0]["result"] == "failed"
    assert items[0]["reason"] == "下载器未确认执行结果"


def test_action_exception_records_failed(autoremove):
    plugin = FakePlugin()
    instance = Mock()
    instance.delete_torrents.side_effect = RuntimeError("boom")
    service = _configure(autoremove, plugin, instance=instance, torrents=[{"hash": "abc"}])

    detail = _detail()
    candidate = _candidate(autoremove.models, hash_="abc", name="seed")
    executed = _run_downloader(service,
        "QB1", [candidate], detail, SimpleNamespace(action="delete"), "手动")

    assert executed == []
    assert detail["failed"] == 1
    items = autoremove.exec_history.query(plugin, "autoremove")["items"]
    assert len(items) == 1
    assert items[0]["result"] == "failed"
    assert "执行异常" in items[0]["reason"]
    assert "boom" in items[0]["reason"]


def test_protection_skip_records_skipped_not_success(autoremove):
    plugin = FakePlugin()
    instance = Mock()
    instance.delete_torrents.return_value = True
    service = _configure(autoremove, plugin, instance=instance, torrents=[{"hash": "abc"}])
    autoremove.service.HrGuard.return_value.should_skip.return_value = True

    detail = _detail()
    candidate = _candidate(autoremove.models, hash_="abc", name="seed")
    executed = _run_downloader(service,
        "QB1", [candidate], detail, SimpleNamespace(action="delete"), "手动")

    assert executed == []
    assert detail["skipped_protected"] == 1
    assert detail["deleted"] == 0
    instance.delete_torrents.assert_not_called()
    items = autoremove.exec_history.query(plugin, "autoremove")["items"]
    assert len(items) == 1
    assert items[0]["result"] == "skipped"
    assert items[0]["reason"] == "H&R 保护跳过"
    assert all(item["result"] != "success" for item in items)


def test_missing_candidate_records_skipped(autoremove):
    plugin = FakePlugin()
    instance = Mock()
    instance.delete_torrents.return_value = True
    # fresh 集合里没有 abc（只有 other），且空名/空站点走既有回退
    service = _configure(autoremove, plugin, instance=instance, torrents=[{"hash": "other"}])

    detail = _detail()
    candidate = _candidate(autoremove.models, hash_="abc", name="", site="")
    executed = _run_downloader(service,
        "QB1", [candidate], detail, SimpleNamespace(action="delete"), "手动")

    assert executed == []
    assert detail["skipped_missing"] == 1
    assert detail["deleted"] == 0
    instance.delete_torrents.assert_not_called()
    items = autoremove.exec_history.query(plugin, "autoremove")["items"]
    assert len(items) == 1
    assert items[0]["result"] == "skipped"
    assert items[0]["reason"] == "候选已不在下载器中"
    assert items[0]["torrent_hash"] == "abc"
    assert items[0]["name"] == "abc"  # name 回退为 torrent_hash
    assert "site" not in items[0]  # 空 site 不写入


def test_instance_unavailable_records_single_downloader_failure(autoremove):
    plugin = FakePlugin()
    plugin.services["QB1"] = None  # service_info 返回 None
    service = autoremove.service.AutoRemoveService(plugin)
    service._stopped = False

    detail = _detail()
    candidates = [
        _candidate(autoremove.models, hash_="a"),
        _candidate(autoremove.models, hash_="b"),
    ]
    executed = _run_downloader(service,
        "QB1", candidates, detail, SimpleNamespace(action="delete"), "手动")

    assert executed == []
    assert detail["failed"] == 2  # 业务计数仍按候选数
    items = autoremove.exec_history.query(plugin, "autoremove")["items"]
    assert len(items) == 1  # 只记一条下载器级失败
    record = items[0]
    assert record["result"] == "failed"
    assert record["downloader_id"] == "QB1"
    assert "torrent_hash" not in record
    assert "整批" in record["reason"]


def test_read_back_failure_records_single_downloader_failure(autoremove):
    plugin = FakePlugin()
    instance = Mock()
    service = _configure(autoremove, plugin, instance=instance, read_error="read failed")

    detail = _detail()
    candidates = [
        _candidate(autoremove.models, hash_="a"),
        _candidate(autoremove.models, hash_="b"),
    ]
    executed = _run_downloader(service,
        "QB1", candidates, detail, SimpleNamespace(action="delete"), "手动")

    assert executed == []
    assert detail["failed"] == 2
    items = autoremove.exec_history.query(plugin, "autoremove")["items"]
    assert len(items) == 1
    record = items[0]
    assert record["result"] == "failed"
    assert "回读" in record["reason"]
    assert "read failed" in record["reason"]
    assert "torrent_hash" not in record


def test_collect_candidates_preview_writes_no_records(autoremove, monkeypatch):
    plugin = FakePlugin()
    instance = Mock()
    plugin.services["QB1"] = SimpleNamespace(type="qbittorrent", instance=instance)
    autoremove.scanner.downloader_type.return_value = "qbittorrent"
    autoremove.scanner.read_torrents.return_value = ([{"hash": "abc"}], "")
    snapshot = _snapshot(autoremove.models, hash_="abc", name="seed", site="test")
    autoremove.scanner.build_snapshot.return_value = snapshot

    service = autoremove.service.AutoRemoveService(plugin)
    service._stopped = False
    service._config = autoremove.models.RemoverConfig(
        enabled=True, action="delete", downloaders=["QB1"])
    service._config_error = ""
    service._conditions = SimpleNamespace(required_tags=None, same_data=False)
    monkeypatch.setattr(autoremove.service, "match_reason", lambda conditions, snap: "命中")

    result = service.collect_candidates("候选预览")
    assert result["candidates"] == 1
    assert instance.stop_torrents.call_count == 0
    assert instance.delete_torrents.call_count == 0
    assert autoremove.exec_history.query(plugin, "autoremove")["items"] == []


def test_history_write_failure_preserves_business_outcome(autoremove):
    plugin = FakePlugin(fail_save=True)
    instance = Mock()
    instance.delete_torrents.return_value = True
    service = _configure(autoremove, plugin, instance=instance, torrents=[{"hash": "abc"}])

    detail = _detail()
    candidate = _candidate(autoremove.models, hash_="abc", name="seed")
    executed = _run_downloader(service,
        "QB1", [candidate], detail, SimpleNamespace(action="delete"), "手动")

    assert executed == [candidate]
    assert detail["deleted"] == 1
    instance.delete_torrents.assert_called_once_with(delete_file=False, ids=["abc"])
    assert autoremove.exec_history.query(plugin, "autoremove")["items"] == []
    # 失败被单独记日志，不吞掉、不虚构已持久化
    assert autoremove.logger.error.called
    assert any(
        "写入展示历史失败" in str(call.args[0])
        for call in autoremove.logger.error.call_args_list)


def test_round_counts_reconcile_with_records(autoremove):
    plugin = FakePlugin()
    instance = Mock()

    def delete_effect(delete_file, ids):
        return ids[0] != "fail"

    instance.delete_torrents.side_effect = delete_effect
    # ok/prot/fail 在 fresh 集合里，gone 缺失
    service = _configure(
        autoremove, plugin, instance=instance,
        torrents=[{"hash": "ok"}, {"hash": "prot"}, {"hash": "fail"}])
    autoremove.service.HrGuard.return_value.should_skip.side_effect = (
        lambda path, downloader, hash_: hash_ == "prot")

    candidates = [
        _candidate(autoremove.models, hash_="ok", name="ok"),
        _candidate(autoremove.models, hash_="gone", name="gone"),
        _candidate(autoremove.models, hash_="prot", name="prot"),
        _candidate(autoremove.models, hash_="fail", name="fail"),
    ]
    detail = _detail()
    executed = _run_downloader(service,
        "QB1", candidates, detail, SimpleNamespace(action="delete"), "定时")

    assert len(executed) == 1
    assert detail["deleted"] == 1
    assert detail["skipped_protected"] == 1
    assert detail["skipped_missing"] == 1
    assert detail["failed"] == 1

    items = autoremove.exec_history.query(plugin, "autoremove")["items"]
    by_result = {}
    for item in items:
        by_result[item["result"]] = by_result.get(item["result"], 0) + 1
    assert len(items) == 4
    assert by_result.get("success", 0) == 1 == detail["deleted"]
    assert by_result.get("skipped", 0) == 2 == detail["skipped_protected"] + detail["skipped_missing"]
    assert by_result.get("failed", 0) == 1 == detail["failed"]


def test_execution_history_clear_triggers_no_downloader_action(autoremove):
    plugin = FakePlugin()
    instance = Mock()
    plugin.services["QB1"] = SimpleNamespace(type="qbittorrent", instance=instance)

    autoremove.exec_history.append(plugin, "autoremove", _record())

    removed = autoremove.exec_history.clear(plugin, "autoremove")
    assert removed == 1
    assert instance.method_calls == []
    assert autoremove.exec_history.query(plugin, "autoremove")["items"] == []


# ── B04b：锁序（落库必须在模块锁之外）与裁决②（failed_operations） ──────

def test_run_cycle_flushes_history_outside_module_lock(autoremove, monkeypatch):
    """锁序断言（可执行，非口头声明）：run_cycle 落库时模块锁已释放。"""
    plugin = FakePlugin()
    instance = Mock()
    instance.delete_torrents.return_value = True
    service = _configure(autoremove, plugin, instance=instance, torrents=[{"hash": "abc"}])
    service._config = autoremove.models.RemoverConfig(
        enabled=True, action="delete", downloaders=["QB1"], notify=False)
    service._config_error = ""
    service._observe_only = False  # 构造未走 initialize，需显式关观察期才会执行
    service._conditions = SimpleNamespace(required_tags=None, same_data=False, action="delete")
    autoremove.scanner.build_snapshot.return_value = _snapshot(autoremove.models)
    monkeypatch.setattr(autoremove.service, "match_reason", lambda conditions, snap: "命中")

    lock_held: list[bool] = []
    original_save = plugin.save_data

    def spy_save(key, value):
        if key == "execution_history":
            lock_held.append(service._lock._is_owned())
        return original_save(key, value)

    plugin.save_data = spy_save
    result = service.run_cycle("定时")

    assert result["deleted"] == 1
    assert lock_held == [False]  # 写入展示历史时未持模块锁
    items = autoremove.exec_history.query(plugin, "autoremove")["items"]
    assert len(items) == 1
    assert items[0]["result"] == "success"
    # 业务状态仍落盘（历史落库不影响既有状态保存）
    assert "remover_state" in plugin.save_calls


def test_batch_failure_separates_failed_operations(autoremove):
    """裁决②：批量失败时 failed=N（工作量），failed_operations=1（=记录条数）。"""
    plugin = FakePlugin()
    plugin.services["QB1"] = None  # 执行前下载器不可用 → 整批未执行
    service = autoremove.service.AutoRemoveService(plugin)
    service._stopped = False

    detail = _detail()
    candidates = [_candidate(autoremove.models, hash_=f"h{i}") for i in range(4)]
    executed = _run_downloader(
        service, "QB1", candidates, detail, SimpleNamespace(action="delete"), "定时")

    assert executed == []
    assert detail["failed"] == 4  # 既有语义不变：影响 4 个候选
    assert detail["failed_operations"] == 1  # 新语义：1 次失败操作
    items = autoremove.exec_history.query(plugin, "autoremove")["items"]
    assert len(items) == 1 == detail["failed_operations"]
    assert items[0]["result"] == "failed" and "整批" in items[0]["reason"]


def test_per_candidate_failure_keeps_operations_in_sync(autoremove):
    """裁决②：逐候选失败时两个计数同步，且都等于记录条数。"""
    plugin = FakePlugin()
    instance = Mock()
    instance.delete_torrents.return_value = False  # 字面 False = 未获确认
    service = _configure(
        autoremove, plugin, instance=instance, torrents=[{"hash": "a"}, {"hash": "b"}])

    detail = _detail()
    candidates = [
        _candidate(autoremove.models, hash_="a"),
        _candidate(autoremove.models, hash_="b"),
    ]
    executed = _run_downloader(
        service, "QB1", candidates, detail, SimpleNamespace(action="delete"), "定时")

    assert executed == []
    assert detail["failed"] == 2
    assert detail["failed_operations"] == 2
    items = autoremove.exec_history.query(plugin, "autoremove")["items"]
    assert len(items) == 2 == detail["failed_operations"]
    assert all(item["result"] == "failed" for item in items)


def test_empty_status_template_carries_failed_operations(autoremove):
    """新增计数键必须进状态模板（否则 reload 后丢失），且不改 0/1 清理判定。"""
    status = autoremove.history.empty_status()
    assert status["failed_operations"] == 0
    assert autoremove.history.history_removed_count(status) == 0
    status["last_run_at"] = 1.0
    assert autoremove.history.history_removed_count(status) == 1
