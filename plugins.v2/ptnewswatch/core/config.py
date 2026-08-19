"""PTNewsWatch 平铺配置模型。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .source_registry import SOURCES


@dataclass
class PluginConfig:
    enabled: bool = False
    notify: bool = True
    onlyonce: bool = False
    cron: str = "30 */12 * * *"
    use_proxy: bool = False
    history_days: int = 30
    max_entries_per_source: int = 20
    first_run_push_recent: bool = False
    invites_cookie: str = ""
    source_pter_digest_enabled: bool = True
    source_tjupt_digest_enabled: bool = True
    source_fengchao_pt_enabled: bool = True
    source_fengchao_invites_enabled: bool = True
    source_invites_pt_fy_enabled: bool = True

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "PluginConfig":
        raw = raw or {}
        return cls(
            enabled=bool(raw.get("enabled", False)),
            notify=bool(raw.get("notify", True)),
            onlyonce=bool(raw.get("onlyonce", False)),
            cron=str(raw.get("cron") or "30 */12 * * *").strip(),
            use_proxy=bool(raw.get("use_proxy", False)),
            history_days=_int(raw.get("history_days"), 30, 1, 365),
            max_entries_per_source=_int(raw.get("max_entries_per_source"), 20, 1, 100),
            first_run_push_recent=bool(raw.get("first_run_push_recent", False)),
            invites_cookie=str(raw.get("invites_cookie") or "").strip(),
            source_pter_digest_enabled=bool(raw.get("source_pter_digest_enabled", True)),
            source_tjupt_digest_enabled=bool(raw.get("source_tjupt_digest_enabled", True)),
            source_fengchao_pt_enabled=bool(raw.get("source_fengchao_pt_enabled", True)),
            source_fengchao_invites_enabled=bool(raw.get("source_fengchao_invites_enabled", True)),
            source_invites_pt_fy_enabled=bool(raw.get("source_invites_pt_fy_enabled", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "notify": self.notify,
            "onlyonce": self.onlyonce,
            "cron": self.cron,
            "use_proxy": self.use_proxy,
            "history_days": self.history_days,
            "max_entries_per_source": self.max_entries_per_source,
            "first_run_push_recent": self.first_run_push_recent,
            "invites_cookie": self.invites_cookie,
            **{
                f"source_{source.source_id}_enabled": getattr(
                    self, f"source_{source.source_id}_enabled"
                )
                for source in SOURCES
            },
        }

    def source_enabled(self, source_id: str) -> bool:
        return bool(getattr(self, f"source_{source_id}_enabled", False))


def _int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        return min(maximum, max(minimum, int(value)))
    except (TypeError, ValueError):
        return default
