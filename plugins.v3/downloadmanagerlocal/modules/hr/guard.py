"""H&R 保护闸门：破坏性删除路径的统一查询入口。

HrService 在每轮检查后写入受保护任务快照（H&R 纳管且未达标的 (downloader, hash)）；
自动删种、整理失败删源、转移源端删除与同步删除转种目标在删除前查询本模块，命中即跳过并
计入对应路径的跳过计数。

所有 HrGuard 实例共享同一进程内状态，调用侧在插件包内用相对导入直接构造即可查询，无需持有
HrService（模块内写 `..hr.guard`，`modules/hr/` 内同级写 `.guard`；不写 `app.plugins.<插件 id>...`
绝对自引用）：::

    from ..hr.guard import SKIP_PATH_TRANSFER_SOURCE, HrGuard

    if HrGuard().should_skip(SKIP_PATH_TRANSFER_SOURCE, downloader_id, torrent_hash):
        return
"""

from __future__ import annotations

from threading import RLock
from typing import Iterable

from .models import hr_task_key

SKIP_PATH_TRANSFER_SOURCE = "transfer_source"
"""转移源端删除跳过计数路径。"""

SKIP_PATH_AUTO_REMOVE = "auto_remove"
"""自动删种跳过计数路径。"""

SKIP_PATH_TRANSFER_FAILURE = "transfer_failure"
"""整理失败删除源文件跳过计数路径。"""

SKIP_PATH_SYNC_DELETE = "sync_delete"
"""同步删除转种目标任务跳过计数路径。"""

SKIP_PATHS = (
    SKIP_PATH_TRANSFER_SOURCE,
    SKIP_PATH_AUTO_REMOVE,
    SKIP_PATH_TRANSFER_FAILURE,
    SKIP_PATH_SYNC_DELETE,
)
"""四条破坏性路径的跳过计数键。"""


class _GuardState:
    """跨实例共享的保护快照与跳过计数。"""

    def __init__(self) -> None:
        self.lock = RLock()
        self.enabled = False
        self.expected = False
        self.snapshot_ready = True
        self.protected_keys: set[str] = set()
        self.protected_hashes: dict[str, set[str]] = {}
        self.skip_stats: dict[str, int] = {}

    def clear(self) -> None:
        """清空保护快照（调用方持锁）。"""
        self.enabled = False
        self.protected_keys = set()
        self.protected_hashes = {}


_state = _GuardState()


class HrGuard:
    """H&R 保护查询与跳过计数；实例共享同一进程内快照。"""

    @property
    def enabled(self) -> bool:
        """返回 H&R 保护是否生效（hr_protection_enabled）。"""
        with _state.lock:
            return _state.enabled



    @property
    def unconfirmed(self) -> bool:
        """保护应按配置生效但没有可用快照：危险删除按「无法确认」保守阻止。"""
        with _state.lock:
            return _state.expected and not _state.snapshot_ready

    def expect(self, *, enabled: bool) -> None:
        """登记保护预期（模块生效但服务不可用时表示无法确认，模块未生效时撤销保护）。

        仅在生命周期初始化时按模块门控调用：enabled=True 且尚无快照时，危险删除保守跳过，
        直到 HrService 下一轮 update 写入真实快照；enabled=False 表示该联动整体跳过。
        """
        with _state.lock:
            _state.expected = bool(enabled)
            _state.snapshot_ready = not bool(enabled)
            _state.clear()

    def mark_unconfirmed(self) -> None:
        """本轮无法生成保护快照（检查中断/失败）：保留预期，快照置为不可用。"""
        with _state.lock:
            _state.snapshot_ready = False
    def update(self, *, enabled: bool, protected: Iterable[tuple[str, str]]) -> None:
        """整体替换受保护任务快照，由 HrService 在每轮检查后调用。"""
        keys: set[str] = set()
        by_hash: dict[str, set[str]] = {}
        for downloader_id, torrent_hash in protected:
            key = hr_task_key(downloader_id, torrent_hash)
            keys.add(key)
            hash_key = str(torrent_hash or "").strip().lower()
            if hash_key:
                by_hash.setdefault(hash_key, set()).add(key)
        with _state.lock:
            _state.enabled = bool(enabled)
            _state.expected = bool(enabled)
            _state.snapshot_ready = True
            _state.protected_keys = keys
            _state.protected_hashes = by_hash

    def is_protected(self, downloader_id: str, torrent_hash: str) -> bool:
        """判断任务是否为 H&R 纳管且未达标；未给下载器名时按 hash 匹配任一实例。"""
        hash_key = str(torrent_hash or "").strip().lower()
        if not hash_key:
            return False
        downloader_key = str(downloader_id or "").strip().lower()
        with _state.lock:
            if not _state.enabled:
                return False
            if downloader_key:
                return hr_task_key(downloader_key, hash_key) in _state.protected_keys
            return bool(_state.protected_hashes.get(hash_key))

    def record_skip(self, path: str) -> None:
        """按破坏性路径累计一次跳过计数。"""
        key = str(path or "").strip()
        if not key:
            return
        with _state.lock:
            _state.skip_stats[key] = _state.skip_stats.get(key, 0) + 1

    def should_skip(self, path: str, downloader_id: str, torrent_hash: str) -> bool:
        """查询保护并在命中时计数；保护状态无法确认时同样阻止这次危险删除。"""
        if not self.is_protected(downloader_id, torrent_hash) and not self.unconfirmed:
            return False
        self.record_skip(path)
        return True

    def get_skip_stats(self) -> dict[str, int]:
        """返回各路径跳过计数，始终包含四条破坏性路径。"""
        with _state.lock:
            stats = {path: _state.skip_stats.get(path, 0) for path in SKIP_PATHS}
            for path, count in _state.skip_stats.items():
                if path not in stats:
                    stats[path] = count
            return stats


_guard = HrGuard()


def get_guard() -> HrGuard:
    """返回共享的 H&R 保护闸门。"""
    return _guard


__all__ = (
    "SKIP_PATHS",
    "SKIP_PATH_AUTO_REMOVE",
    "SKIP_PATH_TRANSFER_FAILURE",
    "SKIP_PATH_TRANSFER_SOURCE",
    "HrGuard",
    "get_guard",
)
