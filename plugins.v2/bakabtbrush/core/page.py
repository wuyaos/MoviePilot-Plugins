"""BakaBTBrush Vuetify 数据页：四卡总览和简洁运行日志。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

try:
    from app.core.config import settings as _mp_settings
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo(getattr(_mp_settings, "TZ", "Asia/Shanghai"))
except Exception:
    _TZ = None


_STATUS_TEXT = {
    "success": "成功",
    "dry_run": "试运行",
    "no_candidate": "无候选",
    "no_qb_slot": "槽位已满",
    "failed": "失败",
    "unknown": "未运行",
}
_STATUS_COLOR = {
    "success": "success",
    "dry_run": "secondary",
    "no_candidate": "warning",
    "no_qb_slot": "info",
    "failed": "error",
    "unknown": "grey",
}


def build_page(state: dict[str, Any]) -> list[dict]:
    """固定布局：第一行四卡，第二部分为运行日志。"""
    return [
        _overview_cards(state),
        _history_table(state),
    ]


def _overview_cards(state: dict[str, Any]) -> dict:
    account = state.get("account") or {}
    qb = state.get("qb") or {}
    last_run = state.get("last_run") or {}
    completed = len(state.get("completed_hashes") or [])
    slots = _slot_text(qb.get("downloading_count", 0), qb.get("max_downloading", 0))

    return {
        "component": "VRow",
        "props": {"class": "mb-3", "align": "stretch"},
        "content": [
            _card(
                "BakaBT 流量",
                "mdi-cloud-upload-outline",
                "primary",
                [
                    f"↑ {_format_mb(account.get('uploaded_mb'))}",
                    f"↓ {_format_mb(account.get('downloaded_mb'))}",
                    f"分享率：{account.get('ratio') or '未获取'}",
                ],
            ),
            _card(
                "qB 刷流流量",
                "mdi-transfer",
                "success",
                [
                    f"↑ {_format_mb(qb.get('uploaded_mb', 0))}",
                    f"↓ {_format_mb(qb.get('downloaded_mb', 0))}",
                    f"下载槽位：{slots}",
                ],
            ),
            _card(
                "历史下载种子",
                "mdi-download-multiple",
                "info",
                [f"{completed} 个", "已完成下载"],
            ),
            _card(
                "上次运行",
                "mdi-clock-outline",
                _STATUS_COLOR.get(last_run.get("status", "unknown"), "grey"),
                [
                    _format_time(last_run.get("time", "")),
                    _STATUS_TEXT.get(last_run.get("status", "unknown"), last_run.get("status") or "未运行"),
                    last_run.get("push") or "-",
                ],
            ),
        ],
    }


def _card(title: str, icon: str, color: str, lines: list[str]) -> dict:
    return {
        "component": "VCol",
        "props": {"cols": 6, "md": 3},
        "content": [{
            "component": "VCard",
            "props": {
                "variant": "tonal",
                "color": color,
                "density": "compact",
                "class": "fill-height rounded-lg",
            },
            "content": [{
                "component": "VCardText",
                "props": {"class": "pa-3"},
                "content": [
                    {
                        "component": "div",
                        "props": {"class": "d-flex align-center mb-2"},
                        "content": [
                            {"component": "VIcon", "props": {"icon": icon, "size": "small", "class": "mr-1"}},
                            {"component": "span", "props": {"class": "text-caption"}, "text": title},
                        ],
                    },
                    *[
                        {
                            "component": "div",
                            "props": {"class": "text-caption" if index else "text-subtitle-2 font-weight-bold"},
                            "text": line,
                        }
                        for index, line in enumerate(lines)
                    ],
                ],
            }],
        }],
    }


def _history_table(state: dict[str, Any]) -> dict:
    history = list(reversed((state.get("history") or [])[-20:]))
    if not history:
        return _empty_history()

    rows = []
    for event in history:
        status = str(event.get("status") or "unknown")
        rows.append({
            "component": "tr",
            "content": [
                _cell(_format_time(event.get("time", "")), "text-no-wrap"),
                {
                    "component": "td",
                    "content": [{
                        "component": "VChip",
                        "props": {
                            "color": _STATUS_COLOR.get(status, "grey"),
                            "size": "x-small",
                            "variant": "flat",
                        },
                        "text": _STATUS_TEXT.get(status, status),
                    }],
                },
                _torrent_cell(str(event.get("torrent") or "-")),
                _cell(_truncate(str(event.get("push") or "未推送"), 24)),
                _cell(_truncate(str(event.get("detail") or ""), 100)),
            ],
        })

    return {
        "component": "VCard",
        "props": {"variant": "flat", "class": "rounded-lg", "border": True},
        "content": [
            _history_title(),
            {"component": "VDivider"},
            {
                "component": "VTable",
                "props": {"density": "compact"},
                "content": [
                    {
                        "component": "thead",
                        "content": [{
                            "component": "tr",
                            "content": [
                                {"component": "th", "props": {"class": "text-caption"}, "text": label}
                                for label in ("时间", "状态", "种子", "推送", "详情")
                            ],
                        }],
                    },
                    {"component": "tbody", "content": rows},
                ],
            },
        ],
    }


def _empty_history() -> dict:
    return {
        "component": "VCard",
        "props": {"variant": "flat", "class": "rounded-lg", "border": True},
        "content": [
            _history_title(),
            {"component": "VDivider"},
            {
                "component": "VCardText",
                "props": {"class": "text-caption text-medium-emphasis pa-3"},
                "text": "暂无运行记录",
            },
        ],
    }


def _history_title() -> dict:
    return {
        "component": "VCardTitle",
        "props": {"class": "text-subtitle-2 pa-3 d-flex align-center"},
        "content": [
            {"component": "VIcon", "props": {"icon": "mdi-history", "size": "small", "class": "mr-1"}},
            {"component": "span", "text": "运行日志"},
        ],
    }


def _cell(text: str, class_name: str = "") -> dict:
    return {"component": "td", "props": {"class": f"text-caption {class_name}".strip()}, "text": text}


def _torrent_cell(title: str) -> dict:
    """日志保留完整种子名，以换行替代截断；窄屏由 VTable 横向滚动承载。"""
    return {
        "component": "td",
        "props": {"class": "text-caption"},
        "content": [{
            "component": "div",
            "props": {
                "class": "text-wrap",
                "style": "min-width: 260px; max-width: 520px; white-space: normal; word-break: break-word;",
            },
            "text": title,
        }],
    }


def _slot_text(current: Any, maximum: Any) -> str:
    try:
        current = max(0, int(current or 0))
        maximum = max(0, int(maximum or 0))
    except (TypeError, ValueError):
        return "未获取"
    return f"{current}/不限" if maximum == 0 else f"{current}/{maximum}"


def _format_mb(value: Any) -> str:
    if value is None:
        return "未获取"
    try:
        return f"{float(value):,.2f} MB"
    except (TypeError, ValueError):
        return "未获取"


def _format_time(value: Any) -> str:
    if not value:
        return "未运行"
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if _TZ:
            timestamp = timestamp.astimezone(_TZ)
        else:
            timestamp = timestamp.astimezone()
        return f"{timestamp.month}月{timestamp.day}日 {timestamp:%H:%M}"
    except (TypeError, ValueError, OSError):
        return str(value)[:16]


def _truncate(text: str, maximum: int) -> str:
    return text if len(text) <= maximum else text[: maximum - 1] + "…"
