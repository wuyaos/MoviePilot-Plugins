"""整理失败清理（failclean）真实分支测试。

替身边界只有三处，都是模块自己声明的隔离点：
- `modules/failclean/hostapi.py`：宿主能力（存储链、整理历史、下载目录、媒体扩展名）。
- H&R 闸门 `modules/hr/guard.py`：保护判定，单独可控。
- 门控 `utils/config.py::module_active`：总开关与模块开关的合并，已由 test_gating.py 覆盖。

被测对象是**真实的** `modules/failclean/service.py` 与真实 `hostapi.py`，重点覆盖
破坏性分支：什么情况下必须删、什么情况下必须不删。文件删除由替身真正 `unlink`，
因此断言基于真实文件系统副作用，而不是 mock 调用次数。
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


class _Recorder:
    """记录宿主侧回调，供断言下载历史清理与事件广播是否发生。"""

    def __init__(self) -> None:
        self.history_deleted: list[str] = []
        self.events_sent: list[tuple[str, str]] = []
        self.deleted_items: list[object] = []
        self.removed_paths: list[str] = []

    def unlink(self, item: object) -> bool:
        """把替身文件项映射回真实路径并真删，返回是否删除成功。"""
        self.deleted_items.append(item)
        path = item if isinstance(item, str) else str((item or {}).get("path", ""))
        try:
            os.remove(path)
        except FileNotFoundError:
            return False
        self.removed_paths.append(path)
        return True


@pytest.fixture
def fc(mp_stubs, monkeypatch):
    """加载真实 hostapi + service，并把宿主边界换成可控替身。"""

    def stub(name: str, **attrs):
        module = types.ModuleType(name)
        # 替身必须带 __spec__：无 spec 的模块会让 pytest 渲染失败回溯时
        # importlib.resources.files() 抛 INTERNALERROR，把真实失败变成 "no tests ran"。
        module.__spec__ = importlib.machinery.ModuleSpec(name, None)
        module.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, module)
        return module

    guard_state = {"skip": False}

    class FakeGuard:
        """H&R 闸门替身：should_skip 结果由 guard_state 控制。"""

        def __init__(self, *args, **kwargs) -> None:
            pass

        def should_skip(self, gate: str, downloader: str, download_hash: str) -> bool:
            return bool(guard_state["skip"])

        def get_skip_stats(self) -> dict:
            return {}

    class FakeDirectoryHelper:
        """宿主下载目录替身：目录列表由测试注入。"""

        def __init__(self, *args, **kwargs) -> None:
            pass

        def get_local_download_dirs(self):
            return [types.SimpleNamespace(download_path=p) for p in dir_state["paths"]]

    class FakeStorageChain:
        """存储链替身：文件项存在性与媒体文件删除由测试注入。"""

        def __init__(self, *args, **kwargs) -> None:
            pass

        def get_file_item(self, storage: str, path: Path):
            exists = path.exists() if storage == "local" else False
            return str(path) if exists else None

        def delete_media_file(self, fileitem):
            return recorder.unlink(fileitem)

    class FakeTransferHistoryOper:
        """整理历史替身：按源路径返回测试注入的成功记录。"""

        def get_success_by_src(self, src: str, storage: str | None = None):
            return history_state["record"]

    class FakeDownloadHistoryOper:
        """下载历史替身：记录被清理的路径，hash 反查由测试注入。"""

        def get_hash_by_fullpath(self, fullpath: str) -> str:
            return str(history_state.get("hash") or "")

        def delete_file_by_fullpath(self, fullpath: str) -> None:
            recorder.history_deleted.append(fullpath)

    dir_state: dict = {"paths": []}
    history_state: dict = {"record": None, "hash": ""}
    recorder = _Recorder()

    stub(f"{PREFIX}.modules.hr.guard", SKIP_PATH_TRANSFER_FAILURE=SKIP_GATE, HrGuard=FakeGuard)
    stub(
        f"{PREFIX}.utils.config",
        module_active=lambda config, key: bool((config or {}).get("failcleanup_enabled")),
    )
    stub(
        f"{PREFIX}.modules.failclean.notify",
        notify_delete_failure=Mock(),
        notify_delete_success=Mock(),
        notify_scan_result=Mock(),
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

    # 中间包也要占位并给真实 __path__：别的测试文件会在导入期把
    # app.plugins.downloadmanagerlocal.service 装成 __path__=[] 的替身，
    # 不占位就会在导入 ...modules.failclean 时 ModuleNotFoundError。
    plugin_root = Path(__file__).resolve().parents[3] / "plugins.v3" / "downloadmanagerlocal"
    for package, relpath in (
        (f"{PREFIX}.modules", "modules"),
        (f"{PREFIX}.modules.failclean", "modules/failclean"),
        (f"{PREFIX}.utils", "utils"),
    ):
        placeholder = types.ModuleType(package)
        placeholder.__spec__ = importlib.machinery.ModuleSpec(
            package, None, is_package=True
        )
        placeholder.__path__ = [str(plugin_root / relpath)]
        monkeypatch.setitem(sys.modules, package, placeholder)

    mp_stubs("modules/failclean/constants.py", "modules.failclean.constants")
    mp_stubs("modules/failclean/config.py", "modules.failclean.config")
    hostapi = mp_stubs("modules/failclean/hostapi.py", "modules.failclean.hostapi")
    service_mod = mp_stubs("modules/failclean/service.py", "modules.failclean.service")

    # 默认替身：命中一次成功整理记录、目标存在、扩展名 .mkv、删除真删文件。
    monkeypatch.setattr(hostapi, "local_download_paths", lambda: [
        Path(p) for p in dir_state["paths"]
    ])
    monkeypatch.setattr(hostapi, "media_extensions", lambda: {".mkv"})
    monkeypatch.setattr(
        hostapi, "get_success_transfer_history", lambda src: history_state["record"]
    )
    monkeypatch.setattr(
        hostapi, "dest_file_exists", lambda storage, dest: bool(dest) and Path(dest).exists()
    )
    monkeypatch.setattr(hostapi, "get_local_file_item", lambda path: str(path))
    monkeypatch.setattr(
        hostapi, "delete_media_file", lambda fileitem: recorder.unlink(fileitem)
    )
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

    def build(config: dict | None = None):
        """构造已初始化的服务实例。"""
        service = service_mod.FailCleanService(Mock())
        service.init_module(
            {
                "failcleanup_enabled": True,
                "failcleanup_notify": False,
                "failcleanup_clean_repeat": True,
                "failcleanup_retain_hours": 1,
                **(config or {}),
            }
        )
        return service

    return types.SimpleNamespace(
        service_mod=service_mod,
        hostapi=hostapi,
        build=build,
        dir_state=dir_state,
        history_state=history_state,
        guard_state=guard_state,
        recorder=recorder,
    )


def _media_file(directory: Path, name: str, age_seconds: float = 7200.0) -> Path:
    """造一个 mtime 已过去 age_seconds 的媒体文件，越过保留时长门槛。"""
    path = directory / name
    path.write_bytes(b"fake")
    stamp = time.time() - age_seconds
    os.utime(path, (stamp, stamp))
    return path


@pytest.fixture
def scan_env(fc, tmp_path):
    """一个下载目录 + 一个目标目录（目标目录不进扫描范围，避免干扰计数）。"""
    download_dir = tmp_path / "downloads"
    dest_dir = tmp_path / "media"
    download_dir.mkdir()
    dest_dir.mkdir()
    fc.dir_state["paths"] = [str(download_dir)]
    return types.SimpleNamespace(
        fc=fc, download=download_dir, dest=dest_dir, tmp=tmp_path
    )


def test_scan_deletes_success_residual(scan_env):
    """有成功整理记录且目标仍存在 → 删源文件、清下载历史、广播删除事件。"""
    src = _media_file(scan_env.download, "dup.mkv")
    dest = scan_env.dest / "kept.mkv"
    dest.write_bytes(b"media")
    scan_env.fc.history_state["record"] = types.SimpleNamespace(
        dest_storage="local", dest=str(dest), downloader="test-qb"
    )
    scan_env.fc.history_state["hash"] = "abcdef012345"

    result = scan_env.fc.build().cleanup_repeat_sources("手动")

    assert result["scanned"] == 1
    assert result["cleaned"] == 1
    assert result["failed"] == 0
    assert not src.exists(), "成功的重复残留必须被删除"
    assert dest.exists(), "目标媒体文件不得被触碰"
    assert scan_env.fc.recorder.history_deleted == [src.as_posix()]
    assert scan_env.fc.recorder.events_sent == [(src.as_posix(), "abcdef012345")]
    assert result["cleaned_preview"] == [src.as_posix()]


@pytest.mark.parametrize(
    "scenario",
    ["无成功整理记录", "目标文件已不存在", "文件仍在保留期内", "非媒体扩展名", "模块未启用", "未开启重复残留清理"],
)
def test_scan_never_deletes(scan_env, scenario):
    """六种情况下都不得删除文件：这是本模块最关键的破坏性边界。"""
    age = 0.0 if scenario == "文件仍在保留期内" else 7200.0
    name = "keep.txt" if scenario == "非媒体扩展名" else "keep.mkv"
    src = _media_file(scan_env.download, name, age)

    if scenario != "无成功整理记录":
        scan_env.fc.history_state["record"] = types.SimpleNamespace(
            dest_storage="local", dest=str(scan_env.dest / "kept.mkv"), downloader="test-qb"
        )
    if scenario != "目标文件已不存在":
        (scan_env.dest / "kept.mkv").write_bytes(b"media")

    config = {}
    if scenario == "模块未启用":
        config["failcleanup_enabled"] = False
    if scenario == "未开启重复残留清理":
        config["failcleanup_clean_repeat"] = False

    result = scan_env.fc.build(config).cleanup_repeat_sources("手动")

    assert src.exists(), f"{scenario} 时文件被删除了"
    assert result["cleaned"] == 0
    assert scan_env.fc.recorder.history_deleted == []
    assert scan_env.fc.recorder.events_sent == []
    if scenario in {"文件仍在保留期内", "非媒体扩展名", "模块未启用", "未开启重复残留清理"}:
        assert result["scanned"] == 0, "候选都算不上，不应计入 scanned"


def test_scan_skips_hr_protected(scan_env):
    """H&R 保护命中 → 跳过删除并计入 skipped，文件保留。"""
    src = _media_file(scan_env.download, "protected.mkv")
    dest = scan_env.dest / "kept.mkv"
    dest.write_bytes(b"media")
    scan_env.fc.history_state["record"] = types.SimpleNamespace(
        dest_storage="local", dest=str(dest), downloader="test-qb"
    )
    scan_env.fc.guard_state["skip"] = True

    result = scan_env.fc.build().cleanup_repeat_sources("手动")

    assert result["scanned"] == 1
    assert result["cleaned"] == 0
    assert result["skipped"] == 1
    assert result["failed"] == 0
    assert src.exists(), "H&R 保护命中时不得删除源文件"
    assert scan_env.fc.recorder.events_sent == []


def test_scan_reports_delete_failure(scan_env, monkeypatch):
    """存储链删除失败 → 计入 failed 且不出现在 cleaned 预览，文件保留。"""
    src = _media_file(scan_env.download, "faildel.mkv")
    dest = scan_env.dest / "kept.mkv"
    dest.write_bytes(b"media")
    scan_env.fc.history_state["record"] = types.SimpleNamespace(
        dest_storage="local", dest=str(dest), downloader="test-qb"
    )
    monkeypatch.setattr(scan_env.fc.hostapi, "delete_media_file", lambda fileitem: False)

    result = scan_env.fc.build().cleanup_repeat_sources("手动")

    assert result["scanned"] == 1
    assert result["cleaned"] == 0
    assert result["failed"] == 1
    assert src.exists()
    assert result["failed_preview"] == [src.as_posix()]


def test_scan_skips_overlapping_run(scan_env):
    """已有巡检在运行 → 重叠触发直接返回空结果，不重复删文件。"""
    src = _media_file(scan_env.download, "overlap.mkv")
    service = scan_env.fc.build()
    service._run_lock.acquire()
    try:
        result = service.cleanup_repeat_sources("定时")
    finally:
        service._run_lock.release()

    assert result["scanned"] == 0
    assert result["cleaned"] == 0
    assert src.exists()


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


def test_transfer_failed_event_deletes_source(fc, tmp_path):
    """整理失败事件 → 立即删源文件、清下载历史、广播删除事件。"""
    src = tmp_path / "failed.mkv"
    src.write_bytes(b"fake")
    service = fc.build()

    result = service.handle_transfer_failed(_failed_event(src))

    assert result["deleted"] == 1
    assert result["history_deleted"] is True
    assert result["skipped"] is False
    # 事件路径用 MP 传来的 fileitem.path 原样（Windows 为反斜杠）；
    # 巡检路径统一 as_posix()。Linux 容器内两者相同，这里按各路径真实来源断言。
    assert result["path"] == str(src)
    assert result["hash"] == "deadbeef"
    assert not src.exists()
    assert fc.recorder.history_deleted == [str(src)]
    assert fc.recorder.events_sent == [(str(src), "deadbeef")]


def test_transfer_failed_event_without_fileitem_is_ignored(fc):
    """事件缺少 fileitem → 不执行任何删除。"""
    service = fc.build()

    result = service.handle_transfer_failed(types.SimpleNamespace(event_data={}))

    assert result["deleted"] == 0
    assert fc.recorder.deleted_items == []
    assert fc.recorder.events_sent == []


def test_transfer_failed_event_disabled_module(fc, tmp_path):
    """模块未启用 → 整理失败事件不触发删除。"""
    src = tmp_path / "disabled.mkv"
    src.write_bytes(b"fake")
    service = fc.build({"failcleanup_enabled": False})

    result = service.handle_transfer_failed(_failed_event(src))

    assert result["deleted"] == 0
    assert src.exists()


def test_transfer_failed_event_dedupes_recent_delete(fc, tmp_path):
    """同一 (hash, 路径) 在窗口内重复到达 → 第二次不重复删除。"""
    src = tmp_path / "dup-event.mkv"
    src.write_bytes(b"fake")
    service = fc.build()

    first = service.handle_transfer_failed(_failed_event(src))
    second = service.handle_transfer_failed(_failed_event(src))

    assert first["deleted"] == 1
    assert second["deleted"] == 0, "窗口内重复事件不得再次执行删除"
    assert second["duplicate"] is True
    assert len(fc.recorder.events_sent) == 1


def test_module_status_exposes_scan_and_event_counters(fc, tmp_path):
    """状态接口暴露开关、保留时长与本轮/累计计数，供数据页展示。"""
    src = tmp_path / "status.mkv"
    src.write_bytes(b"fake")
    service = fc.build()
    service.handle_transfer_failed(_failed_event(src))

    status = service.get_module_status()

    assert status["enabled"] is True
    assert status["clean_repeat"] is True
    assert status["retain_hours"] == 1
    assert status["event"]["deleted"] == 1
    assert status["total"]["cleaned"] == 1
    assert "cron" in status and "last_scan_trigger" in status
