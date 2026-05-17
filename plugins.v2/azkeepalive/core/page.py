# input: 插件 state (history, user_*, last_*) | output: Vuetify JSON 详情页 | pos: 面板构建

from __future__ import annotations

import datetime as dt
from typing import Any

from .models import hnr_required_hours


def build_page(state: dict[str, Any], keepalive_days: int,
               dl_torrents: list[dict] | None = None,
               dl_name: str = "") -> list[dict]:
    """构建插件详情页（行序：保活状态 → 用户信息 → 下载器 → 运行记录）"""
    return [
        _section_title("保活概览", "mdi-shield-clock-outline"),
        _build_status_row(state, keepalive_days),
        _build_user_section(state),
        _build_dl_section(dl_torrents or [], dl_name),
        _build_history_table(state),
    ]


def _section_title(text: str, icon: str) -> dict:
    return {"component": "div", "props": {
        "class": "d-flex align-center text-subtitle-2 font-weight-medium text-medium-emphasis mb-2 mt-1",
    }, "content": [
        {"component": "VIcon", "props": {"icon": icon, "size": "small", "class": "mr-1"}},
        {"component": "span", "text": text},
    ]}


def _remain_days(iso_str: str, limit_days: int, now: dt.datetime) -> tuple:
    """返回 (剩余天数 | None, 显示文字)"""
    if not iso_str:
        return None, "未知"
    try:
        ts = dt.datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=dt.timezone.utc)
        remaining = (ts + dt.timedelta(days=limit_days) - now).days
        if remaining < 0:
            return remaining, f"⚠ 超期{-remaining}天"
        return remaining, f"剩{remaining}天"
    except (ValueError, OSError):
        return None, "未知"


def _urgency_color(days, default: str) -> str:
    if days is None:
        return default
    if days < 10:
        return "error"
    if days < 30:
        return "warning"
    return default


def _build_status_row(state: dict[str, Any], keepalive_days: int) -> dict:
    """保活状态 3 列等高 tonal 卡片（访问/下载分别显示规则和插件间隔）"""
    now = dt.datetime.now(dt.timezone.utc)
    last_status = state.get("last_status", "未运行")
    color_map = {"visit_success": "primary", "download_success": "success",
                 "skipped": "info",
                 "no_candidate": "warning", "failed": "error"}
    status_text = {"visit_success": "访问成功", "download_success": "下载成功",
                   "skipped": "跳过",
                   "no_candidate": "无候选", "failed": "失败"}.get(last_status, last_status)
    last_visit_at = state.get("last_visit_at", "")
    visit_days_left, visit_text = _remain_days(last_visit_at, 60, now)
    _, visit_interval_text = _remain_days(last_visit_at, keepalive_days, now)
    last_download_at = state.get("last_download_at", "")
    download_days_left, download_text = _remain_days(last_download_at, 90, now)
    _, download_interval_text = _remain_days(last_download_at, keepalive_days, now)
    visit_subtitle = _interval_text(visit_text, visit_interval_text, bool(last_visit_at))
    download_subtitle = _interval_text(download_text, download_interval_text, bool(last_download_at))
    return {"component": "VRow", "props": {"class": "mb-3", "align": "stretch"}, "content": [
        _tonal_card("当前状态", status_text, color_map.get(last_status, "grey"), "mdi-pulse", 4),
        _tonal_card("上次访问", _fmt_time(last_visit_at), _urgency_color(visit_days_left, "primary"),
                    "mdi-web", 4, visit_subtitle),
        _tonal_card("上次下载", _fmt_time(last_download_at), _urgency_color(download_days_left, "success"),
                    "mdi-download-circle", 4, download_subtitle),
    ]}


def _interval_text(rule_text: str, interval_text: str, has_time: bool) -> str:
    if not has_time:
        return "首次运行"
    return f"AZ{rule_text} / 间隔{interval_text}"


def _tonal_card(label: str, value: str, color: str, icon: str, cols: int,
                subtitle: str = "") -> dict:
    """等高 tonal 卡片：时间值拆两行，subtitle 显示倒计时或备注"""
    if "月" in value and " " in value:
        date_part, time_part = value.split(" ", 1)
        nodes = [
            {"component": "div", "props": {"class": "text-subtitle-2 font-weight-bold"},
             "text": date_part},
            {"component": "div", "props": {"class": "text-caption text-medium-emphasis"},
             "text": time_part},
        ]
        if subtitle:
            nodes.append({"component": "div", "props": {"class": "text-caption mt-1"},
                          "text": subtitle})
        value_node = {"component": "div", "content": nodes}
    else:
        value_node = {"component": "div", "content": [
            {"component": "div", "props": {"class": "text-subtitle-2 font-weight-bold"},
             "text": _truncate(value or "无", 20)},
            {"component": "div", "props": {"class": "text-caption"},
             "text": subtitle or "\u00a0"},
        ]}
    return {"component": "VCol", "props": {"cols": 6, "md": cols}, "content": [{
        "component": "VCard",
        "props": {"variant": "tonal", "color": color, "density": "compact",
                  "class": "fill-height rounded-lg"},
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


def _build_user_section(state: dict[str, Any]) -> dict:
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
    content = [{"component": "div", "props": {
        "class": "d-flex flex-wrap align-center gap-1"}, "content": chips}]
    if not chips:
        content = [{"component": "div", "props": {
            "class": "text-caption text-medium-emphasis pa-2"},
            "text": "等待首次保活后从站点刷新用户信息"}]
    return {"component": "VCard", "props": {
        "variant": "flat", "class": "mb-3 rounded-lg", "border": True,
    }, "content": [
        {"component": "VCardTitle", "props": {"class": "text-subtitle-2 pa-3 d-flex align-center"},
         "content": [
             {"component": "VIcon", "props": {"icon": "mdi-account-details", "size": "small", "class": "mr-1"}},
             {"component": "span", "text": "账户信息"},
        ]},
        {"component": "VDivider"},
        {"component": "VCardText", "props": {"class": "pa-2"}, "content": content},
    ]}


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
        return {"component": "VCard", "props": {
            "variant": "flat", "class": "mb-3 rounded-lg", "border": True,
        }, "content": [
            {"component": "VCardTitle", "props": {"class": "text-subtitle-2 pa-3 d-flex align-center"},
             "content": [
                 {"component": "VIcon", "props": {"icon": "mdi-download-network", "size": "small", "class": "mr-1"}},
                 {"component": "span", "text": f"{prefix}下载器种子"},
             ]},
            {"component": "VDivider"},
            {"component": "VCardText", "props": {"class": "text-caption text-medium-emphasis pa-3"},
             "text": "暂无 AnimeZ 分类种子"},
        ]}
    rows = []
    for t in torrents[:10]:
        pct = f"{t.get('progress', 0) * 100:.0f}%"
        size_bytes = t.get("size", 0)
        seeding_seconds = t.get("seeding_time", 0) or 0
        required_hours = hnr_required_hours(size_bytes) + 24
        seeded_hours = seeding_seconds // 3600
        hnr = f"✓ {seeded_hours}h" if seeded_hours >= required_hours else f"{seeded_hours}/{required_hours}h"
        rows.append({"component": "tr", "content": [
            {"component": "td", "props": {"class": "text-caption"},
             "text": _truncate(t.get("name", ""), 50)},
            {"component": "td", "props": {"class": "text-caption"}, "text": _sz(size_bytes)},
            {"component": "td", "props": {"class": "text-caption"}, "text": pct},
            {"component": "td", "props": {"class": "text-caption"}, "text": str(t.get("state", ""))},
            {"component": "td", "props": {"class": "text-caption"}, "text": _st(seeding_seconds)},
            {"component": "td", "props": {"class": "text-caption"}, "text": hnr},
        ]})
    return {"component": "VCard", "props": {
        "variant": "flat", "class": "mb-3 rounded-lg", "border": True,
    },
            "content": [
        {"component": "VCardTitle", "props": {"class": "text-subtitle-2 pa-3 d-flex align-center"},
         "content": [
             {"component": "VIcon", "props": {"icon": "mdi-download-network", "size": "small", "class": "mr-1"}},
             {"component": "span", "text": f"{prefix}{len(torrents)} 个种子"},
         ]},
        {"component": "VDivider"},
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
        return {"component": "VCard", "props": {
            "variant": "flat", "class": "mt-2 rounded-lg", "border": True,
        }, "content": [
            {"component": "VCardTitle", "props": {"class": "text-subtitle-2 pa-3 d-flex align-center"},
             "content": [
                 {"component": "VIcon", "props": {"icon": "mdi-history", "size": "small", "class": "mr-1"}},
                 {"component": "span", "text": "运行记录"},
             ]},
            {"component": "VDivider"},
            {"component": "VCardText", "props": {"class": "text-caption text-medium-emphasis pa-3"},
             "text": "暂无运行记录"},
        ]}
    rows = [_history_row(ev) for ev in history]
    return {"component": "VCard", "props": {
        "variant": "flat", "class": "mt-2 rounded-lg", "border": True,
    }, "content": [
        {"component": "VCardTitle", "props": {"class": "text-subtitle-2 pa-3 d-flex align-center"},
         "content": [
             {"component": "VIcon", "props": {"icon": "mdi-history", "size": "small", "class": "mr-1"}},
             {"component": "span", "text": "运行记录"},
        ]},
        {"component": "VDivider"},
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
    color_map = {"visit_success": "primary", "download_success": "success",
                 "skipped": "info",
                 "no_candidate": "warning", "failed": "error"}
    _detail_map = {
        "visit_success": "访问保活成功",
        "download_success": "下载种子保活成功",
        "skipped": "访问和下载均未到插件保活间隔",
        "no_candidate": "未找到可下载的新种子",
    }
    parts = []
    if status in _detail_map:
        parts.append(_detail_map[status])
    if ev.get("reason") and status not in (
        "visit_success", "download_success", "skipped", "no_candidate",
    ):
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
