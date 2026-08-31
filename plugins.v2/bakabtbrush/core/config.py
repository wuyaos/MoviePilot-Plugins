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
    rss_url: str
    timeout: int
    detail_request_retries: int
    publish_age_range_minutes: str
    size_range_mb: str
    publish_age_minimum: int
    publish_age_maximum: int
    size_minimum_mb: int
    size_maximum_mb: int
    downloader: str
    qb_category: str
    qb_tags: tuple[str, ...]
    save_path: str
    max_bakabt_downloading: int
    auto_delete: bool
    delete_files: bool
    delete_seed_hours: float
    delete_ratio: float
    delete_uploaded_gb: float
    delete_download_timeout_hours: float
    delete_inactive_minutes: int
    delete_avg_upload_kbps: float
    delete_protection_minutes: int
    delete_exclude_tags: tuple[str, ...]
    delete_expired_freeleech_incomplete: bool
    page_max_height: int
    page_visible_items: int

    @classmethod
    def from_mapping(cls, raw: dict[str, Any] | None) -> "BrushConfig":
        raw = raw or {}
        publish_text, publish_min, publish_max = parse_range(
            raw.get("publish_age_range_minutes"), "发布时间"
        )
        size_text, size_min, size_max = parse_range(
            raw.get("size_range_mb"), "种子大小"
        )
        config = cls(
            enabled=bool(raw.get("enabled", False)),
            notify=bool(raw.get("notify", True)),
            dry_run=bool(raw.get("dry_run", False)),
            cron=str(raw.get("cron") or "*/10 * * * *").strip(),
            cookie=str(raw.get("cookie") or "").strip(),
            rss_url=str(raw.get("rss_url") or "").strip(),
            timeout=_positive_int(raw.get("timeout"), 20),
            detail_request_retries=_nonnegative_int(raw.get("detail_request_retries"), 3),
            publish_age_range_minutes=publish_text,
            size_range_mb=size_text,
            publish_age_minimum=publish_min,
            publish_age_maximum=publish_max,
            size_minimum_mb=size_min,
            size_maximum_mb=size_max,
            downloader=str(raw.get("downloader") or "").strip(),
            qb_category=str(raw.get("qb_category") or "刷流").strip(),
            qb_tags=_parse_tags(raw.get("qb_tags") or "bakabt,刷流"),
            save_path=str(raw.get("save_path") or "").strip(),
            max_bakabt_downloading=_nonnegative_int(raw.get("max_bakabt_downloading"), 2),
            auto_delete=bool(raw.get("auto_delete", False)),
            delete_files=bool(raw.get("delete_files", False)),
            delete_seed_hours=_nonnegative_float(raw.get("delete_seed_hours"), 0),
            delete_ratio=_nonnegative_float(raw.get("delete_ratio"), 0),
            delete_uploaded_gb=_nonnegative_float(raw.get("delete_uploaded_gb"), 0),
            delete_download_timeout_hours=_nonnegative_float(
                raw.get("delete_download_timeout_hours"), 0
            ),
            delete_inactive_minutes=_nonnegative_int(raw.get("delete_inactive_minutes"), 0),
            delete_avg_upload_kbps=_nonnegative_float(raw.get("delete_avg_upload_kbps"), 0),
            delete_protection_minutes=_nonnegative_int(raw.get("delete_protection_minutes"), 60),
            delete_exclude_tags=_parse_tags(
                raw["delete_exclude_tags"] if "delete_exclude_tags" in raw else "H&R,保留"
            ),
            delete_expired_freeleech_incomplete=bool(
                raw.get("delete_expired_freeleech_incomplete", False)
            ),
            page_max_height=_bounded_int(raw.get("page_max_height"), 520, 240, 1600),
            page_visible_items=_bounded_int(raw.get("page_visible_items"), 8, 1, 30),
        )
        config.validate()
        return config

    def validate(self) -> None:
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
            "rss_url": self.rss_url,
            "timeout": self.timeout,
            "detail_request_retries": self.detail_request_retries,
            "publish_age_range_minutes": self.publish_age_range_minutes,
            "size_range_mb": self.size_range_mb,
            "downloader": self.downloader,
            "qb_category": self.qb_category,
            "qb_tags": ",".join(self.qb_tags),
            "save_path": self.save_path,
            "max_bakabt_downloading": self.max_bakabt_downloading,
            "auto_delete": self.auto_delete,
            "delete_files": self.delete_files,
            "delete_seed_hours": self.delete_seed_hours,
            "delete_ratio": self.delete_ratio,
            "delete_uploaded_gb": self.delete_uploaded_gb,
            "delete_download_timeout_hours": self.delete_download_timeout_hours,
            "delete_inactive_minutes": self.delete_inactive_minutes,
            "delete_avg_upload_kbps": self.delete_avg_upload_kbps,
            "delete_protection_minutes": self.delete_protection_minutes,
            "delete_exclude_tags": ",".join(self.delete_exclude_tags),
            "delete_expired_freeleech_incomplete": self.delete_expired_freeleech_incomplete,
            "page_max_height": self.page_max_height,
            "page_visible_items": self.page_visible_items,
        }


def parse_range(value: Any, label: str) -> tuple[str, int, int]:
    """严格解析：单值为最大值，完整双值为区间，0/空为不限。"""
    text = str(value or "").strip()
    if not text or text == "0":
        return "0", 0, 0
    if "-" not in text:
        maximum = _strict_nonnegative_int(text, label)
        if maximum <= 0:
            return "0", 0, 0
        return str(maximum), 0, maximum
    if text.count("-") != 1:
        raise ConfigError(f"{label}格式无效，只支持单值或“最小值-最大值”")
    minimum_text, maximum_text = (part.strip() for part in text.split("-", 1))
    if not minimum_text or not maximum_text:
        raise ConfigError(f"{label}不支持省略范围端点")
    minimum = _strict_nonnegative_int(minimum_text, label)
    maximum = _strict_nonnegative_int(maximum_text, label)
    if minimum <= 0 or maximum <= 0:
        raise ConfigError(f"{label}区间端点必须为非零整数；0/空仅表示完全不限制")
    if minimum > maximum:
        raise ConfigError(f"{label}最小值不能大于最大值")
    return f"{minimum}-{maximum}", minimum, maximum


def _strict_nonnegative_int(value: Any, label: str) -> int:
    text = str(value).strip()
    if not text.isdigit():
        raise ConfigError(f"{label}仅支持非负整数")
    return int(text)


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


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        return min(maximum, max(minimum, int(value)))
    except (TypeError, ValueError):
        return default


def _nonnegative_float(value: Any, default: float) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return default


def _parse_tags(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple, set)):
        raw_tags = value
    else:
        raw_tags = str(value).split(",")
    return tuple(dict.fromkeys(tag.strip() for tag in raw_tags if str(tag).strip()))
