"""下载中心同步删除服务。"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, Iterable, List

from app.sdk.logging import logger

from ..transfer.tasks import load_transfer_tasks
from ...adapter.moviepilot import get_download_hash_by_fullpath

RECENT_CLEANUP_WINDOW_SECONDS = 30
HR_ACTION_CHECK = "hnr_check"
"""H&R 立即检查的插件动作名。"""

HR_ACTION_SCAN = "hnr_scan"
"""H&R 全量扫描的插件动作名。"""

HR_ACTION_CLEAR_COMPLIANT = "hnr_clear_compliant"
"""H&R 清除已满足记录的插件动作名。"""

HR_ACTION_CLEAR_MISSING = "hnr_clear_missing"
"""H&R 清除需做种记录的插件动作名。"""

_HR_ACTIONS = (
    HR_ACTION_CHECK,
    HR_ACTION_SCAN,
    HR_ACTION_CLEAR_COMPLIANT,
    HR_ACTION_CLEAR_MISSING,
)

_CLEANUP_LOCK_INIT = threading.Lock()


def handle_sync_delete_by_hash_event(plugin, event, trigger: str = "") -> Dict[str, Any]:
    """处理携带下载 hash 的同步删除事件。"""
    event_data = _event_data(event)
    source_hash = _clean_text(_data_get(event_data, "hash") or _data_get(event_data, "download_hash"))
    downloader = _clean_text(_data_get(event_data, "downloader") or _data_get(event_data, "downloader_name"))
    return cleanup_by_hash(plugin, source_hash, downloader=downloader, trigger=trigger)


def handle_webhook_message_event(plugin, event) -> Dict[str, Any]:
    """处理媒体服务器 Webhook 删除事件。"""
    event_data = _event_data(event)
    webhook_event = _clean_text(_data_get(event_data, "event")).lower()
    channel = _clean_text(_data_get(event_data, "channel")).lower()
    if webhook_event != "library.deleted" or (channel and channel != "emby"):
        return _empty_result(trigger="WebhookMessage")
    item_path = _clean_text(_data_get(event_data, "item_path") or _data_get(event_data, "path"))
    return cleanup_by_path(plugin, item_path, trigger="WebhookMessage")


def handle_plugin_action_event(plugin, event) -> Dict[str, Any]:
    """处理插件动作事件：H&R 命令与网盘同步删除。"""
    event_data = _event_data(event)
    action = _clean_text(_data_get(event_data, "action"))
    if action in _HR_ACTIONS:
        return _handle_hr_action(plugin, action)
    if action != "networkdisk_del":
        return _empty_result(trigger="PluginAction")
    source_hash = _clean_text(_data_get(event_data, "hash") or _data_get(event_data, "download_hash"))
    downloader = _clean_text(_data_get(event_data, "downloader") or _data_get(event_data, "downloader_name"))
    if source_hash:
        return cleanup_by_hash(plugin, source_hash, downloader=downloader, trigger="PluginAction")
    item_path = _clean_text(_data_get(event_data, "item_path") or _data_get(event_data, "path"))
    return cleanup_by_path(plugin, item_path, trigger="PluginAction")

def _handle_hr_action(plugin, action: str) -> Dict[str, Any]:
    """执行 H&R 命令动作并返回结果。"""
    result = _empty_result(trigger=action)
    service = getattr(plugin, "_hr_service", None)
    if service is None:
        return result
    if action == HR_ACTION_CHECK:
        result["hr"] = service.check_tasks("命令")
    elif action == HR_ACTION_SCAN:
        result["hr"] = service.run_scan("命令")
    elif action == HR_ACTION_CLEAR_COMPLIANT:
        result["hr"] = {"cleared": service.clear_compliant()}
    else:
        result["hr"] = {"cleared": service.clear_missing()}
    return result


def cleanup_by_path(plugin, item_path: str, trigger: str = "") -> Dict[str, Any]:
    """按媒体文件路径反查源 hash 后执行同步删除。"""
    path_text = _clean_text(item_path)
    if not path_text:
        return _empty_result(trigger=trigger)
    try:
        source_hash = _clean_text(get_download_hash_by_fullpath(path_text))
    except Exception as err:
        logger.error(f"【PT下载中心:失败清理】按路径反查下载 hash 失败 path={path_text}: {err}")
        return _empty_result(trigger=trigger)
    return cleanup_by_hash(plugin, source_hash, trigger=trigger)


def cleanup_by_hash(plugin, source_hash: str, downloader: str = "", trigger: str = "") -> dict[str, Any]:
    """串行清理并防止删除事件重入，失败后允许下一次事件重试。"""
    with _CLEANUP_LOCK_INIT:
        lock = getattr(plugin, "_sync_delete_lock", None)
        if lock is None:
            lock = threading.RLock()
            plugin._sync_delete_lock = lock
            plugin._sync_delete_inflight = set()
    source_hash = _clean_text(source_hash)
    identity = (_clean_text(downloader), source_hash)
    with lock:
        if identity in plugin._sync_delete_inflight:
            result = _empty_result(trigger=trigger)
            result["skipped"] = True
            return result
        plugin._sync_delete_inflight.add(identity)
        try:
            return _cleanup_by_hash(plugin, source_hash, downloader, trigger)
        finally:
            plugin._sync_delete_inflight.discard(identity)


def _cleanup_by_hash(plugin, source_hash: str, downloader: str = "", trigger: str = "") -> Dict[str, Any]:
    """按源下载 hash 记录转种副本（只记录，不清理任何下载器任务）。"""
    source_hash = _clean_text(source_hash)
    result = _empty_result(trigger=trigger)
    result["source_hash"] = source_hash
    if not source_hash:
        return result
    # 只有事件明确携带的下载器才构成身份；旧单链路配置只是查找候选。
    source_downloader = _clean_text(downloader)
    identity = (source_downloader, source_hash)
    if _skip_recent_duplicate(plugin, identity):
        result["skipped"] = True
        return result

    transfer_deleted = _cleanup_transfer_target(plugin, source_hash, source_downloader)
    if transfer_deleted is None:
        # 记录查询失败不写去重缓存，让下一次事件可以重试。
        return result
    if transfer_deleted > 0:
        plugin._sync_delete_recent[identity] = time.time()
    result["transfer_deleted"] = transfer_deleted
    return result


def _cleanup_transfer_target(plugin, source_hash: str, source_downloader: str) -> int | None:
    """转种副本只记录不清理：联动删除不碰任何下载器任务。

    返回 1=发现副本并已记录日志，0=无转种记录，None=记录查询失败（允许下次事件重试）。
    """
    if not source_downloader:
        # 多任务配置下旧单链路键可能为空：遍历已知源下载器找记录。
        record, source_downloader = _find_transfer_record_any_source(plugin, source_hash)
        if record is None:
            return 0
    else:
        record = plugin.get_data(f"{source_downloader}-{source_hash}") or {}
        if not isinstance(record, dict):
            return 0
    target_downloader = _clean_text(record.get("to_download"))
    target_hash = _clean_text(record.get("to_download_id"))
    if not target_downloader or not target_hash:
        return 0
    logger.info(
        f"【PT下载中心:失败清理】媒体文件已删除，转种副本 {target_downloader} / {target_hash} 保留做种，不清理任何任务"
    )
    return 1

def _find_transfer_record_any_source(plugin, source_hash: str):
    """旧键为空时，在全部配置下载器里查源记录（找不到返回 (None, "")）。"""
    names = set()
    legacy_source = _clean_text(getattr(plugin, "_fromdownloader", ""))
    if legacy_source:
        names.add(legacy_source)
    try:
        for task in load_transfer_tasks(plugin):
            name = str(task.get("from_downloader") or "").strip()
            if name:
                names.add(name)
    except Exception:
        pass
    for name in getattr(plugin, "_selected_downloaders", lambda: [])():
        if str(name or "").strip():
            names.add(str(name).strip())
    matches = []
    for name in sorted(names):
        record = plugin.get_data(f"{name}-{source_hash}") or {}
        if isinstance(record, dict) and record.get("to_download"):
            matches.append((record, name))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        logger.warning(f"【PT下载中心:失败清理】同 hash 跨下载器记录不唯一，等待带下载器身份的删除事件：{source_hash}")
    return None, ""



def _skip_recent_duplicate(plugin, source_hash: str) -> bool:
    """短时间内跳过同一源 hash 的重复广播。"""
    now = time.time()
    recent = getattr(plugin, "_sync_delete_recent", None)
    if not isinstance(recent, dict):
        recent = {}
        setattr(plugin, "_sync_delete_recent", recent)
    last = float(recent.get(source_hash) or 0)
    for key, value in list(recent.items()):
        if now - float(value or 0) > RECENT_CLEANUP_WINDOW_SECONDS:
            recent.pop(key, None)
    return bool(last and now - last <= RECENT_CLEANUP_WINDOW_SECONDS)


def _event_data(event) -> Any:
    """从 Event 或测试替身中读取事件数据。"""
    return getattr(event, "event_data", None) or {}


def _data_get(data, key: str) -> Any:
    """兼容 dict、Pydantic 模型和普通对象的字段读取。"""
    if isinstance(data, dict):
        return data.get(key)
    return getattr(data, key, None)


def _clean_text(value) -> str:
    """把可选值收敛为去空白字符串。"""
    return str(value or "").strip()


def _empty_result(trigger: str = "") -> Dict[str, Any]:
    """返回同步删除空结果。"""
    return {
        "trigger": trigger,
        "source_hash": "",
        "transfer_deleted": 0,
        "skipped": False,
    }


__all__ = (
    "HR_ACTION_CHECK",
    "HR_ACTION_CLEAR_COMPLIANT",
    "HR_ACTION_CLEAR_MISSING",
    "HR_ACTION_SCAN",
    "cleanup_by_hash",
    "cleanup_by_path",
    "handle_plugin_action_event",
    "handle_sync_delete_by_hash_event",
    "handle_webhook_message_event",
)
