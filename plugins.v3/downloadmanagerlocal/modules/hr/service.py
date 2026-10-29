"""H&R 服务：任务纳管、状态检查、达标判定、记录清理与汇总通知编排。"""

from __future__ import annotations

import time
from threading import Lock, RLock
from typing import Any, Optional

from app.sdk.logging import logger
from pydantic import ValidationError

from ...utils.config import module_active, observe_skip
from .cleanup import auto_cleanup
from .constants import HR_LOG_PREFIX, HR_TASKS_DATA_KEY
from .evaluator import evaluate_task, initialize_requirements, seeding_progress
from .guard import get_guard
from .models import HrConfig, HrStatus, HrTask, HrTaskType, hr_task_key
from .notify import record_task_event, send_summary
from .rules import parse_hr_config
from .scanner import (
    HrTorrentSnapshot,
    apply_snapshot,
    downloader_services,
    downloader_type,
    is_excluded,
    read_torrents,
    remove_hr_tag,
    resolve_site,
    set_hr_tag,
    torrent_snapshot,
)

_STATUS_SUMMARY_FIELDS = {
    HrStatus.PENDING: "pending",
    HrStatus.IN_PROGRESS: "in_progress",
    HrStatus.COMPLIANT: "compliant",
    HrStatus.NEEDS_SEEDING: "needs_seeding",
    HrStatus.OVERDUE: "overdue",
}

CLEARABLE_STATUSES = (HrStatus.NEEDS_SEEDING, HrStatus.COMPLIANT, HrStatus.OVERDUE)


class HrService:
    """H&R 模块服务对象，由插件生命周期创建并注册调度。

    用法：``HrService(plugin).init_module(config)`` 完成配置加载与状态恢复；调度调用
    :meth:`check_tasks` / :meth:`discover_tasks` / :meth:`run_scan`，汇总通知调用
    :meth:`send_summary`；API 读取 :meth:`get_service_infos`；插件停止时调用 :meth:`stop`。
    """

    def __init__(self, plugin: Any):
        """
        :param plugin: DownloadManagerLocal 插件实例，提供 get_data/save_data/post_message。
        """
        self._plugin = plugin
        self._config = HrConfig()
        self._tasks: dict[str, HrTask] = {}
        self._lock = RLock()
        self._run_lock = Lock()
        self._guard = get_guard()
        self._stopped = False
        self._generation = 0

    @property
    def config(self) -> HrConfig:
        """返回当前 H&R 运行时配置。"""
        return self._config

    def init_module(self, config: Optional[dict] = None) -> None:
        """按插件配置初始化 H&R 模块，恢复持久化任务并刷新 H&R 保护快照。"""
        id_to_name = self._site_id_to_name()
        source = config if isinstance(config, dict) else {}
        self._config = parse_hr_config(source, id_to_name)
        # 门控对齐：服务配置 enabled = 总开关 AND hr_enabled（utils/config.py::module_active）。
        self._config.enabled = module_active(source, "hr")
        self._migrate_legacy_site_ids(source, id_to_name)
        self._tasks = self._load_tasks()
        self._stopped = False
        self._generation += 1  # 新生命周期代次：使旧实例的在途扫描结果失效
        self._refresh_guard()
        logger.info(
            f"{HR_LOG_PREFIX}初始化完成：开关={self._config.enabled} "
            f"保护={self._config.protection_enabled} 下载器={self._config.downloaders} "
            f"站点白名单={len(self._config.sites)}个 站点独立规则={len(self._config.site_rules)}条 "
            f"纳管任务={len(self._tasks)}条"
        )

    @staticmethod
    def _site_id_to_name() -> dict[str, str]:
        """当前站点库 id→站点名映射；站点库不可用时返回空（旧数字 ID 走丢弃路径）。"""
        try:
            from ...adapter.moviepilot import list_builtin_sites

            return {
                str(site.id): (site.name or "").strip()
                for site in (list_builtin_sites() or [])
                if getattr(site, "id", None) is not None
            }
        except Exception as e:
            logger.warning(f"{HR_LOG_PREFIX}读取站点库失败，旧站点 ID 白名单无法迁移：{e}")
            return {}

    def _migrate_legacy_site_ids(self, source: dict, id_to_name: dict[str, str]) -> None:
        """存储里的 hr_sites 仍含数字站点 ID 时，把迁移后的站点名一次性回写插件配置。"""
        raw = source.get("hr_sites")
        if not raw or not id_to_name:
            return
        if not any(str(item).strip().replace(".", "", 1).isdigit() for item in raw):
            return
        try:
            new_config = dict(source)
            new_config["hr_sites"] = list(self._config.sites)
            if self._plugin.update_config(config=new_config) is False:
                logger.warning(f"{HR_LOG_PREFIX}站点白名单迁移写回失败，保留旧值（运行时按站点名生效）")
                return
            logger.info(
                f"{HR_LOG_PREFIX}站点白名单已由站点 ID 迁移为站点名并回写：{new_config['hr_sites']}"
            )
        except Exception as e:
            logger.warning(f"{HR_LOG_PREFIX}站点白名单迁移回写异常，保留旧值：{e}")
    def get_service_infos(self) -> dict[str, Any]:
        """返回 H&R 任务列表与汇总，任务字段含 downloader_id/torrent_hash/name/site/status/
        progress/remain_seconds/deadline/type，deadline 为截止时间戳（0 表示未设考核期）。"""
        with self._lock:
            tasks = [self._task_view(task) for task in self._tasks.values()]
            summary = self._summary_view()
        tasks.sort(key=lambda item: (item["deadline"] or float("inf"), item["name"]))
        return {"tasks": tasks, "summary": summary}

    def check_tasks(self, trigger_source: str = "定时") -> dict[str, Any]:
        """检查一轮 H&R 任务状态并返回统计结果。"""
        if not self._ready(trigger_source):
            return self._empty_result()
        now = time.time()
        try:
            with self._lock:
                return self._check_once(now, trigger_source)
        except Exception:
            # 本轮检查中断：保护快照可能缺失，标记无法确认（危险删除保守跳过），异常照常抛出
            self._guard.mark_unconfirmed()
            raise
        finally:
            self._run_lock.release()

    def discover_tasks(self, trigger_source: str = "自动发现") -> dict[str, Any]:
        """扫描配置下载器，把白名单站点中未纳管的种子纳入 H&R 管理。"""
        if not self._config.auto_discover:
            logger.info(f"{HR_LOG_PREFIX}未启用自动发现，跳过{trigger_source}")
            return {"discovered": 0, "known": 0, "outside_sites": 0, "excluded": 0, "failed_downloaders": []}
        if not self._ready(trigger_source):
            return {"discovered": 0, "known": 0, "outside_sites": 0, "excluded": 0, "failed_downloaders": []}
        now = time.time()
        try:
            with self._lock:
                return self._discover_once(now)
        except Exception:
            # 本轮发现中断：同上，保护状态无法确认
            self._guard.mark_unconfirmed()
            raise
        finally:
            self._run_lock.release()

    def run_scan(self, trigger_source: str = "全量扫描") -> dict[str, Any]:
        """执行一轮自动发现 + 状态检查，用于立即运行一次与手动全量扫描。"""
        if not self._ready(trigger_source):
            return {"discover": {}, "check": self._empty_result()}
        now = time.time()
        try:
            with self._lock:
                discover_result = self._discover_once(now) if self._config.auto_discover else {}
                check_result = self._check_once(now, trigger_source)
        except Exception:
            # 本轮扫描中断：同上，保护状态无法确认
            self._guard.mark_unconfirmed()
            raise
        finally:
            self._run_lock.release()
        return {"discover": discover_result, "check": check_result}

    def register_task(
        self,
        downloader_id: str,
        torrent_hash: str,
        task_type: HrTaskType = HrTaskType.NORMAL,
        torrent_data: Optional[dict] = None,
    ) -> bool:
        """纳管单个新任务；torrent_data 可带 title/size/hit_and_run（事件上下文）。"""
        if not self._config.enabled:
            return False
        downloader = str(downloader_id or "").strip()
        target_hash = str(torrent_hash or "").strip().lower()
        if not downloader or not target_hash:
            return False
        if self._config.downloaders and downloader not in self._config.downloaders:
            logger.debug(f"{HR_LOG_PREFIX}下载器 {downloader} 不在 H&R 下载器列表，跳过纳管 {target_hash}")
            return False
        service = downloader_services([downloader]).get(downloader)
        if service is None:
            logger.warning(f"{HR_LOG_PREFIX}下载器 {downloader} 不可用，跳过纳管 {target_hash}")
            return False
        torrents, error = read_torrents(service, ids=[target_hash])
        if error:
            logger.warning(f"{HR_LOG_PREFIX}读取下载器 {downloader} 任务失败，跳过纳管 {target_hash}：{error}")
            return False
        now = time.time()
        dl_type = downloader_type(service)
        snapshot = next(
            (
                item
                for item in (torrent_snapshot(torrent, downloader, dl_type, now) for torrent in torrents)
                if item.torrent_hash == target_hash
            ),
            None,
        )
        if snapshot is None:
            logger.warning(f"{HR_LOG_PREFIX}下载器中未找到种子 {target_hash}")
            return False
        site_id, site_name = resolve_site(self._tracker_mappings(), snapshot.trackers, self._config.site_rules)
        if not self._config.site_in_scope(site_name):
            logger.info(f"{HR_LOG_PREFIX}站点 {site_name or site_id} 不在 H&R 站点白名单，跳过纳管 {target_hash}")
            return False
        excluded, reason = is_excluded(snapshot, self._config.exclude_tags, self._config.exclude_categories)
        if excluded:
            logger.info(f"{HR_LOG_PREFIX}{site_name or site_id}: 种子 {target_hash} 已排除，跳过纳管（{reason}）")
            return False
        rule = self._config.get_site_rule(site_name)
        hit_and_run = (
            bool((torrent_data or {}).get("hit_and_run"))
            or self._config.hit_and_run_tag in snapshot.tags
            or bool(rule.hr_active)
        )
        if not hit_and_run:
            logger.info(f"{HR_LOG_PREFIX}{site_name or site_id}: {snapshot.title or target_hash} 未命中 H&R，跳过纳管")
            return False

        task = HrTask(
            hash=snapshot.torrent_hash,
            downloader=downloader,
            site=site_id,
            site_name=site_name,
            title=str((torrent_data or {}).get("title") or snapshot.title or ""),
            size=float((torrent_data or {}).get("size") or snapshot.size or 0),
            added_on=snapshot.added_on or now,
            task_type=task_type,
            hit_and_run=True,
            hr_status=HrStatus.IN_PROGRESS,
        )
        initialize_requirements(task, rule)
        apply_snapshot(task, snapshot)
        if not observe_skip(
            self._plugin,
            "hr",
            "打 H&R 标签",
            f"{task.identifier} 标签={self._config.hit_and_run_tag}",
        ):
            set_hr_tag(service, task.hash, self._config.hit_and_run_tag)
        with self._lock:
            self._tasks[task.key] = task
            self._save_tasks()
            self._refresh_guard()
        logger.info(
            f"{HR_LOG_PREFIX}{site_name or site_id}: {task.identifier} 已纳入 H&R 管理 "
            f"[{task.task_type.to_chinese()}] 做种{task.required_hours():g}h/"
            f"期限{task.hr_deadline_days or 0}天"
        )
        return True

    def send_summary(self) -> bool:
        """发送每日汇总通知；无待汇总事件时返回 False。

        持 ``_lock``（与 ``record_task_event`` 的写入路径互斥，P2-9）：汇总期间
        扫描追加的新事件不会在 ``save_events([])`` 清空队列时被误删。
        """
        with self._lock:
            return send_summary(self._plugin, self._config.notify)

    def clear_task(self, downloader_id: str, torrent_hash: str) -> bool:
        """按 (downloader, hash) 清除单条已结束记录，不删除下载器任务与文件。"""
        key = hr_task_key(downloader_id, torrent_hash)
        with self._lock:
            task = self._tasks.get(key)
            if task is None or task.hr_status not in CLEARABLE_STATUSES:
                return False
            del self._tasks[key]
            self._save_tasks()
            self._refresh_guard()
        logger.info(f"{HR_LOG_PREFIX}已清除 H&R 记录: [{task.site_name}] {task.identifier}")
        return True

    def clear_compliant(self) -> int:
        """批量清除已满足 H&R 的记录，返回清除条数。"""
        return self._clear_by_status((HrStatus.COMPLIANT,), "已满足")

    def clear_missing(self) -> int:
        """批量清除 H&R 未满足且种子已不在下载器的记录，返回清除条数。"""
        return self._clear_by_status((HrStatus.NEEDS_SEEDING,), "需做种")

    def stop(self) -> None:
        """停止后续扫描并撤销保护快照，插件停止后不再行使 H&R 保护。"""
        self._stopped = True
        self._generation += 1  # 使在途扫描的落盘/刷新失效（P1-6：旧扫描不得覆盖新状态）
        self._guard.expect(enabled=False)
        logger.info(f"{HR_LOG_PREFIX}服务已停止")

    def _clear_by_status(self, statuses: tuple[HrStatus, ...], label: str) -> int:
        """按状态批量清除记录。"""
        with self._lock:
            removable = [key for key, task in self._tasks.items() if task.hr_status in statuses]
            for key in removable:
                logger.info(f"{HR_LOG_PREFIX}清除{label}记录: [{self._tasks[key].site_name}] {self._tasks[key].identifier}")
                del self._tasks[key]
            if removable:
                self._save_tasks()
                self._refresh_guard()
        return len(removable)

    def _check_once(self, now: float, trigger_source: str) -> dict[str, Any]:
        """执行一轮状态检查：刷新统计、标记删除、达标判定、记录清理与保护快照刷新。"""
        generation_at_start = self._generation
        services = downloader_services(self._config.downloaders)
        if not services:
            logger.warning(f"{HR_LOG_PREFIX}{trigger_source}：没有可用下载器，跳过检查")
            result = self._empty_result()
            result["enabled"] = self._config.enabled
            return result

        # 被选中但不可用（未连接/缺实例）的下载器必须视作「查询失败」：
        # 它们的任务缺席不能当作「种子已删除」，否则会误标 deleted 并最终误清保护记录。
        selected_names = [str(n or "").strip() for n in (self._config.downloaders or [])]
        unavailable = [n for n in selected_names if n and n not in services]
        for name in unavailable:
            logger.warning(f"{HR_LOG_PREFIX}下载器 {name} 不可用，本轮不判定其任务删除")
        failed: list[str] = list(unavailable)
        snapshots: dict[str, HrTorrentSnapshot] = {}
        for name, service in services.items():
            torrents, error = read_torrents(service)
            if error:
                failed.append(name)
                logger.warning(f"{HR_LOG_PREFIX}下载器 {name} 任务读取失败，本轮不判定其任务删除：{error}")
                continue
            dl_type = downloader_type(service)
            for torrent in torrents:
                snapshot = torrent_snapshot(torrent, name, dl_type, now)
                if snapshot.torrent_hash:
                    snapshots[hr_task_key(name, snapshot.torrent_hash)] = snapshot

        if self._generation != generation_at_start or self._stopped:
            # 下载器查询期间发生了 stop/reload：丢弃本轮结果，不落盘、不刷新 guard。
            logger.info(f"{HR_LOG_PREFIX}{trigger_source}：扫描期间服务停止/重载，丢弃本轮结果")
            result = self._empty_result()
            result["enabled"] = False
            return result
        deleted = self._apply_snapshots(snapshots, failed, now)
        changed = self._evaluate_all(services, now)
        cleaned = auto_cleanup(self._tasks, self._config.auto_cleanup_days, now)
        self._save_tasks()
        self._refresh_guard()

        result = {
            "enabled": True,
            "downloaders": len(services),
            "total": len(self._tasks),
            "changed": changed,
            "deleted": deleted,
            "cleaned": cleaned,
            "failed_downloaders": failed,
        }
        logger.info(
            f"{HR_LOG_PREFIX}{trigger_source}检查完成：总{result['total']} 状态变更{changed} "
            f"标记删除{deleted} 清理记录{cleaned} 失败下载器{failed or '无'}"
        )
        return result

    def _discover_once(self, now: float) -> dict[str, Any]:
        """扫描下载器把白名单站点的未纳管种子纳入 H&R 管理。"""
        services = downloader_services(self._config.downloaders)
        result = {"discovered": 0, "known": 0, "outside_sites": 0, "excluded": 0, "failed_downloaders": []}
        if not services:
            logger.warning(f"{HR_LOG_PREFIX}没有可用下载器，跳过自动发现")
            result["failed_downloaders"] = ["无可用下载器"]
            return result

        tag = self._config.hit_and_run_tag
        for name, service in services.items():
            torrents, error = read_torrents(service)
            if error:
                result["failed_downloaders"].append(name)
                logger.warning(f"{HR_LOG_PREFIX}下载器 {name} 任务读取失败，跳过发现：{error}")
                continue
            dl_type = downloader_type(service)
            for torrent in torrents:
                snapshot = torrent_snapshot(torrent, name, dl_type, now)
                if not snapshot.torrent_hash:
                    continue
                if hr_task_key(name, snapshot.torrent_hash) in self._tasks:
                    result["known"] += 1
                    continue
                site_id, site_name = resolve_site(self._tracker_mappings(), snapshot.trackers, self._config.site_rules)
                if not self._config.site_in_scope(site_name):
                    result["outside_sites"] += 1
                    continue
                excluded, reason = is_excluded(snapshot, self._config.exclude_tags, self._config.exclude_categories)
                if excluded:
                    result["excluded"] += 1
                    logger.info(f"{HR_LOG_PREFIX}跳过排除种子：[{name}] [{site_name}] {snapshot.torrent_hash} {reason}")
                    continue
                task = HrTask(
                    hash=snapshot.torrent_hash,
                    downloader=name,
                    site=site_id,
                    site_name=site_name,
                    title=snapshot.title,
                    size=float(snapshot.size),
                    added_on=snapshot.added_on or now,
                    task_type=HrTaskType.DISCOVERED,
                    hit_and_run=True,
                    hr_status=HrStatus.IN_PROGRESS,
                )
                initialize_requirements(task, self._config.get_site_rule(site_name))
                apply_snapshot(task, snapshot)
                self._tasks[task.key] = task
                set_hr_tag(service, task.hash, tag)
                result["discovered"] += 1
                logger.info(
                    f"{HR_LOG_PREFIX}发现: [{name}] [{site_name}] {task.identifier} "
                    f"做种{(task.seeding_time or 0) / 3600:.1f}h 要求{task.required_hours():g}h/"
                    f"{task.hr_deadline_days or 0}天"
                )

        if result["discovered"]:
            self._save_tasks()
            self._refresh_guard()
        logger.info(
            f"{HR_LOG_PREFIX}自动发现完成：新增{result['discovered']} 已纳管{result['known']} "
            f"非目标站{result['outside_sites']} 已排除{result['excluded']}"
        )
        return result

    def _apply_snapshots(
        self,
        snapshots: dict[str, HrTorrentSnapshot],
        failed: list[str],
        now: float,
    ) -> int:
        """按采样更新任务统计，并标记/恢复种子在下载器中的存在状态。"""
        deleted = 0
        for key, task in self._tasks.items():
            if task.downloader in failed:
                continue
            snapshot = snapshots.get(key)
            if snapshot is None:
                if not task.deleted:
                    task.deleted = True
                    task.deleted_time = now
                    deleted += 1
                    logger.warning(f"{HR_LOG_PREFIX}种子已从下载器删除: [{task.site_name}] {task.identifier}")
                continue
            apply_snapshot(task, snapshot)
            if task.deleted:
                task.deleted = False
                task.deleted_time = None
                logger.info(f"{HR_LOG_PREFIX}种子已恢复做种: [{task.site_name}] {task.identifier}")
        return deleted

    def _evaluate_all(self, services: dict[str, Any], now: float) -> int:
        """逐条判定达标状态，并在状态跃迁时移除标签与记录通知事件。"""
        changed = 0
        for task in self._tasks.values():
            rule = self._config.get_site_rule(task.site_name)
            new_status = evaluate_task(task, rule, now)
            if new_status is None:
                continue
            changed += 1
            seeding_hours = (task.seeding_time or 0) / 3600
            if new_status == HrStatus.COMPLIANT:
                self._remove_tag(task, services)
                logger.info(
                    f"{HR_LOG_PREFIX}✓ 已满足: [{task.site_name}] {task.identifier} "
                    f"做种{seeding_hours:.1f}h/{task.required_hours():g}h 率{task.ratio or 0:.2f}"
                )
                record_task_event(self._plugin, task, "【H&R 已完成】", self._config.notify)
            elif new_status == HrStatus.OVERDUE:
                logger.warning(
                    f"{HR_LOG_PREFIX}✗ 已过期: [{task.site_name}] {task.identifier} "
                    f"做种{seeding_hours:.1f}h/{task.required_hours():g}h 截止{task.formatted_deadline()}"
                )
                record_task_event(self._plugin, task, "【H&R 已过期】", self._config.notify, warn=True)
            else:
                logger.warning(
                    f"{HR_LOG_PREFIX}⚠ 需做种: [{task.site_name}] {task.identifier} "
                    f"做种{seeding_hours:.1f}h/{task.required_hours():g}h "
                    f"剩余{task.remain_hours():.1f}h 已从下载器删除"
                )
                record_task_event(self._plugin, task, "【H&R 需要做种】", self._config.notify, warn=True)
        return changed


    def _remove_tag(self, task: HrTask, services: dict[str, Any]) -> None:
        """达标后移除任务上的 H&R 标签。"""
        tag = self._config.hit_and_run_tag
        service = services.get(task.downloader)
        if tag and service is not None:
            if not observe_skip(
                self._plugin,
                "hr",
                "移除 H&R 标签",
                f"{task.identifier} 标签={tag}",
            ):
                remove_hr_tag(service, task.hash, tag)

    def _task_view(self, task: HrTask) -> dict[str, Any]:
        """构造单个任务的对外字段视图。"""
        return {
            "downloader_id": task.downloader,
            "torrent_hash": task.hash,
            "name": task.identifier,
            "site": task.site_name or (str(task.site) if task.site else ""),
            "status": task.hr_status.value,
            "status_text": task.hr_status.to_chinese(),
            "progress": round(seeding_progress(task), 4),
            "remain_seconds": int(task.remain_hours() * 3600),
            "deadline": task.deadline_time if task.hr_deadline_days and task.hr_deadline_days > 0 else 0,
            "type": task.task_type.value,
            "deleted": task.deleted,
        }

    def _summary_view(self) -> dict[str, Any]:
        """构造任务汇总与保护跳过计数视图。"""
        summary = {
            "total": len(self._tasks),
            "pending": 0,
            "in_progress": 0,
            "compliant": 0,
            "needs_seeding": 0,
            "overdue": 0,
            "deleted": 0,
            "enabled": self._config.enabled,
            "protection_enabled": self._config.protection_enabled,
            "skip_stats": self._guard.get_skip_stats(),
        }
        for task in self._tasks.values():
            field = _STATUS_SUMMARY_FIELDS.get(task.hr_status)
            if field:
                summary[field] += 1
            if task.deleted:
                summary["deleted"] += 1
        return summary

    def _empty_result(self) -> dict[str, Any]:
        """构造未执行检查时的空结果。"""
        return {
            "enabled": self._config.enabled,
            "downloaders": 0,
            "total": len(self._tasks),
            "changed": 0,
            "deleted": 0,
            "cleaned": 0,
            "failed_downloaders": [],
        }

    def _ready(self, trigger_source: str) -> bool:
        """判断本轮扫描是否可执行：开关打开、服务未停止且没有重叠运行。"""
        if not self._config.enabled:
            logger.info(f"{HR_LOG_PREFIX}H&R 未启用，跳过{trigger_source}")
            return False
        if self._stopped:
            logger.info(f"{HR_LOG_PREFIX}H&R 服务已停止，跳过{trigger_source}")
            return False
        if not self._run_lock.acquire(blocking=False):
            logger.info(f"{HR_LOG_PREFIX}已有 H&R 任务在运行，跳过重叠触发：{trigger_source}")
            return False
        return True

    def _tracker_mappings(self) -> dict:
        """读取插件当前的 tracker 域名映射。"""
        mappings = getattr(self._plugin, "_tracker_mappings", None)
        return mappings if isinstance(mappings, dict) else {}

    def _refresh_guard(self) -> None:
        """按当前任务集合刷新保护快照：H&R 纳管且未达标的任务受保护。"""
        protected = [
            (task.downloader, task.hash)
            for task in self._tasks.values()
            if task.hash and task.hr_status != HrStatus.COMPLIANT
        ]
        self._guard.update(enabled=self._config.protection_enabled, protected=protected)

    def _load_tasks(self) -> dict[str, HrTask]:
        """读取持久化任务，逐条跳过无法解析的历史记录。"""
        raw = self._plugin.get_data(HR_TASKS_DATA_KEY)
        if not isinstance(raw, dict):
            return {}
        tasks: dict[str, HrTask] = {}
        for value in raw.values():
            try:
                task = HrTask.model_validate(value)
            except ValidationError as error:
                logger.warning(f"{HR_LOG_PREFIX}历史任务记录无效，已跳过：{error}")
                continue
            if task.hash:
                tasks[task.key] = task
        return tasks

    def _save_tasks(self) -> None:
        """保存任务集合。"""
        self._plugin.save_data(
            HR_TASKS_DATA_KEY,
            {key: task.model_dump(mode="json") for key, task in self._tasks.items()},
        )


__all__ = ("CLEARABLE_STATUSES", "HrService")
