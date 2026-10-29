"""重命名补刀失败归档服务实现。"""

from __future__ import annotations

from datetime import datetime, date
from copy import deepcopy
from functools import wraps
from threading import RLock

from app.sdk.logging import logger
from ...model.state import RENAME_RECORDS_KEY, RENAME_RETRY_STATE_KEY

_LOCK_INIT = RLock()


def serialized_rename_state(func):
    """为同一插件实例的归档与历史读改写提供可重入锁。"""
    @wraps(func)
    def locked(plugin, *args, **kwargs):
        """持有实例锁执行完整读改写，允许归档和历史互相调用。"""
        with _LOCK_INIT:
            lock = getattr(plugin, "_rename_state_lock", None)
            if lock is None:
                lock = RLock()
                plugin._rename_state_lock = lock
        with lock:
            return func(plugin, *args, **kwargs)
    return locked


RETRY_STATE_KEY = RENAME_RETRY_STATE_KEY
DEFAULT_ARCHIVE_THRESHOLD = 3

FAILURE_CATEGORY_LABELS = {
    "NO_TRUSTED_SOURCE": "原始发布名无可信候选",
    "LOW_CONFIDENCE_SOURCE": "原始名候选置信度过低",
    "META_PARSE_FAILED": "元数据解析失败",
    "MEDIA_RECOGNIZE_FAILED": "媒体识别失败",
    "FORMAT_EMPTY": "命名模板结果为空",
    "DOWNLOADER_UNAVAILABLE": "目标下载器不可用",
    "TASK_NOT_FOUND": "下载器任务不存在",
    "HASH_MISSING": "种子 hash 缺失",
    "RENAME_API_FAILED": "下载器重命名失败",
    "TAG_FAILED": "站点标签处理失败",
    "EXCLUDED_BY_RULE": "命中排除规则",
    "UNKNOWN_ERROR": "未归类异常",
}


def now_text() -> str:
    """返回统一的状态时间字符串。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log_rename_failure_state(item: dict, reason_text: str) -> None:
    """输出补刀失败分类日志。"""
    logger.warning(
        "【PT下载中心:重命名】hash=%s category=%s label=%s count=%s archived=%s reason=%s",
        item.get("hash", ""),
        item.get("category", ""),
        item.get("category_label", ""),
        item.get("fail_count", 0),
        bool(item.get("archived")),
        reason_text,
    )


def classify_rename_failure(reason: str = "") -> str:
    """根据失败原因文本归类补刀失败。"""
    text = str(reason or "")
    if "原始发布名污染" in text or "无法可靠补刀" in text or "无可信候选" in text:
        return "NO_TRUSTED_SOURCE"
    if "置信度" in text:
        return "LOW_CONFIDENCE_SOURCE"
    if "元数据" in text:
        return "META_PARSE_FAILED"
    if "媒体识别" in text:
        return "MEDIA_RECOGNIZE_FAILED"
    if "格式化" in text or "为空" in text:
        return "FORMAT_EMPTY"
    if "下载器不可用" in text:
        return "DOWNLOADER_UNAVAILABLE"
    if "未在目标下载器找到" in text or "任务不存在" in text:
        return "TASK_NOT_FOUND"
    if "无 hash" in text or "hash 缺失" in text:
        return "HASH_MISSING"
    if "站点标签" in text:
        return "TAG_FAILED"
    if "排除" in text:
        return "EXCLUDED_BY_RULE"
    if "重命名" in text or "API" in text:
        return "RENAME_API_FAILED"
    return "UNKNOWN_ERROR"


@serialized_rename_state
def get_rename_retry_state(plugin) -> dict:
    """读取补刀失败状态。"""
    state = read_state(plugin, RETRY_STATE_KEY)
    state = state if isinstance(state, dict) else {}
    if limit_archive_display(state):
        write_state(plugin, RETRY_STATE_KEY, state)
    return state


@serialized_rename_state
def save_rename_retry_state(plugin, state: dict) -> None:
    """保存补刀失败状态。"""
    limit_archive_display(state)
    write_state(plugin, RETRY_STATE_KEY, state or {})


def is_rename_archived(plugin, torrent_hash: str) -> bool:
    """判断种子是否已归档，不再参与自动补刀。"""
    hash_text = str(torrent_hash or "").strip()
    if not hash_text:
        return False
    item = get_rename_retry_state(plugin).get(hash_text) or {}
    return bool(item.get("archived"))


@serialized_rename_state
def clear_rename_retry_state(plugin, torrent_hash: str) -> None:
    """清理指定种子的补刀失败状态。"""
    hash_text = str(torrent_hash or "").strip()
    if not hash_text:
        return
    state = get_rename_retry_state(plugin)
    if hash_text in state:
        del state[hash_text]
        save_rename_retry_state(plugin, state)


@serialized_rename_state
def record_rename_failure(
    plugin,
    torrent_hash: str,
    torrent_name: str,
    category: str = "",
    reason: str = "",
    threshold: int = DEFAULT_ARCHIVE_THRESHOLD,
) -> dict:
    """记录一次补刀失败，达到阈值后自动归档。"""
    hash_text = str(torrent_hash or "").strip()
    if not hash_text:
        return {}
    reason_text = str(reason or "未知原因")
    category_text = str(category or "").strip() or classify_rename_failure(reason_text)
    threshold = max(1, int(threshold or DEFAULT_ARCHIVE_THRESHOLD))
    state = get_rename_retry_state(plugin)
    item = dict(state.get(hash_text) or {})
    fail_count = int(item.get("fail_count") or 0) + 1
    archived = bool(item.get("archived")) or fail_count >= threshold
    item.update({
        "hash": hash_text,
        "name": str(torrent_name or item.get("name") or ""),
        "category": category_text,
        "category_label": FAILURE_CATEGORY_LABELS.get(category_text, "未归类异常"),
        "reason": reason_text,
        "fail_count": fail_count,
        "last_failed_at": now_text(),
        "archived": archived,
    })
    if archived:
        item["archived_at"] = item.get("archived_at") or now_text()
        item["archive_reason"] = f"连续补刀失败 {fail_count} 次：{reason_text}"
    state[hash_text] = item
    save_rename_retry_state(plugin, state)
    record_daily_result(plugin, False)
    log_rename_failure_state(item, reason_text)
    return item


@serialized_rename_state
def restore_rename_archive(plugin, torrent_hash: str) -> dict:
    """从归档中恢复指定种子，使其重新参与补刀。"""
    hash_text = str(torrent_hash or "").strip()
    if not hash_text:
        return {"code": 1, "msg": "缺少 hash 参数", "hash": ""}
    state = get_rename_retry_state(plugin)
    item = dict(state.get(hash_text) or {})
    if not item:
        return {"code": 1, "msg": "归档记录不存在", "hash": hash_text}
    restored_at = now_text()
    item.update({
        "archived": False,
        "fail_count": 0,
        "restored_at": restored_at,
    })
    item.pop("archived_at", None)
    item.pop("display_hidden", None)
    state[hash_text] = item
    save_rename_retry_state(plugin, state)

    records = plugin.get_data(RENAME_RECORDS_KEY) or {}
    record = records.get(hash_text)
    if isinstance(record, dict):
        record["time"] = restored_at
        plugin.save_data(RENAME_RECORDS_KEY, records)
    return {"code": 0, "msg": "已恢复，后续将重新参与补刀", "hash": hash_text}


@serialized_rename_state
def delete_rename_archive(plugin, torrent_hash: str) -> dict:
    """仅删除归档展示，不解除自动补刀排除状态。"""
    hash_text = str(torrent_hash or "").strip()
    if not hash_text:
        return {"code": 1, "msg": "缺少 hash 参数", "hash": ""}
    state = get_rename_retry_state(plugin)
    if hash_text not in state:
        return {"code": 1, "msg": "归档记录不存在", "hash": hash_text}
    state[hash_text]["display_hidden"] = True
    save_rename_retry_state(plugin, state)
    return {"code": 0, "msg": "已删除归档记录", "hash": hash_text}


@serialized_rename_state
def clear_rename_archive(plugin) -> dict:
    """仅清归档展示；覆盖旧决策 C，依据规格 §7 归档条款 :287。

    保留 archived 安全依据，只有显式恢复才重新允许自动补刀。
    """
    state = get_rename_retry_state(plugin)
    archived_hashes = [
        hash_text
        for hash_text, item in state.items()
        if isinstance(item, dict) and item.get("archived") and not item.get("display_hidden")
    ]
    for hash_text in archived_hashes:
        state[hash_text]["display_hidden"] = True
    if archived_hashes:
        save_rename_retry_state(plugin, state)
    return {"code": 0, "msg": f"已清理 {len(archived_hashes)} 条归档记录", "removed": len(archived_hashes)}


@serialized_rename_state
def list_rename_archive(plugin, page: int = 1, page_size: int = 15) -> dict:
    """返回补刀归档记录分页。"""
    state = get_rename_retry_state(plugin)
    all_items = archive_display_items(state)
    page = max(1, int(page or 1))
    page_size = max(1, int(page_size or 15))
    total = len(all_items)
    start = (page - 1) * page_size
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
        "items": all_items[start:start + page_size],
    }


@serialized_rename_state
def rename_archive_stats(plugin) -> dict:
    """统计补刀失败状态，用于总览和诊断。"""
    state = get_rename_retry_state(plugin)
    items = [item for item in state.values() if isinstance(item, dict)]
    archived = [item for item in items if item.get("archived")]
    visible_archived = archive_display_items(state)
    active_failed = [item for item in items if not item.get("archived") and int(item.get("fail_count") or 0) > 0]
    category_counts = {}
    for item in archived:
        category = item.get("category") or "UNKNOWN_ERROR"
        category_counts[category] = category_counts.get(category, 0) + 1
    return {
        "total": len(items),
        "archived": len(archived),
        "active_failed": len(active_failed),
        "near_archive": sum(1 for item in active_failed if int(item.get("fail_count") or 0) >= DEFAULT_ARCHIVE_THRESHOLD - 1),
        "threshold": DEFAULT_ARCHIVE_THRESHOLD,
        "category_counts": category_counts,
        "recent_archived": visible_archived[:5],
    }


__all__ = (
    "clear_rename_retry_state",
    "delete_rename_archive",
    "is_rename_archived",
    "list_rename_archive",
    "record_rename_failure",
    "rename_archive_stats",
    "restore_rename_archive",
)


def archive_display_items(state: dict) -> list[dict]:
    """时间降序、hash 升序；缺失时间视为最旧，重载与插入顺序无关。"""
    items = [dict(item, hash=key) for key, item in state.items()
             if isinstance(item, dict) and item.get("archived") and not item.get("display_hidden")]
    items.sort(key=lambda item: str(item["hash"]))
    items.sort(key=lambda item: str(item.get("archived_at") or item.get("last_failed_at") or ""), reverse=True)
    return items


def limit_archive_display(state: dict) -> bool:
    """只裁展示记录，不删除不自动重试的安全依据。"""
    overflow = archive_display_items(state)[1000:]
    for item in overflow:
        state[item["hash"]]["display_hidden"] = True
    return bool(overflow)


DAILY_STATS_KEY = "rename_daily_stats"


def read_state(plugin, key):
    """批次内读到本轮尚未落盘的状态。"""
    batch = getattr(plugin, "_rename_write_batch", None)
    if isinstance(batch, dict) and key in batch:
        return deepcopy(batch[key])
    return deepcopy(plugin.get_data(key) or {})


def write_state(plugin, key, value):
    """在批次边界保存一次；单条操作立即保存。"""
    batch = getattr(plugin, "_rename_write_batch", None)
    if isinstance(batch, dict):
        batch[key] = deepcopy(value)
    else:
        plugin.save_data(key, value)


def rename_write_batch(func):
    """串行批次保证清理与执行不交错，异常出口也保留已有真实结果。"""
    @wraps(func)
    @serialized_rename_state
    def batched(plugin, *args, **kwargs):
        if isinstance(getattr(plugin, "_rename_write_batch", None), dict):
            return func(plugin, *args, **kwargs)
        plugin._rename_write_batch = {}
        try:
            return func(plugin, *args, **kwargs)
        finally:
            batch = plugin._rename_write_batch
            plugin._rename_write_batch = None
            for key, value in batch.items():
                plugin.save_data(key, value)
    return batched


@serialized_rename_state
def today_stats(plugin):
    """只读投影；旧版本无计数不从历史时间猜测今日结果。"""
    state = read_state(plugin, DAILY_STATS_KEY)
    today = date.today().isoformat()
    if state.get("date") != today:
        return {"date": today, "today_success": 0, "today_failed": 0}
    return {"date": today, "today_success": int(state.get("today_success") or 0),
            "today_failed": int(state.get("today_failed") or 0)}


@serialized_rename_state
def record_daily_result(plugin, success):
    """在逐条真实结果出口计一次，不再从批次候选或汇总重复累计。"""
    state = today_stats(plugin)
    state["today_success" if success else "today_failed"] += 1
    write_state(plugin, DAILY_STATS_KEY, state)


@serialized_rename_state
def hide_rename_history(plugin) -> int:
    """清历史只设展示标记，仍保留原名与失败候选。"""
    records = read_state(plugin, RENAME_RECORDS_KEY)
    visible = [item for item in records.values() if isinstance(item, dict) and not item.get("history_hidden")]
    for item in visible:
        item["history_hidden"] = True
    if visible:
        write_state(plugin, RENAME_RECORDS_KEY, records)
    return len(visible)
