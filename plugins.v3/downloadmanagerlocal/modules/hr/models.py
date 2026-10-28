"""H&R 领域模型：运行时配置、站点规则、任务实体与达标判定。"""

from __future__ import annotations

import time
from datetime import datetime
from enum import Enum
from typing import Optional

import pytz
from app.sdk.config import settings
from pydantic import BaseModel, ConfigDict, Field


def hr_task_key(downloader_id: str, torrent_hash: str) -> str:
    """返回 (downloader, hash) 复合身份键，用于任务存储与保护快照。"""
    return f"{str(downloader_id or '').strip().lower()}:{str(torrent_hash or '').strip().lower()}"


class HrStatus(str, Enum):
    """H&R 任务的本地判定状态。"""

    PENDING = "Pending"
    IN_PROGRESS = "In Progress"
    COMPLIANT = "Compliant"
    NEEDS_SEEDING = "Needs Seeding"
    OVERDUE = "Overdue"

    def to_chinese(self) -> str:
        """返回状态中文名。"""
        _text = {
            "Pending": "待确认",
            "In Progress": "进行中",
            "Compliant": "已满足",
            "Needs Seeding": "需要做种",
            "Overdue": "已过期",
        }
        return _text.get(self.value, self.value)


class HrTaskType(str, Enum):
    """H&R 任务来源类型。"""

    NORMAL = "Normal"
    BRUSH = "Brush"
    RSS_SUBSCRIBE = "RSS Subscribe"
    DISCOVERED = "Discovered"

    def to_chinese(self) -> str:
        """返回来源类型中文名。"""
        _text = {
            "Normal": "普通",
            "Brush": "刷流",
            "RSS Subscribe": "RSS订阅",
            "Discovered": "自动发现",
        }
        return _text.get(self.value, self.value)


class HrSizeTier(BaseModel):
    """按种子大小分档的 H&R 要求（max_size_gib=0 表示无上限）。"""

    model_config = ConfigDict(extra="ignore")

    max_size_gib: float = 0
    hr_duration: float = 0
    hr_deadline_days: float = 0


class HrSiteRule(BaseModel):
    """站点 H&R 规则；字段为 None 表示继承全局规则，不参与判定。"""

    model_config = ConfigDict(extra="ignore")

    hr_duration: Optional[float] = None
    additional_seed_time: Optional[float] = None
    hr_deadline_days: Optional[float] = None
    hr_ratio: Optional[float] = None
    hr_upload_multiplier: Optional[float] = None
    hr_upload_gte_download: Optional[bool] = None
    hr_active: Optional[bool] = None
    hr_size_tiers: Optional[list[HrSizeTier]] = None
    trackers: Optional[list[str]] = None
    enabled: bool = True
    """条目级启用开关（v3.6.0）：False 为影子条目，屏蔽该站的内置预设与自定义规则（回退全局）。"""
    trackers: Optional[list[str]] = None
    """Tracker 域名/地址列表（v3.6.0，自定义站点用）：种子 tracker 在 MP 站点库识别不出时，按此列表兜底识别站点名。
    支持完整 URL 或裸域名，匹配时按域名精确比对；MP 站点库能识别的站点无需填写。"""


class HrTask(BaseModel):
    """H&R 任务实体：站点要求、下载器实时统计与判定状态。"""

    model_config = ConfigDict(extra="ignore")

    hash: str = ""
    downloader: str = ""
    site: Optional[int] = None
    site_name: Optional[str] = None
    title: str = ""
    size: float = 0
    added_on: float = Field(default_factory=time.time)
    task_type: HrTaskType = HrTaskType.NORMAL
    hit_and_run: bool = False
    hr_status: HrStatus = HrStatus.PENDING
    hr_duration: Optional[float] = None
    additional_seed_time: float = 0
    hr_ratio: Optional[float] = None
    hr_deadline_days: Optional[float] = None
    hr_upload_multiplier: Optional[float] = None
    hr_upload_gte_download: Optional[bool] = None
    ratio: float = 0
    downloaded: float = 0
    uploaded: float = 0
    seeding_time: float = 0
    state: str = ""
    deleted: bool = False
    deleted_time: Optional[float] = None
    hr_met_time: Optional[float] = None

    @property
    def key(self) -> str:
        """返回 (downloader, hash) 复合身份键。"""
        return hr_task_key(self.downloader, self.hash)

    @property
    def identifier(self) -> str:
        """返回通知与日志使用的任务标识。"""
        return self.title or self.hash

    @property
    def deadline_time(self) -> float:
        """返回考核截止时间戳。"""
        return self.added_on + (self.hr_deadline_days or 0) * 86400

    def formatted_deadline(self) -> str:
        """返回本地时区的截止时间文本，未设考核期时为 '-'。"""
        if not self.hr_deadline_days or self.hr_deadline_days <= 0:
            return "-"
        moment = datetime.fromtimestamp(self.deadline_time, pytz.timezone(settings.TZ))
        return moment.strftime("%Y-%m-%d %H:%M")

    def required_hours(self) -> float:
        """返回要求做种时长（小时），已含附加做种时间。"""
        return (self.hr_duration or 0) + (self.additional_seed_time or 0)

    def remain_hours(self) -> float:
        """返回剩余做种时长（小时），已达标时为 0。"""
        return max(self.required_hours() - (self.seeding_time or 0) / 3600, 0)

    def meets_hr(self) -> bool:
        """四条件 OR 判定：做种时长、分享率、上传倍数、上传量不低于下载量。"""
        if self.required_hours() > 0 and (self.seeding_time or 0) / 3600 >= self.required_hours():
            return True
        if self.hr_ratio and self.hr_ratio > 0 and (self.ratio or 0) >= self.hr_ratio:
            return True
        if (
            self.hr_upload_multiplier
            and self.hr_upload_multiplier > 0
            and self.size > 0
            and (self.uploaded or 0) >= self.size * self.hr_upload_multiplier
        ):
            return True
        if (
            self.hr_upload_gte_download
            and (self.downloaded or 0) > 0
            and (self.uploaded or 0) >= (self.downloaded or 0)
        ):
            return True
        return False


class HrConfig(BaseModel):
    """H&R 运行时配置：开关、下载器、站点白名单与站点规则。"""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    protection_enabled: bool = False
    check_period: int = 10
    notify: str = "always"
    downloaders: list[str] = Field(default_factory=list)
    hit_and_run_tag: str = "H&R"
    auto_cleanup_days: float = 15
    auto_discover: bool = True
    brush_plugin: str = "BrushFlow"
    exclude_tags: list[str] = Field(default_factory=list)
    exclude_categories: list[str] = Field(default_factory=list)
    sites: list[str] = Field(default_factory=list)
    notify_summary_cron: str = "0 8 * * *"
    global_rule: HrSiteRule = Field(default_factory=HrSiteRule)
    site_rules: dict[str, HrSiteRule] = Field(default_factory=dict)

    def get_site_rule(self, site_name: Optional[str]) -> HrSiteRule:
        """返回站点独立规则；站点未配置时回退全局规则。"""
        name = str(site_name or "").strip()
        rule = self.site_rules.get(name) if name else None
        return rule if rule is not None else self.global_rule

    def site_in_scope(self, site_name: Optional[str]) -> bool:
        """站点白名单判定：站点名命中白名单，或站点名存在自定义规则条目。

        白名单与规则一律按站点名匹配：站点 ID 是站点库自增主键，站点重建/迁移后会漂移，
        不作判定依据；trackers 兜底识别的自定义站点没有 MP site_id，同样按站点名参与判定。
        """
        name = str(site_name or "").strip()
        if not name:
            return False
        return name in self.sites or name in self.site_rules

__all__ = (
    "HrConfig",
    "HrSiteRule",
    "HrSizeTier",
    "HrStatus",
    "HrTask",
    "HrTaskType",
    "hr_task_key",
)
