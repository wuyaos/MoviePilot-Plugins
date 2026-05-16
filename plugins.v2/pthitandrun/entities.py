# input: config.py (SiteConfig, SizeTier, HNRStatus)
# output: TorrentTask / TorrentHistory 数据模型、HNRStatus / TaskType 枚举
# pos: 数据层，定义种子任务的完整生命周期状态与多条件 HR 判定
"""H&R 种子任务数据模型。支持多条件 OR 判定（做种时间/分享率/上传倍数/上传>=下载）。"""
from __future__ import annotations

import json
import time
from datetime import datetime
from enum import Enum
from typing import Optional

import pytz
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.context import TorrentInfo


class HNRStatus(Enum):
    PENDING = "Pending"            # 待确认
    IN_PROGRESS = "In Progress"    # 进行中
    COMPLIANT = "Compliant"        # 已满足
    UNRESTRICTED = "Unrestricted"  # 无限制
    NEEDS_SEEDING = "Needs Seeding"  # 需要做种（已删除未满足）
    OVERDUE = "Overdue"            # 已过期
    WARNED = "Warned"              # 已警告
    BANNED = "Banned"              # 已封禁

    def to_chinese(self) -> str:
        _map = {
            "Pending": "待确认", "In Progress": "进行中",
            "Compliant": "已满足", "Unrestricted": "无限制",
            "Needs Seeding": "需要做种", "Overdue": "已过期",
            "Warned": "已警告", "Banned": "已封禁",
        }
        return _map.get(self.value, self.value)


class TaskType(Enum):
    NORMAL = "Normal"
    BRUSH = "Brush"
    AUTO_SUBSCRIBE = "Auto Subscribe"
    RSS_SUBSCRIBE = "RSS Subscribe"
    DISCOVERED = "Discovered"  # 自动发现

    def to_chinese(self) -> str:
        _map = {
            "Normal": "普通", "Brush": "刷流",
            "Auto Subscribe": "自动订阅", "RSS Subscribe": "RSS订阅",
            "Discovered": "自动发现",
        }
        return _map.get(self.value, self.value)


class TorrentHistory(BaseModel):
    """种子下载记录（轻量，仅用于去重和回溯）。"""
    site: Optional[int] = None
    site_name: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    enclosure: Optional[str] = None
    page_url: Optional[str] = None
    size: float = 0
    pubdate: Optional[str] = None
    hit_and_run: bool = False
    time: Optional[float] = Field(default_factory=time.time)
    hash: Optional[str] = None
    task_type: TaskType = TaskType.NORMAL

    @classmethod
    def from_torrent_info(cls, torrent_info: TorrentInfo) -> TorrentHistory:
        return cls(**torrent_info.__dict__)

    class Config:
        extra = "ignore"
        arbitrary_types_allowed = True

    def to_dict(self, **kwargs) -> dict:
        return json.loads(self.json(**kwargs))

    @classmethod
    def from_dict(cls, data: dict) -> TorrentHistory:
        return cls.parse_raw(json.dumps(data))


class TorrentTask(TorrentHistory):
    """H&R 种子任务，完整状态追踪。"""
    hr_status: Optional[HNRStatus] = HNRStatus.PENDING
    hr_duration: Optional[float] = None       # 要求做种时间（小时）
    hr_ratio: Optional[float] = None          # 要求分享率
    hr_deadline_days: Optional[float] = None  # 考核期（天）
    hr_upload_multiplier: Optional[float] = None   # 上传量 >= 种子大小 * N
    hr_upload_gte_download: Optional[bool] = None  # 上传量 >= 下载量
    ratio: Optional[float] = 0.0
    downloaded: Optional[float] = 0.0
    uploaded: Optional[float] = 0.0
    seeding_time: Optional[float] = 0.0      # 做种时间（秒）
    deleted: Optional[bool] = False
    deleted_time: Optional[float] = None
    hr_met_time: Optional[float] = None       # 满足 H&R 的时间戳

    @property
    def identifier(self) -> str:
        parts = [self.title, self.description]
        return " | ".join(p.strip() for p in parts if p and p.strip())

    @property
    def deadline_time(self) -> float:
        return self.time + (self.hr_deadline_days or 0) * 86400

    def formatted_deadline(self) -> str:
        dt = datetime.fromtimestamp(self.deadline_time, pytz.timezone(settings.TZ))
        return dt.strftime("%Y-%m-%d %H:%M")

    def remain_time(self, additional_seed_time: float = 0.0) -> Optional[float]:
        """剩余做种时间（小时），已满足返回 None。"""
        if self.hr_status in (HNRStatus.COMPLIANT, HNRStatus.UNRESTRICTED):
            return None
        required = (self.hr_duration or 0) + (additional_seed_time or 0)
        done = (self.seeding_time or 0) / 3600
        return max(required - done, 0)

    def meets_hr(self, additional_seed_time: float = 0.0) -> bool:
        """
        多条件 OR 判定，满足任一即通过：
        1. 做种时间 >= hr_duration + additional_seed_time
        2. 分享率 >= hr_ratio
        3. 上传量 >= 种子大小 * hr_upload_multiplier
        4. 上传量 >= 下载量（hr_upload_gte_download）
        """
        seeding_hours = (self.seeding_time or 0) / 3600
        required_hours = (self.hr_duration or 0) + (additional_seed_time or 0)

        # 条件 1：做种时间
        if required_hours > 0 and seeding_hours >= required_hours:
            return True

        # 条件 2：分享率
        if self.hr_ratio and self.hr_ratio > 0:
            if (self.ratio or 0) >= self.hr_ratio:
                return True

        # 条件 3：上传量 >= 种子大小 * N 倍
        if self.hr_upload_multiplier and self.hr_upload_multiplier > 0:
            if self.size > 0 and (self.uploaded or 0) >= self.size * self.hr_upload_multiplier:
                return True

        # 条件 4：上传量 >= 下载量
        if self.hr_upload_gte_download:
            dl = self.downloaded or 0
            if dl > 0 and (self.uploaded or 0) >= dl:
                return True

        return False

    @staticmethod
    def format_to_chinese(value) -> str:
        return value.to_chinese() if hasattr(value, "to_chinese") else str(value)
