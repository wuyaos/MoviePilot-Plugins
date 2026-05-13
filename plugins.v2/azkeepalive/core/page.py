# input: 插件 state (history, last_success_at, last_status)
# output: Vuetify JSON 详情页组件列表
# pos: 详情页构建器，供 __init__.py get_page() 调用

from __future__ import annotations

import datetime as dt
from typing import Any


def build_page(state: dict[str, Any], keepalive_days: int) -> list[dict]:
    """构建插件详情页 Vuetify JSON"""
    last_status = state.get("last_status", "未运行")
    last_success = state.get("last_success_at", "无")
    last_title = state.get("last_title", "无")
    last_visit = state.get("last_visit_at", "无")
    last_checked = state.get("last_checked_at", "无")

    # 计算下次窗口
    next_window = "未知"
    if last_success and last_success != "无":
        try:
            ts = dt.datetime.fromisoformat(last_success.replace("Z", "+00:00"))
            nxt = ts + dt.timedelta(days=keepalive_days)
            next_window = nxt.strftime("%Y-%m-%d %H:%M UTC")
        except ValueError:
            pass

    # 状态颜色
    color_map = {"success": "success", "skipped": "info", "no_candidate": "warning", "failed": "error"}
    status_color = color_map.get(last_status, "grey")

    # 概览卡片 - 两行
    row1 = {
        "component": "VRow", "props": {"class": "mb-2"},
        "content": [
            _stat_card("当前状态", last_status, status_color, 3),
            _stat_card("上次站点访问", last_visit, "primary", 3),
            _stat_card("上次下载成功", last_success, "success", 3),
            _stat_card("下次保活窗口", next_window, "info", 3),
        ],
    }
    row2 = {
        "component": "VRow", "props": {"class": "mb-4"},
        "content": [
            _stat_card("上次检查", last_checked, "grey", 4),
            _stat_card("上次种子", last_title, "grey", 4),
            _stat_card("保活间隔", f"{keepalive_days} 天", "grey", 4),
        ],
    }

    # 历史表格
    history = list(reversed(state.get("history", [])[-20:]))
    if history:
        rows = [_history_row(ev) for ev in history]
        table = {
            "component": "VTable", "props": {"density": "compact", "class": "mt-4"},
            "content": [
                {"component": "thead", "content": [
                    {"component": "tr", "content": [
                        {"component": "th", "text": "时间"},
                        {"component": "th", "text": "状态"},
                        {"component": "th", "text": "详情"},
                    ]},
                ]},
                {"component": "tbody", "content": rows},
            ],
        }
    else:
        table = {
            "component": "VAlert",
            "props": {"type": "info", "variant": "tonal", "text": "暂无运行记录"},
        }

    return [row1, row2, table]


def _stat_card(label: str, value: str, color: str, cols: int) -> dict:
    return {
        "component": "VCol", "props": {"cols": 12, "md": cols},
        "content": [{
            "component": "VCard", "props": {"variant": "tonal"},
            "content": [{
                "component": "VCardText",
                "content": [
                    {"component": "span", "props": {"class": "text-caption"}, "text": label},
                    {"component": "div", "props": {"class": f"text-h6 text-{color} mt-1"},
                     "text": _truncate(value, 40)},
                ],
            }],
        }],
    }


def _history_row(ev: dict[str, Any]) -> dict:
    status = ev.get("status", "")
    color_map = {"success": "success", "skipped": "info", "no_candidate": "warning", "failed": "error"}
    color = color_map.get(status, "grey")
    detail = ev.get("title") or ev.get("reason") or ""
    return {
        "component": "tr",
        "content": [
            {"component": "td", "props": {"class": "text-caption"}, "text": ev.get("time", "")},
            {"component": "td", "content": [
                {"component": "VChip", "props": {"color": color, "size": "x-small", "variant": "flat"},
                 "text": status},
            ]},
            {"component": "td", "props": {"class": "text-caption"}, "text": _truncate(detail, 60)},
        ],
    }


def _truncate(text: str, max_len: int) -> str:
    return text if len(text) <= max_len else text[:max_len - 1] + "…"


# --- Vuetify JSON 表单辅助（供 __init__.py get_form 使用） ---

def v_row(cols: list) -> dict:
    return {"component": "VRow", "content": cols}

def v_col(md: int, content: dict) -> dict:
    return {"component": "VCol", "props": {"cols": 12, "md": md}, "content": [content]}

def v_switch(model: str, label: str) -> dict:
    return {"component": "VSwitch", "props": {"model": model, "label": label}}

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
    return {"component": "VCronField", "props": props}
