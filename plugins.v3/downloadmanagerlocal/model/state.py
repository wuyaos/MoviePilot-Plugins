"""下载中心持久化状态键与轻量读写 helper。"""

from __future__ import annotations

from datetime import date
from threading import RLock
from typing import Any

from ..modules.hr.constants import HR_NOTIFY_EVENTS_DATA_KEY, HR_TASKS_DATA_KEY

RENAME_RECORDS_KEY = "rename_records"
RENAME_RETRY_STATE_KEY = "rename_retry_state"
SEED_RECHECK_QUEUE_KEY = "seed_recheck_queue"
TRANSFER_STATS_KEY = "transfer_stats"
TRANSFER_STATS_SCHEMA_VERSION = 2
TRANSFER_SKIP_STATS_KEY = "transfer_skip_stats"
SITE_TAG_STATUS_KEY = "sitetag_status"
TAG_CLEANUP_STATUS_KEY = "tag_cleanup_status"
_TRANSFER_STATS_LOCK = RLock()

TRANSFER_SCHEDULE_KEY = "transfer_schedule"
TRANSFER_SCHEDULE_SCHEMA_VERSION = 1

UPLOAD_LIMIT_STATE_KEY = "upload_limit_state"

PERSISTED_STATE_KEYS = {
    "rename_history": RENAME_RECORDS_KEY,
    "rename_retry_state": RENAME_RETRY_STATE_KEY,
    "seed_recheck_queue": SEED_RECHECK_QUEUE_KEY,
    "transfer_stats": TRANSFER_STATS_KEY,
    "transfer_schedule": TRANSFER_SCHEDULE_KEY,
    "upload_limit_state": UPLOAD_LIMIT_STATE_KEY,
    "hr_tasks": HR_TASKS_DATA_KEY,
    "hr_notify_events": HR_NOTIFY_EVENTS_DATA_KEY,
    "sitetag_status": SITE_TAG_STATUS_KEY,
    "tag_cleanup_status": TAG_CLEANUP_STATUS_KEY,
}


def _non_negative_int(value: Any) -> int:
    """把不可信计数规范为非负整数。"""
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def today_stamp() -> str:
    """返回本地时区当天日期戳，用于今日计数按天归零。"""
    return date.today().isoformat()


def _normalize_daily_counters(
    payload: dict,
    *,
    total_keys: tuple[str, ...],
    today_keys: tuple[str, ...],
    nested: bool = True,
) -> dict[str, Any]:
    """按当天日期戳规范化今日计数，跨天读取时视为归零且不写盘。

    :param payload: 原始持久化字典
    :param total_keys: 累计计数字段名，按父子顺序排列，后者必须是前者的子集
    :param today_keys: 今日计数字段名，与累计字段一一对应
    :return: 规范化后的今日日期戳与今日计数字段
    """
    today = today_stamp()
    if str(payload.get("today_date") or "").strip() != today:
        return {"today_date": today, **{key: 0 for key in today_keys}}
    normalized: dict[str, Any] = {"today_date": today}
    ceiling: int | None = None
    for total_key, today_key in zip(total_keys, today_keys):
        limit = _non_negative_int(payload.get(total_key))
        if nested and ceiling is not None:
            limit = min(limit, ceiling)
        value = min(limit, _non_negative_int(payload.get(today_key)))
        normalized[today_key] = value
        ceiling = value
    return normalized


def load_transfer_stats(plugin: Any) -> dict[str, Any]:
    """读取并规范化累计与今日转种成功统计。"""
    raw_value = plugin.get_data(TRANSFER_STATS_KEY)
    payload = raw_value if isinstance(raw_value, dict) else {}
    success_total = _non_negative_int(payload.get("success_total"))
    fallback_success = min(
        success_total,
        _non_negative_int(payload.get("fallback_success")),
    )
    daily = _normalize_daily_counters(
        payload,
        total_keys=("success_total", "fallback_success"),
        today_keys=("today_success", "today_fallback"),
    )
    return {
        "schema_version": TRANSFER_STATS_SCHEMA_VERSION,
        "success_total": success_total,
        "fallback_success": fallback_success,
        **daily,
        "failure_today_date": today_stamp(),
        "failure_today_count": (_non_negative_int(payload.get("failure_today_count"))
                                if payload.get("failure_today_date") == today_stamp() else 0),
    }


def record_transfer_success(plugin: Any, count: int, *, fallback: bool) -> dict[str, Any]:
    """累计一次转种成功批次，并返回最新持久化统计。"""
    increment = _non_negative_int(count)
    with _TRANSFER_STATS_LOCK:
        stats = load_transfer_stats(plugin)
        if increment:
            stats["success_total"] += increment
            stats["today_success"] += increment
            if fallback:
                stats["fallback_success"] += increment
                stats["today_fallback"] += increment
            plugin.save_data(TRANSFER_STATS_KEY, stats)
        return stats


def record_transfer_failure(plugin: Any) -> dict[str, Any]:
    """累计今日进入终态失败的事件；来源索引被新事务覆盖不减少计数。"""
    with _TRANSFER_STATS_LOCK:
        stats = load_transfer_stats(plugin)
        stats["failure_today_count"] += 1
        plugin.save_data(TRANSFER_STATS_KEY, stats)
        return stats
