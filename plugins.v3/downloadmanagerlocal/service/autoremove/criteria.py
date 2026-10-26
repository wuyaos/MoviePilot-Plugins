"""自动删种条件：配置校验、条件编译与逐条匹配（来源规则全部为 AND）。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Pattern

from app.sdk.config import settings

from .constants import REMOVER_ACTIONS
from .models import RemoveSnapshot, RemoverConfig

QBITTORRENT = "qbittorrent"
GIB = 1024 ** 3


class RemoverConfigError(ValueError):
    """配置非法：整轮停止，不做任何处理，避免退化为无筛选全删。"""


@dataclass(frozen=True)
class CompiledConditions:
    """已校验并编译的删种条件。"""

    action: str
    size_limit: bool
    min_size: int
    max_size: int
    ratio: Optional[float]
    seeding_seconds: Optional[float]
    upload_bps: Optional[float]
    required_tags: tuple[str, ...]
    path_pattern: Optional[Pattern[str]]
    tracker_pattern: Optional[Pattern[str]]
    error_pattern: Optional[Pattern[str]]
    torrent_states: str
    torrent_categorys: str
    same_data: bool


def compile_conditions(config: RemoverConfig) -> CompiledConditions:
    """校验并编译删种条件；非法配置抛 RemoverConfigError 停止本轮。"""
    action = str(config.action or "").strip()
    if action not in REMOVER_ACTIONS:
        raise RemoverConfigError(
            f"动作 {action!r} 无效，可选 {'/'.join(REMOVER_ACTIONS)}"
        )
    if config.trtorrentstates:
        raise RemoverConfigError(
            "该版本未实现 Transmission 状态过滤（remover_trtorrentstates），"
            "请清空该配置后重试"
        )

    size_limit = bool(config.size)
    min_size = max_size = 0
    if size_limit:
        min_size, max_size = _parse_size_range(config.size)

    ratio = _parse_number(config.ratio, "分享率")
    hours = _parse_number(config.time, "做种时间")
    speed = _parse_number(config.upspeed, "平均上传速度")
    return CompiledConditions(
        action=action,
        size_limit=size_limit,
        min_size=min_size,
        max_size=max_size,
        ratio=ratio,
        seeding_seconds=hours * 3600 if hours is not None else None,
        upload_bps=speed * 1024 if speed is not None else None,
        required_tags=_required_tags(config),
        path_pattern=_compile(config.pathkeywords, "保存路径关键词"),
        tracker_pattern=_compile(config.trackerkeywords, "Tracker关键词"),
        error_pattern=_compile(config.errorkeywords, "错误信息关键词"),
        torrent_states=str(config.torrentstates or ""),
        torrent_categorys=str(config.torrentcategorys or ""),
        same_data=bool(config.samedata),
    )


def match_reason(conditions: CompiledConditions, snapshot: RemoveSnapshot) -> Optional[str]:
    """按来源 AND 语义逐条判定；命中返回原因文本，未命中返回 None。

    分享率严格大于阈值、做种时长严格大于小时值、大小为 GB 开区间、平均上传速度严格小于
    KB/s 阈值；任务状态与分类仅 qBittorrent 生效且保持来源的字符串包含语义，错误信息关键词
    仅 Transmission 生效。
    """
    if conditions.ratio is not None and not snapshot.ratio > conditions.ratio:
        return None
    if (
        conditions.seeding_seconds is not None
        and not snapshot.seeding_seconds > conditions.seeding_seconds
    ):
        return None
    if conditions.size_limit and not conditions.min_size < snapshot.size < conditions.max_size:
        return None
    if conditions.upload_bps is not None and not snapshot.average_upload_bps < conditions.upload_bps:
        return None
    if conditions.path_pattern is not None and not conditions.path_pattern.findall(snapshot.save_path):
        return None
    if conditions.tracker_pattern is not None and not _match_tracker(conditions.tracker_pattern, snapshot):
        return None
    if snapshot.downloader_type == QBITTORRENT:
        if conditions.torrent_states and snapshot.state not in conditions.torrent_states:
            return None
        if conditions.torrent_categorys and (
            not snapshot.category or snapshot.category not in conditions.torrent_categorys
        ):
            return None
    elif conditions.error_pattern is not None and not conditions.error_pattern.findall(snapshot.error_string):
        return None
    if conditions.required_tags and not set(conditions.required_tags).issubset(snapshot.tags):
        return None
    return _reason(conditions, snapshot)


def _match_tracker(pattern: Pattern[str], snapshot: RemoveSnapshot) -> bool:
    """qBittorrent 匹配当前 tracker，Transmission 匹配任一 tracker。"""
    if snapshot.downloader_type == QBITTORRENT:
        return bool(pattern.findall(snapshot.current_tracker))
    return any(pattern.findall(url) for url in snapshot.trackers)


def _required_tags(config: RemoverConfig) -> tuple[str, ...]:
    """合并标签条件与 MP 标签限定（mponly）。"""
    tags: list[str] = []
    for part in config.labels.replace("，", ",").split(","):
        tag = part.strip()
        if tag and tag not in tags:
            tags.append(tag)
    if config.mponly:
        mp_tag = str(getattr(settings, "TORRENT_TAG", "") or "").strip()
        if mp_tag and mp_tag not in tags:
            tags.append(mp_tag)
    return tuple(tags)


def _parse_number(raw: str, label: str) -> Optional[float]:
    """解析数值条件，空值为未启用，非法值抛配置错误。"""
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError as error:
        raise RemoverConfigError(f"{label} {text!r} 无法解析为数值") from error


def _parse_size_range(raw: str) -> tuple[int, int]:
    """解析 GB 大小范围，取首尾值作开区间边界（与来源 split 首尾一致）。"""
    parts = [part.strip() for part in str(raw).split("-")]
    try:
        values = [float(part) for part in parts]
    except ValueError as error:
        raise RemoverConfigError(f"种子大小 {raw!r} 无法解析为 GB 数值范围") from error
    return int(values[0] * GIB), int(values[-1] * GIB)


def _compile(raw: str, label: str) -> Optional[Pattern[str]]:
    """编译关键词正则，空值为未启用，非法正则抛配置错误。"""
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return re.compile(text, re.I)
    except re.error as error:
        raise RemoverConfigError(f"{label}正则非法：{error}") from error


def _reason(conditions: CompiledConditions, snapshot: RemoveSnapshot) -> str:
    """构造候选命中原因文本，便于观察期核对。"""
    parts: list[str] = []
    if conditions.seeding_seconds is not None:
        parts.append(f"做种{snapshot.seeding_seconds / 3600:.1f}h")
    if conditions.ratio is not None:
        parts.append(f"分享率{snapshot.ratio:.2f}")
    if conditions.size_limit:
        parts.append(f"大小{snapshot.size / GIB:.2f}GB")
    if conditions.upload_bps is not None:
        parts.append(f"平均上传{snapshot.average_upload_bps / 1024:.1f}KB/s")
    if conditions.path_pattern is not None:
        parts.append(f"路径{snapshot.save_path}")
    if conditions.tracker_pattern is not None:
        parts.append("Tracker匹配")
    if conditions.error_pattern is not None and snapshot.downloader_type != QBITTORRENT:
        parts.append(f"错误{snapshot.error_string}")
    if conditions.torrent_states:
        parts.append(f"状态{snapshot.state}")
    if conditions.torrent_categorys:
        parts.append(f"分类{snapshot.category}")
    if conditions.required_tags:
        parts.append("标签" + ",".join(conditions.required_tags))
    return "，".join(parts) if parts else "无筛选条件"


__all__ = (
    "CompiledConditions",
    "RemoverConfigError",
    "compile_conditions",
    "match_reason",
)
