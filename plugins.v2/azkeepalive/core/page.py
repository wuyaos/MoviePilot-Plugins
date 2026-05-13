# input: 插件 state (history, user_*, last_*) | output: Vuetify JSON 详情页 | pos: 面板构建

from __future__ import annotations

import datetime as dt
from typing import Any

# AnimeZ H&R 所需做种时长查找表（GB → 小时），线性插值
_HNR_TABLE = [
    (0, 72), (1, 74), (5, 82), (10, 92), (15, 102), (20, 112),
    (25, 122), (30, 132), (35, 142), (40, 152), (45, 162), (50, 172),
    (60, 190), (70, 206), (80, 219), (90, 231), (100, 241),
    (125, 264), (150, 282), (175, 297), (200, 311), (225, 322),
    (250, 333), (275, 342), (300, 351), (400, 380), (500, 402),
    (600, 420), (700, 436), (800, 449), (900, 461), (1000, 472),
]


def _hnr_req(size_bytes: int) -> int:
    """根据 AnimeZ H&R 规则，按体积插值计算所需做种时长（小时）"""
    gb = size_bytes / 1073741824
    for i in range(len(_HNR_TABLE) - 1):
        s0, h0 = _HNR_TABLE[i]
        s1, h1 = _HNR_TABLE[i + 1]
        if s0 <= gb <= s1:
            return round(h0 + (gb - s0) / (s1 - s0) * (h1 - h0))
    return _HNR_TABLE[-1][1]


def build_page(state: dict[str, Any], keepalive_days: int,
               dl_torrents: list[dict] | None = None,
               dl_name: str = "") -> list[dict]:
    """构建插件详情页（行序：保活状态 → 用户信息 → 下载器 → 运行记录）"""
    result = [_build_status_row(state, keepalive_days)]
    user_row = _build_user_bar(state)
    result.append(user_row or {"component": "VAlert", "props": {
        "type": "info", "variant": "tonal", "density": "compact", "class": "mb-3",
        "text": "用户信息：等待首次运行后从站点获取（需 CookieCloud 配置 AnimeZ 域名）",
    }})
    result.append(_build_dl_section(dl_torrents or [], dl_name))
    result.append(_build_history_table(state))
    return result


def _build_status_row(state: dict[str, Any], keepalive_days: int) -> dict:
    """保活状态 4 列等高 tonal 卡片"""
    last_status = state.get("last_status", "未运行")
    color_map = {"success": "success", "skipped": "info",
                 "no_candidate": "warning", "failed": "error"}
    last_s = state.get("last_success_at", "")
    next_window = "未知"
    if last_s:
        try:
            ts = dt.datetime.fromisoformat(last_s.replace("Z", "+00:00"))
            next_window = _fmt_time((ts + dt.timedelta(days=keepalive_days)).isoformat())
        except ValueError:
            pass
    return {"component": "VRow", "props": {"class": "mb-3", "align": "stretch"}, "content": [
        _tonal_card("当前状态", last_status, color_map.get(last_status, "grey"), "mdi-pulse", 3),
        _tonal_card("上次访问", _fmt_time(state.get("last_visit_at", "")), "primary", "mdi-web", 3),
        _tonal_card("上次下载", _fmt_time(last_s), "success", "mdi-download-circle", 3),
        _tonal_card("下次窗口", next_window, "info", "mdi-calendar-clock", 3),
    ]}


def _tonal_card(label: str, value: str, color: str, icon: str, cols: int) -> dict:
    """等高 tonal 卡片：时间值拆两行，其他值补空行保持对齐"""
    if "月" in value and " " in value:
        date_part, time_part = value.split(" ", 1)
        value_node = {"component": "div", "content": [
            {"component": "div", "props": {"class": "text-subtitle-2 font-weight-bold"},
             "text": date_part},
            {"component": "div", "props": {"class": "text-caption text-medium-emphasis"},
             "text": time_part},
        ]}
    else:
        value_node = {"component": "div", "content": [
            {"component": "div", "props": {"class": "text-subtitle-2 font-weight-bold"},
             "text": _truncate(value or "无", 20)},
            {"component": "div", "props": {"class": "text-caption"}, "text": "\u00a0"},
        ]}
    return {"component": "VCol", "props": {"cols": 6, "md": cols}, "content": [{
        "component": "VCard",
        "props": {"variant": "tonal", "color": color, "density": "compact", "class": "fill-height"},
        "content": [{"component": "VCardText", "props": {"class": "pa-2"},
            "content": [
                {"component": "div", "props": {"class": "d-flex align-center mb-1"},
                 "content": [
                    {"component": "VIcon", "props": {"icon": icon, "size": "x-small", "class": "mr-1"}},
                    {"component": "span", "props": {"class": "text-caption"}, "text": label},
                ]},
                value_node,
            ]}],
    }]}


def _build_user_bar(state: dict[str, Any]) -> dict | None:
    """用户信息横条（含用户名 chip）"""
    fields = [
        ("upload", "mdi-arrow-up", "success"), ("download", "mdi-arrow-down", "warning"),
        ("ratio", "mdi-percent-circle", "info"), ("buffer", "mdi-database", "success"),
        ("seeds", "mdi-upload", "success"), ("leeches", "mdi-download", "warning"),
        ("bonus", "mdi-star", "amber"), ("hnr", "mdi-alert", "error"),
        ("reseed", "mdi-refresh", "grey"),
    ]
    chips = []
    name = state.get("user_name", "")
    if name:
        chips.append({"component": "VChip", "props": {
            "color": "primary", "size": "small", "variant": "flat",
            "class": "mr-1 mb-1", "prepend-icon": "mdi-account",
        }, "text": f"用户名: {name}"})
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
    return {"component": "VCard", "props": {"variant": "flat", "class": "mb-3 pa-2"},
            "content": [{"component": "div", "props": {
                "class": "d-flex flex-wrap align-center gap-1"}, "content": chips}]}


def _build_dl_section(torrents: list[dict], dl_name: str = "") -> dict:
    """下载器 AZ 种子（tonal 卡片风格与保活状态行一致）"""
    def _sz(b: int) -> str:
        for u in ["B", "KB", "MB", "GB", "TB"]:
            if b < 1024:
                return f"{b:.1f}{u}" if u != "B" else f"{b}B"
            b /= 1024
        return str(b)

    def _st(secs: int) -> str:
        if not secs:
            return "-"
        d, h = divmod(secs // 3600, 24)
        return f"{d}d{h}h" if d else f"{h}h"

    prefix = f"{dl_name} / " if dl_name else ""
    if not torrents:
        return {"component": "VAlert", "props": {
            "type": "info", "variant": "tonal", "density": "compact", "class": "mb-3",
            "text": f"下载器种子：{prefix}暂无 AnimeZ 分类种子",
        }}
    rows = []
    for t in torrents[:10]:
        pct = f"{t.get('progress', 0) * 100:.0f}%"
        size_b = t.get("size", 0)
        seed_s = t.get("seeding_time", 0) or 0
        req_h = _hnr_req(size_b)
        done_h = seed_s // 3600
        hnr = f"✓ {done_h}h" if done_h >= req_h else f"{done_h}/{req_h}h"
        rows.append({"component": "tr", "content": [
            {"component": "td", "props": {"class": "text-caption"},
             "text": _truncate(t.get("name", ""), 50)},
            {"component": "td", "props": {"class": "text-caption"}, "text": _sz(size_b)},
            {"component": "td", "props": {"class": "text-caption"}, "text": pct},
            {"component": "td", "props": {"class": "text-caption"}, "text": str(t.get("state", ""))},
            {"component": "td", "props": {"class": "text-caption"}, "text": _st(seed_s)},
            {"component": "td", "props": {"class": "text-caption"}, "text": hnr},
        ]})
    return {"component": "VCard", "props": {"variant": "tonal", "color": "blue-grey", "class": "mb-3"},
            "content": [
        {"component": "VCardTitle", "props": {"class": "text-subtitle-2 pa-3"},
         "text": f"{prefix}{len(torrents)} 个种子"},
        {"component": "VTable", "props": {"density": "compact"}, "content": [
            {"component": "thead", "content": [{"component": "tr", "content": [
                {"component": "th", "props": {"class": "text-caption"}, "text": c}
                for c in ["名称", "体积", "进度", "状态", "做种时长", "H&R"]
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
                {"component": "th", "props": {"class": "text-caption"}, "text": h}
                for h in ["时间", "状态", "详情"]
            ]}]},
            {"component": "tbody", "content": rows},
        ]},
    ]}


def _history_row(ev: dict[str, Any]) -> dict:
    status = ev.get("status", "")
    color_map = {"success": "success", "skipped": "info",
                 "no_candidate": "warning", "failed": "error"}
    _detail_map = {
        "success": "下载种子保活成功",
        "skipped": "访问PT站保活成功",
        "no_candidate": "访问PT站成功，无候选种子",
    }
    parts = []
    if status in _detail_map:
        parts.append(_detail_map[status])
    if ev.get("reason") and status not in ("success", "skipped", "no_candidate"):
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
