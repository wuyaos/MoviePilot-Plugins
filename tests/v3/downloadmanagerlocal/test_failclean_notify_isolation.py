"""整理失败清理通知隔离测试：通知渠道失败不得中断删除与计数主流程。

与 test_failclean_scan.py 的差别：本文件**不替身** `modules/failclean/notify.py`，
加载真实 notify 模块与真实 `utils/notify.py`（统一出口 notify_module_result），
并让宿主 post_message 直接抛异常——验证通知发送失败被吞掉后业务仍完成：

- 整理失败事件删除失败：结果字典、计数（event/total failed=1）、展示历史照常完成。
- 整理失败事件删除成功：文件真删、下载历史清理、删除事件广播照常完成。
- 巡检汇总通知失败：cleaned 计数与清理动作照常完成。
- 宿主没有 post_message：统一出口的 callable 守卫直接跳过，业务照常完成。

替身边界（均为模块自己声明的隔离点）：
- `modules/failclean/hostapi.py`：宿主能力（存储链、下载目录、媒体扩展名）。
- H&R 闸门 `modules/hr/guard.py`：保护判定，单独可控。
- 门控 `utils/config.py::module_active/observe_skip`：已由 test_gating.py 覆盖。
- `model/execution_history.py`：展示历史落盘 sink（真实 append 语义见
  test_failclean_execution_history.py），这里只替身成记录器以断言"历史已写"。
"""

from __future__ import annotations

import importlib.machinery
import os
import sys
import time
import types
from pathlib import Path
from unittest.mock import Mock

import pytest

PREFIX = "app.plugins.downloadmanagerlocal"
SKIP_GATE = "skip_path_transfer_failure"


class _BreakingPlugin:
    """post_message 必抛异常的宿主替身：存储与读取能力保持可用。"""

    def __init__(self) -> None:
        self.saved: list[tuple[str, object]] = []
        self.notified: list[str] = []

    def get_data(self, key):
        return None

    def save_data(self, key, value):
        self.saved.append((key, value))

    def post_message(self, **kwargs):
        self.notified.append(str(kwargs.get("title", "")))
        raise RuntimeError("通知渠道不可用")


class _SilentPlugin:
    """宿主没有 post_message：统一出口的 callable 守卫应直接跳过。"""

    def get_data(self, key):
        return None

    def save_data(self, key, value):
        pass


@pytest.fixture
def notify_env(mp_stubs, monkeypatch, tmp_path):
    """加载真实 notify + 真实 utils.notify + 真实 service，宿主通知必炸。"""

    def stub(name: str, **attrs):
        module = types.ModuleType(name)
        module.__spec__ = importlib.machinery.ModuleSpec(name, None)
        module.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, module)
        return module

    class FakeGuard:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def should_skip(self, gate: str, downloader: str, download_hash: str) -> bool:
            return False

        def get_skip_stats(self) -> dict:
            return {}

    class FakeDirectoryHelper:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def get_local_download_dirs(self):
            return [types.SimpleNamespace(download_path=p) for p in dir_state["paths"]]

    class FakeStorageChain:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def get_file_item(self, storage: str, path: Path):
            return None

        def delete_media_file(self, fileitem):
            return recorder.unlink(fileitem)

    class FakeTransferHistoryOper:
        def get_success_by_src(self, src: str, storage: str | None = None):
            return history_state["record"]

    class FakeDownloadHistoryOper:
        def get_hash_by_fullpath(self, fullpath: str) -> str:
            return str(history_state.get("hash") or "")

        def delete_file_by_fullpath(self, fullpath: str) -> None:
            recorder.history_deleted.append(fullpath)

    dir_state: dict = {"paths": [str(tmp_path)]}
    history_state: dict = {"record": None, "hash": ""}
    recorder = types.SimpleNamespace(
        unlinked=[],
        history_deleted=[],
        events_sent=[],
        history_records=[],
    )

    def unlink(item) -> bool:
        path = item if isinstance(item, str) else str((item or {}).get("path", ""))
        recorder.unlinked.append(path)
        try:
            os.remove(path)
        except FileNotFoundError:
            return False
        return True

    recorder.unlink = unlink

    stub(f"{PREFIX}.modules.hr.guard", SKIP_PATH_TRANSFER_FAILURE=SKIP_GATE, HrGuard=FakeGuard)
    stub(
        f"{PREFIX}.utils.config",
        module_active=lambda config, key: bool((config or {}).get("failcleanup_enabled")),
        observe_skip=lambda *args, **kwargs: False,
    )
    stub("app.application.directory", DirectoryHelper=FakeDirectoryHelper)
    stub("app.chain")
    stub("app.chain.storage", StorageChain=FakeStorageChain)
    stub("app.db.oper.transferhistory", TransferHistoryOper=FakeTransferHistoryOper)
    stub("app.schemas.types", MediaType=Mock(), MessageType=Mock(), EventType=Mock())
    stub("app.sdk.events", eventmanager=types.SimpleNamespace(
        send_event=lambda event_type, payload: recorder.events_sent.append(
            (str(event_type), str(payload.get("hash", "")))
        )
    ))

    # 中间包占位（带真实 __path__），避免与其他测试文件的替身互相污染
    plugin_root = Path(__file__).resolve().parents[3] / "plugins.v3" / "downloadmanagerlocal"
    for package, relpath in (
        (f"{PREFIX}.modules", "modules"),
        (f"{PREFIX}.modules.failclean", "modules/failclean"),
        (f"{PREFIX}.utils", "utils"),
        (f"{PREFIX}.model", "model"),
    ):
        placeholder = types.ModuleType(package)
        placeholder.__spec__ = importlib.machinery.ModuleSpec(package, None, is_package=True)
        placeholder.__path__ = [str(plugin_root / relpath)]
        monkeypatch.setitem(sys.modules, package, placeholder)

    # 展示历史落盘 sink 替身：只记录 append 调用，断言"历史已写"
    stub(
        f"{PREFIX}.model.execution_history",
        append=lambda plugin, module, record: recorder.history_records.append(record),
    )

    mp_stubs("modules/failclean/constants.py", "modules.failclean.constants")
    mp_stubs("modules/failclean/config.py", "modules.failclean.config")
    hostapi = mp_stubs("modules/failclean/hostapi.py", "modules.failclean.hostapi")
    service_mod = mp_stubs("modules/failclean/service.py", "modules.failclean.service")
    # 真实通知链：modules/failclean/notify.py 与 utils/notify.py 都不替身
    notify_mod = mp_stubs("modules/failclean/notify.py", "modules.failclean.notify")
    utils_notify = mp_stubs("utils/notify.py", "utils.notify")

    monkeypatch.setattr(hostapi, "local_download_paths", lambda: [Path(p) for p in dir_state["paths"]])
    monkeypatch.setattr(hostapi, "media_extensions", lambda: {".mkv"})
    monkeypatch.setattr(hostapi, "get_success_transfer_history", lambda src: history_state["record"])
    monkeypatch.setattr(
        hostapi, "dest_file_exists", lambda storage, dest: bool(dest) and Path(dest).exists()
    )
    monkeypatch.setattr(hostapi, "get_local_file_item", lambda path: str(path))
    monkeypatch.setattr(hostapi, "delete_media_file", unlink)
    monkeypatch.setattr(hostapi, "get_download_hash_by_fullpath", lambda fullpath: str(
        history_state.get("hash") or ""
    ))
    monkeypatch.setattr(
        hostapi, "delete_download_history_file", lambda fullpath: recorder.history_deleted.append(fullpath)
    )
    monkeypatch.setattr(
        hostapi,
        "send_download_file_deleted",
        lambda src, download_hash: recorder.events_sent.append((src, download_hash)),
    )

    def build(config: dict | None = None, plugin=None):
        """构造已初始化的服务实例；plugin 默认为 post_message 必炸的替身。"""
        service = service_mod.FailCleanService(plugin or _BreakingPlugin())
        service.init_module(
            {
                "failcleanup_enabled": True,
                "failcleanup_notify": True,
                "failcleanup_clean_repeat": True,
                "failcleanup_retain_hours": 1,
                **(config or {}),
            }
        )
        return service

    return types.SimpleNamespace(
        service_mod=service_mod,
        notify_mod=notify_mod,
        utils_notify=utils_notify,
        hostapi=hostapi,
        build=build,
        dir_state=dir_state,
        history_state=history_state,
        recorder=recorder,
        tmp_path=tmp_path,
    )

def _media_file(directory: Path, name: str, age_seconds: float = 7200.0) -> Path:
    """造一个 mtime 已过去 age_seconds 的媒体文件，越过保留时长门槛。"""
    path = directory / name
    path.write_bytes(b"fake")
    stamp = time.time() - age_seconds
    os.utime(path, (stamp, stamp))
    return path


def _failed_event(path: Path, download_hash: str = "deadbeef"):
    """构造整理失败事件替身。"""
    return types.SimpleNamespace(
        event_data={
            "fileitem": {"path": str(path)},
            "download_hash": download_hash,
            "downloader": "test-qb",
            "transferinfo": {"message": "整理器拒绝了该文件"},
        }
    )


def test_delete_failure_notifies_but_survives(notify_env, monkeypatch):
    """删除失败 + post_message 抛异常 → 异常被吞，结果/计数/历史照常完成。"""
    src = notify_env.tmp_path / "notifyfail.mkv"
    src.write_bytes(b"fake")
    monkeypatch.setattr(notify_env.hostapi, "delete_media_file", lambda fileitem: False)
    plugin = _BreakingPlugin()
    service = notify_env.build(plugin=plugin)

    result = service.handle_transfer_failed(_failed_event(src))

    assert result["deleted"] == 0
    assert result["skipped"] is False
    assert result["duplicate"] is False
    assert result["path"] == str(src)
    assert result["hash"] == "deadbeef"
    assert src.exists(), "删除失败时文件必须保留"
    # 通知确实被尝试过：真实 notify 链路拼好统一标题后调用 post_message 并炸掉
    assert plugin.notified == ["下载中心 · 失败清理（源文件删除失败）"]
    assert notify_env.recorder.history_records, "删除失败必须写 failed 展示历史"
    assert notify_env.recorder.history_records[0]["result"] == "failed"
    status = service.get_module_status()
    assert status["event"]["failed"] == 1
    assert status["total"]["failed"] == 1


def test_delete_success_notifies_but_survives(notify_env):
    """删除成功 + post_message 抛异常 → 文件真删、历史清理、事件广播照常完成。"""
    src = notify_env.tmp_path / "notifysuccess.mkv"
    src.write_bytes(b"fake")
    service = notify_env.build()

    result = service.handle_transfer_failed(_failed_event(src))

    assert result["deleted"] == 1
    assert result["history_deleted"] is True
    assert not src.exists()
    assert notify_env.recorder.history_deleted == [str(src)]
    assert notify_env.recorder.events_sent == [(str(src), "deadbeef")]
    assert notify_env.recorder.history_records, "删除成功必须写展示历史"
    assert notify_env.recorder.history_records[0]["result"] == "success"
    status = service.get_module_status()
    assert status["event"]["deleted"] == 1
    assert status["total"]["cleaned"] == 1


def test_scan_summary_notifies_but_survives(notify_env, tmp_path):
    """巡检清理成功 + post_message 抛异常 → cleaned 计数与文件删除照常完成。"""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    notify_env.dir_state["paths"] = [str(download_dir)]
    src = _media_file(download_dir, "residual.mkv")
    notify_env.history_state["record"] = types.SimpleNamespace(
        dest_storage="local", dest=str(tmp_path / "kept.mkv"), downloader="test-qb"
    )
    (tmp_path / "kept.mkv").write_bytes(b"media")
    notify_env.history_state["hash"] = "abcdef012345"
    service = notify_env.build()

    result = service.cleanup_repeat_sources("手动")

    assert result["cleaned"] == 1
    assert result["failed"] == 0
    assert not src.exists()
    assert notify_env.recorder.history_deleted == [src.as_posix()]


def test_missing_post_message_is_skipped(notify_env):
    """宿主没有 post_message → 统一出口 callable 守卫跳过，业务照常完成。"""
    src = notify_env.tmp_path / "silent.mkv"
    src.write_bytes(b"fake")
    service = notify_env.build(plugin=_SilentPlugin())

    result = service.handle_transfer_failed(_failed_event(src))

    assert result["deleted"] == 1
    assert not src.exists()
    assert service.get_module_status()["event"]["deleted"] == 1
