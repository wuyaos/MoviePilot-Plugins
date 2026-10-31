"""自动删种服务：候选扫描、条件执行、H&R 保护与运行状态汇总。"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock, RLock
from typing import Any, Optional

from app.schemas.types import MessageType
from app.sdk.logging import logger

from ...utils.config import module_active, module_observe_only
from ...utils.torrent_adapter import delete_torrent_with_files
from ..hr.guard import SKIP_PATH_AUTO_REMOVE, HrGuard
from .constants import (
    REMOVER_CANDIDATE_VIEW_LIMIT,
    REMOVER_LOG_PREFIX,
    REMOVER_NOTIFY_ITEM_LIMIT,
    REMOVER_STATE_DATA_KEY,
)
from .criteria import CompiledConditions, RemoverConfigError, compile_conditions, match_reason
from .history import cleared_status, empty_status as _empty_status, history_removed_count
from .models import RemoveCandidate, RemoveSnapshot, RemoverConfig, format_bytes
from .rules import parse_remover_config
from .scanner import build_snapshot, downloader_type, read_torrents, torrent_hash

_COUNTER_KEYS = (
    "candidates",
    "paused",
    "deleted",
    "deleted_files",
    "skipped_protected",
    "skipped_missing",
    "skipped",
    "failed",
    "failed_operations",
)


@dataclass
class _CycleScan:
    """一轮候选扫描结果：对外结果、按下载器保留的候选对象与编译后的条件。"""

    result: dict[str, Any]
    candidates: dict[str, list[RemoveCandidate]]
    conditions: Optional[CompiledConditions] = None


class AutoRemoveService:
    """自动删种模块服务对象，由插件生命周期创建并注册 cron 服务。

    用法：``AutoRemoveService(plugin).init_module(config)`` 完成配置加载与状态恢复；
    cron/立即运行调用 :meth:`run_cycle`；只读预览调用 :meth:`collect_candidates`；
    overview/前端读取 :meth:`get_module_status`；插件停止时调用 :meth:`stop`。
    """

    def __init__(self, plugin: Any):
        """
        :param plugin: DownloadManagerLocal 插件实例，提供 service_info/get_data/save_data/post_message。
        """
        self._plugin = plugin
        self._config = RemoverConfig()
        self._conditions: Optional[CompiledConditions] = None
        self._config_error = ""
        self._observe_only = True
        self._status: dict[str, Any] = {}
        self._lock = RLock()
        self._run_lock = Lock()
        self._stopped = True

    @property
    def config(self) -> RemoverConfig:
        """返回当前自动删种运行时配置。"""
        return self._config

    @property
    def observe_only(self) -> bool:
        """返回是否处于迁移观察期（只列候选、不执行下载器写操作）。"""
        return self._observe_only

    def init_module(self, config: Optional[dict] = None) -> None:
        """按插件配置初始化模块：解析 remover_* 配置、读取观察闸门、校验条件并恢复运行状态。"""
        self._config = parse_remover_config(config)
        # 门控对齐：服务配置 enabled = 总开关 AND remover_enabled（utils/config.py::module_active）。
        self._config.enabled = module_active(config or {}, "autoremove")
        source = config if isinstance(config, dict) else {}
        # 观察模式（阶段三）：新键 remover_observe_only 优先，缺失时继承旧键 migration_observe_only。
        self._observe_only = module_observe_only(source, "autoremove")
        self._conditions = None
        self._config_error = ""
        try:
            self._conditions = compile_conditions(self._config)
        except RemoverConfigError as error:
            self._config_error = str(error)
            logger.error(f"{REMOVER_LOG_PREFIX}配置非法，模块不会执行删除：{self._config_error}")
        self._status = self._load_status()
        self._stopped = False
        logger.info(
            f"{REMOVER_LOG_PREFIX}初始化完成：开关={self._config.enabled} 观察={self._observe_only} "
            f"动作={self._config.action} 下载器={self._config.downloaders or '未配置'} "
            f"周期={self._config.cron or '未设置'} 通知={self._config.notify}"
        )

    def collect_candidates(self, trigger_source: str = "候选预览") -> dict[str, Any]:
        """只读收集候选，不执行任何下载器写操作；结果不写入运行状态。"""
        if not self._config.enabled:
            logger.info(f"{REMOVER_LOG_PREFIX}未启用，跳过{trigger_source}")
            return self._empty_result(trigger_source)
        if not self._run_lock.acquire(blocking=False):
            logger.info(f"{REMOVER_LOG_PREFIX}已有任务在运行，跳过重叠触发：{trigger_source}")
            return self._empty_result(trigger_source)
        try:
            with self._lock:
                return self._collect(trigger_source).result
        finally:
            self._run_lock.release()

    def run_cycle(self, trigger_source: str = "定时") -> dict[str, Any]:
        """执行一轮自动删种；观察期只列候选，正式执行前回读身份并查询 H&R 保护。"""
        if not self._config.enabled:
            logger.info(f"{REMOVER_LOG_PREFIX}未启用，跳过{trigger_source}")
            return self._empty_result(trigger_source)
        if not self._run_lock.acquire(blocking=False):
            logger.info(f"{REMOVER_LOG_PREFIX}已有任务在运行，跳过重叠触发：{trigger_source}")
            return self._empty_result(trigger_source)
        try:
            records: list[dict[str, Any]] = []
            with self._history_flush_guard(records), self._lock:
                scan = self._collect(trigger_source)
                result = scan.result
                if result["config_error"]:
                    self._record_status(result)
                    return result
                if self._observe_only:
                    logger.info(
                        f"{REMOVER_LOG_PREFIX}{trigger_source}：观察期仅列出 {result['candidates']} 个候选，"
                        f"不执行 {result['action']}"
                    )
                    if self._config.notify and result["candidates"]:
                        from ...utils.notify import notify_module_result, result_text

                        notify_module_result(
                            self._plugin, "autoremove",
                            text=result_text(observe=True, preview_count=result["candidates"]),
                            suffix="观察模式",
                        )
                else:
                    self._execute(scan, records)
                self._record_status(result)
                return result
        finally:
            self._run_lock.release()

    def get_module_status(self) -> dict[str, Any]:
        """返回自动删种模块运行状态（最近执行、候选/命中/跳过计数、保护跳过统计）供 overview。"""
        with self._lock:
            status = dict(self._status)
        guard = HrGuard()
        skip_stats = guard.get_skip_stats()
        status.update(
            {
                "enabled": self._config.enabled,
                "cron": self._config.cron,
                "action": self._config.action,
                "downloaders": list(self._config.downloaders),
                "observe_only": self._observe_only,
                "config_error": self._config_error,
                "running": self._run_lock.locked(),
                "guard_enabled": guard.enabled,
                "guard_unconfirmed": guard.unconfirmed,
                "protected_skips": skip_stats.get(SKIP_PATH_AUTO_REMOVE, 0),
                "skip_stats": skip_stats,
            }
        )
        return status

    def clear_history(self) -> dict[str, Any]:
        """清理最近一轮执行状态（数据页「清理记录」），只清历史，不动配置与 H&R 状态。

        :return: ``{"removed": int, "busy": bool}``；``busy=True`` 表示已有任务在运行，
            未做任何清理，由 handler 转 409。
        """
        if not self._run_lock.acquire(blocking=False):
            return {"removed": 0, "busy": True}
        try:
            with self._lock:
                removed = history_removed_count(self._status)
                if not removed:
                    return {"removed": 0, "busy": False}
                cleared = cleared_status()
                self._plugin.save_data(REMOVER_STATE_DATA_KEY, cleared)
                self._status = cleared
                return {"removed": removed, "busy": False}
        finally:
            self._run_lock.release()

    def stop(self) -> None:
        """插件停止：置停止标志，令在途的候选处理尽快退出。"""
        self._stopped = True
        logger.info(f"{REMOVER_LOG_PREFIX}服务已停止")

    def _collect(self, trigger_source: str) -> _CycleScan:
        """读取下载器并收集候选，返回结果与按下载器保留的候选对象。"""
        result = self._empty_result(trigger_source)
        if self._stopped:
            logger.info(f"{REMOVER_LOG_PREFIX}服务已停止，跳过{trigger_source}")
            return _CycleScan(result=result, candidates={})
        if self._config_error:
            result["config_error"] = self._config_error
            logger.error(f"{REMOVER_LOG_PREFIX}配置非法，本轮不处理任何任务：{self._config_error}")
            return _CycleScan(result=result, candidates={})
        if not self._config.downloaders:
            logger.warning(f"{REMOVER_LOG_PREFIX}未配置下载器，跳过{trigger_source}")
            return _CycleScan(result=result, candidates={})

        conditions = self._conditions
        now = time.time()
        candidates: dict[str, list[RemoveCandidate]] = {}
        for name in self._config.downloaders:
            if self._stopped:
                logger.info(f"{REMOVER_LOG_PREFIX}收到停止请求，中止本轮扫描")
                break
            detail = _downloader_detail(name)
            result["details"].append(detail)
            service = self._plugin.service_info(name)
            instance = getattr(service, "instance", None) if service else None
            if instance is None:
                detail["failed"] = 1
                detail["error"] = "下载器不可用"
                continue
            dl_type = downloader_type(service)
            torrents, error = read_torrents(instance)
            if error:
                detail["failed"] = 1
                detail["error"] = error
                logger.warning(f"{REMOVER_LOG_PREFIX}下载器 {name} 任务读取失败，本轮不处理：{error}")
                continue
            # 来源在查询时即按 labels/mponly 标签过滤；这里等价地先筛出带齐必需标签的任务，
            # samedata 的辅种扫描池同样受限，避免把不带 MP 标签的任务当作辅种处理。
            pool = [
                snapshot
                for snapshot in (
                    build_snapshot(torrent, name, dl_type, now) for torrent in torrents
                )
                if snapshot.torrent_hash and _has_required_tags(conditions, snapshot)
            ]
            matched: list[RemoveCandidate] = []
            for snapshot in pool:
                reason = match_reason(conditions, snapshot)
                if reason is not None:
                    matched.append(RemoveCandidate(snapshot=snapshot, reason=reason))
            if conditions.same_data and matched:
                matched = _append_same_data(matched, pool)
            detail["candidates"] = len(matched)
            candidates[name] = matched
            logger.info(
                f"{REMOVER_LOG_PREFIX}下载器 {name}：读取{len(torrents)}个任务，标签筛选后{len(pool)}个，"
                f"命中{len(matched)}个候选"
            )

        self._sync_totals(result)
        result["candidate_list"] = [
            candidate.to_view() for items in candidates.values() for candidate in items
        ][:REMOVER_CANDIDATE_VIEW_LIMIT]
        logger.info(
            f"{REMOVER_LOG_PREFIX}{trigger_source}扫描完成：候选{result['candidates']} "
            f"失败下载器{result['failed']} 配置错误={result['config_error'] or '无'}"
        )
        return _CycleScan(result=result, candidates=candidates, conditions=conditions)

    def _execute(self, scan: _CycleScan, records: list[dict[str, Any]]) -> None:
        """按候选执行下载器动作：先回读身份，再查询 H&R 保护。"""
        conditions = scan.conditions
        if conditions is None:
            return
        result = scan.result
        for name, candidates in scan.candidates.items():
            if self._stopped:
                logger.info(f"{REMOVER_LOG_PREFIX}收到停止请求，中止本轮执行")
                break
            if not candidates:
                continue
            detail = next(item for item in result["details"] if item["downloader"] == name)
            executed = self._execute_downloader(
                name, candidates, detail, conditions, result["trigger"], records)
            if executed and self._config.notify:
                self._notify(name, executed, conditions.action)
        self._sync_totals(result)
        logger.info(
            f"{REMOVER_LOG_PREFIX}执行完成：暂停{result['paused']} 删除{result['deleted']}"
            f"（含文件{result['deleted_files']}） H&R保护跳过{result['skipped_protected']} "
            f"已消失{result['skipped_missing']} 失败{result['failed']}"
        )

    def _execute_downloader(
        self,
        downloader: str,
        candidates: list[RemoveCandidate],
        detail: dict[str, Any],
        conditions: CompiledConditions,
        trigger_source: str,
        records: list[dict[str, Any]],
    ) -> list[RemoveCandidate]:
        """执行单个下载器的候选动作，返回实际执行成功的候选，并把历史追加进本轮收集列表。"""
        action = conditions.action
        service = self._plugin.service_info(downloader)
        instance = getattr(service, "instance", None) if service else None
        if instance is None:
            detail["failed"] += len(candidates)
            detail["failed_operations"] += 1
            detail["error"] = "执行前下载器不可用"
            logger.warning(f"{REMOVER_LOG_PREFIX}执行前下载器 {downloader} 不可用，跳过 {len(candidates)} 个候选")
            self._record_history(records,
                trigger=trigger_source,
                action=action,
                result="failed",
                reason=f"执行前下载器 {downloader} 不可用，整批 {len(candidates)} 个候选未执行",
                downloader=downloader,
            )
            return []
        dl_type = downloader_type(service)
        torrents, error = read_torrents(instance)
        if error:
            detail["failed"] += len(candidates)
            detail["failed_operations"] += 1
            detail["error"] = error
            logger.warning(f"{REMOVER_LOG_PREFIX}执行前回读 {downloader} 失败，本轮不处理其候选：{error}")
            self._record_history(records,
                trigger=trigger_source,
                action=action,
                result="failed",
                reason=f"执行前回读 {downloader} 失败，整批 {len(candidates)} 个候选未执行：{error}",
                downloader=downloader,
            )
            return []
        fresh = {torrent_hash(torrent, dl_type) for torrent in torrents}
        executed: list[RemoveCandidate] = []
        for candidate in candidates:
            if self._stopped:
                break
            snapshot = candidate.snapshot
            label = snapshot.name or snapshot.torrent_hash
            if snapshot.torrent_hash not in fresh:
                detail["skipped_missing"] += 1
                logger.info(f"{REMOVER_LOG_PREFIX}候选已不在下载器中，跳过：{downloader} {label}")
                self._record_history(records,
                    trigger=trigger_source,
                    action=action,
                    result="skipped",
                    reason="候选已不在下载器中",
                    downloader=downloader,
                    torrent_hash=snapshot.torrent_hash,
                    name=label,
                    site=snapshot.site or None,
                )
                continue
            if self._skip_for_protection(action, downloader, snapshot.torrent_hash):
                detail["skipped_protected"] += 1
                self._record_history(records,
                    trigger=trigger_source,
                    action=action,
                    result="skipped",
                    reason="H&R 保护跳过",
                    downloader=downloader,
                    torrent_hash=snapshot.torrent_hash,
                    name=label,
                    site=snapshot.site or None,
                )
                continue
            try:
                success = self._apply_action(instance, snapshot.torrent_hash, action)
            except Exception as error:
                detail["failed"] += 1
                detail["failed_operations"] += 1
                logger.error(f"{REMOVER_LOG_PREFIX}{action} 执行失败：{downloader} {label}: {error}")
                self._record_history(records,
                    trigger=trigger_source,
                    action=action,
                    result="failed",
                    reason=f"执行异常：{error}",
                    downloader=downloader,
                    torrent_hash=snapshot.torrent_hash,
                    name=label,
                    site=snapshot.site or None,
                )
                continue
            if not success:
                detail["failed"] += 1
                detail["failed_operations"] += 1
                logger.warning(f"{REMOVER_LOG_PREFIX}{action} 未获下载器确认：{downloader} {label}")
                self._record_history(records,
                    trigger=trigger_source,
                    action=action,
                    result="failed",
                    reason="下载器未确认执行结果",
                    downloader=downloader,
                    torrent_hash=snapshot.torrent_hash,
                    name=label,
                    site=snapshot.site or None,
                )
                continue
            _count_action(detail, action)
            executed.append(candidate)
            logger.info(
                f"{REMOVER_LOG_PREFIX}{action} 完成：{downloader} {label} "
                f"来自站点：{snapshot.site or '-'} 大小：{format_bytes(snapshot.size)}"
            )
            self._record_history(records,
                trigger=trigger_source,
                action=action,
                result="success",
                reason="执行成功",
                downloader=downloader,
                torrent_hash=snapshot.torrent_hash,
                name=label,
                site=snapshot.site or None,
            )
        return executed

    def _record_history(
        self,
        records: list[dict[str, Any]],
        *,
        trigger: str,
        action: str,
        result: str,
        reason: str,
        downloader: Optional[str] = None,
        torrent_hash: Optional[str] = None,
        name: Optional[str] = None,
        site: Optional[str] = None,
    ) -> None:
        """把一条展示历史追加进本轮收集列表；落库由 :meth:`_flush_history` 在模块锁外完成。"""
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
        if site is not None:
            record["site"] = site
        records.append(record)

    @contextmanager
    def _history_flush_guard(self, records: list[dict[str, Any]]):
        """收集本轮展示历史，退出时（模块锁已释放）统一落库。

        `with self._history_flush_guard(records), self._lock:` 的 with 栈后进先出
        ——先释放模块锁，再 flush，避免持锁做 `save_data`。落库失败只记日志：
        历史不可用不得改变业务结果，因此导入与调用都在 try 内。
        """
        try:
            yield records
        finally:
            self._flush_history(records)

    def _flush_history(self, records: list[dict[str, Any]]) -> None:
        """逐条写入共享展示历史；每条独立 try/except，失败不影响其他记录与业务结果。"""
        pending, records[:] = list(records), []
        for record in pending:
            try:
                from ...model import execution_history

                execution_history.append(self._plugin, "autoremove", record)
            except Exception as error:
                logger.error(f"{REMOVER_LOG_PREFIX}写入展示历史失败（不影响业务结果）：{error}")

    def _skip_for_protection(self, action: str, downloader: str, torrent_hash: str) -> bool:
        """破坏性删除前查询 H&R 保护；命中时 guard 自身已计数，这里不重复计数。"""
        if action == "pause":
            return False
        if HrGuard().should_skip(SKIP_PATH_AUTO_REMOVE, downloader, torrent_hash):
            logger.info(f"{REMOVER_LOG_PREFIX}H&R 保护跳过：{downloader} {torrent_hash}")
            return True
        return False

    def _apply_action(self, instance: Any, torrent_hash: str, action: str) -> bool:
        """执行下载器动作，返回下载器是否确认成功。"""
        if action == "pause":
            return instance.stop_torrents(ids=[torrent_hash]) is not False
        if action == "delete":
            return instance.delete_torrents(delete_file=False, ids=[torrent_hash]) is not False
        delete_torrent_with_files(instance, torrent_hash, delete_file=True)
        return True

    def _notify(self, downloader: str, executed: list[RemoveCandidate], action: str) -> None:
        """发送单个下载器的处理结果通知，超出上限的条目只汇总数量。"""
        if action == "pause":
            head = f"{downloader} 共暂停{len(executed)}个种子"
        elif action == "delete":
            head = f"{downloader} 共删除{len(executed)}个种子"
        else:
            head = f"{downloader} 共删除{len(executed)}个种子及文件"
        lines = [head]
        for candidate in executed[:REMOVER_NOTIFY_ITEM_LIMIT]:
            snapshot = candidate.snapshot
            lines.append(
                f"{snapshot.name} 来自站点：{snapshot.site or '-'} 大小：{format_bytes(snapshot.size)}"
            )
        if len(executed) > REMOVER_NOTIFY_ITEM_LIMIT:
            lines.append(f"其余 {len(executed) - REMOVER_NOTIFY_ITEM_LIMIT} 个已省略")
        from ...utils.notify import notify_module_result

        notify_module_result(
            self._plugin, "autoremove",
            text="\n".join(lines), mtype=MessageType.SiteMessage,
        )

    def _sync_totals(self, result: dict[str, Any]) -> None:
        """按下载器明细汇总本轮计数，明细是唯一计数来源。"""
        for key in _COUNTER_KEYS:
            if key == "skipped":
                continue
            result[key] = sum(int(detail.get(key) or 0) for detail in result["details"])
        result["skipped"] = result["skipped_protected"] + result["skipped_missing"]

    def _record_status(self, result: dict[str, Any]) -> None:
        """保存最近一轮执行状态，供 reload 后的 overview 展示。"""
        status = {
            "last_run_at": time.time(),
            "last_trigger": result["trigger"],
            "candidates": result["candidates"],
            "paused": result["paused"],
            "deleted": result["deleted"],
            "deleted_files": result["deleted_files"],
            "skipped_protected": result["skipped_protected"],
            "skipped_missing": result["skipped_missing"],
            "skipped": result["skipped_protected"] + result["skipped_missing"],
            "failed": result["failed"],
            "failed_operations": result["failed_operations"],
            "config_error": result["config_error"],
            "observe_only": self._observe_only,
            "action": self._config.action,
            "candidate_list": result["candidate_list"],
            "details": result["details"],
        }
        self._status = status
        self._plugin.save_data(REMOVER_STATE_DATA_KEY, status)

    def _load_status(self) -> dict[str, Any]:
        """读取持久化的最近一轮执行状态，缺失字段取空状态默认值。"""
        raw = self._plugin.get_data(REMOVER_STATE_DATA_KEY)
        status = _empty_status()
        if isinstance(raw, dict):
            for key in status:
                if key in raw:
                    status[key] = raw[key]
        return status

    def _empty_result(self, trigger_source: str) -> dict[str, Any]:
        """构造未执行/未启用时的空结果。"""
        return {
            "trigger": trigger_source,
            "enabled": self._config.enabled,
            "observe_only": self._observe_only,
            "action": self._config.action,
            "downloaders": list(self._config.downloaders),
            "candidates": 0,
            "paused": 0,
            "deleted": 0,
            "deleted_files": 0,
            "skipped_protected": 0,
            "skipped_missing": 0,
            "skipped": 0,
            "failed": 0,
            "failed_operations": 0,
            "config_error": self._config_error,
            "candidate_list": [],
            "details": [],
        }


def _downloader_detail(downloader: str) -> dict[str, Any]:
    """构造单个下载器的统计明细。"""
    return {
        "downloader": downloader,
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


def _has_required_tags(conditions: CompiledConditions, snapshot: RemoveSnapshot) -> bool:
    """判断任务是否带齐标签条件与 MP 标签限定，等价来源按 tags 查询下载器。"""
    if not conditions.required_tags:
        return True
    return set(conditions.required_tags).issubset(snapshot.tags)


def _append_same_data(
    candidates: list[RemoveCandidate],
    snapshots: list[RemoveSnapshot],
) -> list[RemoveCandidate]:
    """samedata=true 时在同一标签筛选池内按名称与大小追加辅种候选，不跨下载器扩散。"""
    known = {candidate.torrent_hash for candidate in candidates}
    extra: list[RemoveCandidate] = []
    for candidate in candidates:
        for snapshot in snapshots:
            if snapshot.torrent_hash in known:
                continue
            if snapshot.name == candidate.snapshot.name and snapshot.size == candidate.snapshot.size:
                known.add(snapshot.torrent_hash)
                extra.append(
                    RemoveCandidate(
                        snapshot=snapshot,
                        reason="同数据辅种追加（名称与大小相同）",
                        same_data=True,
                    )
                )
    return candidates + extra


def _count_action(detail: dict[str, Any], action: str) -> None:
    """按动作累计执行计数。"""
    if action == "pause":
        detail["paused"] += 1
    elif action == "delete":
        detail["deleted"] += 1
    else:
        detail["deleted"] += 1
        detail["deleted_files"] += 1


__all__ = ("AutoRemoveService",)
