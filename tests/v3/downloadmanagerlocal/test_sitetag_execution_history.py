# -*- coding: utf-8 -*-
"""站点标签（tag / tag_cleanup）展示历史接线测试（B06）。

运行：
  C:/app/scoop/apps/micromamba/2.9.0-0/base/envs/mp3/python.exe -m pytest tests/v3/downloadmanagerlocal/test_sitetag_execution_history.py -q

覆盖：
1. complement_history 四种 _apply_metadata 返回形态 → success/observed/failed/observed（可区分）；
2. process_download_added 三个早退分支 → 各自 1 条 failed（reason 可区分），skipped 计数不变；
3. 下载器级 get_torrents 失败 → 恰好 1 条下载器级 failed，无 per-torrent 记录，skipped 计数不变；
4. execute_tag_cleanup 成功/失败项 → 每条计划项一条记录，不拆 per-hash；
5. 快照过期 / 无待清理项 → 不写 success；
6. 观察模式 → 恰好 1 条 observed，无 success；
7. truncated（>1000 项）→ 记录数等于实际处理项数；
8. 历史写入失败 → 业务结果（返回值/计数/下载器写入）不变，上层不报业务失败；
9. clear 不触发下载器动作，只碰历史键；
10. 两个流互不污染。
"""
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

HASH_1 = "a" * 40
HASH_2 = "b" * 40
HASH_3 = "c" * 40
HASH_4 = "d" * 40


@pytest.fixture
def sitetag_history(monkeypatch):
    """加载真实 execution_history.py 与 sitetag/service.py，宿主与依赖全部替身。"""

    def module(name, **attrs):
        path = attrs.pop("__path__", None)
        result = types.ModuleType(name)
        result.__spec__ = importlib.machinery.ModuleSpec(
            name, None, is_package=path is not None
        )
        if path is not None:
            result.__path__ = path
        result.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, result)
        return result

    def load(relpath, name):
        spec = importlib.util.spec_from_file_location(name, PLUGIN / relpath)
        result = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, result)
        spec.loader.exec_module(result)
        return result

    # 宿主替身
    module("app")
    module("app.sdk")
    module("app.plugins")
    module(PREFIX, __path__=[str(PLUGIN)])
    module("app.sdk.logging", logger=Mock())
    module("app.sdk.config", settings=SimpleNamespace(TORRENT_TAG=""))

    # 插件包
    module(PREFIX + ".model", __path__=[str(PLUGIN / "model")])
    state = module(
        PREFIX + ".model.state",
        SITE_TAG_STATUS_KEY="sitetag_status",
        TAG_CLEANUP_STATUS_KEY="tag_cleanup_status",
        EXECUTION_HISTORY_KEY="execution_history",
        EXECUTION_HISTORY_SCHEMA_VERSION=1,
        _HISTORY_LOCK=threading.RLock(),
    )
    exec_history = load("model/execution_history.py", PREFIX + ".model.execution_history")

    module(PREFIX + ".adapter", __path__=[str(PLUGIN / "adapter")])
    adapter = module(
        PREFIX + ".adapter.moviepilot",
        generate_random_tag=lambda length=10: "TMP_TAG",
        get_site_indexer=lambda domain: None,
        get_url_domain=lambda value: "",
        list_site_dicts=lambda: [],
        get_download_history_by_hash=lambda torrent_hash: None,
    )

    module(PREFIX + ".utils", __path__=[str(PLUGIN / "utils")])
    load("utils/tag_cleanup.py", PREFIX + ".utils.tag_cleanup")
    load("utils/torrent_adapter.py", PREFIX + ".utils.torrent_adapter")
    config = module(PREFIX + ".utils.config")
    config.observe_skip = lambda *args, **kwargs: False

    module(PREFIX + ".modules", __path__=[str(PLUGIN / "modules")])
    tag = load("modules/sitetag/service.py", PREFIX + ".modules.sitetag.service")

    return SimpleNamespace(
        tag=tag,
        history=exec_history,
        state=state,
        config=config,
        adapter=adapter,
    )


class FakePlugin:
    """最小插件桩：内存存储 + 保存调用记录 + 可注入指定键保存失败。"""

    def __init__(self, data=None, fail_save_keys=()):
        self._data = dict(data or {})
        self.save_calls = []
        self.fail_save_keys = set(fail_save_keys)
        self._active_temporary_tags = set()
        self._torrent_tags = []
        self._tag_siteprefix = ""
        self._hr_hit_and_run_tag = ""
        self._hr_service = None
        self._site_tag_config = None
        self._tag_cleanup_status = None
        self._services = {}

    def get_data(self, key=None):
        return dict(self._data) if key is None else self._data.get(key)

    def save_data(self, key, value):
        if key in self.fail_save_keys:
            raise RuntimeError("save failed: %s" % key)
        self.save_calls.append(key)
        self._data[key] = value

    def get_config(self):
        return {}

    def service_info(self, name):
        return self._services.get(name)


def _items(history, plugin, module):
    return history.query(plugin, module)["items"]


# ── 流 1：tag（补全流）────────────────────────────────────────────────
def test_complement_history_four_shapes(sitetag_history, monkeypatch):
    """四种 _apply_metadata 返回形态分别映射 success/observed/failed/observed。"""
    tag = sitetag_history.tag
    history = sitetag_history.history

    service = SimpleNamespace(
        name="QB1",
        type="qbittorrent",
        instance=SimpleNamespace(
            get_torrents=Mock(
                return_value=([{"name": "T1"}, {"name": "T2"}, {"name": "T3"}, {"name": "T4"}], None)
            )
        ),
    )
    plugin = FakePlugin()
    plugin._services = {"QB1": service}

    outcomes = [
        {"ok": True, "changed": True, "hash": HASH_1, "tags": ["SITE"], "category": None, "site": "SITE", "history": True},
        {"ok": True, "changed": False, "hash": HASH_2, "site": None, "history": False},
        {"ok": False, "reason": "hash_missing"},
        {"ok": True, "changed": False, "observe_only": True, "hash": HASH_4, "site": "SITE", "history": True},
    ]
    monkeypatch.setattr(tag, "_apply_metadata", Mock(side_effect=outcomes))

    result = tag.complement_history(plugin, {"downloaders": ["QB1"]})

    # 既有计数语义保持不变
    assert result["completed"] == 1
    assert result["skipped"] == 1
    assert result["round"]["success"] == 1
    assert result["round"]["failed"] == 1
    assert result["round"]["no_update"] == 2

    items = _items(history, plugin, "tag")
    by_result = {}
    for item in items:
        by_result.setdefault(item["result"], []).append(item)
    assert sorted(by_result) == ["failed", "observed", "success"]
    assert len(by_result["success"]) == 1
    assert len(by_result["failed"]) == 1
    assert len(by_result["observed"]) == 2

    assert by_result["success"][0]["reason"] == "已写入 标签=['SITE']"
    assert by_result["failed"][0]["reason"] == "hash_missing"
    observed_reasons = sorted(item["reason"] for item in by_result["observed"])
    assert observed_reasons == ["无变更", "观察模式：仅预览未执行"]


def test_process_download_added_early_returns(sitetag_history):
    """三个早退分支各写 1 条 failed（reason 可区分），skipped 计数不变。"""
    tag = sitetag_history.tag
    history = sitetag_history.history
    plugin = FakePlugin()
    cfg = {"downloaders": ["QB1"]}

    ev1 = SimpleNamespace(event_data={"downloader": "QB1", "hash": ""})
    assert tag.process_download_added(plugin, ev1, cfg)["reason"] == "downloader_or_hash_missing"

    ev2 = SimpleNamespace(event_data={"downloader": "QB1", "hash": HASH_1})
    assert tag.process_download_added(plugin, ev2, cfg)["reason"] == "downloader_unavailable"

    service = SimpleNamespace(
        name="QB1",
        type="qbittorrent",
        instance=SimpleNamespace(get_torrents=Mock(return_value=([], "err"))),
    )
    plugin._services = {"QB1": service}
    ev3 = SimpleNamespace(event_data={"downloader": "QB1", "hash": HASH_1})
    assert tag.process_download_added(plugin, ev3, cfg)["reason"] == "torrent_not_found"

    items = _items(history, plugin, "tag")
    assert len(items) == 3
    assert all(item["result"] == "failed" for item in items)
    assert sorted(item["reason"] for item in items) == [
        "downloader_or_hash_missing",
        "downloader_unavailable",
        "torrent_not_found",
    ]
    # 既有 skipped 计数不变（三次早退各 +1）
    assert tag._module_state(plugin)["skipped"] == 3


def test_complement_downloader_level_failure(sitetag_history, monkeypatch):
    """下载器级 get_torrents 失败记 1 条下载器级 failed，无 per-torrent 记录。"""
    tag = sitetag_history.tag
    history = sitetag_history.history

    service = SimpleNamespace(
        name="QB1",
        type="qbittorrent",
        instance=SimpleNamespace(get_torrents=Mock(return_value=([], "下载器挂了"))),
    )
    plugin = FakePlugin()
    plugin._services = {"QB1": service}
    spy = Mock(return_value={"ok": True, "changed": False, "hash": "x", "site": None, "history": False})
    monkeypatch.setattr(tag, "_apply_metadata", spy)

    result = tag.complement_history(plugin, {"downloaders": ["QB1"]})

    assert result["skipped"] == 1
    assert spy.call_count == 0  # 未进入 per-torrent 循环
    items = _items(history, plugin, "tag")
    assert len(items) == 1
    assert items[0]["result"] == "failed"
    assert "下载器挂了" in items[0]["reason"]
    assert items[0]["downloader_id"] == "QB1"


# ── 流 2：tag_cleanup（人工标签清理流）───────────────────────────────
def test_execute_tag_cleanup_records_per_plan_item(sitetag_history, monkeypatch):
    """成功/失败项各记一条（按计划项，不按 hash 拆分）。"""
    tag = sitetag_history.tag
    history = sitetag_history.history

    snapshot = {
        "scan_id": "s1",
        "downloaders": [
            {
                "name": "QB1",
                "tags": [
                    {"tag": "user", "hashes": [HASH_1, HASH_2, HASH_3]},
                    {"tag": "bad", "hashes": [HASH_4]},
                ],
            }
        ],
    }
    plugin = FakePlugin()
    plugin._tag_cleanup_status = snapshot
    service = SimpleNamespace(name="QB1", type="qbittorrent", instance=Mock())
    service.instance.get_torrents.return_value = (
        [
            {"hash": HASH_1, "tags": ["user"]},
            {"hash": HASH_2, "tags": ["user"]},
            {"hash": HASH_3, "tags": ["user"]},
            {"hash": HASH_4, "tags": ["bad"]},
        ],
        None,
    )
    plugin._services = {"QB1": service}

    def fake_remove(dl, tag_name, hashes):
        if tag_name == "user":
            return {"ok": True, "removed": len(list(hashes)), "definition_deleted": False}
        return {"ok": False, "removed": 0, "definition_deleted": False, "error": "boom"}

    monkeypatch.setattr(tag, "_remove_tag_snapshot", fake_remove)

    result = tag.execute_tag_cleanup(
        plugin,
        [
            {"downloader": "QB1", "tag": "user", "hashes": [HASH_1, HASH_2, HASH_3]},
            {"downloader": "QB1", "tag": "bad", "hashes": [HASH_4]},
        ],
        "s1",
    )

    assert len(result["removed"]) == 1
    assert len(result["failed"]) == 1

    items = _items(history, plugin, "tag_cleanup")
    assert len(items) == 2  # 3 个 hash 的 user 也只记 1 条
    by_result = {item["result"]: item for item in items}
    assert set(by_result) == {"success", "failed"}
    assert by_result["success"]["downloader_id"] == "QB1"
    assert "3" in by_result["success"]["reason"]
    assert by_result["failed"]["reason"] == "boom"


def test_execute_tag_cleanup_early_returns_no_success(sitetag_history):
    """快照过期 / 无待清理项：不写任何记录（尤其不写 success）。"""
    tag = sitetag_history.tag
    history = sitetag_history.history
    plugin = FakePlugin()
    plugin._tag_cleanup_status = {"scan_id": "current", "downloaders": []}

    r1 = tag.execute_tag_cleanup(plugin, [{"downloader": "QB1", "tag": "x", "hashes": [HASH_1]}], "old")
    assert "已过期" in r1["msg"]

    r2 = tag.execute_tag_cleanup(plugin, [], "current")
    assert "没有需要清理" in r2["msg"]

    assert _items(history, plugin, "tag_cleanup") == []


def test_execute_tag_cleanup_observe_mode(sitetag_history, monkeypatch):
    """观察模式记恰好 1 条 observed，无 success。"""
    tag = sitetag_history.tag
    history = sitetag_history.history
    plugin = FakePlugin()
    plugin._tag_cleanup_status = {"scan_id": "s1", "downloaders": []}

    monkeypatch.setattr(sitetag_history.config, "observe_skip", lambda *a, **k: True)

    result = tag.execute_tag_cleanup(plugin, [{"downloader": "QB1", "tag": "x", "hashes": [HASH_1]}], "s1")

    assert result.get("observed") == 1
    items = _items(history, plugin, "tag_cleanup")
    assert len(items) == 1
    assert items[0]["result"] == "observed"
    assert "仅预览" in items[0]["reason"]
    assert all(item["result"] != "success" for item in items)


def test_execute_tag_cleanup_truncated(sitetag_history):
    """truncated 场景记录数等于实际处理项数（1000），不写未处理项。"""
    tag = sitetag_history.tag
    history = sitetag_history.history
    plugin = FakePlugin()
    plugin._tag_cleanup_status = {"scan_id": "s1", "downloaders": []}

    removals = [{"downloader": "", "tag": "x", "hashes": [HASH_1]}] * 1001
    result = tag.execute_tag_cleanup(plugin, removals, "s1")

    assert result["truncated"] is True
    assert result["requested"] == 1001
    assert result["processed"] == 1000

    items = _items(history, plugin, "tag_cleanup")
    assert len(items) == 1000
    assert all(item["result"] == "failed" for item in items)
    assert all(item["reason"] == "清理参数不完整" for item in items)


# ── 硬约束：失败不影响业务 / clear 隔离 / 流互不污染 ──────────────────
def test_history_write_failure_does_not_change_business(sitetag_history, monkeypatch):
    """历史写入失败（save_data 抛错）不改变业务结果，也不向上报业务失败。"""
    tag = sitetag_history.tag
    history = sitetag_history.history

    # complement：真实 _apply_metadata 写标签，历史键 save 抛错
    monkeypatch.setattr(tag, "get_url_domain", lambda v: "example.com")
    monkeypatch.setattr(tag, "list_site_dicts", lambda: [{"domain": "example.com", "name": "SITE"}])
    torrent = {
        "hash": HASH_1,
        "name": "A.mkv",
        "tags": [],
        "trackers": [{"url": "udp://tracker.example:6969/announce"}],
        "save_path": "/data",
        "category": "",
    }
    dl = Mock()
    dl.get_torrents.return_value = ([torrent], None)
    service = SimpleNamespace(name="QB1", type="qbittorrent", instance=dl)
    plugin = FakePlugin(fail_save_keys={"execution_history"})
    plugin._services = {"QB1": service}

    result = tag.complement_history(
        plugin,
        {"downloaders": ["QB1"], "enable_tag": True, "siteprefix": "",
         "enable_media_tag": False, "enable_category": False},
    )

    assert result["completed"] == 1
    assert dl.set_torrents_tag.call_count == 1  # 标签已写入
    assert "sitetag_status" in plugin.save_calls  # 业务快照仍保存
    assert _items(history, plugin, "tag") == []  # 历史未写入

    # cleanup：真实 _remove_tag_snapshot 移除标签，历史键 save 抛错
    plugin2 = FakePlugin(fail_save_keys={"execution_history"})
    plugin2._tag_cleanup_status = {
        "scan_id": "s1",
        "downloaders": [{"name": "QB1", "tags": [{"tag": "user", "hashes": [HASH_1]}]}],
    }
    dl2 = Mock()
    dl2.get_torrents.side_effect = lambda ids=None: (
        [{"hash": HASH_1, "tags": ["user"]}], None
    ) if ids else ([], None)
    dl2.remove_torrents_tag.return_value = True
    dl2.delete_torrents_tag.return_value = True
    service2 = SimpleNamespace(name="QB1", type="qbittorrent", instance=dl2)
    plugin2._services = {"QB1": service2}

    result2 = tag.execute_tag_cleanup(
        plugin2, [{"downloader": "QB1", "tag": "user", "hashes": [HASH_1]}], "s1"
    )

    assert result2["code"] == 0
    assert len(result2["removed"]) == 1
    assert dl2.remove_torrents_tag.call_count == 1  # 标签已移除
    assert _items(history, plugin2, "tag_cleanup") == []  # 历史未写入


def test_clear_does_not_trigger_downloader_and_only_touches_history(sitetag_history):
    """clear 不触发下载器动作，save_data 只碰历史键。"""
    history = sitetag_history.history
    downloader = Mock()
    plugin = FakePlugin(data={
        "execution_history": {
            "schema_version": 1,
            "streams": {
                "tag": [{"record_id": "r1", "trigger": "x", "occurred_at": 1.0,
                         "action": "a", "result": "success", "reason": "ok", "module": "tag"}],
                "tag_cleanup": [{"record_id": "r2", "trigger": "x", "occurred_at": 1.0,
                                 "action": "a", "result": "failed", "reason": "boom", "module": "tag_cleanup"}],
            },
        },
        "sitetag_status": {"completed": 1},
    })
    plugin.downloader = downloader

    assert history.clear(plugin, "tag") == 1
    assert history.clear(plugin, "tag_cleanup") == 1

    assert downloader.method_calls == []
    assert plugin.save_calls == ["execution_history", "execution_history"]
    assert plugin._data["sitetag_status"] == {"completed": 1}


def test_streams_do_not_pollute_each_other(sitetag_history, monkeypatch):
    """补全流与清理流的记录互不出现在对方流中。"""
    tag = sitetag_history.tag
    history = sitetag_history.history
    plugin = FakePlugin()

    # tag 流：complement changed → success
    service = SimpleNamespace(
        name="QB1",
        type="qbittorrent",
        instance=SimpleNamespace(get_torrents=Mock(return_value=([{"name": "T"}], None))),
    )
    plugin._services = {"QB1": service}
    monkeypatch.setattr(
        tag,
        "_apply_metadata",
        Mock(return_value={"ok": True, "changed": True, "hash": HASH_1, "tags": ["SITE"],
                           "category": None, "site": "SITE", "history": True}),
    )
    tag.complement_history(plugin, {"downloaders": ["QB1"]})

    # tag_cleanup 流：观察模式 → observed
    plugin._tag_cleanup_status = {"scan_id": "s1", "downloaders": []}
    monkeypatch.setattr(sitetag_history.config, "observe_skip", lambda *a, **k: True)
    tag.execute_tag_cleanup(plugin, [{"downloader": "QB1", "tag": "x", "hashes": [HASH_1]}], "s1")

    tag_items = _items(history, plugin, "tag")
    cleanup_items = _items(history, plugin, "tag_cleanup")

    assert len(tag_items) == 1
    assert tag_items[0]["result"] == "success"
    assert len(cleanup_items) == 1
    assert cleanup_items[0]["result"] == "observed"
    assert all(item["module"] == "tag" for item in tag_items)
    assert all(item["module"] == "tag_cleanup" for item in cleanup_items)
