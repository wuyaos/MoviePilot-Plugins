"""BakaBTBrush 的纯数据模型，不依赖 MoviePilot 宿主。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class BakaBTTorrent:
    """BakaBT 浏览页或详情页上的一个种子。"""

    torrent_id: str
    title: str
    detail_url: str
    size_mb: float
    added_text: str = ""
    published_at: datetime | None = None
    is_freeleech: bool = False
    download_url: str | None = None
    infohash: str | None = None


@dataclass(frozen=True)
class AccountSnapshot:
    """BakaBT 用户页解析到的累计流量。"""

    uploaded_mb: float | None
    downloaded_mb: float | None
    ratio: str = ""


@dataclass(frozen=True)
class BrowsePage:
    """浏览页解析结果，账户页地址来自已登录导航栏。"""

    torrents: list[BakaBTTorrent]
    account_url: str | None


@dataclass(frozen=True)
class RssFeed:
    """RSS 中可用于新种发现、时间与体积预筛的种子集合。"""

    torrents: list[BakaBTTorrent]


@dataclass(frozen=True)
class DetailPage:
    """详情页中用于二次校验和下载的字段。"""

    is_freeleech: bool
    published_at: datetime | None
    download_url: str | None
    infohash: str | None


@dataclass(frozen=True)
class QBTorrentSnapshot:
    """qB 中与 BakaBT 刷流、展示和自动删除有关的字段集合。"""

    infohash: str
    name: str
    category: str
    tags: tuple[str, ...]
    state: str
    progress: float
    uploaded: int
    downloaded: int
    added_on: int = 0
    completion_on: int = 0
    last_activity: int = 0
    seeding_time: int = 0
    ratio: float = 0.0
    up_speed: int = 0
    total_size: int = 0
