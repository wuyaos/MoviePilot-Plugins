# input: 插件 state (history, user_*, last_*) | output: Vuetify JSON 详情页 | pos: 面板构建

from __future__ import annotations

import datetime as dt
from typing import Any


def build_page(state: dict[str, Any], keepalive_days: int) -> list[dict]:
    """构建插件详情页"""
    result = []
    # 用户信息条（单卡片横排）
    user_row = _build_user_bar(state)
    if user_row:
        result.append(user_row)
    # 保活状态卡片
    result.append(_build_status_row(state, keepalive_days))
    # 运行记录表格
    result.append(_build_history_table(state))
    return result


def _build_user_bar(state: dict[str, Any]) -> dict | None:
    """用户信息横条（类似 AZ ratio-bar）"""
    fields = [
        ("upload", "mdi-arrow-up", "success"), ("download", "mdi-arrow-down", "warning"),
        ("ratio", "mdi-percent-circle", "info"), ("buffer", "mdi-database", "success"),
        ("seeds", "mdi-upload", "success"), ("leeches", "mdi-download", "warning"),
        ("bonus", "mdi-star", "amber"), ("hnr", "mdi-alert", "error"),
        ("reseed", "mdi-refresh", "grey"),
    ]
    chips = []
    for key, icon, color in fields:
        val = state.get(f"user_{key}", "")
        if not val:
            continue
        label = {"upload": "Up", "download": "Down", "ratio": "R", "buffer": "Buf",
                 "seeds": "S", "leeches": "L", "bonus": "BP", "hnr": "H&R",
                 "reseed": "Reseed"}.get(key, key)
        chips.append({"component": "VChip", "props": {
            "color": color, "size": "small", "variant": "tonal",
            "class": "mr-1 mb-1", "prepend-icon": icon,
        }, "text": f"{label}: {val}"})
    if not chips:
        return None
    return {"component": "VCard", "props": {"variant": "flat", "class": "mb-3 pa-3"},
            "content": [{"component": "div", "props": {
                "class": "d-flex flex-wrap align-center gap-1"}, "content": chips}]}


def _build_status_row(state: dict[str, Any], keepalive_days: int) -> dict:
    """保活状态 + 下载器状态（4列卡片）"""
    last_status = state.get("last_status", "未运行")
    color_map = {"success": "success", "skipped": "info",
                 "no_candidate": "warning", "failed": "error"}

    # 计算下次窗口
    next_window = "未知"
    last_s = state.get("last_success_at", "")
    if last_s:
        try:
            ts = dt.datetime.fromisoformat(last_s.replace("Z", "+00:00"))
            nxt = ts + dt.timedelta(days=keepalive_days)
            next_window = _fmt_time(nxt.isoformat())
        except ValueError:
            pass

    # 下载器状态
    dl_status = state.get("last_dl_status", "未知")

    return {"component": "VRow", "props": {"class": "mb-3"}, "content": [
        _tonal_card("当前状态", last_status, color_map.get(last_status, "grey"), "mdi-pulse", 3),
        _tonal_card("上次访问", _fmt_time(state.get("last_visit_at", "")), "primary", "mdi-web", 3),
        _tonal_card("上次下载", _fmt_time(last_s), "success", "mdi-download-circle", 3),
        _tonal_card("下次窗口", next_window, "info", "mdi-calendar-clock", 3),
    ]}


def _tonal_card(label: str, value: str, color: str, icon: str, cols: int) -> dict:
    return {"component": "VCol", "props": {"cols": 6, "md": cols}, "content": [{
        "component": "VCard", "props": {"variant": "tonal", "color": color},
        "content": [{"component": "VCardText", "props": {"class": "pa-3"},
            "content": [
                {"component": "div", "props": {"class": "d-flex align-center"},
                 "content": [
                    {"component": "VIcon", "props": {
                        "icon": icon, "size": "small", "class": "mr-2"}},
                    {"component": "span", "props": {"class": "text-caption"}, "text": label},
                ]},
                {"component": "div", "props": {"class": "text-subtitle-1 font-weight-bold mt-1"},
                 "text": _truncate(value or "无", 30)},
            ]}],
    }]}


def _build_history_table(state: dict[str, Any]) -> dict:
    """运行记录表格"""
    history = list(reversed(state.get("history", [])[-20:]))
    if not history:
        return {"component": "VAlert", "props": {
            "type": "info", "variant": "tonal", "text": "暂无运行记录", "class": "mt-2"}}
    rows = [_history_row(ev) for ev in history]
    return {"component": "VCard", "props": {"variant": "flat", "class": "mt-2"}, "content": [
        {"component": "VCardTitle", "props": {"class": "text-subtitle-2 pa-3"}, "text": "运行记录"},
        {"component": "VTable", "props": {"density": "compact"}, "content": [
            {"component": "thead", "content": [{"component": "tr", "content": [
                {"component": "th", "props": {"class": "text-caption"}, "text": "时间"},
                {"component": "th", "props": {"class": "text-caption"}, "text": "状态"},
                {"component": "th", "props": {"class": "text-caption"}, "text": "详情"},
            ]}]},
            {"component": "tbody", "content": rows},
        ]},
    ]}


def _history_row(ev: dict[str, Any]) -> dict:
    status = ev.get("status", "")
    color_map = {"success": "success", "skipped": "info",
                 "no_candidate": "warning", "failed": "error"}
    # 拼接详情：种子名 | 体积 | 做种 | Free | 原因
    parts = []
    if ev.get("title"):
        parts.append(ev["title"])
    if ev.get("size"):
        parts.append(ev["size"])
    if ev.get("seeders") is not None:
        parts.append(f"S:{ev['seeders']}")
    if ev.get("free"):
        parts.append("Free")
    if ev.get("reason"):
        parts.append(ev["reason"])
    detail = " | ".join(parts) if parts else ""
    return {"component": "tr", "content": [
        {"component": "td", "props": {"class": "text-caption text-no-wrap"},
         "text": _fmt_time(ev.get("time", ""))},
        {"component": "td", "content": [{"component": "VChip", "props": {
            "color": color_map.get(status, "grey"), "size": "x-small", "variant": "flat",
        }, "text": status}]},
        {"component": "td", "props": {"class": "text-caption"},
         "text": _truncate(detail, 80)},
    ]}


def _fmt_time(iso_str: str) -> str:
    """ISO 时间 → 'M月D日 HH:MM'"""
    if not iso_str or iso_str == "无":
        return "无"
    try:
        ts = dt.datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        local = ts.astimezone()
        return f"{local.month}月{local.day}日 {local.strftime('%H:%M')}"
    except (ValueError, OSError):
        return iso_str[:16]


def _truncate(text: str, max_len: int) -> str:
    return text if len(text) <= max_len else text[:max_len - 1] + "…"


# --- Vuetify JSON 表单辅助（供 __init__.py get_form 使用） ---

def v_row(cols: list) -> dict:
    return {"component": "VRow", "content": cols}

def v_col(md: int, content: dict) -> dict:
    return {"component": "VCol", "props": {"cols": 12, "md": md}, "content": [content]}

def v_switch(model: str, label: str) -> dict:
    return {"component": "VSwitch", "props": {"model": model, "label": label}}

def v_select(model: str, label: str, items: list) -> dict:
    return {"component": "VSelect", "props": {"model": model, "label": label, "items": items}}

def v_text(model: str, label: str, placeholder: str = "", input_type: str = "") -> dict:
    props: dict = {"model": model, "label": label}
    if placeholder:
        props["placeholder"] = placeholder
    if input_type:
        props["type"] = input_type
    return {"component": "VTextField", "props": props}

def v_cron(model: str, label: str, placeholder: str = "") -> dict:
    props: dict = {"model": model, "label": label}
    if placeholder:
        props["placeholder"] = placeholder
    props["hint"] = "5位cron表达式，留空则每天9-23点随机执行一次"
    return {"component": "VCronField", "props": props}
