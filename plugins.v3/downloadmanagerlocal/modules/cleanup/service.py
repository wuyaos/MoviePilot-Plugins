"""下载中心同步删除服务。"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, Iterable, List

from app.sdk.logging import logger

from ..hr.guard import SKIP_PATH_SYNC_DELETE, HrGuard
from ..transfer.tasks import load_transfer_tasks
from ...adapter.moviepilot import get_download_hash_by_fullpath, get_downloader_services

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
    with lock:
        if source_hash in plugin._sync_delete_inflight:
            result = _empty_result(trigger=trigger)
            result["skipped"] = True
            return result
        plugin._sync_delete_inflight.add(source_hash)
        try:
            return _cleanup_by_hash(plugin, source_hash, downloader, trigger)
        finally:
            plugin._sync_delete_inflight.discard(source_hash)


def _cleanup_by_hash(plugin, source_hash: str, downloader: str = "", trigger: str = "") -> Dict[str, Any]:
    """按源下载 hash 清理转种目标任务。"""
    source_hash = _clean_text(source_hash)
    result = _empty_result(trigger=trigger)
    result["source_hash"] = source_hash
    if not source_hash:
        return result
    if _skip_recent_duplicate(plugin, source_hash):
        result["skipped"] = True
        return result

    source_downloader = _clean_text(downloader or getattr(plugin, "_fromdownloader", ""))
    transfer_deleted = _cleanup_transfer_target(plugin, source_hash, source_downloader)
    if transfer_deleted is None:
        # 确定了目标但删除调用失败（或 H&R 保护跳过且需要显式反馈时）不记录去重，
        # 允许下一轮重试；result 保持 0 让上层按未删除处理。
        transfer_deleted = 0
    if transfer_deleted >= 0:
        plugin._sync_delete_recent[source_hash] = time.time()
    result["transfer_deleted"] = max(0, transfer_deleted)
    if transfer_deleted:
        logger.info(f"【PT下载中心:失败清理】{trigger or '事件'} 已按源 hash={source_hash} 删除转种 {transfer_deleted} 个（含文件）")
    return result


def _cleanup_transfer_target(plugin, source_hash: str, source_downloader: str) -> int:
    """删除源 hash 对应的转种目标任务。

    返回：删除的目标数量；0 = 无记录/无目标/H&R 保护跳过/删除失败；
    记录存在但事件未提供下载器时返回 -1（由调用方决定是否重试，不写入去重表）。
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
    if HrGuard().should_skip(SKIP_PATH_SYNC_DELETE, target_downloader, target_hash):
        logger.info(f"【PT下载中心:失败清理】H&R 保护跳过转种目标 {target_downloader} / {target_hash}")
        return 0
    try:
        service = get_downloader_services(name_filters=[target_downloader]).get(target_downloader)
        instance = getattr(service, "instance", None)
        if instance is None or instance.is_inactive():
            logger.warning(f"【PT下载中心:失败清理】转种目标下载器 {target_downloader} 不可用，跳过删除 {target_hash}")
            return 0
    except Exception as err:
        logger.error(f"【PT下载中心:失败清理】查询转种目标下载器 {target_downloader} 失败：{err}")
        return 0
    try:
        if instance.delete_torrents(delete_file=True, ids=[target_hash]) is False:
            logger.error(f"【PT下载中心:失败清理】删除转种目标失败：{target_downloader} / {target_hash}")
            return 0
    except Exception as err:
        logger.error(f"【PT下载中心:失败清理】删除转种目标异常：{target_downloader} / {target_hash} {err}")
        return 0
    logger.info(f"【PT下载中心:失败清理】已删除转种目标 {target_downloader} / {target_hash}")
    return 1


def _find_transfer_record_any_source(plugin, source_hash: str):
    """旧键为空时，在全部配置下载器里查源记录（找不到返回 (None, "")）。"""
    names = set()
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
    for name in sorted(names):
        record = plugin.get_data(f"{name}-{source_hash}") or {}
        if isinstance(record, dict) and record.get("to_download"):
            return record, name
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
