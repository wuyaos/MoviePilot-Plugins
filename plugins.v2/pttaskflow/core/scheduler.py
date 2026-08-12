"""MoviePilot 公共服务调度适配。"""
from datetime import datetime, timedelta
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from app.core.config import settings
from app.log import logger


class TaskScheduler:
    def __init__(self, plugin):
        self.plugin = plugin

    def services(self):
        if not self.plugin.config.enabled or not self.plugin.config.cron:
            return []
        try:
            trigger = CronTrigger.from_crontab(self.plugin.config.cron, timezone=settings.TZ)
        except Exception as error:
            logger.error(f"[PtTaskFlow] [调度] Cron 无效：{error}")
            return []
        services = [{
            "id": "pttaskflow_main", "name": "PT任务流", "trigger": trigger,
            "func": self.plugin.run_scheduled, "kwargs": {},
        }]
        if self._has_zm():
            services.append({
                "id": "pttaskflow_zm", "name": "织梦24h电力调度",
                "trigger": DateTrigger(run_date=self._next_zm_time()),
                "func": self.plugin.run_zm, "kwargs": {},
            })
        return services

    def _has_zm(self):
        return any(site.domain == "zmpt.cc" for site in self.plugin.runtime_sites())

    def _next_zm_time(self):
        now = datetime.now()
        retry_at = getattr(self.plugin, "_zm_retry_at", None)
        if retry_at and retry_at > now:
            return retry_at
        if self.plugin.config.zm_mail_time:
            try:
                mail_due = datetime.strptime(
                    self.plugin.config.zm_mail_time, "%Y-%m-%d %H:%M:%S") + timedelta(hours=24)
                if mail_due > now:
                    return mail_due
            except ValueError:
                logger.warning("[PtTaskFlow] [调度] 织梦邮件时间格式无效，改用最近执行时间续排")

        # 邮件时间过期或未解析到新邮件时，用最近执行时间续排；否则 date 任务会立即
        # 触发并被冷却跳过，随后因一次性任务已消费而永久丢失。
        if self.plugin.config.last_zm_execution_time:
            try:
                execution_due = datetime.fromisoformat(
                    self.plugin.config.last_zm_execution_time) + timedelta(hours=24)
                if execution_due > now:
                    return execution_due
            except (TypeError, ValueError):
                logger.warning("[PtTaskFlow] [调度] 织梦最近执行时间格式无效，稍后重新执行")

        # 首次、超过 24 小时或无有效时间时尽快执行，任务结束后读取邮件时间并续排。
        return now + timedelta(seconds=3)
