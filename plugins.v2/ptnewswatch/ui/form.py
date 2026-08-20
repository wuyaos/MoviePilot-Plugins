"""PTNewsWatch 配置页。"""
from __future__ import annotations

from typing import Any

from ..core.config import PluginConfig
from ..core.models import SourceAuthMode, SourceKind
from ..core.source_registry import SOURCES


def build_form(config: PluginConfig, config_error: str = "") -> tuple[list[dict], dict[str, Any]]:
    source_cards = [
        {"component": "VCol", "props": {"cols": 12, "md": 6, "class": "d-flex"}, "content": [_source_card(source, config)]}
        for source in SOURCES
    ]
    content = []
    if config_error:
        content.append({"component": "VAlert", "props": {
            "type": "error", "variant": "tonal", "density": "compact", "class": "mb-3",
            "text": config_error,
        }})
    content.extend([
        _global_card(),
        {"component": "div", "props": {"class": "text-subtitle-1 font-weight-medium mb-2"}, "text": "来源配置"},
        {"component": "VRow", "props": {"class": "mb-1"}, "content": source_cards},
    ])
    return ([{"component": "VForm", "content": content}], config.to_dict())


def _global_card():
    return {"component": "VCard", "props": {"variant": "outlined", "class": "mb-3"}, "content": [
        {"component": "VCardTitle", "props": {"class": "text-subtitle-1"}, "text": "通用设置"},
        {"component": "VCardSubtitle", "text": "定时检查、通知与资讯保留"},
        {"component": "VDivider", "props": {"class": "mt-2"}},
        {"component": "VCardText", "props": {"class": "pa-3"}, "content": [
            {"component": "VRow", "content": [
                _col(3, _switch("enabled", "启用插件")),
                _col(3, _switch("notify", "开启通知")),
                _col(3, _switch("use_proxy", "使用系统代理")),
                _col(3, _switch("onlyonce", "立即检查一次")),
            ]},
            {"component": "VRow", "content": [
                _col(6, _text("cron", "检查周期", "30 */12 * * *", "默认每天 00:30、12:30")),
                _col(3, _number("history_days", "资讯保留天数", 1)),
                _col(3, _number("max_entries_per_source", "单来源最大通知条数", 1, "同一来源的多个地址共享此上限")),
            ]},
            {"component": "VAlert", "props": {
                "type": "info", "variant": "tonal", "density": "compact",
                "text": "来源首次成功检查会推送最近消息，并建立已见基线；推送数量受单来源上限控制。",
            }},
        ]},
    ]}


def _source_card(source, config):
    auth_text = {
        SourceAuthMode.PUBLIC: "公开 Feed，无需 Cookie",
        SourceAuthMode.MP_SITE_COOKIE: f"使用 MoviePilot 站点管理中的 {source.site_domain} Cookie 与 UA",
        SourceAuthMode.INVITES_COOKIE: "手工 Cookie 优先；为空时从 CookieCloud 获取并保存",
    }[source.auth_mode]
    kind_text = {
        SourceKind.RSS: "RSS", SourceKind.ATOM: "Atom",
        SourceKind.NEXUS_TOPIC: "NexusPHP 主题页（每个地址最后2页）",
    }[source.kind]
    urls_model = f"source_{source.source_id}_urls"
    urls = config.source_urls_text(source.source_id)
    count = len([line for line in urls.splitlines() if line.strip()])
    body = [
        {"component": "VCardTitle", "props": {"class": "d-flex align-center text-subtitle-1 py-2"}, "content": [
            {"component": "VIcon", "props": {"class": "mr-2", "size": "small", "color": _color(source.source_id)}, "text": _icon(source.source_id)},
            {"component": "span", "text": source.title},
            {"component": "VSpacer"},
            _switch(f"source_{source.source_id}_enabled", "启用", hide_details=True),
        ]},
        {"component": "VCardSubtitle", "props": {"class": "pb-2"}, "text": f"{kind_text} · {auth_text}"},
        {"component": "VDivider"},
        {"component": "VCardText", "props": {"class": "pa-3"}, "content": [
            {"component": "VTextarea", "props": {
                "model": urls_model, "label": "来源地址（每行一个）", "rows": 3,
                "auto-grow": True, "density": "compact", "variant": "outlined",
                "hint": f"仅允许 {source.site_domain} 的 HTTPS 地址；最多10个。当前 {count} 个。",
                "persistent-hint": True,
            }},
        ]},
    ]
    if source.auth_mode == SourceAuthMode.INVITES_COOKIE:
        body[-1]["content"].append(_text(
            "invites_cookie", "药丸 Atom Cookie", "留空时从 CookieCloud 自动获取",
            "Cookie 仅用于请求，不进入日志、通知或数据页", password=True,
        ))
    return {"component": "VCard", "props": {"variant": "outlined", "class": "h-100 w-100"}, "content": body}


def _col(md, component):
    return {"component": "VCol", "props": {"cols": 12, "md": md}, "content": [component]}


def _switch(model, label, hint="", hide_details=False):
    props = {"model": model, "label": label, "color": "primary", "density": "compact"}
    if hint:
        props.update({"hint": hint, "persistent-hint": True})
    if hide_details:
        props["hide-details"] = True
    return {"component": "VSwitch", "props": props}


def _text(model, label, placeholder="", hint="", password=False):
    props = {"model": model, "label": label, "placeholder": placeholder, "clearable": True, "density": "compact"}
    if password:
        props["type"] = "password"
    if hint:
        props.update({"hint": hint, "persistent-hint": True})
    return {"component": "VTextField", "props": props}


def _number(model, label, minimum, hint=""):
    props = {"model": model, "label": label, "type": "number", "min": minimum, "density": "compact"}
    if hint:
        props.update({"hint": hint, "persistent-hint": True})
    return {"component": "VTextField", "props": props}


def _icon(source_id):
    return {
        "pter_digest": "mdi-cloud-outline", "tjupt_digest": "mdi-school-outline",
        "fengchao_pt": "mdi-beehive-outline", "fengchao_invites": "mdi-email-fast-outline",
        "invites_pt_fy": "mdi-pill",
    }.get(source_id, "mdi-rss")


def _color(source_id):
    return {
        "pter_digest": "blue-grey", "tjupt_digest": "indigo",
        "fengchao_pt": "amber", "fengchao_invites": "orange",
        "invites_pt_fy": "purple",
    }.get(source_id, "primary")
