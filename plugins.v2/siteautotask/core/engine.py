"""任务执行引擎。

只负责编排：站点发现、任务开关、结果收集、反馈关联与通知数据。
站点业务逻辑留在 sites/，UI 留在 ui/，调度留在 scheduler.py。
"""
from datetime import datetime
import threading
import pytz
from app.core.config import settings
from app.log import logger
from ..base.result import TaskResult
from ..base.decorator import TaskType
from .history import HistoryStore
from .task_keys import site_task_key
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
                task_key = site_task_key(site, task)
                if retry_keys is not None and task.get("id") not in retry_keys and task_key not in retry_keys:
                    continue
                enabled = cfg.task_switches.get(task_key)
                if enabled is None:
                    # 兼容早期以站点文件名生成的旧键
                    enabled = cfg.task_switches.get(task["id"], False)
                if not enabled:
                    continue
                task = dict(task)
                task["config_key"] = task_key
                record = self._run_task(handler, task)
                records.append(record)
        self.history.append(records, cfg.history_days)
        self._schedule_failed(records)
        from .notify import send_summary
        send_summary(self.plugin, records)
        return records

    def _build_handler(self, site):
        info = dict(site)
        info["use_proxy"] = self.plugin.config.use_proxy
        info["feedback_timeout"] = self.plugin.config.feedback_timeout
        try:
            return get_site_handler(info, self.plugin.handler_classes)
        except Exception as e:
            logger.error(f"构造站点处理器失败 [{site.get('name')}]: {e}")
            return None

    def _run_task(self, handler, task):
        now = datetime.now(tz=pytz.timezone(settings.TZ)).strftime("%Y-%m-%d %H:%M:%S")
        try:
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
            logger.error(f"执行任务失败 [{handler.site_name}/{task.get('id')}]: {e}", exc_info=True)
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
