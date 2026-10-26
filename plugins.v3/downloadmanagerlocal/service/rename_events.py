"""下载新增事件触发的即时重命名调度。"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta

import pytz
from apscheduler.schedulers.background import BackgroundScheduler

from app.sdk.config import settings
from app.sdk.logging import logger

from ..utils.torrent_adapter import get_hash
from .rename import (
    build_rename_config,
    notify_rename_result,
    record_rename_module_result,
    rename_candidate,
)

EVENT_JOB_PREFIX = "rename_event_"


def handle_download_added_rename(plugin, event) -> dict:
    """合并同一 (下载器, hash) 的下载新增事件，防抖后即时重命名。"""
    rename_config = build_rename_config(getattr(plugin, "_rename_config", None))
    if not rename_config["enabled"] or not rename_config["on_download_added"]:
        return {"ok": False, "reason": "disabled"}

    data = getattr(event, "event_data", None)
    data = data if isinstance(data, dict) else {}
    downloader_name = str(data.get("downloader") or data.get("downloader_name") or "").strip()
    torrent_hash = str(data.get("hash") or data.get("torrent_hash") or "").strip()
    if not downloader_name or not torrent_hash:
        return {"ok": False, "reason": "identity_missing"}
    if downloader_name not in rename_config["downloader"]:
        return {"ok": False, "reason": "downloader_not_selected"}

    key = f"{downloader_name}:{torrent_hash}"
    with _pending_lock(plugin):
        _pending_tasks(plugin)[key] = {"downloader": downloader_name, "hash": torrent_hash}
        _schedule_pending_rename(plugin, rename_config, key)
    return {"ok": True, "scheduled": key}


def clear_rename_pending(plugin) -> None:
    """插件停止时清空待处理事件，避免旧回调继续重命名。"""
    lock = getattr(plugin, "_rename_pending_lock", None)
    if lock is None:
        return
    with lock:
        _pending_tasks(plugin).clear()


def _pending_lock(plugin):
    """返回待处理事件锁，首次访问时创建。"""
    lock = getattr(plugin, "_rename_pending_lock", None)
    if lock is None:
        lock = threading.RLock()
        plugin._rename_pending_lock = lock
    return lock


def _pending_tasks(plugin) -> dict:
    """返回待处理事件表，首次访问时创建。"""
    tasks = getattr(plugin, "_rename_pending", None)
    if not isinstance(tasks, dict):
        tasks = {}
        plugin._rename_pending = tasks
    return tasks


def _schedule_pending_rename(plugin, rename_config: dict, key: str) -> None:
    """按防抖秒数登记延迟任务，重复事件替换同 key 的待处理任务。"""
    scheduler = getattr(plugin, "_scheduler", None)
    if scheduler is None:
        scheduler = BackgroundScheduler(timezone=settings.TZ)
        plugin._scheduler = scheduler
    if not scheduler.running:
        scheduler.start()
    delay = max(1, int(rename_config.get("event_debounce_seconds") or 3))
    scheduler.add_job(
        _run_pending_rename,
        "date",
        run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=delay),
        id=f"{EVENT_JOB_PREFIX}{key}",
        kwargs={"plugin": plugin, "key": key},
        replace_existing=True,
        misfire_grace_time=None,
    )


def _run_pending_rename(plugin, key: str) -> None:
    """处理一条已防抖的下载新增事件。"""
    event = getattr(plugin, "_event", None)
    if event is not None and event.is_set():
        return
    with _pending_lock(plugin):
        task = _pending_tasks(plugin).pop(key, None)
    if not task:
        return

    rename_config = build_rename_config(getattr(plugin, "_rename_config", None))
    if not rename_config["enabled"] or not rename_config["on_download_added"]:
        return

    service = plugin.service_info(task["downloader"])
    if not service or not getattr(service, "instance", None):
        logger.warning(f"事件重命名跳过：下载器不可用 {task['downloader']}")
        record_rename_module_result(plugin, "event", 0, 1, 0)
        return

    torrents, error = service.instance.get_torrents(ids=[task["hash"]])
    if error or not torrents:
        logger.warning(f"事件重命名跳过：读取任务失败 {task['downloader']} {task['hash']} {error or ''}")
        record_rename_module_result(plugin, "event", 0, 1, 0)
        return

    result = {"renamed": 0, "failed": 0, "skipped": 0}
    for torrent in torrents:
        if get_hash(torrent, service.type) != task["hash"]:
            continue
        result[rename_candidate(plugin, service, rename_config, torrent)] += 1
    record_rename_module_result(plugin, "event", result["renamed"], result["failed"], result["skipped"])
    notify_rename_result(plugin, "下载新增事件", rename_config, result)


__all__ = (
    "clear_rename_pending",
    "handle_download_added_rename",
)
