"""任务执行引擎。

只负责编排：站点发现、任务开关、结果收集、反馈关联与通知数据。
站点业务逻辑留在 sites/，UI 留在 ui/，调度留在 scheduler.py。
"""
from datetime import datetime, timedelta
import threading
import pytz
from app.core.config import settings
from app.log import logger
from ..base.result import TaskResult
from ..base.decorator import TaskType
from .history import HistoryStore
from .task_keys import site_task_key, claim_task_key
from ..sites import get_site_handler


class TaskEngine:
    def __init__(self, plugin):
        self.plugin = plugin
        self.history = plugin.history
        self._lock = threading.Lock()

    def run(self, retry_only=False):
        if not self._lock.acquire(blocking=False):
            logger.warning("已有站点任务正在执行，跳过本次调度")
            return []
        try:
            return self._run_locked(retry_only=retry_only)
        finally:
            self._lock.release()

    def _run_locked(self, retry_only=False):
        cfg = self.plugin.config
        retry_keys = {item.get("task_id") for item in getattr(self.plugin, "retry_records", [])} if retry_only else None
        if not cfg.chat_sites:
            logger.info("未配置需要执行的站点")
            return []
        records = []
        for site in self.plugin.selected_sites():
            handler = self._build_handler(site)
            if not handler:
                continue
            tasks = self.plugin.tasks_for(handler)
            for task in tasks:
                # MEDAL 任务由独立勋章调度执行，主 cron 跳过
                if task.get("task_type") == TaskType.MEDAL:
                    continue
                task_key = site_task_key(site, task)
                if retry_keys is not None and task.get("id") not in retry_keys and task_key not in retry_keys:
                    continue
                if not self.plugin.task_enabled(task_key):
                    continue
                task = dict(task)
                task["config_key"] = task_key
                # CLAIM 任务：读取用户选择的 task_id，空则跳过
                claim_id = None
                if task.get("task_type") == TaskType.CLAIM:
                    task["claim_key"] = claim_task_key(site, task)
                    claim_id = self.plugin.claim_task_id(task["claim_key"])
                record = self._run_task(handler, task, claim_task_id=claim_id, skip_if_no_claim=True)
                records.append(record)
        self.history.append(records, cfg.history_days)
        self._schedule_failed(records)
        from .notify import send_summary
        send_summary(self.plugin, records, is_retry=retry_only)
        return records

    def _build_handler(self, site):
        info = dict(site)
        info["use_proxy"] = self.plugin.config.use_proxy
        info["feedback_timeout"] = self.plugin.config.feedback_timeout
        info["interval_cnt"] = self.plugin.config.interval_cnt
        try:
            return get_site_handler(info, self.plugin.handler_classes)
        except Exception as e:
            logger.error(f"构造站点处理器失败：{site.get('name')}，错误：{e}")
            return None

    def _run_task(self, handler, task, claim_task_id=None, skip_if_no_claim=False):
        """执行单个任务。

        :param claim_task_id: CLAIM 任务传入的 task_id；None 表示 debug 模式（用 func 默认值）
        :param skip_if_no_claim: 正式模式下为 True，CLAIM 任务未配置 task_id 时跳过
        """
        now = datetime.now(tz=pytz.timezone(settings.TZ)).strftime("%Y-%m-%d %H:%M:%S")
        try:
            # CLAIM 任务或带下拉的 MEDAL 任务：正式模式下未配置 task_id 则跳过
            needs_claim_id = task.get("task_type") == TaskType.CLAIM or task.get("claim_options")
            if needs_claim_id:
                if skip_if_no_claim and not claim_task_id:
                    return {
                        "date": now, "site": handler.site_name, "domain": handler.domain,
                        "task_id": task.get("id"), "task_label": task.get("label"),
                        "task_type": task.get("task_type", TaskType.GENERIC),
                        "success": True, "status": "未配置，跳过",
                    }
                if claim_task_id is not None:
                    raw = task["func"](claim_task_id)
                else:
                    raw = task["func"]()
            else:
                raw = task["func"]()
            result = self.normalize_result(raw)
            feedback = None
            if task.get("task_type") == TaskType.CHAT and self.plugin.config.get_feedback:
                feedback = handler.get_feedback()
            record = {
                "date": now, "site": handler.site_name, "domain": handler.domain,
                "task_id": task["id"], "task_label": task.get("label"),
                "task_type": task.get("task_type", TaskType.GENERIC),
                "success": result.success, "status": result.message,
            }
            if feedback:
                record["feedback"] = feedback
            if result.rewards:
                record["rewards"] = result.rewards
            return record
        except Exception as e:
            logger.error(f"执行任务失败：{handler.site_name}/{task.get('id')}，错误：{e}", exc_info=True)
            return {
                "date": now, "site": handler.site_name, "domain": handler.domain,
                "task_id": task.get("id"), "task_label": task.get("label"),
                "task_type": task.get("task_type", TaskType.GENERIC),
                "success": False, "status": f"执行失败: {e}",
            }

    def _schedule_failed(self, records):
        """持久化失败任务，交由下一次 date 服务重试。"""
        failed = [record for record in records if not record.get("success")]
        if not failed or self.plugin.config.retry_count <= 0:
            return
        self.plugin.retry_records = failed
        self.plugin.retry_attempt = getattr(self.plugin, "retry_attempt", 0) + 1

    def run_debug(self, site_filter=None, task_filter=None):
        """调试执行：绕过配置开关与 chat_sites 限制，按过滤器直接执行指定任务。

        用于本地真实调试。写历史但不调度重试、不发通知，避免污染正常运行状态。
        site_filter: 站点 id（字符串）或域名；为空则执行全部站点。
        task_filter: 任务 id/name/label 子串（不区分大小写）；为空则执行该站点全部任务。
        """
        if not self._lock.acquire(blocking=False):
            logger.warning("调试执行被跳过：已有站点任务正在执行")
            return []
        try:
            return self._run_debug_locked(site_filter, task_filter)
        finally:
            self._lock.release()

    def _run_debug_locked(self, site_filter, task_filter):
        cfg = self.plugin.config
        sites = self.plugin.all_sites()
        if site_filter:
            sites = [s for s in sites
                     if str(s.get("id")) == str(site_filter)
                     or (s.get("domain") or "") == site_filter]
        if not sites:
            logger.info(f"调试执行：未匹配到站点 {site_filter!r}")
            return []
        records = []
        for site in sites:
            handler = self._build_handler(site)
            if not handler:
                continue
            tasks = self.plugin.tasks_for(handler)
            if task_filter:
                kw = task_filter.lower()
                tasks = [t for t in tasks
                         if kw in t.get("id", "").lower()
                         or kw in t.get("name", "").lower()
                         or kw in t.get("label", "").lower()]
            for task in tasks:
                task = dict(task)
                task["config_key"] = site_task_key(site, task)
                # CLAIM 任务：读配置，空则跳过（与正式运行一致）
                claim_id = None
                if task.get("task_type") == TaskType.CLAIM:
                    task["claim_key"] = claim_task_key(site, task)
                    claim_id = self.plugin.claim_task_id(task["claim_key"]) or None
                record = self._run_task(handler, task, claim_task_id=claim_id, skip_if_no_claim=True)
                records.append(record)
        self.history.append(records, cfg.history_days)
        return records

    def run_medal(self, delay_seconds: int = 120):
        """勋章续购专用执行：通过插件调度器延迟执行，避免 cron 触发时勋章尚未过期。

        由 scheduler 注册一次性 date 任务，不占用主锁，不与其他任务冲突。
        若已有延迟任务在等待则跳过重复触发。
        """
        scheduler = getattr(self.plugin, "scheduler", None)
        if not scheduler or not scheduler.scheduler:
            logger.warning("调度器未就绪，勋章续购立即执行")
            return self._execute_medal()
        # 检查是否已有等待中的勋章延迟任务
        existing = [j for j in scheduler.scheduler.get_jobs() if j.name == "siteautotask_medal_delayed"]
        if existing:
            logger.info("勋章续购延迟任务已在等待，跳过本次触发")
            return []
        run_at = datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=delay_seconds)
        scheduler.scheduler.add_job(
            self._execute_medal, "date", run_date=run_at,
            name="siteautotask_medal_delayed")
        logger.info(f"勋章续购已触发，延迟 {delay_seconds} 秒后执行（预计 {run_at.strftime('%H:%M:%S')}）")
        return []

    def _execute_medal(self):
        """延迟后实际执行的勋章续购逻辑。"""
        logger.info("勋章续购延迟到期，开始执行")
        if not self._lock.acquire(blocking=False):
            logger.warning("已有站点任务正在执行，跳过本次勋章续购")
            return []
        try:
            return self._run_medal_locked()
        finally:
            self._lock.release()

    def _run_medal_locked(self):
        cfg = self.plugin.config
        if not cfg.chat_sites:
            logger.info("未配置需要执行的站点")
            return []
        records = []
        for site in self.plugin.selected_sites():
            handler = self._build_handler(site)
            if not handler:
                continue
            tasks = self.plugin.tasks_for(handler)
            for task in tasks:
                if task.get("task_type") != TaskType.MEDAL:
                    continue
                task_key = site_task_key(site, task)
                if not self.plugin.task_enabled(task_key):
                    continue
                task = dict(task)
                task["config_key"] = task_key
                # MEDAL 任务复用 CLAIM 下拉机制读 medal_id，空则跳过
                claim_id = None
                if task.get("claim_options"):
                    task["claim_key"] = claim_task_key(site, task)
                    claim_id = self.plugin.claim_task_id(task["claim_key"])
                    if not claim_id:
                        now = datetime.now(tz=pytz.timezone(settings.TZ)).strftime("%Y-%m-%d %H:%M:%S")
                        records.append({
                            "date": now, "site": handler.site_name, "domain": handler.domain,
                            "task_id": task.get("id"), "task_label": task.get("label"),
                            "task_type": TaskType.MEDAL,
                            "success": True, "status": "未选择勋章，跳过",
                        })
                        continue
                record = self._run_task(handler, task, claim_task_id=claim_id, skip_if_no_claim=False)
                records.append(record)
        self.history.append(records, cfg.history_days)
        from .notify import send_summary
        send_summary(self.plugin, records, is_retry=False)
        return records

    def retry_failed(self):
        """只重试最近一次失败任务；站点任务方法会重新构造，避免复用失效 session。"""
        if not getattr(self.plugin, "retry_records", None):
            return []
        if getattr(self.plugin, "retry_attempt", 0) > self.plugin.config.retry_count:
            self.plugin.retry_records = []
            return []
        records = self.run(retry_only=True)
        # 锁冲突时 run 返回空列表，此时不能清空重试状态（all([]) 为真会误判）
        if records and all(record.get("success") for record in records):
            self.plugin.retry_records = []
        return records

    @staticmethod
    def normalize_result(raw):
        # TaskResult（鸭子类型：MoviePilot 跨路径加载时 isinstance 可能失败）
        if hasattr(raw, "success") and hasattr(raw, "message") and not isinstance(raw, (tuple, dict)):
            return TaskResult(
                bool(raw.success),
                str(raw.message) if raw.message is not None else "",
                getattr(raw, "feedback", None),
                getattr(raw, "rewards", None) or [],
            )
        if isinstance(raw, TaskResult):
            return raw
        if isinstance(raw, tuple) and len(raw) >= 2:
            return TaskResult.ok(str(raw[1])) if raw[0] else TaskResult.fail(str(raw[1]))
        if isinstance(raw, dict):
            return TaskResult(
                bool(raw.get("success", True)),
                str(raw.get("message") or raw.get("msg") or raw.get("status") or "执行完成"),
                raw.get("feedback"), raw.get("rewards") or [],
            )
        text = "执行完成" if raw is None else str(raw)
        failed = any(word in text.lower() for word in ("失败", "异常", "error"))
        return TaskResult(not failed, text)
