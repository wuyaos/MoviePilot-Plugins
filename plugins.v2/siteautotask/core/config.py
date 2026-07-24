"""插件配置状态对象，避免主入口类堆积配置字段。"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PluginConfig:
    enabled: bool = False
    cron: str = "30 9,21 * * *"
    onlyonce: bool = False
    notify: bool = False
    history_days: int = 30
    use_proxy: bool = False
    get_feedback: bool = True
    feedback_timeout: int = 5
    retry_count: int = 2
    retry_interval: int = 10
    retry_notify: bool = False
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
        values["retry_count"] = int(values.get("retry_count", 2))
        values["retry_interval"] = int(values.get("retry_interval", 10))
        values["chat_sites"] = list(values.get("chat_sites") or [])
        return cls(**values)

    def to_dict(self):
        return {
            "enabled": self.enabled, "cron": self.cron, "onlyonce": self.onlyonce,
            "notify": self.notify, "history_days": self.history_days,
            "use_proxy": self.use_proxy, "get_feedback": self.get_feedback,
            "feedback_timeout": self.feedback_timeout, "retry_count": self.retry_count,
            "retry_interval": self.retry_interval, "retry_notify": self.retry_notify,
            "chat_sites": self.chat_sites,
        }
