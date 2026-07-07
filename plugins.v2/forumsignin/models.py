from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


@dataclass
class ForumSigninConfig:
    enabled: bool = False
    notify: bool = False
    cron: str = "7 9 * * *"
    onlyonce: bool = False
    update_info_now: bool = False
    history_days: int = 30
    retry_count: int = 0
    retry_interval: int = 10
    use_proxy: bool = True
    fengchao_enabled: bool = True
    invites_enabled: bool = True
    fengchao_username: str = ""
    fengchao_password: str = ""
    fengchao_cookie: str = ""
    invites_username: str = ""
    invites_password: str = ""
    invites_cookie: str = ""
    mp_push_enabled: bool = False
    mp_push_interval: int = 1
    last_push_time: Optional[str] = None
    timed_update_enabled: bool = False
    timed_update_cron: str = "0 */2 * * *"
    timed_update_retry_count: int = 0
    timed_update_retry_interval: int = 0
    fengchao_current_retry: int = 0
    invites_current_retry: int = 0
    timed_update_current_retry: int = 0

    @classmethod
    def from_config(cls, config: Optional[Dict[str, Any]], get_data: Callable[[str], Any]):
        config = config or {}
        return cls(
            enabled=config.get("enabled", False),
            notify=config.get("notify", False),
            cron=config.get("cron", "7 9 * * *"),
            onlyonce=config.get("onlyonce", False),
            update_info_now=config.get("_update_info_now", config.get("update_info_now", False)),
            history_days=int(config.get("history_days") or 30),
            retry_count=int(config.get("retry_count") or 0),
            retry_interval=int(config.get("retry_interval") or 10),
            use_proxy=config.get("use_proxy", True),
            fengchao_enabled=config.get("fengchao_enabled", True),
            invites_enabled=config.get("invites_enabled", True),
            fengchao_username=config.get("fengchao_username", ""),
            fengchao_password=config.get("fengchao_password", ""),
            fengchao_cookie=config.get("fengchao_cookie", ""),
            invites_username=config.get("invites_username", ""),
            invites_password=config.get("invites_password", ""),
            invites_cookie=config.get("invites_cookie", ""),
            mp_push_enabled=config.get("mp_push_enabled", False),
            mp_push_interval=int(config.get("mp_push_interval") or 1),
            last_push_time=get_data('last_push_time'),
            timed_update_enabled=config.get("timed_update_enabled", False),
            timed_update_cron=config.get("timed_update_cron", "0 */2 * * *"),
            timed_update_retry_count=int(config.get("timed_update_retry_count") or 0),
            timed_update_retry_interval=int(config.get("timed_update_retry_interval") or 0)
        )

    def to_config_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "notify": self.notify,
            "cron": self.cron,
            "onlyonce": self.onlyonce,
            "_update_info_now": self.update_info_now,
            "history_days": self.history_days,
            "retry_count": self.retry_count,
            "retry_interval": self.retry_interval,
            "use_proxy": self.use_proxy,
            "fengchao_enabled": self.fengchao_enabled,
            "invites_enabled": self.invites_enabled,
            "fengchao_username": self.fengchao_username,
            "fengchao_password": self.fengchao_password,
            "fengchao_cookie": self.fengchao_cookie,
            "invites_username": self.invites_username,
            "invites_password": self.invites_password,
            "invites_cookie": self.invites_cookie,
            "mp_push_enabled": self.mp_push_enabled,
            "mp_push_interval": self.mp_push_interval,
            "timed_update_enabled": self.timed_update_enabled,
            "timed_update_cron": self.timed_update_cron,
            "timed_update_retry_count": self.timed_update_retry_count,
            "timed_update_retry_interval": self.timed_update_retry_interval
        }


@dataclass
class PluginCallbacks:
    save_data: Callable[[str, Any], None]
    get_data: Callable[[str], Any]
    update_config: Callable[[Dict[str, Any]], None]
    post_message: Callable[..., None]
    save_history: Callable[[Dict[str, Any]], None]
    schedule_retry: Callable[..., None]
    get_proxy_url: Callable[[], Optional[str]]
    send_notification: Callable[[str, str], None]
    send_signin_failure_notification: Callable[..., None]
    schedule_info_update_retry: Callable[[], None]
    send_info_update_failure_notification: Callable[[str], None]
    persist_config: Callable[[], None]
