"""整理失败清理状态的空模板与纯函数（服务与无服务回退共用）。

状态分三段：`scan`＝最近一轮巡检结果、`event`＝整理失败即时清理结果、
`total`＝累计计数。清理记录只清最近结果并保留 `total`，判定「有没有可清理的
最近结果」也以这两段为准 —— 服务与 `controller/handlers.py` 的无服务回退、
数据页清理计数共用这里的实现。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

EMPTY_STATUS: dict[str, Any] = {
    "last_scan_time": 0.0,
    "last_scan_trigger": "",
    "scan": {"scanned": 0, "cleaned": 0, "failed": 0, "skipped": 0},
    "event": {"deleted": 0, "failed": 0, "skipped": 0},
    "total": {"cleaned": 0, "failed": 0, "skipped": 0},
}


def empty_status() -> dict[str, Any]:
    """返回状态空副本（含嵌套计数段，深拷贝避免共享引用）。"""
    return deepcopy(EMPTY_STATUS)


def as_float(value: Any) -> float:
    """把时间戳收敛为非负浮点数。"""
    try:
        return max(float(value), 0.0)
    except (TypeError, ValueError):
        return 0.0


def as_counter(value: Any) -> int:
    """把计数收敛为非负整数。"""
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0


def history_removed_count(raw: Any) -> int:
    """判断状态里是否存在可清理的最近结果（0/1）；只有累计计数时返回 0。"""
    if not isinstance(raw, dict):
        return 0
    if as_float(raw.get("last_scan_time")) > 0:
        return 1
    for section in ("scan", "event"):
        stored = raw.get(section)
        if isinstance(stored, dict) and any(as_counter(value) for value in stored.values()):
            return 1
    return 0


def cleared_status(raw: Any) -> dict[str, Any]:
    """生成清理最近结果后的状态：最近巡检与即时清理结果归零，`total` 累计值保留。"""
    status = empty_status()
    stored = raw.get("total") if isinstance(raw, dict) else None
    if isinstance(stored, dict):
        for key in status["total"]:
            status["total"][key] = as_counter(stored.get(key))
    return status


__all__ = ("EMPTY_STATUS", "as_counter", "as_float", "cleared_status", "empty_status", "history_removed_count")
