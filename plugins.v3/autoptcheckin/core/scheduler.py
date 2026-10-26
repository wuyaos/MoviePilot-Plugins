"""声明宿主服务；随机计划独立持久化，不创建第二个调度线程。"""
from datetime import datetime
import math
import random
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger


class Scheduler:
    def __init__(self, get_data=None, save_data=None, timezone=None):
        self.get_data = get_data or (lambda key: None)
        self.save_data = save_data or (lambda key, value: None)
        self.timezone = ZoneInfo(timezone) if isinstance(timezone, str) else timezone or datetime.now().astimezone().tzinfo
        self.services = []
        self.error = None

    def clear(self):
        self.services = []
        self.error = None

    def build(self, config, callback):
        self.clear()
        if not config.get("scheduler_enabled", False):
            return []
        if not config.get("enabled", False):
            return []
        try:
            mode = config.get("cron_mode", "interval")
            if mode == "cron":
                crons = [str(config.get("cron", "")).strip()]
            elif mode == "interval":
                interval = float(config.get("interval_hours", 2))
                begin, end = int(config.get("begin_hour", 8)), int(config.get("end_hour", 24))
                if not math.isfinite(interval) or interval < 0.5 or not 0 <= begin < end <= 24:
                    raise ValueError("invalid interval window")
                signature = f"interval:{interval}:{begin}:{end}:v2"  # v2: 首槽=开始时间
                crons = self.get_data("schedule_crons") or []
                if self.get_data("schedule_signature") != signature or not crons:
                    crons = [f"0 {begin} * * *"]  # 2026-10-23 用户裁决：开始时间本身是首个时刻（8-24 → 8:00 也算）。
                    minute = begin * 60
                    # 与 V2 TimerUtils.random_scheduler 相同：其后从 begin 起累计随机间隔。
                    for _ in range(max(1, int((end - begin) / interval)) - 1):
                        minute += random.randint(max(30, int(interval * 60 * 0.5)), int(interval * 60))
                        if minute // 60 > end:
                            break
                        crons.append(f"{minute % 60} {min(minute // 60, 23)} * * *")
                    self.save_data("schedule_crons", crons)
                    self.save_data("schedule_signature", signature)
            else:
                raise ValueError("invalid schedule mode")
            services = []
            for index, cron in enumerate(crons):
                trigger = CronTrigger.from_crontab(cron, timezone=self.timezone)
                name = "PT 签到中心"
                if mode == "interval":
                    minute, hour, *_ = cron.split()
                    name += f" {int(hour):02d}:{int(minute):02d}"
                services.append({"id": "AutoSignIn" if mode == "cron" else f"AutoSignIn.{index}",
                                 "name": name, "trigger": trigger, "func": callback, "kwargs": {}})
            self.services = services
            # interval 随机表可能整体过期（如跨天后所有小时已过）：无未来触发点则强制重排一次
            now = datetime.now(self.timezone)
            future = [svc for svc in services if svc['trigger'].get_next_fire_time(None, now)]
            if mode == 'interval' and crons and not future:
                self.save_data('schedule_signature', '')
                return self.build(config, callback)
        except (ValueError, TypeError, OverflowError):
            self.error = "invalid_schedule"
        return list(self.services)

    def next_schedule(self):
        now = datetime.now(self.timezone)
        times = [service["trigger"].get_next_fire_time(None, now) for service in self.services]
        times = [time for time in times if time is not None]
        return min(times).isoformat() if times else None
