"""MoviePilot 小型状态存储：去重、流量快照、完成记录和运行历史。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

try:
    from app.core.config import settings as _mp_settings
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo(getattr(_mp_settings, "TZ", "Asia/Shanghai"))
except Exception:
    _TZ = None

from .models import AccountSnapshot, BakaBTTorrent


MAX_HISTORY = 20
MAX_DETAIL_HISTORY = 500


def default_state() -> dict[str, Any]:
    return {
        "account": {
            "uploaded_mb": None,
            "downloaded_mb": None,
            "ratio": "",
            "updated_at": "",
        },
        "qb": {
            "uploaded_mb": 0.0,
            "downloaded_mb": 0.0,
            "downloading_count": 0,
            "max_downloading": 0,
            "updated_at": "",
        },
        "added": {},
        # 已解析详情页元数据，仅当天复用；跨日自动重新解析 Today 种子。
        "detail_cache_date": "",
        "detail_history": {},
        "completed_hashes": [],
        "last_run": {},
        "history": [],
    }


def normalize_state(raw: Any) -> dict[str, Any]:
    """向后兼容地补全缺失字段，丢弃格式明显错误的历史数据。"""
    state = default_state()
    if not isinstance(raw, dict):
        return state

    for key in ("account", "qb", "added", "last_run"):
        if isinstance(raw.get(key), dict):
            state[key].update(deepcopy(raw[key]))
    state["detail_cache_date"] = str(raw.get("detail_cache_date") or "")
    if isinstance(raw.get("detail_history"), dict):
        entries = [
            (str(torrent_id), deepcopy(detail))
            for torrent_id, detail in raw["detail_history"].items()
            if torrent_id and isinstance(detail, dict)
        ]
        # 保留最近解析的详情，控制 PluginData 体积。
        entries.sort(key=lambda item: str(item[1].get("parsed_at") or ""), reverse=True)
        state["detail_history"] = dict(entries[:MAX_DETAIL_HISTORY])

    if isinstance(raw.get("completed_hashes"), list):
        state["completed_hashes"] = list(dict.fromkeys(
            str(value).lower() for value in raw["completed_hashes"] if value
        ))
    if isinstance(raw.get("history"), list):
        state["history"] = [entry for entry in raw["history"] if isinstance(entry, dict)][-MAX_HISTORY:]
    return state


def was_added(state: dict[str, Any], torrent_id: str) -> bool:
    return str(torrent_id) in state.get("added", {})


def remember_added(state: dict[str, Any], item: BakaBTTorrent, infohash: str) -> None:
    state.setdefault("added", {})[str(item.torrent_id)] = {
        "title": item.title,
        "infohash": infohash.lower(),
        "added_at": utc_now(),
    }


def reset_detail_cache_for_day(state: dict[str, Any], now: datetime) -> None:
    """按当前本地日期隔离详情缓存，跨日重新解析 Today 种子。"""
    cache_date = now.astimezone(_TZ).date().isoformat() if _TZ else now.astimezone().date().isoformat()
    if state.get("detail_cache_date") != cache_date:
        state["detail_cache_date"] = cache_date
        state["detail_history"] = {}


def restore_detail(state: dict[str, Any], item: BakaBTTorrent) -> bool:
    """将历史详情页元数据恢复到浏览页种子；返回是否命中有效缓存。"""
    detail = (state.get("detail_history") or {}).get(str(item.torrent_id))
    if not isinstance(detail, dict):
        return False
    published_text = detail.get("published_at")
    if not published_text:
        return False
    try:
        published_at = datetime.fromisoformat(str(published_text).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    item.published_at = published_at
    item.is_freeleech = bool(detail.get("is_freeleech", item.is_freeleech))
    item.download_url = str(detail.get("download_url") or "") or None
    item.infohash = str(detail.get("infohash") or "") or None
    return True


def remember_detail(state: dict[str, Any], item: BakaBTTorrent) -> None:
    """持久化详情页精确发布时间及下载元数据。"""
    if item.published_at is None:
        return
    history = state.setdefault("detail_history", {})
    history[str(item.torrent_id)] = {
        "title": item.title,
        "published_at": item.published_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "is_freeleech": bool(item.is_freeleech),
        "download_url": item.download_url or "",
        "infohash": item.infohash or "",
        "parsed_at": utc_now(),
    }
    if len(history) > MAX_DETAIL_HISTORY:
        oldest = sorted(history, key=lambda key: str(history[key].get("parsed_at") or ""))
        for torrent_id in oldest[:len(history) - MAX_DETAIL_HISTORY]:
            history.pop(torrent_id, None)


def completed_hashes(state: dict[str, Any]) -> set[str]:
    return {str(value).lower() for value in state.get("completed_hashes", []) if value}


def remember_completed(state: dict[str, Any], hashes: set[str]) -> None:
    known = completed_hashes(state)
    known.update(value.lower() for value in hashes if value)
    state["completed_hashes"] = sorted(known)


def update_account(state: dict[str, Any], snapshot: AccountSnapshot) -> None:
    state["account"] = {
        "uploaded_mb": snapshot.uploaded_mb,
        "downloaded_mb": snapshot.downloaded_mb,
        "ratio": snapshot.ratio,
        "updated_at": utc_now(),
    }


def update_qb(
    state: dict[str, Any], *, uploaded_mb: float, downloaded_mb: float,
    downloading_count: int, max_downloading: int,
) -> None:
    state["qb"] = {
        "uploaded_mb": round(max(0.0, uploaded_mb), 2),
        "downloaded_mb": round(max(0.0, downloaded_mb), 2),
        "downloading_count": max(0, int(downloading_count)),
        "max_downloading": max(0, int(max_downloading)),
        "updated_at": utc_now(),
    }


def record_run(state: dict[str, Any], event: dict[str, Any]) -> None:
    """写入最近一轮与日志表，最多保留 MAX_HISTORY 条。"""
    normalized = {
        "time": event.get("time") or utc_now(),
        "status": str(event.get("status") or "unknown"),
        "torrent": str(event.get("torrent") or "-"),
        "push": str(event.get("push") or "未推送"),
        "detail": str(event.get("detail") or ""),
    }
    state["last_run"] = normalized
    history = list(state.get("history") or [])
    history.append(normalized)
    state["history"] = history[-MAX_HISTORY:]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
