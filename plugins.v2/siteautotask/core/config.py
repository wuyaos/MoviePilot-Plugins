"""插件配置状态对象，避免主入口类堆积配置字段。"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PluginConfig:
    enabled: bool = False
    cron: str = "0 4 * * *"
    notify: bool = False
    history_days: int = 30
    use_proxy: bool = False
    get_feedback: bool = True
    feedback_timeout: int = 5
    interval_cnt: int = 30
    retry_count: int = 3
    retry_interval: int = 10
    retry_notify: bool = False
    medal_cron: str = ""
    # 织梦 24h 电力冷却调度
    zm_cooldown: int = 3600  # 执行冷却秒数，防止短时重复触发
    zm_mail_time: str = ""  # 最新电力邮件时间 "YYYY-MM-DD HH:MM:SS"
    last_zm_execution_time: str = ""  # 上次织梦喊话执行时间（ISO 格式）
    chat_sites: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: Optional[dict] = None):
        raw = raw or {}
        values = {}
        for name, field_info in cls.__dataclass_fields__.items():
            if name in raw:
                values[name] = raw[name]
        values["history_days"] = int(values.get("history_days", 30))
        values["feedback_timeout"] = int(values.get("feedback_timeout", 5))
        values["interval_cnt"] = int(values.get("interval_cnt", 30))
        values["retry_count"] = int(values.get("retry_count", 3))
        values["retry_interval"] = int(values.get("retry_interval", 10))
        values["chat_sites"] = list(values.get("chat_sites") or [])
        values["medal_cron"] = str(values.get("medal_cron") or "").strip()
        values["zm_cooldown"] = int(values.get("zm_cooldown", 3600))
        values["zm_mail_time"] = str(values.get("zm_mail_time") or "")
        values["last_zm_execution_time"] = str(values.get("last_zm_execution_time") or "")
        return cls(**values)

    def to_dict(self):
        return {
            "enabled": self.enabled, "cron": self.cron,
            "notify": self.notify, "history_days": self.history_days,
            "use_proxy": self.use_proxy, "get_feedback": self.get_feedback,
            "feedback_timeout": self.feedback_timeout, "interval_cnt": self.interval_cnt,
            "retry_count": self.retry_count, "retry_interval": self.retry_interval,
            "retry_notify": self.retry_notify, "medal_cron": self.medal_cron,
            "zm_cooldown": self.zm_cooldown, "zm_mail_time": self.zm_mail_time,
            "last_zm_execution_time": self.last_zm_execution_time,
            "chat_sites": self.chat_sites,
        }
