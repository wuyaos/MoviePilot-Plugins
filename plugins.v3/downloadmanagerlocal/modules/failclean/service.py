"""整理失败清理服务：整理失败即时删源与重复下载残留巡检。"""

from __future__ import annotations

import time
import traceback
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock, RLock
from typing import Any, Optional

from app.sdk.logging import logger

from dataclasses import replace
from ...utils.config import module_active, observe_skip
from ..hr.guard import SKIP_PATH_TRANSFER_FAILURE, HrGuard
from . import hostapi
from .config import FailCleanConfig, parse_failclean_config
from .constants import (
    FAILCLEAN_LOG_PREFIX,
    FAILCLEAN_NOTIFY_PREVIEW_LIMIT,
    FAILCLEAN_RECENT_WINDOW_SECONDS,
    FAILCLEAN_SCAN_TRIGGER,
    FAILCLEAN_STATUS_DATA_KEY,
    FAILCLEAN_TRANSFER_FAILED_TRIGGER,
)
from .history import (
    as_counter as _as_counter,
    as_float as _as_float,
    cleared_status,
    empty_status,
    history_removed_count,
)
from .notify import notify_delete_failure, notify_delete_success, notify_scan_result

REPEAT_RESIDUAL_REASON = "已整理成功的重复下载残留"
UNKNOWN_FAIL_REASON = "未知"

STATUS_TEMPLATE = empty_status()
"""持久化的最近巡检、整理失败即时清理与累计计数模板（空模板见 history.py）。"""


def empty_transfer_failed_result() -> dict[str, Any]:
    """返回整理失败清理的空结果。"""
    return {
        "trigger": FAILCLEAN_TRANSFER_FAILED_TRIGGER,
        "path": "",
        "hash": "",
        "deleted": 0,
        "history_deleted": False,
        "skipped": False,
        "duplicate": False,
    }


def empty_scan_result(trigger_source: str) -> dict[str, Any]:
    """返回巡检清理的空结果。"""
    return {
        "enabled": False,
        "trigger": trigger_source,
        "scanned": 0,
        "cleaned": 0,
        "failed": 0,
        "skipped": 0,
        "cleaned_preview": [],
        "failed_preview": [],
    }


class FailCleanService:
    """整理失败清理服务对象，由插件生命周期创建并注册调度。

    用法：``FailCleanService(plugin).init_module(config)`` 完成配置加载与计数恢复；
    事件路径调用 :meth:`handle_transfer_failed`，巡检调用 :meth:`cleanup_repeat_sources`；
    API/总览读取 :meth:`get_module_status`；插件停止时调用 :meth:`stop`。

    所有实例共享进程内 H&R 保护快照（:class:`HrGuard`），破坏性删除前统一查询
    ``SKIP_PATH_TRANSFER_FAILURE``，命中即跳过并只由闸门计数。
    """

    def __init__(self, plugin: Any):
        """
        :param plugin: DownloadManagerLocal 插件实例，提供 get_data/save_data/post_message。
        """
        self._plugin = plugin
        self._config = FailCleanConfig()
        self._status = deepcopy(STATUS_TEMPLATE)
        self._guard = HrGuard()
        self._recent_deletes: dict[str, float] = {}
        self._status_lock = RLock()
        self._run_lock = Lock()
        self._stopped = False

    @property
    def config(self) -> FailCleanConfig:
        """返回当前运行时配置。"""
        return self._config

    def init_module(self, config: Optional[dict] = None) -> None:
        """按插件配置初始化模块并恢复持久化计数。"""
        parsed = parse_failclean_config(config)
        # 门控对齐：服务配置 enabled = 总开关 AND failcleanup_enabled（utils/config.py::module_active）。
        # FailCleanConfig 是 frozen dataclass，用 dataclasses.replace 构造新实例。
        self._config = replace(parsed, enabled=module_active(config or {}, "failclean"))
        self._status = self._load_status()
        self._recent_deletes.clear()
        self._stopped = False
        logger.info(
            f"{FAILCLEAN_LOG_PREFIX}初始化完成：开关={self._config.enabled} "
            f"重复残留清理={self._config.clean_repeat} 保留={self._config.retain_hours}h "
            f"周期={self._config.cron or '未配置'}"
        )

    def handle_transfer_failed(self, event: Any) -> dict[str, Any]:
        """处理整理失败事件：立即删除源文件、下载历史并广播下载文件删除事件。"""
        result = empty_transfer_failed_result()
        if not self._config.enabled:
            logger.info(f"{FAILCLEAN_LOG_PREFIX}未启用，跳过整理失败清理")
            return result

        event_data = getattr(event, "event_data", None) or {}
        fileitem = _field(event_data, "fileitem")
        path = _text(_field(fileitem, "path"))
        if fileitem is None or not path:
            logger.warning(f"{FAILCLEAN_LOG_PREFIX}整理失败事件缺少 fileitem，跳过源文件清理")
            self._record_history(
                trigger=FAILCLEAN_TRANSFER_FAILED_TRIGGER,
                action="删除源文件",
                result="failed",
                reason="整理失败事件缺少 fileitem",
            )
            return result

        fail_reason = _text(_field(_field(event_data, "transferinfo"), "message")) or UNKNOWN_FAIL_REASON
        download_hash = _text(_field(event_data, "download_hash"))
        downloader_id = _text(_field(event_data, "downloader"))
        logger.info(f"{FAILCLEAN_LOG_PREFIX}整理失败，准备删除源文件：{path}，原因：{fail_reason}")
        delete_result = self._delete_source_file(
            fileitem=fileitem,
            path=path,
            download_hash=download_hash,
            downloader_id=downloader_id,
            reason=f"整理失败：{fail_reason}",
            send_notify=True,
        )
        self._record_result(
            scope="event",
            **counters_of(delete_result),
        )
        self._record_delete_history(
            trigger=FAILCLEAN_TRANSFER_FAILED_TRIGGER,
            delete_result=delete_result,
            downloader_id=downloader_id,
            torrent_hash=download_hash,
            name=path,
        )
        result.update({key: delete_result[key] for key in ("deleted", "history_deleted", "skipped", "duplicate")})
        result["path"] = path
        result["hash"] = download_hash
        return result

    def cleanup_repeat_sources(self, trigger_source: str = FAILCLEAN_SCAN_TRIGGER) -> dict[str, Any]:
        """巡检本地下载目录，清理已成功整理但重复下载残留的媒体文件。

        :param trigger_source: 触发来源名，用于日志与状态展示。
        :return: 本轮巡检统计：scanned/cleaned/failed/skipped 与最多 10 条路径预览。
        """
        if not self._config.enabled or not self._config.clean_repeat:
            logger.info(f"{FAILCLEAN_LOG_PREFIX}未启用重复下载残留清理，跳过{trigger_source}")
            return empty_scan_result(trigger_source)
        if self._stopped:
            logger.info(f"{FAILCLEAN_LOG_PREFIX}服务已停止，跳过{trigger_source}巡检")
            return empty_scan_result(trigger_source)
        if not self._run_lock.acquire(blocking=False):
            logger.info(f"{FAILCLEAN_LOG_PREFIX}已有巡检在运行，跳过重叠触发：{trigger_source}")
            return empty_scan_result(trigger_source)
        try:
            return self._scan_once(trigger_source)
        finally:
            self._run_lock.release()

    def get_module_status(self) -> dict[str, Any]:
        """返回模块状态：最近巡检、整理失败清理计数、累计清理数与 H&R 保护跳过数。"""
        with self._status_lock:
            last_scan_time = self._status["last_scan_time"]
            last_scan_trigger = self._status["last_scan_trigger"]
            scan = dict(self._status["scan"])
            event = dict(self._status["event"])
            total = dict(self._status["total"])
        return {
            "enabled": self._config.enabled,
            "clean_repeat": self._config.clean_repeat,
            "cron": self._config.cron,
            "retain_hours": self._config.retain_hours,
            "last_scan_time": last_scan_time,
            "last_scan_trigger": last_scan_trigger,
            "scan": scan,
            "event": event,
            "total": total,
            "skip_stats": self._guard.get_skip_stats(),
        }

    def clear_history(self) -> dict[str, Any]:
        """清理最近巡检与整理失败即时清理结果，保留累计计数（数据页「清理记录」）。

        :return: ``{"removed": int, "busy": bool}``；``busy=True`` 表示巡检正在运行，
            未做任何清理，由 handler 转 409。
        """
        if not self._run_lock.acquire(blocking=False):
            return {"removed": 0, "busy": True}
        try:
            with self._status_lock:
                removed = history_removed_count(self._status)
                if not removed:
                    return {"removed": 0, "busy": False}
                cleared = cleared_status(self._status)
                self._plugin.save_data(FAILCLEAN_STATUS_DATA_KEY, deepcopy(cleared))
                self._status = cleared
                return {"removed": removed, "busy": False}
        finally:
            self._run_lock.release()

    def stop(self) -> None:
        """停止后续巡检；已在运行的巡检在文件之间退出。"""
        self._stopped = True
        logger.info(f"{FAILCLEAN_LOG_PREFIX}服务已停止")

    def _scan_once(self, trigger_source: str) -> dict[str, Any]:
        """执行一轮巡检：按本地下载目录递归扫描候选残留文件并逐个清理。"""
        cutoff_time = datetime.now() - timedelta(hours=self._config.retain_hours)
        media_exts = hostapi.media_extensions()
        cleaned_paths: list[str] = []
        failed_paths: list[str] = []
        scanned = 0
        cleaned = 0
        failed = 0
        skipped = 0

        for base_path in hostapi.local_download_paths():
            if self._stopped:
                logger.info(f"{FAILCLEAN_LOG_PREFIX}服务已停止，中断{trigger_source}巡检")
                break
            if not base_path.exists():
                logger.debug(f"{FAILCLEAN_LOG_PREFIX}跳过不存在的下载目录：{base_path}")
                continue

            for file_path in base_path.rglob("*"):
                if self._stopped:
                    logger.info(f"{FAILCLEAN_LOG_PREFIX}服务已停止，中断{trigger_source}巡检")
                    break
                try:
                    if not file_path.is_file():
                        continue
                    if file_path.suffix.lower() not in media_exts:
                        continue
                    if datetime.fromtimestamp(file_path.stat().st_mtime) > cutoff_time:
                        continue
                    scanned += 1
                    delete_result = self._cleanup_repeat_file(file_path)
                except Exception as error:
                    logger.error(
                        f"{FAILCLEAN_LOG_PREFIX}巡检重复下载残留失败：{file_path}，{error}\n"
                        f"{traceback.format_exc()}"
                    )
                    failed_paths.append(file_path.as_posix())
                    failed += 1
                    self._record_history(
                        trigger=trigger_source,
                        action="删除源文件",
                        result="failed",
                        reason=f"巡检异常：{error}",
                        name=file_path.as_posix(),
                    )
                    continue

                if delete_result is None:
                    continue
                counts = counters_of(delete_result)
                cleaned += counts["deleted"]
                failed += counts["failed"]
                skipped += counts["skipped"]
                self._record_delete_history(
                    trigger=trigger_source,
                    delete_result=delete_result,
                    downloader_id=delete_result.get("downloader_id", ""),
                    torrent_hash=delete_result.get("torrent_hash", ""),
                    name=file_path.as_posix(),
                )
                if delete_result["deleted"]:
                    cleaned_paths.append(file_path.as_posix())
                elif counts["failed"]:
                    failed_paths.append(file_path.as_posix())
            if self._stopped:
                break

        scan_counts = {
            "scanned": scanned,
            "cleaned": cleaned,
            "failed": failed,
            "skipped": skipped,
        }
        self._record_scan_result(trigger_source, scan_counts)
        if cleaned_paths:
            logger.info(f"{FAILCLEAN_LOG_PREFIX}巡检完成，共清理 {len(cleaned_paths)} 个文件")
            if self._config.notify:
                notify_scan_result(self._plugin, cleaned_paths)
        if failed_paths:
            logger.warning(
                f"{FAILCLEAN_LOG_PREFIX}巡检失败，共 {len(failed_paths)} 个文件待人工检查："
                f"{failed_paths[:FAILCLEAN_NOTIFY_PREVIEW_LIMIT]}"
            )

        result = empty_scan_result(trigger_source)
        result["enabled"] = self._config.enabled
        result.update(scan_counts)
        result["cleaned_preview"] = cleaned_paths[:FAILCLEAN_NOTIFY_PREVIEW_LIMIT]
        result["failed_preview"] = failed_paths[:FAILCLEAN_NOTIFY_PREVIEW_LIMIT]
        return result

    def _cleanup_repeat_file(self, file_path: Path) -> Optional[dict[str, Any]]:
        """校验单个候选文件并清理；不是“已成功整理且目标仍在”的残留时返回 None。"""
        transfer_history = hostapi.get_success_transfer_history(file_path.as_posix())
        if transfer_history is None:
            return None
        dest_storage = _text(_field(transfer_history, "dest_storage"))
        dest = _text(_field(transfer_history, "dest"))
        if not hostapi.dest_file_exists(dest_storage, dest):
            return None
        fileitem = hostapi.get_local_file_item(file_path)
        if fileitem is None:
            return None
        downloader_id = _text(_field(transfer_history, "downloader"))
        download_hash = hostapi.get_download_hash_by_fullpath(file_path.as_posix())
        result = self._delete_source_file(
            fileitem=fileitem,
            path=file_path.as_posix(),
            download_hash=download_hash,
            downloader_id=downloader_id,
            reason=REPEAT_RESIDUAL_REASON,
            send_notify=False,
        )
        result["downloader_id"] = downloader_id
        result["torrent_hash"] = download_hash
        return result

    def _delete_source_file(
        self,
        *,
        fileitem: Any,
        path: str,
        download_hash: str,
        downloader_id: str,
        reason: str,
        send_notify: bool,
    ) -> dict[str, Any]:
        """删除源文件与下载历史；H&R 保护命中时整条路径跳过（闸门自身完成计数）。"""
        if observe_skip(self._plugin, "failclean", "删除源文件", f"{path}（{reason}）"):
            return {
                "deleted": 0,
                "history_deleted": False,
                "skipped": True,
                "duplicate": False,
            }
        if self._is_recent_delete(path, download_hash):
            logger.info(f"{FAILCLEAN_LOG_PREFIX}忽略窗口内重复的删除请求：{path}")
            return {
                "deleted": 0,
                "history_deleted": False,
                "skipped": False,
                "duplicate": True,
            }

        # 一次保护查询同时覆盖源文件删除与下载历史删除，避免闸门重复计数。
        if self._guard.should_skip(SKIP_PATH_TRANSFER_FAILURE, downloader_id, download_hash):
            logger.warning(
                f"{FAILCLEAN_LOG_PREFIX}H&R 保护跳过删除：{path}"
                f"（{downloader_id or '未知下载器'} / {download_hash or '无 hash'}）"
            )
            return {
                "deleted": 0,
                "history_deleted": False,
                "skipped": True,
                "duplicate": False,
            }

        if not hostapi.delete_media_file(fileitem):
            logger.error(f"{FAILCLEAN_LOG_PREFIX}源文件删除失败：{path}，原因：{reason}")
            if send_notify and self._config.notify:
                notify_delete_failure(self._plugin, path, reason)
            return {
                "deleted": 0,
                "history_deleted": False,
                "skipped": False,
                "duplicate": False,
            }

        logger.info(f"{FAILCLEAN_LOG_PREFIX}源文件已删除：{path}，原因：{reason}")
        self._mark_recent_delete(path, download_hash)
        history_deleted = self._clean_download_history(path, download_hash)
        if send_notify and self._config.notify:
            notify_delete_success(self._plugin, path, reason)
        return {
            "deleted": 1,
            "history_deleted": history_deleted,
            "skipped": False,
            "duplicate": False,
        }

    def _clean_download_history(self, path: str, download_hash: str) -> bool:
        """删除下载历史并广播下载文件删除事件；记录清理失败不改变文件已删除的事实。"""
        try:
            hostapi.delete_download_history_file(path)
            if download_hash:
                hostapi.send_download_file_deleted(path, download_hash)
        except Exception as error:
            logger.error(f"{FAILCLEAN_LOG_PREFIX}清理下载记录失败：{path}：{error}")
            return False
        return True

    def _is_recent_delete(self, path: str, download_hash: str) -> bool:
        """判断同一 (hash, 路径) 是否刚处理过，避免事件重发重复删除。"""
        now = time.time()
        for key, timestamp in list(self._recent_deletes.items()):
            if now - float(timestamp or 0) > FAILCLEAN_RECENT_WINDOW_SECONDS:
                self._recent_deletes.pop(key, None)
        last = float(self._recent_deletes.get(_delete_key(path, download_hash)) or 0)
        return bool(last and now - last <= FAILCLEAN_RECENT_WINDOW_SECONDS)

    def _mark_recent_delete(self, path: str, download_hash: str) -> None:
        """登记一次已执行的删除操作。"""
        self._recent_deletes[_delete_key(path, download_hash)] = time.time()

    def _record_delete_history(
        self,
        *,
        trigger: str,
        delete_result: dict[str, Any],
        downloader_id: str,
        torrent_hash: str,
        name: str,
    ) -> None:
        """把一次删除结果映射为展示历史并逐条写入（duplicate 不写；写入失败只记日志）。

        delete_result 的 duplicate/skipped/deleted 语义与 counters_of 一致：
        duplicate 表示窗口内重复请求（不写，与既有「不计入任何计数」口径一致），
        skipped 需区分观察模式（observed）与 H&R 保护（skipped）。
        """
        if delete_result.get("duplicate"):
            return
        if delete_result.get("deleted"):
            result = "success"
            reason = "源文件已删除"
        elif delete_result.get("skipped"):
            if self._observe_only():
                result = "observed"
                reason = "观察模式：未执行删除"
            else:
                result = "skipped"
                reason = "H&R 保护跳过"
        else:
            result = "failed"
            reason = "删除源文件失败"
        self._record_history(
            trigger=trigger,
            action="删除源文件",
            result=result,
            reason=reason,
            downloader=downloader_id,
            torrent_hash=torrent_hash,
            name=name,
        )

    def _record_history(
        self,
        *,
        trigger: str,
        action: str,
        result: str,
        reason: str,
        downloader: Optional[str] = None,
        torrent_hash: Optional[str] = None,
        name: Optional[str] = None,
    ) -> None:
        """写一条展示历史；写入失败只记日志，绝不改变业务结果或既有计数。"""
        record: dict[str, Any] = {
            "trigger": trigger,
            "occurred_at": time.time(),
            "action": action,
            "result": result,
            "reason": reason,
        }
        if downloader is not None:
            record["downloader_id"] = downloader
        if torrent_hash is not None:
            record["torrent_hash"] = torrent_hash
        if name is not None:
            record["name"] = name
        try:
            from ...model import execution_history

            execution_history.append(self._plugin, "failclean", record)
        except Exception as error:
            logger.error(f"{FAILCLEAN_LOG_PREFIX}写入展示历史失败（不影响业务结果）：{error}")

    def _observe_only(self) -> bool:
        """只读判断本轮是否处于观察模式（用于区分 observed/skipped 记录）。

        延迟导入：观察模式快照由 utils.config 提供，但既有测试桩只导出了
        module_active/observe_skip；缺失时按「非观察」处理——该环境下
        observe_skip 恒返回 False，skipped 结果只能来自 H&R 保护。
        """
        try:
            from ...utils.config import observe_only
        except ImportError:
            return False
        return bool(observe_only(self._plugin, "failclean"))

    def _record_result(
        self,
        *,
        scope: str,
        deleted: int,
        failed: int,
        skipped: int,
        duplicate: bool = False,
    ) -> None:
        """累计一次删除结果；重复请求不计入任何计数。"""
        if duplicate:
            return
        with self._status_lock:
            if scope == "event":
                self._status["event"]["deleted"] += deleted
                self._status["event"]["failed"] += failed
                self._status["event"]["skipped"] += skipped
            self._status["total"]["cleaned"] += deleted
            self._status["total"]["failed"] += failed
            self._status["total"]["skipped"] += skipped
            self._save_status()

    def _record_scan_result(self, trigger_source: str, scan_counts: dict[str, int]) -> None:
        """登记最近一轮巡检结果与时间。"""
        with self._status_lock:
            self._status["last_scan_time"] = time.time()
            self._status["last_scan_trigger"] = trigger_source
            self._status["scan"] = dict(scan_counts)
            self._record_result(
                scope="scan",
                deleted=scan_counts["cleaned"],
                failed=scan_counts["failed"],
                skipped=scan_counts["skipped"],
            )

    def _load_status(self) -> dict[str, Any]:
        """读取持久化计数；缺失或结构不符时回退模板。"""
        raw = self._plugin.get_data(FAILCLEAN_STATUS_DATA_KEY)
        status = deepcopy(STATUS_TEMPLATE)
        if not isinstance(raw, dict):
            return status
        with self._status_lock:
            status["last_scan_time"] = _as_float(raw.get("last_scan_time"))
            status["last_scan_trigger"] = _text(raw.get("last_scan_trigger"))
            for section in ("scan", "event", "total"):
                stored = raw.get(section)
                if not isinstance(stored, dict):
                    continue
                for key in status[section]:
                    status[section][key] = _as_counter(stored.get(key))
            return status

    def _save_status(self) -> None:
        """保存累计计数（与状态读改写共用状态锁）。"""
        with self._status_lock:
            self._plugin.save_data(FAILCLEAN_STATUS_DATA_KEY, deepcopy(self._status))


def counters_of(delete_result: dict[str, Any]) -> dict[str, Any]:
    """把删除结果映射为 (清理数, 失败数, 跳过数)；重复请求三项均为 0。"""
    if delete_result["duplicate"]:
        return {"deleted": 0, "failed": 0, "skipped": 0, "duplicate": True}
    if delete_result["skipped"]:
        return {"deleted": 0, "failed": 0, "skipped": 1, "duplicate": False}
    if delete_result["deleted"]:
        return {"deleted": 1, "failed": 0, "skipped": 0, "duplicate": False}
    return {"deleted": 0, "failed": 1, "skipped": 0, "duplicate": False}


def _delete_key(path: str, download_hash: str) -> str:
    """返回 (hash, 路径) 去重键。"""
    return f"{download_hash or '-'}|{path}"


def _field(source: Any, name: str) -> Any:
    """兼容字典与模型对象读取事件字段。"""
    if isinstance(source, dict):
        return source.get(name)
    return getattr(source, name, None)


def _text(value: Any) -> str:
    """把可选值收敛为去空白字符串。"""
    return str(value or "").strip()


__all__ = ("FailCleanService", "STATUS_TEMPLATE", "empty_scan_result", "empty_transfer_failed_result")
