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
        if self.plugin.config.zm_mail_time:
            try:
                value = datetime.strptime(
                    self.plugin.config.zm_mail_time, "%Y-%m-%d %H:%M:%S") + timedelta(hours=24)
                # 与 GroupChatZone 一致：已过期时尽快执行，而不是再延后 24 小时。
                return value if value > now else now + timedelta(seconds=3)
            except ValueError:
                logger.warning("[PtTaskFlow] [调度] 织梦邮件时间格式无效，稍后执行获取新时间")
                return now + timedelta(seconds=3)
        # 首次没有邮件时间时尽快执行，任务结束后读取邮件时间并续排。
        return now + timedelta(seconds=3)
