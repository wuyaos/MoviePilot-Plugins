# input: 无外部依赖
# output: FeedItem 数据类, format_size, parse_size_bytes, hnr_required_hours
# pos: 数据模型层，供 keepalive / page 模块使用

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class FeedItem:
    """种子条目"""
    title: str
    url: str
    seeders: int | None
    size_bytes: int | None
    size_text: str
    is_free: bool = False


def format_size(size_bytes: int | None, fallback: str = "") -> str:
    """字节数格式化为人类可读字符串"""
    if size_bytes is None:
        return fallback or "未知"
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    value = float(size_bytes)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return str(size_bytes)


def parse_size_bytes(value: str) -> int | None:
    """解析体积字符串为字节数"""
    text = value.strip()
    if not text:
        return None
    numeric_only = re.fullmatch(r"\d+", text.replace(",", ""))
    if numeric_only:
        return int(text.replace(",", ""))
    match = re.search(r"([\d,.]+)\s*([kmgtp]?i?b|[kmgtp])?", text, re.I)
    if not match:
        return None
    number = float(match.group(1).replace(",", ""))
    unit = (match.group(2) or "b").lower()
    multipliers = {
        "b": 1, "k": 1000, "kb": 1000, "m": 1e6, "mb": 1e6,
        "g": 1e9, "gb": 1e9, "t": 1e12, "tb": 1e12,
        "kib": 1024, "mib": 1024**2, "gib": 1024**3, "tib": 1024**4,
    }
    return int(number * multipliers.get(unit, 1))


# AnimeZ H&R 所需做种时长查找表（GB → 小时），线性插值
_HNR_TABLE = [
    (0, 72), (1, 74), (5, 82), (10, 92), (15, 102), (20, 112),
    (25, 122), (30, 132), (35, 142), (40, 152), (45, 162), (50, 172),
    (60, 190), (70, 206), (80, 219), (90, 231), (100, 241),
    (125, 264), (150, 282), (175, 297), (200, 311), (225, 322),
    (250, 333), (275, 342), (300, 351), (400, 380), (500, 402),
    (600, 420), (700, 436), (800, 449), (900, 461), (1000, 472),
]


def hnr_required_hours(size_bytes: int) -> int:
    """根据 AnimeZ H&R 规则，按体积插值计算所需做种时长（小时）"""
    gb = size_bytes / 1073741824
    for i in range(len(_HNR_TABLE) - 1):
        s0, h0 = _HNR_TABLE[i]
        s1, h1 = _HNR_TABLE[i + 1]
        if s0 <= gb <= s1:
            return round(h0 + (gb - s0) / (s1 - s0) * (h1 - h0))
    return _HNR_TABLE[-1][1]
