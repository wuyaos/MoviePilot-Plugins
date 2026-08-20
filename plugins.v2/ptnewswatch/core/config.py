"""PTNewsWatch 平铺配置模型。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .source_registry import SOURCES

_DEFAULT_URLS = {source.source_id: source.url for source in SOURCES}


@dataclass
class PluginConfig:
    enabled: bool = False
    notify: bool = True
    onlyonce: bool = False
    cron: str = "30 */12 * * *"
    use_proxy: bool = False
    history_days: int = 30
    max_entries_per_source: int = 20
    invites_cookie: str = ""
    source_pter_digest_enabled: bool = False
    source_tjupt_digest_enabled: bool = False
    source_fengchao_pt_enabled: bool = False
    source_fengchao_invites_enabled: bool = False
    source_invites_pt_fy_enabled: bool = False
    source_pter_digest_urls: str = _DEFAULT_URLS["pter_digest"]
    source_tjupt_digest_urls: str = _DEFAULT_URLS["tjupt_digest"]
    source_fengchao_pt_urls: str = _DEFAULT_URLS["fengchao_pt"]
    source_fengchao_invites_urls: str = _DEFAULT_URLS["fengchao_invites"]
    source_invites_pt_fy_urls: str = _DEFAULT_URLS["invites_pt_fy"]

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "PluginConfig":
        raw = raw or {}
        kwargs = {
            "enabled": bool(raw.get("enabled", False)),
            "notify": bool(raw.get("notify", True)),
            "onlyonce": bool(raw.get("onlyonce", False)),
            "cron": str(raw.get("cron") or "30 */12 * * *").strip(),
            "use_proxy": bool(raw.get("use_proxy", False)),
            "history_days": _int(raw.get("history_days"), 30, 1, 365),
            "max_entries_per_source": _int(raw.get("max_entries_per_source"), 20, 1, 100),
            "invites_cookie": str(raw.get("invites_cookie") or "").strip(),
        }
        for source in SOURCES:
            kwargs[f"source_{source.source_id}_enabled"] = bool(
                raw.get(f"source_{source.source_id}_enabled", False)
            )
            kwargs[f"source_{source.source_id}_urls"] = str(
                raw.get(f"source_{source.source_id}_urls") or source.url
            ).strip()
        return cls(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        values = {
            "enabled": self.enabled,
            "notify": self.notify,
            "onlyonce": self.onlyonce,
            "cron": self.cron,
            "use_proxy": self.use_proxy,
            "history_days": self.history_days,
            "max_entries_per_source": self.max_entries_per_source,
            "invites_cookie": self.invites_cookie,
        }
        for source in SOURCES:
            values[f"source_{source.source_id}_enabled"] = self.source_enabled(source.source_id)
            values[f"source_{source.source_id}_urls"] = self.source_urls_text(source.source_id)
        return values

    def source_enabled(self, source_id: str) -> bool:
        return bool(getattr(self, f"source_{source_id}_enabled", False))

    def source_urls_text(self, source_id: str) -> str:
        return str(getattr(self, f"source_{source_id}_urls", _DEFAULT_URLS.get(source_id, "")) or "").strip()


def _int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        return min(maximum, max(minimum, int(value)))
    except (TypeError, ValueError):
        return default
