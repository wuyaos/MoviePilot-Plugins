# input: 无外部依赖
# output: FeedItem 数据类, format_size, parse_size_bytes
# pos: 数据模型层，供 keepalive / page 模块使用

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class FeedItem:
    """RSS 种子条目"""
    title: str
    url: str
    seeders: int | None
    size_bytes: int | None
    size_text: str


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
