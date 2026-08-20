"""PTNewsWatch 紧凑来源状态与资讯列表数据页。"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from ..core.source_instances import build_source_instances
from ..core.source_registry import SOURCE_BY_ID, SOURCES
from ..core.url_utils import safe_content_link

_URL_LINE = re.compile(r"^(?P<prefix>.*?)(?P<url>https?://\S+)$", re.I)


def build_page(state: dict, timezone_name: str, *, config) -> list[dict]:
    state = state or {}
    last_run = state.get("last_run") or {}
    sources_state = state.get("sources") or {}
    instances = build_source_instances(config, include_disabled=True)
    enabled = [item for item in instances if config.source_enabled(item.base_id)]
    normal = sum(1 for item in enabled if _status(sources_state.get(item.source_id))[0] == "正常")
    failed = sum(1 for item in enabled if _status(sources_state.get(item.source_id))[0] == "异常")
    pending = max(0, len(enabled) - normal - failed)
    recent = sorted(state.get("recent_entries") or [], key=lambda item: item.get("published_at", ""), reverse=True)
    return [
        _overview(last_run, len(enabled), normal, failed, pending, timezone_name),
        _source_health(config, instances, sources_state, timezone_name),
        _timeline(recent, timezone_name),
    ]


def _overview(last_run, enabled, normal, failed, pending, tz):
    cells = [
        ("最近检查", _time(last_run.get("time"), tz)),
        ("启用来源", str(enabled)),
        ("正常", str(normal)),
        ("本轮新增", str(last_run.get("new_count", 0))),
        ("异常/待检查", f"{failed}/{pending}"),
        ("通知", "已发送" if last_run.get("notification_sent") else ("未发送" if last_run else "—")),
    ]
    return {"component": "VCard", "props": {"variant": "outlined", "class": "mb-3"}, "content": [
        {"component": "VCardTitle", "props": {"class": "text-subtitle-1 py-2"}, "text": "运行概览"},
        {"component": "VDivider"},
        {"component": "VCardText", "props": {"class": "pa-2"}, "content": [
            {"component": "VRow", "props": {"class": "ma-0"}, "content": [
                {"component": "VCol", "props": {"cols": 6, "sm": 4, "md": "auto", "class": "pa-1 flex-grow-1"}, "content": [
                    {"component": "div", "props": {
                        "class": "rounded border pa-2 text-center h-100",
                        "style": "background: rgb(var(--v-theme-surface));",
                    }, "content": [
                        {"component": "div", "props": {"class": "text-subtitle-2 font-weight-bold"}, "text": value},
                        {"component": "div", "props": {"class": "text-caption text-medium-emphasis"}, "text": label},
                    ]},
                ]} for label, value in cells
            ]},
        ]},
    ]}


def _source_health(config, instances, source_state, tz):
    cards = []
    for source in SOURCES:
        source_instances = [item for item in instances if item.base_id == source.source_id]
        enabled = config.source_enabled(source.source_id)
        rows = []
        for index, instance in enumerate(source_instances, 1):
            status = source_state.get(instance.source_id) or {}
            label, color = ("已禁用", "grey") if not enabled else _status(status)
            detail = _instance_label(instance.url, index)
            rows.append({"component": "div", "props": {"class": "py-1"}, "content": [
                {"component": "div", "props": {"class": "d-flex align-center ga-2"}, "content": [
                    {"component": "VIcon", "props": {"icon": "mdi-circle", "size": 9, "color": color}},
                    {"component": "span", "props": {"class": "text-body-2 text-truncate"}, "text": detail},
                    {"component": "VSpacer"},
                    {"component": "VChip", "props": {"size": "x-small", "color": color, "variant": "tonal"}, "text": label},
                ]},
                {"component": "div", "props": {"class": "text-caption text-medium-emphasis ml-4"}, "text": (
                    f"最近成功 {_time(status.get('last_success_at'), tz)} · "
                    f"新增 {status.get('last_new_count', 0)} · 已见 {len(status.get('seen_entry_ids') or [])}"
                )},
                {"component": "div", "props": {"class": "text-caption text-error ml-4"}, "text": str(status.get("last_error") or "")}
                if status.get("last_error") else {"component": "div"},
            ]})
        if not rows:
            rows = [{"component": "div", "props": {"class": "text-caption text-medium-emphasis"}, "text": "未配置来源地址"}]
        cards.append({"component": "VCol", "props": {"cols": 12, "md": 6, "class": "d-flex"}, "content": [
            {"component": "VCard", "props": {"variant": "outlined", "class": "h-100 w-100"}, "content": [
                {"component": "VCardTitle", "props": {"class": "text-subtitle-2 d-flex align-center py-2"}, "content": [
                    {"component": "span", "text": source.title},
                    {"component": "VSpacer"},
                    {"component": "span", "props": {"class": "text-caption text-medium-emphasis"}, "text": f"{len(source_instances)}个地址"},
                ]},
                {"component": "VDivider"},
                {"component": "VCardText", "props": {"class": "pa-2"}, "content": rows},
            ]},
        ]})
    return {"component": "VCard", "props": {"variant": "outlined", "class": "mb-3"}, "content": [
        {"component": "VCardTitle", "props": {"class": "text-subtitle-1 py-2"}, "text": "来源状态"},
        {"component": "VDivider"},
        {"component": "VCardText", "props": {"class": "pa-2"}, "content": [{"component": "VRow", "content": cards}]},
    ]}


def _timeline(entries, tz):
    items = []
    for entry in entries:
        base_id = entry.get("base_source_id") or str(entry.get("source_id") or "").split("#", 1)[0]
        source = SOURCE_BY_ID.get(base_id)
        source_title = entry.get("source_title") or (source.title if source else base_id)
        title_node = _link_or_text(entry.get("title") or "无标题", entry.get("link") or "")
        items.append({"component": "VListItem", "props": {"class": "px-0 py-1"}, "content": [
            {"component": "VCard", "props": {"variant": "flat", "class": "w-100 rounded-0 border-b"}, "content": [
                {"component": "VCardText", "props": {"class": "pa-3"}, "content": [
                    {"component": "div", "props": {"class": "d-flex align-center flex-wrap ga-1 mb-1"}, "content": [
                        {"component": "VChip", "props": {"size": "x-small", "variant": "tonal", "color": "primary"}, "text": source_title},
                        {"component": "span", "props": {"class": "text-medium-emphasis"}, "text": "—"},
                        title_node,
                        {"component": "VSpacer"},
                        {"component": "span", "props": {"class": "text-caption text-medium-emphasis"}, "text": _time(entry.get("published_at"), tz)},
                    ]},
                    {"component": "div", "props": {"class": "text-caption text-medium-emphasis mb-2"}, "text": str(entry.get("author") or "")}
                    if entry.get("author") else {"component": "div"},
                    *_content_nodes(entry.get("content") or ""),
                ]},
            ]},
        ]})
    content = [{"component": "VAlert", "props": {"type": "info", "variant": "tonal", "density": "compact", "text": "暂无资讯。"}}] if not items else [
        {"component": "VList", "props": {"density": "compact", "class": "pa-0"}, "content": items}
    ]
    return {"component": "VCard", "props": {"variant": "outlined", "class": "mb-3"}, "content": [
        {"component": "VCardTitle", "props": {"class": "text-subtitle-1 py-2 d-flex align-center"}, "content": [
            {"component": "span", "text": "资讯时间轴"},
            {"component": "VSpacer"},
            {"component": "VChip", "props": {"size": "x-small", "variant": "tonal", "color": "primary"}, "text": f"{len(entries)} 条"},
        ]},
        {"component": "VDivider"},
        {"component": "VCardText", "props": {
            "class": "pa-2", "style": "max-height: 640px; overflow-y: auto; overscroll-behavior: contain;",
        }, "content": content},
    ]}


def _content_nodes(content: str) -> list[dict]:
    nodes = []
    for line in str(content or "").splitlines()[:80]:
        stripped = line.strip()
        if stripped.startswith("> "):
            nodes.append({"component": "div", "props": {
                "class": "text-body-2 text-medium-emphasis pl-3 py-1 border-s",
                "style": "line-height: 1.65;",
            }, "text": stripped[2:].strip()})
            continue
        if stripped.startswith("- "):
            nodes.append({"component": "div", "props": {
                "class": "text-body-2 pl-2", "style": "line-height: 1.65;",
            }, "text": f"• {stripped[2:].strip()}"})
            continue
        match = _URL_LINE.match(stripped)
        if match and safe_content_link(match.group("url")):
            row = []
            if match.group("prefix").strip():
                row.append({"component": "span", "props": {"class": "text-body-2"}, "text": match.group("prefix").strip()})
            row.append(_link_or_text(match.group("url"), match.group("url"), compact=True))
            nodes.append({"component": "div", "props": {"class": "d-flex align-center flex-wrap ga-1"}, "content": row})
        else:
            nodes.append({"component": "div", "props": {
                "class": "text-body-2", "style": "white-space: pre-wrap; line-height: 1.65; min-height: 0.5rem;",
            }, "text": line})
    return nodes


def _link_or_text(title: str, url: str, compact: bool = False) -> dict:
    link = safe_content_link(url)
    title_class = "text-body-2" if compact else "text-subtitle-1 font-weight-medium"
    if not link:
        return {"component": "span", "props": {"class": title_class}, "text": title}
    return {"component": "VBtn", "props": {
        "href": link, "target": "_blank", "rel": "noopener noreferrer",
        "variant": "text", "size": "small" if compact else "default",
        "class": f"{title_class} text-none px-1",
        "density": "compact" if compact else "default",
        "style": "height: auto; white-space: normal; word-break: break-word; text-align: left;",
    }, "text": title}


def _status(status):
    if status and status.get("last_error"):
        return "异常", "error"
    if status and status.get("last_success_at"):
        return "正常", "success"
    return "待检查", "warning"


def _instance_label(url: str, index: int) -> str:
    from urllib.parse import parse_qs, urlsplit
    parsed = urlsplit(url)
    query = parse_qs(parsed.query)
    topic = (query.get("topicid") or [""])[0]
    return f"topicid={topic}" if topic else f"地址 {index}"


def _time(value, timezone_name):
    if not value:
        return "—"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(ZoneInfo(timezone_name)).strftime("%m-%d %H:%M")
    except Exception:
        return str(value)[:16]
