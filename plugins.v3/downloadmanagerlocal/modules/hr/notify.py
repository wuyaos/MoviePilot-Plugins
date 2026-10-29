"""H&R 通知：状态变更事件队列与每日汇总。"""

from __future__ import annotations

import time
from typing import Any, Iterable

from app.schemas.types import MessageType
from app.sdk.logging import logger

from ...utils.notify import module_title
from .constants import HR_LOG_PREFIX, HR_NOTIFY_EVENTS_DATA_KEY, HR_NOTIFY_MODES
from .models import HrStatus, HrTask

SUMMARY_TITLE = module_title("hr")
SUMMARY_GROUPS = (
    ("【已完成】", HrStatus.COMPLIANT),
    ("【已过期】", HrStatus.OVERDUE),
    ("【需要做种】", HrStatus.NEEDS_SEEDING),
)
SUMMARY_GROUP_LIMIT = 20


def should_notify(notify: str, warn: bool) -> bool:
    """按通知模式判断是否记录事件：none 不记录，on_error 仅记录异常，always 全部记录。"""
    mode = str(notify or "").strip().lower()
    if mode not in HR_NOTIFY_MODES:
        mode = "always"
    if mode == "none":
        return False
    if mode == "on_error" and not warn:
        return False
    return True


def load_events(plugin: Any) -> list[dict]:
    """读取待汇总通知事件。"""
    raw = plugin.get_data(HR_NOTIFY_EVENTS_DATA_KEY)
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


def save_events(plugin: Any, events: list[dict]) -> None:
    """保存待汇总通知事件。"""
    plugin.save_data(HR_NOTIFY_EVENTS_DATA_KEY, events)


def record_task_event(plugin: Any, task: HrTask, title: str, notify: str, warn: bool = False) -> bool:
    """记录一条状态变更事件；同一 (downloader, hash) 只保留最新一条。"""
    if not should_notify(notify, warn):
        return False
    events = [
        item
        for item in load_events(plugin)
        if not (item.get("torrent_hash") == task.hash and item.get("downloader") == task.downloader)
    ]
    events.append(_event_payload(task, title, warn))
    save_events(plugin, events)
    return True


def send_summary(plugin: Any, notify: str) -> bool:
    """按状态分组发送汇总通知，投递后清空队列；关闭通知或队列为空时返回 False。"""
    if str(notify or "").strip().lower() == "none":
        return False
    events = dedupe_events(load_events(plugin))
    if not events:
        return False
    text = build_summary_text(events)
    plugin.post_message(mtype=MessageType.SiteMessage, title=SUMMARY_TITLE, parse_mode="plain", text=text)
    save_events(plugin, [])
    logger.info(f"{HR_LOG_PREFIX}已发送汇总通知，共 {len(events)} 条状态变更")
    return True


def dedupe_events(events: Iterable[dict]) -> list[dict]:
    """按 (downloader, hash) 去重，保留最后写入的事件。"""
    unique: dict[tuple, dict] = {}
    for item in events:
        unique[(item.get("downloader"), item.get("torrent_hash"))] = item
    return list(unique.values())


def build_summary_text(events: Iterable[dict]) -> str:
    """按状态分组渲染汇总文本，每组最多 20 条。"""
    items = list(events)
    lines: list[str] = []
    for group_title, status in SUMMARY_GROUPS:
        group = [item for item in items if item.get("status") == status.value]
        if not group:
            continue
        lines.append(f"{group_title} {len(group)} 条")
        for item in group[:SUMMARY_GROUP_LIMIT]:
            ratio_req = f"/≥{item.get('hr_ratio')}" if item.get("hr_ratio") else ""
            lines.append(
                f"- [{item.get('site_name', '-')}] {item.get('identifier', '-')} "
                f"@{item.get('downloader', '-')} 做种{item.get('seeding_h', '0.0')}h/"
                f"{item.get('required_h', '0')}h 率{item.get('ratio', '0.00')}{ratio_req} "
                f"剩余{item.get('remain', '-')} 截止{item.get('deadline', '-')}"
            )
        if len(group) > SUMMARY_GROUP_LIMIT:
            lines.append(f"... 还有 {len(group) - SUMMARY_GROUP_LIMIT} 条")
    return "\n".join(lines) if lines else f"共 {len(items)} 条 H&R 状态变更"


def _event_payload(task: HrTask, title: str, warn: bool) -> dict:
    """构造单条通知事件，字段与来源插件保持一致。"""
    return {
        "torrent_hash": task.hash,
        "downloader": task.downloader,
        "site_name": task.site_name or "-",
        "identifier": task.identifier,
        "title": title,
        "warn": warn,
        "status": task.hr_status.value,
        "status_text": task.hr_status.to_chinese(),
        "task_type": task.task_type.value,
        "seeding_h": f"{(task.seeding_time or 0) / 3600:.1f}",
        "required_h": f"{task.required_hours():g}",
        "ratio": f"{(task.ratio or 0):.2f}",
        "hr_ratio": task.hr_ratio,
        "remain": f"{task.remain_hours():.1f}h",
        "deadline": task.formatted_deadline(),
        "time": time.time(),
    }


__all__ = (
    "build_summary_text",
    "dedupe_events",
    "load_events",
    "record_task_event",
    "save_events",
    "send_summary",
    "should_notify",
)
