# -*- coding: utf-8 -*-
"""B07：上传限速「二维只读投影」与「真实调整历史」行为测试。

运行：
  C:/app/scoop/apps/micromamba/2.9.0-0/base/envs/mp3/python.exe -m pytest tests/v3/downloadmanagerlocal/test_upload_limit_rows_and_history.py -q

宿主（app.*）与下载器客户端全部替身，不连接 MoviePilot 或真实下载器。
覆盖：downloader_site_rows 同站求和 / 不重复 / 未知不伪造 / 关闭态；
以及 upload_limit 历史流：无变化不写、全局写入、单种写入、写入失败、恢复、
外部改动、历史保存失败、锁序、清理不破坏恢复。
"""

import copy
import importlib.machinery
import importlib.util
import sys
import threading
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

PLUGIN = Path(__file__).resolve().parents[3] / "plugins.v3/downloadmanagerlocal"
PREFIX = "app.plugins.downloadmanagerlocal"


def _module(monkeypatch, name, **attrs):
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


@pytest.fixture
def svc(monkeypatch):
    """加载真实 service / allocator / adapter / execution_history，桩掉 MP 宿主边界。"""
    for package, path in (
        (PREFIX, PLUGIN),
        (PREFIX + ".adapter", PLUGIN / "adapter"),
        (PREFIX + ".model", PLUGIN / "model"),
        (PREFIX + ".modules", PLUGIN / "modules"),
        (PREFIX + ".modules.uploadlimit", PLUGIN / "modules/uploadlimit"),
        (PREFIX + ".utils", PLUGIN / "utils"),
    ):
        _module(monkeypatch, package, __path__=[str(path)])

    # 桩掉 model.state：service 与 execution_history 都从这里取键与锁。
    _module(
        monkeypatch,
        PREFIX + ".model.state",
        UPLOAD_LIMIT_STATE_KEY="upload_limit_state",
        EXECUTION_HISTORY_KEY="execution_history",
        EXECUTION_HISTORY_SCHEMA_VERSION=1,
        _HISTORY_LOCK=threading.RLock(),
    )

    # 桩掉 utils.config：只提供 service 真正 import 的三个符号。
    def _is_upload_limit_active(plugin):
        selected = getattr(plugin, "_upload_limit_downloaders", []) or []
        limits = getattr(plugin, "_upload_limit_downloader_limits_kib", {}) or {}
        return bool(
            getattr(plugin, "_upload_limit_enabled", False)
            and selected
            and all(int(limits.get(name, 0) or 0) > 0 for name in selected)
        )

    _module(
        monkeypatch,
        PREFIX + ".utils.config",
        is_upload_limit_active=_is_upload_limit_active,
        normalize_upload_limit_config=lambda config: {},
        observe_only=lambda plugin, module: False,
    )

    upload_model = _load(monkeypatch, "model/upload_limit.py", PREFIX + ".model.upload_limit")
    exec_history = _load(monkeypatch, "model/execution_history.py", PREFIX + ".model.execution_history")
    adapter = _load(monkeypatch, "adapter/upload_limit.py", PREFIX + ".adapter.upload_limit")
    allocator = _load(monkeypatch, "modules/uploadlimit/allocator.py", PREFIX + ".modules.uploadlimit.allocator")
    service = _load(monkeypatch, "modules/uploadlimit/service.py", PREFIX + ".modules.uploadlimit.service")

    return SimpleNamespace(
        service=service,
        exec_history=exec_history,
        adapter=adapter,
        allocator=allocator,
        upload_model=upload_model,
    )


class FakeQb:
    """qBittorrent 客户端最小假实现，记录全局/单种写入调用与可注入失败。"""

    def __init__(self, upload_limit_bps=0, alt_up_limit=0, torrents=None):
        self.transfer = SimpleNamespace(upload_limit=upload_limit_bps)
        self.qbc = self
        self._prefs = {"alt_up_limit": alt_up_limit}
        self.torrents = list(torrents or [])
        self.set_prefs_calls = []
        self.torrent_limit_calls = []
        self.write_global_error = None
        self.write_torrent_error = None
        self.get_torrents_error = None

    def app_preferences(self):
        return dict(self._prefs)

    def app_set_preferences(self, prefs):
        if self.write_global_error is not None:
            raise self.write_global_error
        self.set_prefs_calls.append(dict(prefs))
        self._prefs.update(prefs)

    def torrents_set_upload_limit(self, limit=None, torrent_hashes=None):
        if self.write_torrent_error is not None:
            raise self.write_torrent_error
        self.torrent_limit_calls.append({"limit": limit, "hashes": torrent_hashes})

    def get_torrents(self):
        if self.get_torrents_error is not None:
            raise self.get_torrents_error
        return (list(self.torrents), None)


class FakePlugin:
    """最小插件桩：内存存储 + 保存调用记录 + 历史保存失败注入 + 锁持有观测。"""

    def __init__(self, state=None, fail_history_save=False):
        self._data = {}
        self.save_calls = []
        self.fail_history_save = fail_history_save
        self._upload_limit_state = state
        self._upload_limit_state_error = ""
        self._upload_limit_enabled = True
        self._upload_limit_downloaders = ["QB1"]
        self._upload_limit_downloader_limits_kib = {"QB1": 100}
        self._upload_limit_site_rules = {}
        self._upload_limit_grace_minutes = 30
        self._transfer_stop_generation = 0
        self._upload_limit_stop_event = None
        self._tag_siteprefix = "🏠"
        self._upload_limit_cycle_lock = None
        self.history_lock_held = None
        self.state_lock_held = None
        self.services = {}

    def get_data(self, key=None):
        if key is None:
            return dict(self._data)
        return self._data.get(key)

    def save_data(self, key, value):
        lock = getattr(self, "_upload_limit_cycle_lock", None)
        owned = lock._is_owned() if lock is not None else False
        if key == "execution_history":
            if self.fail_history_save:
                raise RuntimeError("history save failed")
            self.history_lock_held = owned
        elif key == "upload_limit_state":
            self.state_lock_held = owned
        self.save_calls.append(key)
        self._data[key] = value

    def service_info(self, name):
        return self.services.get(name)

    def add_downloader(self, name, qb):
        self.services[name] = SimpleNamespace(type="qbittorrent", instance=qb)


def _qb_torrent(hash_, name="t", tags="", up_limit=0, upspeed=0, num_leechs=0):
    return {
        "hash": hash_,
        "name": name,
        "tags": tags,
        "state": "uploading",
        "progress": 1.0,
        "amount_left": 0,
        "total_size": 1024,
        "added_on": 1000.0,
        "completion_on": 1000.0,
        "upspeed": upspeed,
        "num_leechs": num_leechs,
        "up_limit": up_limit,
    }


def _empty_state():
    return {
        "schema_version": 1,
        "management_active": False,
        "activated_at": 0.0,
        "cycle": 0,
        "last_run_at": 0.0,
        "downloaders": {},
        "torrents": {},
        "failures": {},
        "last_summary": {},
    }


def _seed_downloader(limit_kib=100):
    """返回已接管（last_written_global 与期望值一致）的下载器条目。"""
    return {
        "downloader_type": "qbittorrent",
        "first_managed_at": 1000.0,
        "initial_scan_complete": True,
        "per_torrent_management_active": True,
        "original_global": {
            "upload_limit_bps": 0,
            "upload_enabled": False,
            "alternate_upload_limit_bps": 0,
            "alternate_upload_enabled": False,
        },
        "last_written_global": {
            "upload_limit_bps": limit_kib * 1024,
            "upload_enabled": True,
            "alternate_upload_limit_bps": limit_kib * 1024,
            "alternate_upload_enabled": True,
        },
        "total_limit_kib": limit_kib,
        "last_seen_at": 1000.0,
    }


# ── B07a：downloader_site_rows 只读投影 ──────────────────────────────


def test_rows_sum_equals_site_total(svc):
    state = _empty_state()
    state["last_run_at"] = 1000.0
    state["torrents"] = {
        "A:1": {"downloader_id": "A", "site_key": "site-a", "grace_until": 0.0,
                "upload_rate_bps": 1024, "last_allocation_kib": 10},
        "A:2": {"downloader_id": "A", "site_key": "site-a", "grace_until": 0.0,
                "upload_rate_bps": 2048, "last_allocation_kib": 20},
        "B:1": {"downloader_id": "B", "site_key": "site-a", "grace_until": 0.0,
                "upload_rate_bps": 512, "last_allocation_kib": 5},
    }
    rows = svc.service._build_downloader_site_rows(state)
    assert {r["downloader_id"] for r in rows} == {"A", "B"}
    assert sum(r["torrent_count"] for r in rows) == 3
    assert sum(r["uploading_torrents"] for r in rows) == 3
    assert sum(r["upload_rate_bps"] for r in rows) == 1024 + 2048 + 512
    assert sum(r["allocated_kib"] for r in rows) == 10 + 20 + 5


def test_rows_no_duplicate_cross_downloader_total(svc):
    state = _empty_state()
    state["last_run_at"] = 1000.0
    state["torrents"] = {
        "A:1": {"downloader_id": "A", "site_key": "site-a", "grace_until": 0.0,
                "upload_rate_bps": 100, "last_allocation_kib": 30},
        "B:1": {"downloader_id": "B", "site_key": "site-a", "grace_until": 0.0,
                "upload_rate_bps": 0, "last_allocation_kib": 10},
    }
    rows = svc.service._build_downloader_site_rows(state)
    total_allocated = 40
    assert sum(r["allocated_kib"] for r in rows) == total_allocated
    # 任何单行都不得被复制成跨下载器总额度
    assert all(r["allocated_kib"] != total_allocated for r in rows)
    assert {r["allocated_kib"] for r in rows} == {30, 10}


def test_rows_missing_rate_is_unknown_not_zero(svc):
    state = _empty_state()
    state["last_run_at"] = 1000.0
    state["torrents"] = {
        "A:1": {"downloader_id": "A", "site_key": "site-a", "grace_until": 0.0,
                "last_allocation_kib": 50},
        # upload_rate_bps 缺失 → 不得伪造 0
    }
    rows = svc.service._build_downloader_site_rows(state)
    assert len(rows) == 1
    row = rows[0]
    assert row["torrent_count"] == 1
    assert row["allocated_kib"] == 50  # 真实值保留
    assert row["upload_rate_bps"] is None
    assert row["uploading_torrents"] is None
    assert row["status"] != "ok"


def test_status_closed_has_no_healthy_rows(svc):
    plugin = FakePlugin(state=_empty_state())
    plugin._upload_limit_enabled = False
    status = svc.service.get_upload_limit_status(plugin)
    assert status["downloader_site_rows"] == []
    assert status["service_status"] == "disabled"


# ── B07b：upload_limit 真实调整历史 ──────────────────────────────────


def test_no_change_cycle_writes_no_history(svc):
    qb = FakeQb(upload_limit_bps=100 * 1024, alt_up_limit=100 * 1024)
    state = _empty_state()
    state["management_active"] = True
    state["cycle"] = 1
    state["last_run_at"] = 1000.0
    state["downloaders"] = {"QB1": _seed_downloader()}
    plugin = FakePlugin(state=state)
    plugin._upload_limit_site_rules = {}  # 下载器-only 模式，无单种写入
    plugin.add_downloader("QB1", qb)

    result = svc.service.run_upload_limit_cycle(plugin, now=2000.0)

    assert result["service_status"] == "running"
    assert qb.set_prefs_calls == []  # 全局写入函数 0 次
    assert qb.torrent_limit_calls == []  # 单种写入函数 0 次
    assert svc.exec_history.query(plugin, "upload_limit")["items"] == []


def test_global_write_records_history(svc):
    qb = FakeQb(upload_limit_bps=0, alt_up_limit=0)
    plugin = FakePlugin()
    plugin._upload_limit_site_rules = {}  # 无站点策略 → 只有全局写入
    plugin.add_downloader("QB1", qb)

    svc.service.run_upload_limit_cycle(plugin, now=1000.0)

    items = svc.exec_history.query(plugin, "upload_limit")["items"]
    assert len(items) == 1
    rec = items[0]
    assert rec["action"] == "global_limit"
    assert rec["result"] == "success"
    assert rec["downloader_id"] == "QB1"
    assert rec["torrent_hash"] == ""
    assert rec["before"]["upload_limit_bps"] == 0
    assert rec["after"]["upload_limit_bps"] == 100 * 1024
    # 历史绝不覆盖 original_global（仍为接管前原值）
    state = plugin.get_data("upload_limit_state")
    assert state["downloaders"]["QB1"]["original_global"]["upload_limit_bps"] == 0
    assert qb.transfer.upload_limit == 100 * 1024


def test_torrent_write_records_history(svc):
    qb = FakeQb(upload_limit_bps=100 * 1024, alt_up_limit=100 * 1024)
    qb.torrents = [_qb_torrent("aaa111", tags="🏠site-a", up_limit=0, upspeed=5120, num_leechs=1)]
    state = _empty_state()
    state["management_active"] = True
    state["cycle"] = 1
    state["last_run_at"] = 1000.0
    state["downloaders"] = {"QB1": _seed_downloader()}
    state["torrents"] = {
        "QB1:aaa111": {
            "downloader_id": "QB1",
            "downloader_type": "qbittorrent",
            "torrent_hash": "aaa111",
            "site_key": "site-a",
            "grace_until": 0.0,
            "original_settings": {"limit_bps": 0, "enabled": False},
            "upload_rate_bps": 5120,
            "upload_demand_peers": 1,
            "last_seen_at": 1000.0,
        }
    }
    plugin = FakePlugin(state=state)
    plugin._upload_limit_site_rules = {"site-a": {"limit_kib": 100}}
    plugin.add_downloader("QB1", qb)

    svc.service.run_upload_limit_cycle(plugin, now=2000.0)

    items = svc.exec_history.query(plugin, "upload_limit")["items"]
    torrent_records = [r for r in items if r["action"] == "torrent_limit"]
    assert len(torrent_records) == 1
    rec = torrent_records[0]
    assert rec["result"] == "success"
    assert rec["torrent_hash"] == "aaa111"
    assert rec["site"] == "site-a"
    assert rec["before"]["limit_bps"] == 0
    assert len(qb.torrent_limit_calls) == 1
    assert rec["after"]["limit_bps"] == qb.torrent_limit_calls[0]["limit"]


def test_torrent_write_failure_records_failed(svc):
    qb = FakeQb(upload_limit_bps=100 * 1024, alt_up_limit=100 * 1024)
    qb.write_torrent_error = RuntimeError("torrent write boom")
    qb.torrents = [_qb_torrent("aaa111", tags="🏠site-a", up_limit=0, upspeed=5120, num_leechs=1)]
    state = _empty_state()
    state["management_active"] = True
    state["cycle"] = 1
    state["last_run_at"] = 1000.0
    state["downloaders"] = {"QB1": _seed_downloader()}
    state["torrents"] = {
        "QB1:aaa111": {
            "downloader_id": "QB1",
            "downloader_type": "qbittorrent",
            "torrent_hash": "aaa111",
            "site_key": "site-a",
            "grace_until": 0.0,
            "original_settings": {"limit_bps": 0, "enabled": False},
            "upload_rate_bps": 5120,
            "upload_demand_peers": 1,
            "last_seen_at": 1000.0,
        }
    }
    plugin = FakePlugin(state=state)
    plugin._upload_limit_site_rules = {"site-a": {"limit_kib": 100}}
    plugin.add_downloader("QB1", qb)

    result = svc.service.run_upload_limit_cycle(plugin, now=2000.0)

    items = svc.exec_history.query(plugin, "upload_limit")["items"]
    failed = [r for r in items if r["result"] == "failed"]
    assert len(failed) == 1
    assert failed[0]["action"] == "torrent_limit"
    assert failed[0]["torrent_hash"] == "aaa111"
    assert failed[0]["reason"] == "torrent write boom"
    assert any("aaa111" in e and "torrent write boom" in e for e in result.get("errors", []))
    assert "service_status" in result  # 业务照常返回，不抛异常


def test_restore_records_history_and_preserves_behavior(svc):
    qb = FakeQb(upload_limit_bps=100 * 1024, alt_up_limit=100 * 1024)
    qb.torrents = [_qb_torrent("aaa111", tags="🏠site-a", up_limit=50 * 1024)]
    state = _empty_state()
    state["management_active"] = True
    state["downloaders"] = {
        "QB1": {
            "downloader_type": "qbittorrent",
            "original_global": {
                "upload_limit_bps": 0,
                "upload_enabled": False,
                "alternate_upload_limit_bps": 0,
                "alternate_upload_enabled": False,
            },
            "last_written_global": {
                "upload_limit_bps": 100 * 1024,
                "upload_enabled": True,
                "alternate_upload_limit_bps": 100 * 1024,
                "alternate_upload_enabled": True,
            },
        }
    }
    state["torrents"] = {
        "QB1:aaa111": {
            "downloader_id": "QB1",
            "downloader_type": "qbittorrent",
            "torrent_hash": "aaa111",
            "site_key": "site-a",
            "original_settings": {"limit_bps": 0, "enabled": False},
            "last_written_settings": {"limit_bps": 50 * 1024, "enabled": True},
        }
    }
    plugin = FakePlugin(state=state)
    plugin.add_downloader("QB1", qb)

    result = svc.service.restore_upload_limits(plugin)

    items = svc.exec_history.query(plugin, "upload_limit")["items"]
    actions = {r["action"] for r in items}
    assert {"global_restore", "torrent_restore"} <= actions
    g = next(r for r in items if r["action"] == "global_restore")
    t = next(r for r in items if r["action"] == "torrent_restore")
    assert g["result"] == "success" and g["downloader_id"] == "QB1"
    assert g["before"]["upload_limit_bps"] == 100 * 1024
    assert g["after"]["upload_limit_bps"] == 0
    assert t["result"] == "success" and t["torrent_hash"] == "aaa111"
    assert t["before"]["limit_bps"] == 50 * 1024
    assert t["after"]["limit_bps"] == 0
    # 恢复行为不变：状态被清空、下载器值还原
    assert plugin._upload_limit_state["downloaders"] == {}
    assert plugin._upload_limit_state["torrents"] == {}
    assert qb.transfer.upload_limit == 0
    assert qb.torrent_limit_calls == [{"limit": 0, "hashes": "aaa111"}]
    assert result["code"] == 0


def test_external_change_keeps_original_global_logic(svc):
    qb = FakeQb(upload_limit_bps=200 * 1024, alt_up_limit=200 * 1024)
    state = _empty_state()
    state["management_active"] = True
    state["cycle"] = 1
    state["last_run_at"] = 1000.0
    state["downloaders"] = {"QB1": _seed_downloader()}
    plugin = FakePlugin(state=state)
    plugin._upload_limit_site_rules = {}
    plugin.add_downloader("QB1", qb)

    svc.service.run_upload_limit_cycle(plugin, now=2000.0)

    state_after = plugin.get_data("upload_limit_state")
    # 既有「重新识别 original_global」逻辑仍按原样执行：外部值被识别为新原值
    assert state_after["downloaders"]["QB1"]["original_global"]["upload_limit_bps"] == 200 * 1024
    # 历史是独立流，不与 upload_limit_state 混存
    assert "streams" not in state_after
    assert "history" not in state_after
    items = svc.exec_history.query(plugin, "upload_limit")["items"]
    assert len(items) == 1
    assert items[0]["before"]["upload_limit_bps"] == 200 * 1024
    assert items[0]["after"]["upload_limit_bps"] == 100 * 1024


def test_history_save_failure_does_not_change_business(svc):
    qb = FakeQb(upload_limit_bps=0, alt_up_limit=0)
    plugin = FakePlugin(fail_history_save=True)
    plugin._upload_limit_site_rules = {}
    plugin.add_downloader("QB1", qb)

    result = svc.service.run_upload_limit_cycle(plugin, now=1000.0)

    # 限速写入照常成功、状态照常落盘、异常不冒泡
    assert qb.transfer.upload_limit == 100 * 1024
    assert "upload_limit_state" in plugin.save_calls
    assert result["service_status"] == "running"
    assert svc.exec_history.query(plugin, "upload_limit")["items"] == []


def test_history_flush_after_lock_release(svc):
    qb = FakeQb(upload_limit_bps=0, alt_up_limit=0)
    plugin = FakePlugin()
    plugin._upload_limit_site_rules = {}
    plugin.add_downloader("QB1", qb)

    svc.service.run_upload_limit_cycle(plugin, now=1000.0)

    # 状态落盘发生在持锁期间，历史落盘发生在锁释放之后
    assert plugin.state_lock_held is True
    assert plugin.history_lock_held is False
    assert len(svc.exec_history.query(plugin, "upload_limit")["items"]) == 1


def test_clear_history_does_not_break_restore(svc):
    qb = FakeQb(upload_limit_bps=100 * 1024, alt_up_limit=100 * 1024)
    qb.torrents = [_qb_torrent("aaa111", tags="🏠site-a", up_limit=50 * 1024)]
    state = _empty_state()
    state["management_active"] = True
    state["downloaders"] = {
        "QB1": {
            "downloader_type": "qbittorrent",
            "original_global": {
                "upload_limit_bps": 0,
                "upload_enabled": False,
                "alternate_upload_limit_bps": 0,
                "alternate_upload_enabled": False,
            },
            "last_written_global": {
                "upload_limit_bps": 100 * 1024,
                "upload_enabled": True,
                "alternate_upload_limit_bps": 100 * 1024,
                "alternate_upload_enabled": True,
            },
        }
    }
    state["torrents"] = {
        "QB1:aaa111": {
            "downloader_id": "QB1",
            "downloader_type": "qbittorrent",
            "torrent_hash": "aaa111",
            "site_key": "site-a",
            "original_settings": {"limit_bps": 0, "enabled": False},
            "last_written_settings": {"limit_bps": 50 * 1024, "enabled": True},
        }
    }
    plugin = FakePlugin(state=state)
    plugin.add_downloader("QB1", qb)

    svc.exec_history.append(plugin, "upload_limit", {
        "trigger": "周期", "occurred_at": 1.0, "action": "x",
        "result": "success", "reason": "y",
    })
    before_state = copy.deepcopy(plugin._upload_limit_state)
    removed = svc.exec_history.clear(plugin, "upload_limit")
    assert removed == 1
    # 清理不破坏持久化状态
    assert plugin._upload_limit_state == before_state

    # 停用恢复仍然可用
    result = svc.service.restore_upload_limits(plugin)
    assert result["code"] == 0
    assert plugin._upload_limit_state["downloaders"] == {}
    assert plugin._upload_limit_state["torrents"] == {}
    assert qb.transfer.upload_limit == 0
