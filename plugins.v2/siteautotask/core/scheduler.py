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
        if not cfg.enabled:
            return
        self.scheduler = BackgroundScheduler(timezone=settings.TZ)
        # 仅处理动态 Zm/勋章调度；人为“立即运行一次”由入口线程执行。
        # stop() 已清空旧实例的等待任务，普通重载不会恢复或执行它们。
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
            "func": self.plugin.run_scheduled,
            "kwargs": {},
        })
        # 失败重试已并入主 cron，不再注册独立重试服务。
        # 织梦 24h 电力冷却调度（固定 cron 每天 0:10）
        if cfg.enabled and self._has_zm_site():
            services.append({
                "id": "siteautotask_zm",
                "name": "织梦24h电力调度",
                "trigger": CronTrigger.from_crontab("10 0 * * *"),
                "func": self.plugin.run_zm,
                "kwargs": {},
            })
        return services

    def _has_zm_site(self):
        """检查已选站点中是否有织梦。"""
        try:
            for site in self.plugin.selected_sites():
                name = (site.get("name") or "")
                domain = (site.get("domain") or "")
                if "织梦" in name or "zmpt.cc" in domain:
                    return True
        except Exception:
            pass
        return False

    def _compute_zm_next_time(self, cfg):
        """计算织梦下次执行时间；重载时不补执行过期任务。"""
        tz = pytz.timezone(settings.TZ)
        now = datetime.now(tz=tz)
        fallback_time = now + timedelta(hours=24)
        if not cfg.zm_mail_time:
            return fallback_time
        try:
            mail_time = datetime.strptime(cfg.zm_mail_time, "%Y-%m-%d %H:%M:%S")
            if mail_time.tzinfo is None:
                mail_time = tz.localize(mail_time)
            next_time = mail_time + timedelta(hours=24)
            return next_time if next_time > now else fallback_time
        except Exception as e:
            logger.error(f"解析织梦邮件时间失败：{e}")
            return fallback_time
