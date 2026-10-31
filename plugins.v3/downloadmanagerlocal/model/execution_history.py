"""展示历史（execution history）轻量存储、查询与清理。

为五个固定业务流提供共享的逐条展示历史能力；本模块不接入任何业务模块
（真实接线在后续包），也不依赖数据库、消息队列或宿主新表。

统一 record 结构（schema v1）：
  record_id      一次记录的唯一标识（不等同 torrent hash）
  module         所属流（白名单五流之一）
  trigger        触发来源（如「定时」「手动」「DownloadAdded」）
  occurred_at    Unix 秒（float）
  action         动作摘要
  result         终态：success/failed/skipped/observed
  reason         结果说明
  涉及种子追加：downloader_id / torrent_hash / name
  涉及站点追加：site

存储形态（model/state.py::EXECUTION_HISTORY_KEY）：
  {"schema_version": 1, "streams": {"<module>": [record, ...]}}
每条流独立裁剪到 HISTORY_MAX_ITEMS 条，超限从最旧（列表头部）裁掉。
"""

from __future__ import annotations

import copy
import uuid
from typing import Any

from app.sdk.logging import logger

from .state import (
    EXECUTION_HISTORY_KEY,
    EXECUTION_HISTORY_SCHEMA_VERSION,
    _HISTORY_LOCK,
)

HISTORY_STREAMS = ("autoremove", "failclean", "tag", "tag_cleanup", "upload_limit")
HISTORY_MAX_ITEMS = 1000
HISTORY_RESULT_VALUES = ("success", "failed", "skipped", "observed")
HISTORY_FILTERS = ("all", "success", "failed", "skipped", "observed")

_REQUIRED_KEYS = ("trigger", "occurred_at", "action", "result", "reason")
_OPTIONAL_KEYS = ("downloader_id", "torrent_hash", "name", "site")
_KNOWN_KEYS = {"record_id", "module", *_REQUIRED_KEYS, *_OPTIONAL_KEYS}


class HistoryRecordError(ValueError):
    """展示历史记录不合法（白名单外 module、非法 result、缺必需字段）。"""


def _ensure_module(module: str) -> str:
    if not isinstance(module, str) or module not in HISTORY_STREAMS:
        allowed = "、".join(HISTORY_STREAMS)
        raise HistoryRecordError(f"未知历史流：{module!r}（只支持 {allowed}）")
    return module


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _require_epoch(value: Any) -> float:
    """校验 occurred_at 是 Unix 秒数值：非法值显式报错，不静默归一化为 0。"""
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise HistoryRecordError(f"occurred_at 必须是 Unix 秒数值，收到 {value!r}") from error


def _normalize_result(result: Any) -> str:
    if result not in HISTORY_RESULT_VALUES:
        allowed = "、".join(HISTORY_RESULT_VALUES)
        raise HistoryRecordError(f"非法 result：{result!r}（只支持 {allowed}）")
    return result


def _normalize_record(module: str, record: dict) -> dict:
    if not isinstance(record, dict):
        raise HistoryRecordError("record 必须是字典")
    missing = [key for key in _REQUIRED_KEYS if key not in record]
    if missing:
        raise HistoryRecordError(f"记录缺少必需字段：{', '.join(missing)}")
    normalized: dict[str, Any] = {
        "record_id": str(record.get("record_id") or uuid.uuid4().hex),
        "module": module,
        "trigger": str(record.get("trigger") or ""),
        "occurred_at": _require_epoch(record.get("occurred_at")),
        "action": str(record.get("action") or ""),
        "result": _normalize_result(record.get("result")),
        "reason": str(record.get("reason") or ""),
    }
    for key in _OPTIONAL_KEYS:
        if record.get(key) is not None:
            normalized[key] = str(record[key])
    for key, value in record.items():
        if key not in normalized and key not in _KNOWN_KEYS:
            normalized[key] = copy.deepcopy(value)
    return normalized


def _load_payload(plugin) -> dict:
    """读取历史键并返回可安全改写的新字典（不改写插件内存态）。"""
    raw = plugin.get_data(EXECUTION_HISTORY_KEY)
    if not isinstance(raw, dict):
        return {"schema_version": EXECUTION_HISTORY_SCHEMA_VERSION, "streams": {}}
    payload = copy.deepcopy(raw)
    payload.setdefault("schema_version", EXECUTION_HISTORY_SCHEMA_VERSION)
    if not isinstance(payload.get("streams"), dict):
        payload["streams"] = {}
    return payload


def _extract_stream_items(raw: Any, module: str) -> list[dict]:
    if not isinstance(raw, dict):
        return []
    streams = raw.get("streams")
    if not isinstance(streams, dict):
        return []
    items = streams.get(module)
    if not isinstance(items, list):
        return []
    return [copy.deepcopy(item) for item in items if isinstance(item, dict)]


def append(plugin, module: str, record: dict) -> dict:
    """追加一条展示历史记录，超限裁掉最旧，返回写入记录（深拷贝）。

    保存失败（save_data 返回 False）记 warning 并继续，不抛异常：
    展示历史属旁路数据，写入失败不得影响已成功的业务动作；
    save_data 抛异常时原样上抛，由调用方决定是否记录。
    """
    module = _ensure_module(module)
    normalized = _normalize_record(module, record)
    with _HISTORY_LOCK:
        payload = _load_payload(plugin)
        streams = payload["streams"]
        items = streams.get(module)
        if not isinstance(items, list):
            items = []
            streams[module] = items
        items.append(normalized)
        if len(items) > HISTORY_MAX_ITEMS:
            del items[: len(items) - HISTORY_MAX_ITEMS]
        if plugin.save_data(EXECUTION_HISTORY_KEY, payload) is False:
            logger.warning(f"【PT下载中心】展示历史保存失败（save_data 返回 False）：{module} 本条仅在内存，重启后丢失")
    return copy.deepcopy(normalized)


def query(plugin, module: str, result_filter: str = "all") -> dict:
    """读取指定流、按 result 筛选并稳定排序后的结果。

    返回 {"initialized": bool, "items": [record...]}。initialized=False 表示历史键
    从未写入（升级后尚无新记录）；items 已深拷贝。排序：occurred_at 倒序，
    相同时间按 record_id 升序稳定次序。
    """
    module = _ensure_module(module)
    if result_filter != "all" and result_filter not in HISTORY_FILTERS:
        raise HistoryRecordError(f"未知 result_filter：{result_filter}")
    with _HISTORY_LOCK:
        raw = plugin.get_data(EXECUTION_HISTORY_KEY)
        initialized = isinstance(raw, dict)
        items = _extract_stream_items(raw, module)
    if result_filter != "all":
        items = [item for item in items if item.get("result") == result_filter]
    items.sort(key=lambda item: item.get("record_id") or "")
    items.sort(key=lambda item: _as_float(item.get("occurred_at")), reverse=True)
    return {"initialized": initialized, "items": items}


def clear(plugin, module: str) -> int:
    """清空指定流的新展示历史，返回清理条数；不影响业务/保护/恢复数据。"""
    module = _ensure_module(module)
    with _HISTORY_LOCK:
        payload = _load_payload(plugin)
        streams = payload["streams"]
        items = streams.get(module)
        removed = len(items) if isinstance(items, list) else 0
        streams[module] = []
        if plugin.save_data(EXECUTION_HISTORY_KEY, payload) is False:
            logger.warning(f"【PT下载中心】展示历史保存失败（save_data 返回 False）：{module} 清理未落盘")
    return removed
