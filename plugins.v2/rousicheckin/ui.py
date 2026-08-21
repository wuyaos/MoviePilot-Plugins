"""RousiCheckin 的 MoviePilot Vuetify 表单与详情页。"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple


def build_form() -> Tuple[List[dict], Dict[str, Any]]:
    return [{
        "component": "VForm",
        "content": [
            {
                "component": "VAlert",
                "props": {"type": "info", "variant": "tonal", "class": "mb-3"},
                "text": "运行时优先使用 Cookie；Cookie 失效后自动用账号密码重新登录，并回写新的30天 Session Cookie。",
            },
            _form_card("mdi-cog-outline", "通用设置", "#E91E63", [{
                "component": "VRow", "content": [
                    _form_col(_switch("enabled", "启用插件", "primary"), 3),
                    _form_col(_switch("notify", "签到结果通知", "info"), 3),
                    _form_col(_switch("message_notify", "站内消息增量推送", "success"), 3),
                    _form_col(_switch("onlyonce", "立即运行一次", "warning"), 3),
                ],
            }]),
            _form_card("mdi-account-key", "登录设置", "#AD1457", [
                {"component": "VRow", "content": [
                    _form_col({"component": "VTextField", "props": {
                        "model": "username", "label": "用户名或邮箱", "autocomplete": "username",
                        "clearable": True,
                    }}, 6),
                    _form_col({"component": "VTextField", "props": {
                        "model": "password", "label": "密码", "type": "password",
                        "autocomplete": "current-password", "clearable": True,
                    }}, 6),
                ]},
                {"component": "VRow", "content": [
                    _form_col({"component": "VTextField", "props": {
                        "model": "cookie", "label": "Session Cookie", "type": "password",
                        "placeholder": "__Host-peergo_session=...", "autocomplete": "new-password",
                        "clearable": True,
                        "hint": "可手动填写；留空或失效时使用上方账号密码自动获取并保存。",
                        "persistent-hint": True,
                    }}, 12),
                ]},
            ]),
            _form_card("mdi-clock-outline", "调度设置", "#8E24AA", [{
                "component": "VRow", "content": [
                    _form_col({"component": "VCronField", "props": {
                        "model": "cron", "label": "签到周期", "placeholder": "7 9 * * *",
                        "hint": "默认每天09:07执行，避开整点。",
                    }}, 6),
                    _form_col({"component": "VTextField", "props": {
                        "model": "random_delay_minutes", "label": "随机抖动（分钟）",
                        "type": "number", "min": 0, "placeholder": "3",
                    }}, 6),
                ],
            }]),
            _form_card("mdi-information-outline", "使用说明", "#1976D2", [{
                "component": "VList", "props": {"density": "comfortable", "lines": "two"}, "content": [
                    _list_item("mdi-cookie", "Cookie 优先", "有效 Cookie 直接复用，不会每次重复登录；Cookie 约30天有效。"),
                    _list_item("mdi-login-variant", "自动续期", "Cookie 失效时使用账号密码登录，成功后把新 Cookie 回写插件配置。"),
                    _list_item("mdi-calendar-check", "签到逻辑", "先查询今日状态；已签到直接记录，未签到才提交 fixed 模式签到。"),
                    _list_item("mdi-message-text-clock", "站内消息", "首次仅建立消息基线，后续只推送未见过的通知，避免重复。"),
                ],
            }]),
        ],
    }], {
        "enabled": False,
        "notify": True,
        "message_notify": True,
        "username": "",
        "password": "",
        "cookie": "",
        "cron": "7 9 * * *",
        "random_delay_minutes": 3,
        "onlyonce": False,
    }


def build_page(
    auth_state: Dict[str, Any],
    user_info: Dict[str, Any],
    last_run: Dict[str, Any],
    history: List[Dict[str, Any]],
) -> List[dict]:
    return [
        {"component": "VRow", "props": {"class": "mb-4"}, "content": [
            _auth_card(auth_state),
            _user_card(user_info),
            _last_run_card(last_run),
        ]},
        _history_card(history),
    ]


def _switch(model: str, label: str, color: str) -> Dict[str, Any]:
    return {"component": "VSwitch", "props": {"model": model, "label": label, "color": color}}


def _form_card(icon: str, title: str, color: str, content: List[dict]) -> Dict[str, Any]:
    return {
        "component": "VCard", "props": {"variant": "outlined", "class": "mt-3"}, "content": [
            {"component": "VCardTitle", "props": {"class": "d-flex align-center"}, "content": [
                {"component": "VIcon", "props": {"style": f"color: {color};", "class": "mr-2"}, "text": icon},
                {"component": "span", "text": title},
            ]},
            {"component": "VDivider"},
            {"component": "VCardText", "content": content},
        ],
    }


def _form_col(component: Dict[str, Any], md: int) -> Dict[str, Any]:
    return {"component": "VCol", "props": {"cols": 12, "md": md}, "content": [component]}


def _list_item(icon: str, title: str, subtitle: str) -> Dict[str, Any]:
    return {"component": "VListItem", "content": [
        {"component": "template", "props": {"v-slot:prepend": ""}, "content": [
            {"component": "VIcon", "props": {"color": "primary"}, "text": icon},
        ]},
        {"component": "VListItemTitle", "text": title},
        {"component": "VListItemSubtitle", "text": subtitle},
    ]}


def _auth_card(state: Dict[str, Any]) -> Dict[str, Any]:
    status = state.get("status") or "unconfigured"
    meta = {
        "valid": ("Cookie 有效", "#4CAF50", "mdi-check-circle"),
        "refreshed": ("Cookie 已刷新", "#2196F3", "mdi-refresh-circle"),
        "failed": ("登录失败", "#F44336", "mdi-close-circle"),
        "unconfigured": ("未配置", "#9E9E9E", "mdi-alert-circle"),
    }.get(status, ("未知", "#9E9E9E", "mdi-help-circle"))
    label, color, icon = meta
    return _summary_card("mdi-cookie-check", "登录状态", "#E91E63", [
        _info_line("账号", state.get("username") or "-"),
        _info_line("Session 到期", state.get("expires_at") or "-"),
        _info_line("检查时间", state.get("updated_at") or "-"),
        _info_line("说明", state.get("message") or "-"),
    ], chip={"label": label, "color": color, "icon": icon})


def _user_card(info: Dict[str, Any]) -> Dict[str, Any]:
    return _summary_card("mdi-account-circle", "用户信息", "#AD1457", [
        _info_line("用户名", info.get("username") or "-"),
        _info_line("上传量", info.get("uploaded") or "-"),
        _info_line("下载量", info.get("downloaded") or "-"),
        _info_line("等级", info.get("level") if info.get("level") is not None else "-"),
        _info_line("魔力值", info.get("magic") if info.get("magic") is not None else "-"),
    ])


def _last_run_card(last_run: Dict[str, Any]) -> Dict[str, Any]:
    return _summary_card("mdi-history", "最近运行", "#8E24AA", [
        _info_line("运行时间", last_run.get("time") or "-"),
        _info_line("状态", last_run.get("status") or "-"),
        _info_line("连续天数", last_run.get("current_streak") if last_run.get("current_streak") not in (None, "") else "-"),
        _info_line("新消息数", last_run.get("new_message_count", 0)),
        _info_line("说明", last_run.get("message") or "-"),
    ])


def _summary_card(
    icon: str, title: str, color: str, lines: List[dict], chip: Dict[str, str] | None = None
) -> Dict[str, Any]:
    title_content = [
        {"component": "VIcon", "props": {"style": f"color: {color};", "class": "mr-2"}, "text": icon},
        {"component": "span", "text": title},
    ]
    if chip:
        title_content.extend([
            {"component": "VSpacer"},
            {"component": "VChip", "props": {
                "style": f"background-color: {chip['color']}; color: white;", "size": "small",
            }, "content": [
                {"component": "VIcon", "props": {"start": True, "size": "small", "style": "color: white;"}, "text": chip["icon"]},
                {"component": "span", "text": chip["label"]},
            ]},
        ])
    return {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [{
        "component": "VCard", "props": {"variant": "outlined", "class": "h-100"}, "content": [
            {"component": "VCardTitle", "props": {"class": "d-flex align-center"}, "content": title_content},
            {"component": "VDivider"},
            {"component": "VCardText", "content": lines},
        ],
    }]}


def _info_line(label: str, value: Any) -> Dict[str, Any]:
    return {"component": "div", "props": {"class": "d-flex justify-space-between py-1"}, "content": [
        {"component": "span", "props": {"class": "text-medium-emphasis"}, "text": label},
        {"component": "span", "props": {"class": "font-weight-medium text-right ml-2"}, "text": str(value)},
    ]}


def _history_card(history: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows = []
    for record in history:
        meta = _history_status_meta(record.get("status_code"))
        rows.append({"component": "tr", "content": [
            {"component": "td", "props": {"class": "text-caption text-no-wrap"}, "text": record.get("date") or "-"},
            {"component": "td", "props": {"class": "text-caption text-no-wrap"}, "text": record.get("time") or "-"},
            {"component": "td", "content": [{"component": "VChip", "props": {
                "style": f"background-color: {meta['color']}; color: white;", "size": "small",
            }, "content": [
                {"component": "VIcon", "props": {"start": True, "size": "small", "style": "color: white;"}, "text": meta["icon"]},
                {"component": "span", "text": meta["label"]},
            ]}]},
            {"component": "td", "props": {"class": "text-caption"}, "text": record.get("current_streak") if record.get("current_streak") not in (None, "") else "-"},
            {"component": "td", "props": {"class": "text-caption"}, "text": record.get("new_message_count", 0)},
            {"component": "td", "props": {"class": "text-caption", "style": "white-space: normal; min-width: 220px;"}, "text": record.get("message") or "-"},
        ]})
    table = [{"component": "VAlert", "props": {
        "type": "info", "variant": "tonal", "class": "ma-2",
    }, "text": "暂无签到历史"}] if not rows else [{
        "component": "VResponsive", "content": [{"component": "VTable", "props": {
            "hover": True, "density": "comfortable",
        }, "content": [
            {"component": "thead", "content": [{"component": "tr", "content": [
                {"component": "th", "text": "日期"},
                {"component": "th", "text": "时间"},
                {"component": "th", "text": "状态"},
                {"component": "th", "text": "连续天数"},
                {"component": "th", "text": "新消息数"},
                {"component": "th", "text": "说明"},
            ]}]},
            {"component": "tbody", "content": rows},
        ]}],
    }]
    return {"component": "VCard", "props": {"variant": "outlined", "class": "mb-4"}, "content": [
        {"component": "VCardTitle", "props": {"class": "d-flex align-center"}, "content": [
            {"component": "VIcon", "props": {"style": "color: #E91E63;", "class": "mr-2"}, "text": "mdi-table-clock"},
            {"component": "span", "props": {"class": "text-h6 font-weight-bold"}, "text": "签到历史"},
        ]},
        {"component": "VDivider"},
        {"component": "VCardText", "props": {"class": "pa-0 pa-md-2"}, "content": table},
    ]}


def _history_status_meta(status_code: Any) -> Dict[str, str]:
    return {
        "success_new": {"label": "签到成功", "color": "#4CAF50", "icon": "mdi-check-circle"},
        "success_already": {"label": "今日已签", "color": "#2196F3", "icon": "mdi-check-decagram"},
        "auth_failed": {"label": "登录失效", "color": "#F44336", "icon": "mdi-close-circle"},
        "failed": {"label": "签到失败", "color": "#FB8C00", "icon": "mdi-alert-circle"},
        "running": {"label": "执行中", "color": "#9E9E9E", "icon": "mdi-progress-clock"},
    }.get(status_code, {"label": "未知", "color": "#9E9E9E", "icon": "mdi-help-circle"})
