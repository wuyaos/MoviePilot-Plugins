"""MoviePilot 配置字典到 BakaBTBrush 运行配置的转换。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ConfigError(ValueError):
    """配置字段存在会改变筛选结果的无效组合。"""


@dataclass(frozen=True)
class BrushConfig:
    enabled: bool
    notify: bool
    dry_run: bool
    cron: str
    cookie: str
    timeout: int
    detail_request_retries: int
    min_publish_age_minutes: int
    max_publish_age_minutes: int
    min_size_mb: int
    max_size_mb: int
    downloader: str
    qb_category: str
    qb_tags: tuple[str, ...]
    save_path: str
    max_bakabt_downloading: int

    @classmethod
    def from_mapping(cls, raw: dict[str, Any] | None) -> "BrushConfig":
        raw = raw or {}
        config = cls(
            enabled=bool(raw.get("enabled", False)),
            notify=bool(raw.get("notify", True)),
            dry_run=bool(raw.get("dry_run", False)),
            cron=str(raw.get("cron") or "*/10 * * * *").strip(),
            cookie=str(raw.get("cookie") or "").strip(),
            timeout=_positive_int(raw.get("timeout"), 20),
            detail_request_retries=_nonnegative_int(raw.get("detail_request_retries"), 3),
            min_publish_age_minutes=_nonnegative_int(raw.get("min_publish_age_minutes"), 0),
            max_publish_age_minutes=_nonnegative_int(raw.get("max_publish_age_minutes"), 0),
            min_size_mb=_nonnegative_int(raw.get("min_size_mb"), 0),
            max_size_mb=_nonnegative_int(raw.get("max_size_mb"), 0),
            downloader=str(raw.get("downloader") or "").strip(),
            qb_category=str(raw.get("qb_category") or "刷流").strip(),
            qb_tags=_parse_tags(raw.get("qb_tags") or "bakabt,刷流"),
            save_path=str(raw.get("save_path") or "").strip(),
            max_bakabt_downloading=_nonnegative_int(raw.get("max_bakabt_downloading"), 2),
        )
        config.validate()
        return config

    def validate(self) -> None:
        _validate_range(
            self.min_publish_age_minutes,
            self.max_publish_age_minutes,
            "最小发种时间不能大于最大发种时间",
        )
        _validate_range(
            self.min_size_mb,
            self.max_size_mb,
            "最小体积不能大于最大体积",
        )
        if "bakabt" not in self.qb_tags:
            raise ConfigError("qB 标签必须包含 bakabt，供下载槽位和流量统计使用")

    def to_mapping(self, *, onlyonce: bool = False) -> dict[str, Any]:
        """完整映射用于 CookieCloud 回写，避免覆盖其它已有配置。"""
        return {
            "enabled": self.enabled,
            "notify": self.notify,
            "onlyonce": onlyonce,
            "dry_run": self.dry_run,
            "cron": self.cron,
            "cookie": self.cookie,
            "timeout": self.timeout,
            "detail_request_retries": self.detail_request_retries,
            "min_publish_age_minutes": self.min_publish_age_minutes,
            "max_publish_age_minutes": self.max_publish_age_minutes,
            "min_size_mb": self.min_size_mb,
            "max_size_mb": self.max_size_mb,
            "downloader": self.downloader,
            "qb_category": self.qb_category,
            "qb_tags": ",".join(self.qb_tags),
            "save_path": self.save_path,
            "max_bakabt_downloading": self.max_bakabt_downloading,
        }


def _nonnegative_int(value: Any, default: int) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _positive_int(value: Any, default: int) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def _parse_tags(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple, set)):
        raw_tags = value
    else:
        raw_tags = str(value).split(",")
    return tuple(dict.fromkeys(tag.strip() for tag in raw_tags if str(tag).strip()))


def _validate_range(minimum: int, maximum: int, message: str) -> None:
    # 0 是“无约束”；只有两个端点均启用时才有大小关系。
    if minimum > 0 and maximum > 0 and minimum > maximum:
        raise ConfigError(message)
