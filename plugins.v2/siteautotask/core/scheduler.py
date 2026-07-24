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
                logger.error(f"停止调度器失败: {e}")
            finally:
                self.scheduler = None

    def start(self):
        self.stop()
        cfg = self.plugin.config
        if not (cfg.enabled or cfg.onlyonce):
            return
        self.scheduler = BackgroundScheduler(timezone=settings.TZ)
        if cfg.onlyonce:
            self.scheduler.add_job(self.plugin.run_once, "date", run_date=self._after(3), name="siteautotask_once")
        elif cfg.cron:
            self.scheduler.add_job(self.plugin.run_once, CronTrigger.from_crontab(str(cfg.cron)), name="siteautotask_cron")
        if self.scheduler.get_jobs():
            self.scheduler.start()

    @staticmethod
    def _after(seconds):
        return datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=seconds)

    def services(self):
        cfg = self.plugin.config
        if not (cfg.enabled and cfg.cron):
            return []
        return [{
            "id": "siteautotask",
            "name": "站点自动任务",
            "trigger": CronTrigger.from_crontab(str(cfg.cron)),
            "func": self.plugin.run_once,
            "kwargs": {},
        }]
