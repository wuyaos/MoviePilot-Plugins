"""PTNewsWatch 配置页。"""
from __future__ import annotations

from typing import Any

from ..core.config import PluginConfig
from ..core.models import SourceAuthMode, SourceKind
from ..core.source_registry import SOURCES


def build_form(config: PluginConfig) -> tuple[list[dict], dict[str, Any]]:
    return ([{
        "component": "VForm",
        "content": [
            _global_card(),
            *[_source_card(source) for source in SOURCES],
        ],
    }], config.to_dict())


def _global_card():
    return {
        "component": "VCard",
        "props": {"variant": "outlined", "class": "mb-3"},
        "content": [
            {"component": "VCardTitle", "text": "通用设置"},
            {"component": "VDivider"},
            {"component": "VCardText", "content": [
                {"component": "VRow", "content": [
                    _col(3, _switch("enabled", "启用插件")),
                    _col(3, _switch("notify", "开启通知")),
                    _col(3, _switch("use_proxy", "使用系统代理")),
                    _col(3, _switch("onlyonce", "立即检查一次")),
                ]},
                {"component": "VRow", "content": [
                    _col(6, _text("cron", "检查周期", "30 */12 * * *", "默认每天 00:30、12:30")),
                    _col(3, _number("history_days", "历史保留天数", 1)),
                    _col(3, _number("max_entries_per_source", "单来源最大通知条数", 1)),
                ]},
                {"component": "VRow", "content": [
                    _col(6, _switch("first_run_push_recent", "首次运行推送最近消息", hint="默认关闭：首次仅建立已见基线，不推送历史消息")),
                ]},
            ]},
        ],
    }


def _source_card(source):
    auth_text = {
        SourceAuthMode.PUBLIC: "公开 Feed，无需 Cookie",
        SourceAuthMode.MP_SITE_COOKIE: f"使用 MoviePilot 站点管理中的 {source.site_domain} Cookie 与 UA",
        SourceAuthMode.INVITES_COOKIE: "手工 Cookie 优先；为空时从 CookieCloud 获取 invites.fun Cookie 并保存",
    }[source.auth_mode]
    kind_text = {
        SourceKind.RSS: "RSS",
        SourceKind.ATOM: "Atom",
        SourceKind.NEXUS_TOPIC: "NexusPHP 主题页（最后 2 页）",
    }[source.kind]
    content = [
        {"component": "VCardTitle", "props": {"class": "d-flex align-center"}, "content": [
            {"component": "VIcon", "props": {"class": "mr-2", "color": _color(source.source_id)}, "text": _icon(source.source_id)},
            {"component": "span", "text": source.title},
            {"component": "VSpacer"},
            _switch(f"source_{source.source_id}_enabled", "启用", hide_details=True),
        ]},
        {"component": "VDivider"},
        {"component": "VCardText", "content": [
            {"component": "VAlert", "props": {
                "type": "info", "variant": "tonal", "density": "compact",
                "text": f"{kind_text} · {auth_text}",
            }},
            {"component": "VRow", "props": {"class": "mt-1"}, "content": [
                _col(10, {"component": "VTextField", "props": {
                    "label": "来源地址", "model-value": source.url,
                    "readonly": True, "hide-details": True, "density": "compact",
                }}),
                _col(2, {"component": "VBtn", "props": {
                    "href": source.url, "target": "_blank", "variant": "tonal", "block": True,
                }, "text": "打开"}),
            ]},
        ]},
    ]
    if source.auth_mode == SourceAuthMode.INVITES_COOKIE:
        content[-1]["content"].append({"component": "VRow", "content": [
            _col(12, _text(
                "invites_cookie", "药丸 Atom Cookie", "留空时从 CookieCloud 自动获取",
                "Cookie 仅用于请求，不进入日志、通知或数据页", password=True,
            )),
        ]})
    return {"component": "VCard", "props": {"variant": "outlined", "class": "mb-3"}, "content": content}


def _col(md, component):
    return {"component": "VCol", "props": {"cols": 12, "md": md}, "content": [component]}


def _switch(model, label, hint="", hide_details=False):
    props = {"model": model, "label": label, "color": "primary"}
    if hint:
        props.update({"hint": hint, "persistent-hint": True})
    if hide_details:
        props["hide-details"] = True
    return {"component": "VSwitch", "props": props}


def _text(model, label, placeholder="", hint="", password=False):
    props = {"model": model, "label": label, "placeholder": placeholder, "clearable": True}
    if password:
        props["type"] = "password"
    if hint:
        props.update({"hint": hint, "persistent-hint": True})
    return {"component": "VTextField", "props": props}


def _number(model, label, minimum):
    return {"component": "VTextField", "props": {"model": model, "label": label, "type": "number", "min": minimum}}


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
