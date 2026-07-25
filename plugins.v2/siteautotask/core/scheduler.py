"""定时调度适配层。"""
from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.core.config import settings
from app.log import logger


class TaskScheduler:
    def __init__(self, plugin):
        self.plugin = plugin
        self.scheduler = None

    def stop(self):
        if self.scheduler:
            try:
                self.scheduler.remove_all_jobs()
                if self.scheduler.running:
                    self.scheduler.shutdown(wait=False)
            except Exception as e:
                logger.error(f"停止调度器失败：{e}")
            finally:
                self.scheduler = None

    def start(self):
        self.stop()
        cfg = self.plugin.config
        if not (cfg.enabled or cfg.onlyonce):
            return
        self.scheduler = BackgroundScheduler(timezone=settings.TZ)
        # cron 由 MoviePilot get_service() 统一管理；插件自建调度器只承载一次性任务。
        if cfg.onlyonce:
            self.scheduler.add_job(self.plugin.run_once, "date", run_date=self._after(3), name="siteautotask_once")
        if self.scheduler.get_jobs():
            self.scheduler.start()

    @staticmethod
    def _after(seconds):
        return datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=seconds)

    def services(self):
        cfg = self.plugin.config
        services = []
        if cfg.enabled and cfg.cron:
            services.append({
            "id": "siteautotask",
            "name": "站点自动任务",
            "trigger": CronTrigger.from_crontab(str(cfg.cron)),
            "func": self.plugin.run_once,
            "kwargs": {},
        })
        if cfg.enabled and cfg.retry_count > 0:
            services.append({
                "id": "siteautotask_retry",
                "name": "站点自动任务失败重试",
                "trigger": "interval",
                "func": self.plugin.run_retry,
                "kwargs": {"minutes": cfg.retry_interval},
            })
        if cfg.enabled and cfg.medal_cron:
            try:
                medal_trigger = CronTrigger.from_crontab(str(cfg.medal_cron))
            except Exception as e:
                logger.error(f"勋章 cron 解析失败：{cfg.medal_cron}，错误：{e}")
            else:
                services.append({
                    "id": "siteautotask_medal",
                    "name": "站点勋章续购",
                    "trigger": medal_trigger,
                    "func": self.plugin.run_medal,
                    "kwargs": {},
                })
        return services
