# -*- coding: utf-8 -*-
"""失败清理接入展示历史（B05）行为测试。

运行：
  C:/app/scoop/apps/micromamba/2.9.0-0/base/envs/mp3/python.exe -m pytest tests/v3/downloadmanagerlocal/test_failclean_execution_history.py -q

覆盖：整理失败事件成功/失败/观察/保护/重复逐条记录、未启用与缺 fileitem、
巡检逐条与异常、锁序、历史写入失败不影响业务、clear 不触发删除。
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import sys
import threading
import time
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

PLUGIN = Path(__file__).resolve().parents[3] / "plugins.v3" / "downloadmanagerlocal"
PREFIX = "app.plugins.downloadmanagerlocal"

FAILCLEAN_STATUS_KEY = "failclean_status"
EXECUTION_HISTORY_KEY = "execution_history"


class FakePlugin:
    """最小插件桩：内存存储 + 保存调用记录 + 可注入保存钩子（锁序/失败验证）。"""

    def __init__(self, data=None):
        self._data = dict(data or {})
        self.save_calls = []
        self._save_hook = None

    def get_data(self, key=None):
        if key is None:
            return dict(self._data)
        return self._data.get(key)

    def save_data(self, key, value):
        if self._save_hook is not None:
            self._save_hook(key, value)
        self.save_calls.append(key)
        self._data[key] = value

    def post_message(self, *args, **kwargs):
        pass


@pytest.fixture
def fc(monkeypatch):
    """加载真实 service/execution_history；hostapi/notify/guard/config 用可控替身。"""

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
    module("app.schemas")
    module("app.schemas.types", MediaType=Mock(), MessageType=Mock(), EventType=Mock())
    module("app.plugins")
    module(PREFIX, __path__=[str(PLUGIN)])

    module(PREFIX + ".modules", __path__=[str(PLUGIN / "modules")])
    module(PREFIX + ".modules.failclean", __path__=[str(PLUGIN / "modules/failclean")])
    module(PREFIX + ".modules.hr", __path__=[str(PLUGIN / "modules/hr")])
    module(PREFIX + ".utils", __path__=[str(PLUGIN / "utils")])
    module(PREFIX + ".model", __path__=[str(PLUGIN / "model")])

    # 观察/H&R 状态，测试内通过 state 开关控制
    state = {"observe": False, "skip": False}

    module(
        PREFIX + ".utils.config",
        module_active=Mock(side_effect=lambda config, mod: bool(
            (config or {}).get("failcleanup_enabled", False))),
        observe_skip=Mock(side_effect=lambda *a, **k: state["observe"]),
        observe_only=Mock(side_effect=lambda plugin, mod: state["observe"]),
    )
    module(
        PREFIX + ".modules.hr.guard",
        SKIP_PATH_TRANSFER_FAILURE="skip_path_transfer_failure",
        HrGuard=Mock(return_value=SimpleNamespace(
            should_skip=Mock(side_effect=lambda gate, dl, h: state["skip"]),
            get_skip_stats=Mock(return_value={}),
        )),
    )
    module(
        PREFIX + ".modules.failclean.notify",
        notify_delete_failure=Mock(),
        notify_delete_success=Mock(),
        notify_scan_result=Mock(),
    )
    module(
        PREFIX + ".model.state",
        EXECUTION_HISTORY_KEY=EXECUTION_HISTORY_KEY,
        EXECUTION_HISTORY_SCHEMA_VERSION=1,
        _HISTORY_LOCK=threading.RLock(),
    )

    exec_history = load("model/execution_history.py", PREFIX + ".model.execution_history")
    constants = load("modules/failclean/constants.py", PREFIX + ".modules.failclean.constants")
    fconfig = load("modules/failclean/config.py", PREFIX + ".modules.failclean.config")
    load("modules/failclean/history.py", PREFIX + ".modules.failclean.history")

    # hostapi 完全替身：每测试按需赋函数可控行为
    hostapi = module(
        PREFIX + ".modules.failclean.hostapi",
        delete_media_file=Mock(return_value=True),
        delete_download_history_file=Mock(),
        send_download_file_deleted=Mock(),
    )

    service = load("modules/failclean/service.py", PREFIX + ".modules.failclean.service")

    return SimpleNamespace(
        service=service,
        exec_history=exec_history,
        constants=constants,
        fconfig=fconfig,
        hostapi=hostapi,
        state=state,
        logger=logger,
    )


def _build(fc, plugin, *, enabled=True):
    service = fc.service.FailCleanService(plugin)
    service.init_module({
        "failcleanup_enabled": enabled,
        "failcleanup_notify": False,
        "failcleanup_clean_repeat": True,
        "failcleanup_retain_hours": 1,
    })
    return service


def _failed_event(path, download_hash="deadbeef", downloader="test-qb"):
    return SimpleNamespace(event_data={
        "fileitem": {"path": str(path)},
        "download_hash": download_hash,
        "downloader": downloader,
        "transferinfo": {"message": "整理器拒绝了该文件"},
    })


def _items(fc, plugin):
    return fc.exec_history.query(plugin, "failclean")["items"]


def _media_file(directory, name="dup.mkv", age_seconds=7200.0):
    path = directory / name
    path.write_bytes(b"fake")
    stamp = time.time() - age_seconds
    os.utime(path, (stamp, stamp))
    return path


def _scan_setup(fc, download_dir, *, record=None, hash_="abcdef012345",
                delete_media=True, get_history_error=None):
    fc.hostapi.local_download_paths = Mock(return_value=[download_dir])
    fc.hostapi.media_extensions = Mock(return_value={".mkv"})
    if get_history_error is not None:
        fc.hostapi.get_success_transfer_history = Mock(side_effect=get_history_error)
    else:
        fc.hostapi.get_success_transfer_history = Mock(return_value=record)
    fc.hostapi.dest_file_exists = Mock(return_value=True)
    fc.hostapi.get_local_file_item = Mock(return_value="item")
    fc.hostapi.get_download_hash_by_fullpath = Mock(return_value=hash_)
    fc.hostapi.delete_media_file = Mock(return_value=delete_media)
    fc.hostapi.delete_download_history_file = Mock()
    fc.hostapi.send_download_file_deleted = Mock()


# ── 整理失败事件逐条记录 ──────────────────────────────────────────────

def test_transfer_failed_success_records_success(fc):
    plugin = FakePlugin()
    service = _build(fc, plugin)
    fc.hostapi.delete_media_file = Mock(return_value=True)

    result = service.handle_transfer_failed(_failed_event("/tmp/a.mkv"))

    assert result["deleted"] == 1
    items = _items(fc, plugin)
    assert len(items) == 1
    record = items[0]
    assert record["result"] == "success"
    assert record["action"] == "删除源文件"
    assert record["trigger"] == "TransferFailed"
    assert record["downloader_id"] == "test-qb"
    assert record["torrent_hash"] == "deadbeef"
    assert record["name"] == "/tmp/a.mkv"
    assert record["occurred_at"] > 0
    assert service._status["event"]["deleted"] == 1
    assert service._status["total"]["cleaned"] == 1


def test_transfer_failed_delete_false_records_failed(fc):
    plugin = FakePlugin()
    service = _build(fc, plugin)
    fc.hostapi.delete_media_file = Mock(return_value=False)

    result = service.handle_transfer_failed(_failed_event("/tmp/a.mkv"))

    assert result["deleted"] == 0
    assert result["skipped"] is False
    items = _items(fc, plugin)
    assert len(items) == 1
    assert items[0]["result"] == "failed"
    assert items[0]["reason"] == "删除源文件失败"
    assert service._status["event"]["failed"] == 1
    assert service._status["total"]["failed"] == 1


def test_transfer_failed_observe_records_observed_without_delete(fc):
    plugin = FakePlugin()
    service = _build(fc, plugin)
    fc.state["observe"] = True

    result = service.handle_transfer_failed(_failed_event("/tmp/a.mkv"))

    assert result["deleted"] == 0
    assert result["skipped"] is True
    fc.hostapi.delete_media_file.assert_not_called()
    items = _items(fc, plugin)
    assert len(items) == 1
    assert items[0]["result"] == "observed"
    assert items[0]["reason"] == "观察模式：未执行删除"
    assert service._status["event"]["skipped"] == 1
    assert service._status["total"]["skipped"] == 1


def test_transfer_failed_hr_skip_records_skipped_not_observed(fc):
    plugin = FakePlugin()
    service = _build(fc, plugin)
    fc.state["observe"] = False
    fc.state["skip"] = True

    result = service.handle_transfer_failed(_failed_event("/tmp/a.mkv"))

    assert result["deleted"] == 0
    assert result["skipped"] is True
    fc.hostapi.delete_media_file.assert_not_called()
    items = _items(fc, plugin)
    assert len(items) == 1
    assert items[0]["result"] == "skipped"
    assert items[0]["reason"] == "H&R 保护跳过"


def test_transfer_failed_duplicate_writes_no_record(fc):
    plugin = FakePlugin()
    service = _build(fc, plugin)
    fc.hostapi.delete_media_file = Mock(return_value=True)
    event = _failed_event("/tmp/a.mkv")

    first = service.handle_transfer_failed(event)
    second = service.handle_transfer_failed(event)

    assert first["deleted"] == 1
    assert second["duplicate"] is True
    items = _items(fc, plugin)
    assert len(items) == 1
    assert items[0]["result"] == "success"
    assert service._status["total"]["cleaned"] == 1
    assert service._status["total"]["failed"] == 0
    assert service._status["total"]["skipped"] == 0


def test_transfer_failed_disabled_writes_no_record(fc):
    plugin = FakePlugin()
    service = _build(fc, plugin, enabled=False)

    result = service.handle_transfer_failed(_failed_event("/tmp/a.mkv"))

    assert result["deleted"] == 0
    assert _items(fc, plugin) == []


def test_transfer_failed_missing_fileitem_records_one_failed(fc):
    plugin = FakePlugin()
    service = _build(fc, plugin)

    result = service.handle_transfer_failed(SimpleNamespace(event_data={}))

    assert result["deleted"] == 0
    items = _items(fc, plugin)
    assert len(items) == 1
    assert items[0]["result"] == "failed"
    assert items[0]["reason"] == "整理失败事件缺少 fileitem"


# ── 巡检逐条记录 ──────────────────────────────────────────────────────

def test_scan_no_residual_writes_no_record(fc, tmp_path):
    plugin = FakePlugin()
    service = _build(fc, plugin)
    download = tmp_path / "downloads"
    download.mkdir()
    _media_file(download, "old.mkv")
    _scan_setup(fc, download, record=None)

    result = service.cleanup_repeat_sources("手动")

    assert result["scanned"] == 1
    assert result["cleaned"] == 0
    assert _items(fc, plugin) == []
    fc.hostapi.delete_media_file.assert_not_called()


def test_scan_success_records_success(fc, tmp_path):
    plugin = FakePlugin()
    service = _build(fc, plugin)
    download = tmp_path / "downloads"
    dest = tmp_path / "media"
    download.mkdir()
    dest.mkdir()
    src = _media_file(download, "dup.mkv")
    dest_file = dest / "kept.mkv"
    dest_file.write_bytes(b"media")
    record = SimpleNamespace(dest_storage="local", dest=str(dest_file), downloader="test-qb")
    _scan_setup(fc, download, record=record, hash_="abcdef")

    result = service.cleanup_repeat_sources("手动")

    assert result["cleaned"] == 1
    assert result["failed"] == 0
    items = _items(fc, plugin)
    assert len(items) == 1
    assert items[0]["result"] == "success"
    assert items[0]["trigger"] == "手动"
    assert items[0]["torrent_hash"] == "abcdef"
    assert items[0]["downloader_id"] == "test-qb"
    assert items[0]["name"] == src.as_posix()


def test_scan_delete_failure_records_failed(fc, tmp_path):
    plugin = FakePlugin()
    service = _build(fc, plugin)
    download = tmp_path / "downloads"
    dest = tmp_path / "media"
    download.mkdir()
    dest.mkdir()
    src = _media_file(download, "faildel.mkv")
    dest_file = dest / "kept.mkv"
    dest_file.write_bytes(b"media")
    record = SimpleNamespace(dest_storage="local", dest=str(dest_file), downloader="test-qb")
    _scan_setup(fc, download, record=record, delete_media=False)

    result = service.cleanup_repeat_sources("手动")

    assert result["cleaned"] == 0
    assert result["failed"] == 1
    items = _items(fc, plugin)
    assert len(items) == 1
    assert items[0]["result"] == "failed"
    assert items[0]["reason"] == "删除源文件失败"


def test_scan_observe_records_observed(fc, tmp_path):
    plugin = FakePlugin()
    service = _build(fc, plugin)
    fc.state["observe"] = True
    download = tmp_path / "downloads"
    dest = tmp_path / "media"
    download.mkdir()
    dest.mkdir()
    src = _media_file(download, "observe.mkv")
    dest_file = dest / "kept.mkv"
    dest_file.write_bytes(b"media")
    record = SimpleNamespace(dest_storage="local", dest=str(dest_file), downloader="test-qb")
    _scan_setup(fc, download, record=record)

    result = service.cleanup_repeat_sources("手动")

    assert result["skipped"] == 1
    fc.hostapi.delete_media_file.assert_not_called()
    items = _items(fc, plugin)
    assert len(items) == 1
    assert items[0]["result"] == "observed"
    assert items[0]["reason"] == "观察模式：未执行删除"


def test_scan_exception_records_one_failed(fc, tmp_path):
    plugin = FakePlugin()
    service = _build(fc, plugin)
    download = tmp_path / "downloads"
    download.mkdir()
    src = _media_file(download, "boom.mkv")
    _scan_setup(fc, download, record=None, get_history_error=RuntimeError("boom"))

    result = service.cleanup_repeat_sources("手动")

    assert result["failed"] == 1
    assert result["failed_preview"] == [src.as_posix()]
    items = _items(fc, plugin)
    assert len(items) == 1
    assert items[0]["result"] == "failed"
    assert "boom" in items[0]["reason"]
    assert items[0]["name"] == src.as_posix()
    assert service._status["total"]["failed"] == 1


# ── 锁序 / 失败隔离 / clear ───────────────────────────────────────────

def test_history_write_occurs_after_status_lock_released(fc):
    plugin = FakePlugin()
    service = _build(fc, plugin)
    fc.hostapi.delete_media_file = Mock(return_value=True)
    lock_owned = []

    def save_hook(key, value):
        if key == EXECUTION_HISTORY_KEY:
            lock_owned.append(service._status_lock._is_owned())

    plugin._save_hook = save_hook

    service.handle_transfer_failed(_failed_event("/tmp/a.mkv"))

    assert lock_owned == [False]
    assert plugin.save_calls.index(FAILCLEAN_STATUS_KEY) < plugin.save_calls.index(
        EXECUTION_HISTORY_KEY)


def test_history_write_failure_preserves_business(fc):
    plugin = FakePlugin()
    service = _build(fc, plugin)
    fc.hostapi.delete_media_file = Mock(return_value=True)

    def save_hook(key, value):
        if key == EXECUTION_HISTORY_KEY:
            raise RuntimeError("save failed")

    plugin._save_hook = save_hook

    result = service.handle_transfer_failed(_failed_event("/tmp/a.mkv"))

    assert result["deleted"] == 1
    assert result["history_deleted"] is True
    assert service._status["total"]["cleaned"] == 1
    assert _items(fc, plugin) == []
    assert fc.logger.error.called
    assert any(
        "写入展示历史失败" in str(call.args[0])
        for call in fc.logger.error.call_args_list)


def test_execution_history_clear_triggers_no_delete(fc):
    plugin = FakePlugin()
    _build(fc, plugin)
    fc.hostapi.delete_media_file = Mock(return_value=True)
    fc.exec_history.append(plugin, "failclean", {
        "trigger": "定时",
        "occurred_at": 1000.0,
        "action": "删除源文件",
        "result": "success",
        "reason": "ok",
    })

    removed = fc.exec_history.clear(plugin, "failclean")

    assert removed == 1
    assert fc.hostapi.delete_media_file.call_count == 0
    assert _items(fc, plugin) == []
