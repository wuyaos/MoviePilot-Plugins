# input: 插件 state (history, user_*, last_*) | output: Vuetify JSON 详情页 | pos: 面板构建

from __future__ import annotations

import datetime as dt
from typing import Any


def build_page(state: dict[str, Any], keepalive_days: int,
               dl_torrents: list[dict] | None = None) -> list[dict]:
    """构建插件详情页"""
    result = []
    # 1. 用户信息（无数据时显示占位）
    user_row = _build_user_bar(state)
    result.append(user_row or {"component": "VAlert", "props": {
        "type": "info", "variant": "tonal", "density": "compact", "class": "mb-3",
        "text": "用户信息：等待首次运行后从站点获取（需 CookieCloud 配置 AnimeZ 域名）",
    }})
    # 2. 保活状态
    result.append(_build_status_row(state, keepalive_days))
    # 3. 下载器种子（始终显示）
    result.append(_build_dl_table(dl_torrents or []))
    # 4. 运行记录
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
    # 时间值（含"月日 HH:MM"）拆为两行显示
    if "月" in value and " " in value:
        date_part, time_part = value.split(" ", 1)
        value_node = {"component": "div", "content": [
            {"component": "div", "props": {"class": "text-subtitle-2 font-weight-bold"},
             "text": date_part},
            {"component": "div", "props": {"class": "text-caption text-grey"},
             "text": time_part},
        ]}
    else:
        value_node = {"component": "div",
                      "props": {"class": "text-subtitle-1 font-weight-bold"},
                      "text": _truncate(value or "无", 20)}
    return {"component": "VCol", "props": {"cols": 6, "md": cols}, "content": [{
        "component": "VCard", "props": {"variant": "tonal", "color": color, "density": "compact"},
        "content": [{"component": "VCardText", "props": {"class": "pa-2"},
            "content": [
                {"component": "div", "props": {"class": "d-flex align-center mb-1"},
                 "content": [
                    {"component": "VIcon", "props": {
                        "icon": icon, "size": "x-small", "class": "mr-1"}},
                    {"component": "span", "props": {"class": "text-caption"}, "text": label},
                ]},
                value_node,
            ]}],
    }]}


def _build_dl_table(torrents: list[dict]) -> dict:
    """下载器中 AZ 分类的种子"""
    def _sz(b: int) -> str:
        for u in ["B", "KB", "MB", "GB", "TB"]:
            if b < 1024: return f"{b:.1f}{u}" if u != "B" else f"{b}B"
            b /= 1024
        return str(b)
    if not torrents:
        return {"component": "VAlert", "props": {
            "type": "info", "variant": "tonal", "density": "compact", "class": "mt-2 mb-2",
            "text": "下载器种子：暂无 AnimeZ 分类种子",
        }}
    rows = []
    for t in torrents[:10]:
        pct = f"{t.get('progress', 0) * 100:.0f}%"
        rows.append({"component": "tr", "content": [
            {"component": "td", "props": {"class": "text-caption"}, "text": _truncate(t.get("name", ""), 50)},
            {"component": "td", "props": {"class": "text-caption"}, "text": _sz(t.get("size", 0))},
            {"component": "td", "props": {"class": "text-caption"}, "text": pct},
            {"component": "td", "props": {"class": "text-caption"}, "text": str(t.get("state", ""))},
        ]})
    return {"component": "VCard", "props": {"variant": "flat", "class": "mt-2 mb-2"}, "content": [
        {"component": "VCardTitle", "props": {"class": "text-subtitle-2 pa-3"},
         "text": f"下载器种子 ({len(torrents)})"},
        {"component": "VTable", "props": {"density": "compact"}, "content": [
            {"component": "thead", "content": [{"component": "tr", "content": [
                {"component": "th", "props": {"class": "text-caption"}, "text": c}
                for c in ["名称", "体积", "进度", "状态"]
            ]}]},
            {"component": "tbody", "content": rows},
        ]},
    ]}


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
