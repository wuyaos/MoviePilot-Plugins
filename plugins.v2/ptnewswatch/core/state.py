"""PTNewsWatch PluginData 状态、来源水位、时间轴和运行历史。"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

from .models import ForumEntry, SourceFetchResult

MAX_SEEN_PER_SOURCE = 500
MAX_RECENT_ENTRIES = 500
MAX_RUN_HISTORY = 100


def default_state() -> dict[str, Any]:
    return {
        "sources": {},
        "recent_entries": [],
        "history": [],
        "last_run": {},
    }


def normalize_state(raw: Any) -> dict[str, Any]:
    state = default_state()
    if not isinstance(raw, dict):
        return state
    if isinstance(raw.get("sources"), dict):
        state["sources"] = deepcopy(raw["sources"])
        for source_state in state["sources"].values():
            if isinstance(source_state, dict) and isinstance(source_state.get("seen_entry_ids"), list):
                source_state["seen_entry_ids"] = list(dict.fromkeys(
                    str(value) for value in source_state["seen_entry_ids"] if value
                ))[-MAX_SEEN_PER_SOURCE:]
    if isinstance(raw.get("recent_entries"), list):
        state["recent_entries"] = [item for item in raw["recent_entries"] if isinstance(item, dict)][-MAX_RECENT_ENTRIES:]
    if isinstance(raw.get("history"), list):
        state["history"] = [item for item in raw["history"] if isinstance(item, dict)][-MAX_RUN_HISTORY:]
    if isinstance(raw.get("last_run"), dict):
        state["last_run"] = deepcopy(raw["last_run"])
    return state


def apply_source_result(
    state: dict[str, Any],
    result: SourceFetchResult,
    *,
    first_run_push_recent: bool,
) -> list[ForumEntry]:
    """成功时更新来源 seen；失败时严格不推进水位。"""
    source_state = state.setdefault("sources", {}).setdefault(result.source_id, {
        "initialized": False,
        "seen_entry_ids": [],
        "last_success_at": "",
        "last_error": "",
        "last_auth_status": "",
        "last_new_count": 0,
    })
    source_state["last_auth_status"] = result.auth_status
    if not result.success:
        source_state["last_error"] = result.error
        source_state["last_new_count"] = 0
        return []

    seen = list(dict.fromkeys(str(value) for value in source_state.get("seen_entry_ids", []) if value))
    seen_set = set(seen)
    ordered = sorted(result.entries, key=lambda item: item.published_at)
    if not source_state.get("initialized"):
        new_entries = ordered if first_run_push_recent else []
        source_state["initialized"] = True
    else:
        new_entries = [entry for entry in ordered if entry.entry_id not in seen_set]

    for entry in ordered:
        if entry.entry_id not in seen_set:
            seen.append(entry.entry_id)
            seen_set.add(entry.entry_id)
    source_state["seen_entry_ids"] = seen[-MAX_SEEN_PER_SOURCE:]
    source_state["last_success_at"] = _iso(result.fetched_at or datetime.now(timezone.utc))
    source_state["last_error"] = ""
    source_state["last_new_count"] = len(new_entries)
    return new_entries


def add_recent_entries(state: dict[str, Any], entries: list[ForumEntry], history_days: int) -> None:
    existing = {
        (item.get("source_id"), item.get("entry_id")): item
        for item in state.get("recent_entries", [])
        if isinstance(item, dict)
    }
    for entry in entries:
        existing[(entry.source_id, entry.entry_id)] = entry_to_dict(entry)
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, history_days))
    records = []
    for item in existing.values():
        try:
            published = datetime.fromisoformat(str(item.get("published_at", "")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if published >= cutoff:
            records.append(item)
    records.sort(key=lambda item: item.get("published_at", ""))
    state["recent_entries"] = records[-MAX_RECENT_ENTRIES:]


def record_run(state: dict[str, Any], record: dict[str, Any], history_days: int) -> None:
    normalized = dict(record)
    normalized.setdefault("time", _iso(datetime.now(timezone.utc)))
    state["last_run"] = normalized
    history = [item for item in state.get("history", []) if isinstance(item, dict)]
    history.append(normalized)
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, history_days))
    retained = []
    for item in history:
        try:
            timestamp = datetime.fromisoformat(str(item.get("time", "")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if timestamp >= cutoff:
            retained.append(item)
    state["history"] = retained[-MAX_RUN_HISTORY:]


def entry_to_dict(entry: ForumEntry) -> dict[str, Any]:
    return {
        "source_id": entry.source_id,
        "entry_id": entry.entry_id,
        "title": entry.title,
        "author": entry.author,
        "content": entry.content,
        "link": entry.link,
        "published_at": _iso(entry.published_at),
    }


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
