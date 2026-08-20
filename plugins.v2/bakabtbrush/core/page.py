"""BakaBTBrush Vuetify 数据页：流量、当前任务、运行历史和删除历史。"""

from __future__ import annotations

from typing import Any

from .presentation import format_elapsed, format_local_time


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
    return [
        _overview_cards(state),
        _current_downloads(state),
        _history_table(state),
        _deletion_table(state),
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
            _card("BakaBT 流量", "mdi-cloud-upload-outline", "primary", [
                f"↑ {_format_mb(account.get('uploaded_mb'))}",
                f"↓ {_format_mb(account.get('downloaded_mb'))}",
                f"分享率：{account.get('ratio') or '未获取'}",
            ]),
            _card("qB 刷流流量", "mdi-transfer", "success", [
                f"↑ {_format_mb(qb.get('uploaded_mb', 0))}",
                f"↓ {_format_mb(qb.get('downloaded_mb', 0))}",
                f"下载槽位：{slots}",
            ]),
            _card("历史下载种子", "mdi-download-multiple", "info", [
                f"{completed} 个", "已完成下载",
            ]),
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
                "variant": "tonal", "color": color, "density": "compact",
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


def _current_downloads(state: dict[str, Any]) -> dict:
    qb = state.get("qb") or {}
    torrents = [
        item for item in qb.get("torrents") or []
        if isinstance(item, dict) and float(item.get("progress") or 0) < 0.999999
    ]
    title = _section_title("mdi-download-network-outline", "当前 BakaBT 下载流程")
    if not torrents:
        return _empty_card(title, "当前没有未完成的 BakaBT 下载任务")
    rows = []
    for item in torrents:
        title_content = _link_or_text(
            str(item.get("name") or "未知种子"), str(item.get("detail_url") or "")
        )
        rows.append({
            "component": "VCol",
            "props": {"cols": 12, "md": 6},
            "content": [{
                "component": "VCard",
                "props": {"variant": "tonal", "class": "h-100 rounded-lg"},
                "content": [{
                    "component": "VCardText",
                    "props": {"class": "pa-3"},
                    "content": [
                        title_content,
                        {"component": "div", "props": {"class": "text-caption mt-2"},
                         "text": f"状态：{item.get('state') or '-'}　进度：{float(item.get('progress') or 0) * 100:.1f}%"},
                        {"component": "div", "props": {"class": "text-caption"},
                         "text": f"上传：{_format_mb(item.get('uploaded_mb'))}　下载：{_format_mb(item.get('downloaded_mb'))}"},
                        {"component": "div", "props": {"class": "text-caption"},
                         "text": f"分享率：{item.get('ratio', 0)}　上传速度：{item.get('up_speed_kbps', 0)} KB/s"},
                    ],
                }],
            }],
        })
    return {
        "component": "VCard",
        "props": {"variant": "flat", "class": "rounded-lg mb-3", "border": True},
        "content": [title, {"component": "VDivider"}, {"component": "VRow", "props": {"class": "pa-2"}, "content": rows}],
    }


def _history_table(state: dict[str, Any]) -> dict:
    history = list(reversed((state.get("history") or [])[-20:]))
    title = _section_title("mdi-history", "运行历史")
    if not history:
        return _empty_card(title, "暂无运行记录")
    added_by_title = {
        str(record.get("title") or ""): record
        for record in (state.get("added") or {}).values()
        if isinstance(record, dict) and record.get("title")
    }
    rows = []
    for event in history:
        status = str(event.get("status") or "unknown")
        rows.append({
            "component": "tr",
            "content": [
                _cell(_format_time(event.get("time", "")), "text-no-wrap"),
                _status_cell(status),
                _torrent_cell(event, added_by_title),
                _cell(_truncate(str(event.get("push") or "未推送"), 24)),
                _cell(_truncate(str(event.get("detail") or ""), 100)),
            ],
        })
    return _table_card(title, ("时间", "状态", "本轮候选 / 推送", "推送", "详情"), rows)


def _deletion_table(state: dict[str, Any]) -> dict:
    deletions = list(reversed((state.get("deletions") or [])[-20:]))
    title = _section_title("mdi-delete-clock-outline", "自动删除历史")
    if not deletions:
        return _empty_card(title, "暂无自动删除记录")
    rows = []
    for record in deletions:
        rows.append({
            "component": "tr",
            "content": [
                _cell(_format_time(record.get("time", "")), "text-no-wrap"),
                {
                    "component": "td",
                    "content": [_link_or_text(
                        str(record.get("title") or "未知种子"),
                        str(record.get("detail_url") or ""),
                    )],
                },
                _cell(str(record.get("reason") or "-")),
                _cell("已删除" if record.get("delete_files") else "保留"),
                _cell(f"{float(record.get('uploaded_gb') or 0):.3f} GB"),
                _cell(str(record.get("ratio") or 0)),
            ],
        })
    return _table_card(title, ("时间", "种子", "删除原因", "文件", "上传量", "分享率"), rows)


def _torrent_cell(event: dict[str, Any], added_by_title: dict[str, dict[str, Any]]) -> dict:
    links = list(event.get("torrent_links") or [])
    if not links:
        for title in str(event.get("torrent") or "").split("、"):
            record = added_by_title.get(title)
            if record and record.get("detail_url"):
                links.append({
                    "title": title,
                    "url": record.get("detail_url"),
                    "published_at": record.get("published_at"),
                    "size_mb": record.get("size_mb"),
                })
    if not links:
        return _cell(str(event.get("torrent") or "-"))
    content = []
    run_time = event.get("time")
    for item in links:
        published_at = item.get("published_at")
        content.extend([
            _link_or_text(str(item.get("title") or "未知种子"), str(item.get("url") or "")),
            {
                "component": "div",
                "props": {"class": "text-caption text-medium-emphasis mb-1"},
                "text": (
                    f"发布：{format_local_time(published_at, compact=True)}　"
                    f"间隔：{format_elapsed(published_at, _parse_run_time(run_time))}"
                ),
            },
        ])
    return {
        "component": "td",
        "props": {
            "class": "text-caption",
            "style": "min-width: 280px; max-width: 560px; white-space: normal; word-break: break-word;",
        },
        "content": content,
    }


def _link_or_text(title: str, url: str) -> dict:
    if not url:
        return {"component": "div", "props": {"class": "text-body-2 text-wrap"}, "text": title}
    return {
        "component": "VBtn",
        "props": {
            "href": url, "target": "_blank", "rel": "noopener noreferrer",
            "variant": "text", "color": "primary", "size": "small",
            "class": "px-0 text-none text-wrap justify-start",
        },
        "text": title,
    }


def _status_cell(status: str) -> dict:
    return {
        "component": "td",
        "content": [{
            "component": "VChip",
            "props": {"color": _STATUS_COLOR.get(status, "grey"), "size": "x-small", "variant": "flat"},
            "text": _STATUS_TEXT.get(status, status),
        }],
    }


def _table_card(title: dict, headers: tuple[str, ...], rows: list[dict]) -> dict:
    return {
        "component": "VCard",
        "props": {"variant": "flat", "class": "rounded-lg mb-3", "border": True},
        "content": [
            title,
            {"component": "VDivider"},
            {
                "component": "VTable",
                "props": {"density": "compact"},
                "content": [
                    {"component": "thead", "content": [{
                        "component": "tr",
                        "content": [
                            {"component": "th", "props": {"class": "text-caption"}, "text": label}
                            for label in headers
                        ],
                    }]},
                    {"component": "tbody", "content": rows},
                ],
            },
        ],
    }


def _empty_card(title: dict, text: str) -> dict:
    return {
        "component": "VCard",
        "props": {"variant": "flat", "class": "rounded-lg mb-3", "border": True},
        "content": [
            title,
            {"component": "VDivider"},
            {"component": "VCardText", "props": {"class": "text-caption text-medium-emphasis pa-3"}, "text": text},
        ],
    }


def _section_title(icon: str, text: str) -> dict:
    return {
        "component": "VCardTitle",
        "props": {"class": "text-subtitle-2 pa-3 d-flex align-center"},
        "content": [
            {"component": "VIcon", "props": {"icon": icon, "size": "small", "class": "mr-1"}},
            {"component": "span", "text": text},
        ],
    }


def _cell(text: str, class_name: str = "") -> dict:
    return {"component": "td", "props": {"class": f"text-caption {class_name}".strip()}, "text": text}


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
    formatted = format_local_time(value, compact=True)
    return formatted if formatted != "未知" else "未运行"


def _parse_run_time(value: Any):
    from .presentation import parse_datetime
    return parse_datetime(value)


def _truncate(text: str, maximum: int) -> str:
    return text if len(text) <= maximum else text[: maximum - 1] + "…"
