"""MoviePilot 小型状态存储：去重、流量快照、完成记录和运行历史。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from .models import AccountSnapshot, BakaBTTorrent


MAX_HISTORY = 20


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
