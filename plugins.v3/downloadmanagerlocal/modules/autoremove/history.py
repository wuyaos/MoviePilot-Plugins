"""自动删种最近执行状态的空模板与纯函数（服务与无服务回退共用）。

本模块不依赖插件其它包，`controller/handlers.py` 的「无服务回退」与其数据页
清理计数都从这里取同一口径，避免出现两套「有没有可清理历史」的判断。
"""

from __future__ import annotations

from typing import Any

_EMPTY_TEMPLATE: dict[str, Any] = {
    "last_run_at": 0.0,
    "last_trigger": "",
    "candidates": 0,
    "paused": 0,
    "deleted": 0,
    "deleted_files": 0,
    "skipped_protected": 0,
    "skipped_missing": 0,
    "skipped": 0,
    "failed": 0,
    "failed_operations": 0,
    "config_error": "",
    "candidate_list": [],
    "details": [],
}


def empty_status() -> dict[str, Any]:
    """返回最近执行状态的空副本（列表字段独立，避免共享引用）。"""
    return {
        key: (list(value) if isinstance(value, list) else value)
        for key, value in _EMPTY_TEMPLATE.items()
    }


def history_removed_count(raw: Any) -> int:
    """判断状态里是否存在可清理的最近执行结果（0/1）。

    自动删种状态只保存最近一轮执行结果，没有独立累计段：有 `last_run_at` 即
    代表存在可清理记录；空状态模板（全 0）返回 0，不因「对象非空」误报。
    """
    if not isinstance(raw, dict):
        return 0
    try:
        return 1 if float(raw.get("last_run_at") or 0.0) > 0 else 0
    except (TypeError, ValueError):
        return 0


def cleared_status() -> dict[str, Any]:
    """生成清理后的状态：回到空状态（无累计计数需要保留）。"""
    return empty_status()


__all__ = ("cleared_status", "empty_status", "history_removed_count")
