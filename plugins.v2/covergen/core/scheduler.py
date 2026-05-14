# input: PluginConfig + CoverEngine + stop_event
# output: 定时任务注册 / TransferComplete 事件防抖 / 停止信号管理
# pos: core/ 调度层，管理插件的计划任务与事件驱动更新
"""定时任务与事件调度。TransferComplete 防抖、cron 注册、stop 信号。"""
from __future__ import annotations

import datetime
import logging
import threading
from typing import Any, Callable, Dict, Optional

from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings

logger = logging.getLogger(__name__)
LOG_PREFIX = "【CoverGen】"


class Scheduler:
    """插件调度管理器。"""

    def __init__(self, *, stop_event: threading.Event, delay: int = 60):
        self.stop_event = stop_event
        self.delay = max(1, delay)
        self._timers: Dict[str, threading.Timer] = {}
        self._timer_lock = threading.Lock()
        self._bg_scheduler = None

    # ---- 定时任务注册 ----

    def build_services(self, *, enabled: bool, cron: str, run_fn: Callable,
                       stop_fn: Callable, service_id: str, stop_id: str,
                       legacy_id: str = "", legacy_stop_id: str = "") -> list:
        """构建 get_service() 的服务列表。"""
        services = []
        if enabled and cron:
            services.append({
                "id": service_id,
                "name": "媒体库封面更新服务",
                "trigger": CronTrigger.from_crontab(cron),
                "func": run_fn,
                "kwargs": {},
            })
            if legacy_id and legacy_id != service_id:
                services.append({
                    "id": legacy_id,
                    "name": "媒体库封面更新服务（兼容旧ID）",
                    "trigger": None,
                    "func": run_fn,
                    "kwargs": {},
                })
        services.append({
            "id": stop_id,
            "name": "停止当前更新任务",
            "trigger": None,
            "func": stop_fn,
            "kwargs": {},
        })
        if legacy_stop_id and legacy_stop_id != stop_id:
            services.append({
                "id": legacy_stop_id,
                "name": "停止当前更新任务（兼容旧ID）",
                "trigger": None,
                "func": stop_fn,
                "kwargs": {},
            })
        return services

    # ---- 立即运行（一次性） ----

    def run_once(self, fn: Callable, delay_seconds: int = 3):
        """延迟 N 秒后执行一次（用于 update_now）。"""
        from apscheduler.schedulers.background import BackgroundScheduler
        import pytz
        self._bg_scheduler = BackgroundScheduler(timezone=settings.TZ)
        self._bg_scheduler.add_job(
            func=fn, trigger="date",
            run_date=datetime.datetime.now(tz=pytz.timezone(settings.TZ))
            + datetime.timedelta(seconds=delay_seconds),
        )
        if self._bg_scheduler.get_jobs():
            self._bg_scheduler.print_jobs()
            self._bg_scheduler.start()

    # ---- TransferComplete 防抖 ----

    def debounce_transfer(self, key: str, fn: Callable, *args, **kwargs):
        """防抖处理 TransferComplete 事件（同 key 仅执行最后一次）。"""
        with self._timer_lock:
            old = self._timers.pop(key, None)
            if old:
                old.cancel()
            timer = threading.Timer(self.delay, fn, args=args, kwargs=kwargs)
            timer.daemon = True
            self._timers[key] = timer
            timer.start()
            logger.info(f"{LOG_PREFIX} [防抖] {key} 延迟 {self.delay}s 后执行")

    # ---- 停止 ----

    def stop(self):
        """停止所有任务与定时器。"""
        with self._timer_lock:
            for key, timer in self._timers.items():
                timer.cancel()
            self._timers.clear()
        self.stop_event.set()
        if self._bg_scheduler:
            try:
                for job in self._bg_scheduler.get_jobs():
                    job.remove()
                self._bg_scheduler.shutdown(wait=False)
            except Exception:
                pass
            self._bg_scheduler = None
        self.stop_event.clear()

    def request_stop(self) -> str:
        """用户手动停止。"""
        if not self.stop_event.is_set():
            self.stop_event.set()
            return "已发送停止信号，请等待当前操作完成"
        return "任务已处于停止状态"
