"""插件全局配置。任务开关/选择值保持在 raw dict，由 Control.key 定位。"""
from dataclasses import dataclass, field


LEGACY_CONFIG_MAP = {
    "chat_sites": "site_ids",
    "interval_cnt": "interval",
}


def migrate_legacy_config(raw):
    """将 SiteAutoTask 的确定性全局字段迁移到 PtTaskFlow。

    任务 key 使用相同的 ``task_{site_id}_{task_name}`` 形式，直接保留；
    claim_* 旧下拉键不迁移，因为新模型统一使用 task_*，避免半选状态误执行。
    """
    raw = dict(raw or {})
    for old_key, new_key in LEGACY_CONFIG_MAP.items():
        if new_key not in raw and old_key in raw:
            raw[new_key] = raw[old_key]
    if "interval" not in raw and "interval_cnt" in raw:
        raw["interval"] = raw["interval_cnt"]
    return raw


@dataclass
class PluginConfig:
    enabled: bool = False
    cron: str = "4 0,12 * * *"
    notify: bool = False
    use_proxy: bool = False
    get_feedback: bool = True
    feedback_timeout: int = 5
    interval: int = 30
    retry_count: int = 3
    retry_interval: int = 10
    retry_notify: bool = False
    history_days: int = 30
    zm_cooldown: int = 3600
    zm_mail_time: str = ""
    last_zm_execution_time: str = ""
    site_ids: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw=None):
        raw = migrate_legacy_config(raw)
        return cls(
            enabled=bool(raw.get("enabled", False)),
            cron=str(raw.get("cron") or "4 0,12 * * *"),
            notify=bool(raw.get("notify", False)),
            use_proxy=bool(raw.get("use_proxy", False)),
            get_feedback=bool(raw.get("get_feedback", True)),
            feedback_timeout=max(0, min(10, int(raw.get("feedback_timeout", 5) or 0))),
            interval=max(0, int(raw.get("interval", 30) or 0)),
            retry_count=max(0, int(raw.get("retry_count", 3) or 0)),
            retry_interval=max(0, int(raw.get("retry_interval", 10) or 0)),
            retry_notify=bool(raw.get("retry_notify", False)),
            history_days=max(1, int(raw.get("history_days", 30) or 30)),
            zm_cooldown=max(0, int(raw.get("zm_cooldown", 3600) or 0)),
            zm_mail_time=str(raw.get("zm_mail_time") or ""),
            last_zm_execution_time=str(raw.get("last_zm_execution_time") or ""),
            site_ids=list(raw.get("site_ids") or []),
        )

    def to_dict(self):
        return {
            "enabled": self.enabled, "cron": self.cron,
            "notify": self.notify, "use_proxy": self.use_proxy,
            "get_feedback": self.get_feedback, "feedback_timeout": self.feedback_timeout,
            "interval": self.interval, "retry_count": self.retry_count,
            "retry_interval": self.retry_interval, "retry_notify": self.retry_notify,
            "history_days": self.history_days, "zm_cooldown": self.zm_cooldown,
            "zm_mail_time": self.zm_mail_time,
            "last_zm_execution_time": self.last_zm_execution_time,
            "site_ids": self.site_ids,
        }
