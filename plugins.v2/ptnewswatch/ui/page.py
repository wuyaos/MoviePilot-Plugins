"""PTNewsWatch 资讯时间轴数据页。"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from ..core.source_registry import SOURCE_BY_ID, SOURCES


def build_page(state: dict, timezone_name: str) -> list[dict]:
    state = state or {}
    last_run = state.get("last_run") or {}
    sources_state = state.get("sources") or {}
    recent = sorted(state.get("recent_entries") or [], key=lambda item: item.get("published_at", ""), reverse=True)
    success_count = sum(1 for source in SOURCES if not (sources_state.get(source.source_id) or {}).get("last_error"))
    failed_count = sum(1 for source in SOURCES if (sources_state.get(source.source_id) or {}).get("last_error"))
    return [
        _overview(last_run, success_count, failed_count, timezone_name),
        _source_health(sources_state, timezone_name),
        _timeline(recent, timezone_name),
        _history(state.get("history") or [], timezone_name),
    ]


def _overview(last_run, success_count, failed_count, tz):
    cards = [
        ("最近检查", _time(last_run.get("time"), tz)),
        ("本轮新增", str(last_run.get("new_count", 0))),
        ("正常来源", f"{success_count}/{len(SOURCES)}"),
        ("失败来源", str(failed_count)),
    ]
    return {"component": "VCard", "props": {"variant": "outlined", "class": "mb-3"}, "content": [
        {"component": "VCardTitle", "text": "运行概览"},
        {"component": "VDivider"},
        {"component": "VCardText", "content": [{"component": "VRow", "content": [
            {"component": "VCol", "props": {"cols": 6, "md": 3}, "content": [
                {"component": "VCard", "props": {"variant": "tonal", "class": "text-center pa-3 h-100"}, "content": [
                    {"component": "div", "props": {"class": "text-h6 font-weight-bold"}, "text": value},
                    {"component": "div", "props": {"class": "text-caption text-medium-emphasis"}, "text": label},
                ]},
            ]} for label, value in cards
        ]}]},
    ]}


def _source_health(source_state, tz):
    cards = []
    for source in SOURCES:
        status = source_state.get(source.source_id) or {}
        error = status.get("last_error") or ""
        cards.append({"component": "VCol", "props": {"cols": 12, "md": 6, "class": "d-flex"}, "content": [
            {"component": "VCard", "props": {"variant": "outlined", "class": "h-100 w-100"}, "content": [
                {"component": "VCardTitle", "props": {"class": "d-flex align-center"}, "content": [
                    {"component": "VIcon", "props": {"class": "mr-2", "color": "error" if error else "success"}, "text": "mdi-alert-circle" if error else "mdi-check-circle"},
                    {"component": "span", "text": source.title},
                ]},
                {"component": "VCardText", "content": [
                    {"component": "div", "text": f"认证：{status.get('last_auth_status') or '未检查'}"},
                    {"component": "div", "text": f"最近成功：{_time(status.get('last_success_at'), tz)}"},
                    {"component": "div", "text": f"本轮新增：{status.get('last_new_count', 0)} 条"},
                    {"component": "div", "text": f"已见消息：{len(status.get('seen_entry_ids') or [])} 条"},
                    {"component": "VAlert", "props": {"type": "error", "variant": "tonal", "density": "compact", "text": error}} if error else {"component": "div", "props": {"class": "text-success"}, "text": "状态：正常"},
                ]},
            ]},
        ]})
    return {"component": "VCard", "props": {"variant": "outlined", "class": "mb-3"}, "content": [
        {"component": "VCardTitle", "text": "来源状态"}, {"component": "VDivider"},
        {"component": "VCardText", "content": [{"component": "VRow", "content": cards}]},
    ]}


def _timeline(entries, tz):
    items = []
    for entry in entries:
        source = SOURCE_BY_ID.get(entry.get("source_id"))
        items.append({"component": "VTimelineItem", "props": {"dot-color": "primary", "size": "small"}, "content": [
            {"component": "VCard", "props": {"variant": "tonal", "class": "mb-2"}, "content": [
                {"component": "VCardTitle", "props": {"class": "text-subtitle-1"}, "text": entry.get("title") or "无标题"},
                {"component": "VCardSubtitle", "text": f"{source.title if source else entry.get('source_id')} · {_time(entry.get('published_at'), tz)}" + (f" · {entry.get('author')}" if entry.get("author") else "")},
                {"component": "VCardText", "text": _summary(entry.get("content") or "", 300)},
                {"component": "VCardActions", "content": [{"component": "VBtn", "props": {"href": entry.get("link"), "target": "_blank", "variant": "text"}, "text": "打开原帖"}]},
            ]},
        ]})
    content = [{"component": "VAlert", "props": {"type": "info", "variant": "tonal", "text": "暂无新增资讯。"}}] if not items else [
        {"component": "VTimeline", "props": {"density": "compact", "side": "end"}, "content": items}
    ]
    return {"component": "VCard", "props": {"variant": "outlined", "class": "mb-3"}, "content": [
        {"component": "VCardTitle", "text": "资讯时间轴"}, {"component": "VDivider"},
        {"component": "VCardText", "content": content},
    ]}


def _history(history, tz):
    rows = [{
        "time": _time(item.get("time"), tz),
        "success": item.get("success_sources", 0),
        "failed": item.get("failed_sources", 0),
        "new": item.get("new_count", 0),
        "notice": "已发送" if item.get("notification_sent") else "未发送",
        "error": "；".join(item.get("errors") or []),
    } for item in list(history)[-30:][::-1]]
    return {"component": "VCard", "props": {"variant": "outlined"}, "content": [
        {"component": "VCardTitle", "text": "运行历史"}, {"component": "VDivider"},
        {"component": "VCardText", "content": [{"component": "VDataTable", "props": {
            "headers": [
                {"title": "时间", "key": "time"}, {"title": "成功来源", "key": "success"},
                {"title": "失败来源", "key": "failed"}, {"title": "新增", "key": "new"},
                {"title": "通知", "key": "notice"}, {"title": "错误", "key": "error"},
            ],
            "items": rows, "items-per-page": 10, "density": "compact", "no-data-text": "暂无运行记录",
        }}]},
    ]}


def _time(value, timezone_name):
    if not value:
        return "—"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(ZoneInfo(timezone_name)).strftime("%m-%d %H:%M")
    except (TypeError, ValueError, OSError):
        return str(value)[:16]


def _summary(value, maximum):
    value = " ".join(str(value or "").split())
    return value if len(value) <= maximum else value[:maximum - 1] + "…"
