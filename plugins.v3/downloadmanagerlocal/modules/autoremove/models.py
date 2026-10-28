"""自动删种领域模型：运行时配置、下载器采样快照与候选视图。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def format_bytes(value: Any) -> str:
    """把字节数格式化为易读文本，用于通知与候选视图。"""
    size = float(value or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.2f}{unit}"
        size /= 1024
    return f"{size:.2f}TB"


class RemoverConfig(BaseModel):
    """自动删种运行时配置：动作、下载器与全部筛选条件。"""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    notify: bool = False
    action: str = "pause"
    downloaders: list[str] = Field(default_factory=list)
    cron: str = "0 */12 * * *"
    samedata: bool = False
    mponly: bool = False
    size: str = ""
    ratio: str = ""
    time: str = ""
    upspeed: str = ""
    labels: str = ""
    pathkeywords: str = ""
    trackerkeywords: str = ""
    errorkeywords: str = ""
    torrentstates: str = ""
    torrentcategorys: str = ""


@dataclass(frozen=True)
class RemoveSnapshot:
    """下载器无关的删种采样快照：条件判定的唯一输入。"""

    downloader: str
    downloader_type: str
    torrent_hash: str
    name: str
    size: int
    ratio: float
    seeding_seconds: float
    uploaded: float
    save_path: str
    current_tracker: str
    trackers: tuple[str, ...]
    site: str
    state: str
    category: str
    tags: tuple[str, ...]
    error_string: str

    @property
    def average_upload_bps(self) -> float:
        """做种期间平均上传速度（字节/秒），未开始做种时为 0。"""
        if self.seeding_seconds <= 0:
            return 0.0
        return self.uploaded / self.seeding_seconds


@dataclass(frozen=True)
class RemoveCandidate:
    """命中全部条件的候选；reason 保存命中原因，same_data 标记辅种追加。"""

    snapshot: RemoveSnapshot
    reason: str
    same_data: bool = False

    @property
    def downloader(self) -> str:
        """返回候选所属下载器实例名。"""
        return self.snapshot.downloader

    @property
    def torrent_hash(self) -> str:
        """返回候选种子 hash。"""
        return self.snapshot.torrent_hash

    def to_view(self) -> dict[str, Any]:
        """构造候选对外字段视图。"""
        snapshot = self.snapshot
        return {
            "downloader_id": snapshot.downloader,
            "downloader_type": snapshot.downloader_type,
            "torrent_hash": snapshot.torrent_hash,
            "name": snapshot.name,
            "site": snapshot.site,
            "size": snapshot.size,
            "size_text": format_bytes(snapshot.size),
            "ratio": round(snapshot.ratio, 4),
            "seeding_hours": round(snapshot.seeding_seconds / 3600, 2),
            "average_upload_bps": round(snapshot.average_upload_bps, 2),
            "state": snapshot.state,
            "category": snapshot.category,
            "save_path": snapshot.save_path,
            "tags": list(snapshot.tags),
            "reason": self.reason,
            "same_data": self.same_data,
        }


__all__ = ("RemoveCandidate", "RemoveSnapshot", "RemoverConfig", "format_bytes")
