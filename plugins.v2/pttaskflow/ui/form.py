"""配置页：沿用 SiteAutoTask 视觉结构，由 Control 数据驱动任务控件。"""
from ..core.models import ControlKind


_TASK_ORDER = {"checkin": 0, "chat": 1, "exchange": 2, "lottery": 3, "medal": 4, "claim": 9, "generic": 10}


def _switch(model, label, md=3, **props):
    return {"component": "VCol", "props": {"cols": 12, "md": md}, "content": [{
        "component": "VSwitch", "props": {
            "model": model, "label": label, "hide-details": "auto",
            "density": "comfortable", **props,
        },
    }]}


def _text(model, label, md=3, **props):
    return {"component": "VCol", "props": {"cols": 12, "md": md}, "content": [{
        "component": "VTextField", "props": {
            "model": model, "label": label, "hide-details": "auto",
            "density": "comfortable", **props,
        },
    }]}


def _subcard(title, rows):
    return {
        "component": "VCard",
        "props": {"variant": "flat", "class": "mb-3", "border": True},
        "content": [
            {"component": "VCardTitle", "props": {
                "class": "text-subtitle-1 font-weight-bold text-primary pa-2",
            }, "text": title},
            {"component": "VCardText", "props": {"class": "px-3 pb-2 pt-0"}, "content": rows},
        ],
    }


def _control_component(control):
    if control.kind == ControlKind.SWITCH:
        body = {"component": "VSwitch", "props": {
            "model": control.key, "label": control.label, "hint": control.hint,
            "hide-details": "auto", "density": "compact",
        }}
    else:
        props = {
            "model": control.key, "label": control.label, "hint": control.hint,
            "items": control.options, "itemTitle": "label", "itemValue": "id",
            "placeholder": control.placeholder, "clearable": True,
            "hide-details": "auto", "density": "compact",
        }
        if control.kind == ControlKind.SELECT_MANY:
            props.update({"multiple": True, "chips": True})
        body = {"component": "VSelect", "props": props}
    return {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [body]}


def _site_card(option, site):
    controls = []
    for task in sorted(site.tasks, key=lambda item: _TASK_ORDER.get(item.task_type, 9)):
        controls.extend(_control_component(control) for control in task.controls(site))
    url = (option.get("site", {}).get("url") or "").strip()
    title = {"component": "VBtn", "props": {
        "href": url, "target": "_blank", "variant": "text", "color": "primary",
        "class": "text-subtitle-1 font-weight-bold pa-0 ma-0",
        "prepend-icon": "mdi-open-in-new",
    }, "text": site.site_name} if url else {"component": "span", "text": site.site_name}
    return {
        "component": "VCard", "props": {"variant": "outlined", "class": "mb-3"},
        "content": [
            {"component": "VCardTitle", "props": {
                "class": "text-subtitle-1 font-weight-bold text-primary pa-2 d-flex align-center",
            }, "content": [title]},
            {"component": "VDivider"},
            {"component": "VCardText", "content": [{
                "component": "VRow", "props": {"class": "mb-2"},
                "content": controls or [{"component": "div", "props": {
                    "class": "text-medium-emphasis pa-2",
                }, "text": "暂无任务"}],
            }]},
        ],
    }


def build_form(plugin):
    available = plugin.available_site_options()
    selected = {str(value) for value in plugin.config.site_ids}
    site_cards = []
    for option in available:
        if str(option["id"]) not in selected:
            continue
        site_cards.append(_site_card(option, plugin.build_site(option["site"])))

    base_card = _subcard("基础", [
        {"component": "VRow", "props": {"class": "mb-2"}, "content": [
            _switch("enabled", "启用插件", md=3),
            _switch("onlyonce", "立即运行一次", md=3),
            _switch("notify", "开启通知", md=3),
            _switch("use_proxy", "使用系统代理", md=3),
        ]},
        {"component": "VRow", "props": {"class": "mb-2"}, "content": [
            _text("cron", "定时规则", md=6,
                  hint="默认每天 00:04 和 12:04，例如：4 0,12 * * *"),
            _text("history_days", "历史保留天数", md=6, type="number"),
        ]},
        {"component": "VRow", "content": [{
            "component": "VCol", "props": {"cols": 12}, "content": [{
                "component": "VSelect", "props": {
                    "model": "site_ids", "label": "启用站点", "multiple": True,
                    "chips": True, "items": [
                        {"id": item["id"], "name": item["name"]} for item in available
                    ], "itemTitle": "name", "itemValue": "id", "hide-details": "auto",
                },
            }],
        }]},
    ])
    chat_card = _subcard("喊话", [{
        "component": "VRow", "content": [
            _switch("get_feedback", "获取喊话反馈", md=4),
            _text("feedback_timeout", "反馈等待秒数", md=4, type="number"),
            _text("interval", "消息间隔秒数", md=4, type="number"),
        ],
    }])
    retry_card = _subcard("重试", [{
        "component": "VRow", "content": [
            _switch("retry_notify", "重试结果通知", md=4),
            _text("retry_count", "重试次数", md=4, type="number"),
            _text("retry_interval", "重试间隔(分钟)", md=4, type="number"),
        ],
    }])

    form = [{"component": "VForm", "content": [
        {"component": "VCard", "props": {"variant": "outlined", "class": "mt-3"},
         "content": [
             {"component": "VCardTitle", "props": {
                 "class": "text-subtitle-1 py-2",
             }, "text": "全局设置"},
             {"component": "VDivider"},
             {"component": "VCardText", "props": {"class": "pt-3"},
              "content": [base_card, chat_card, retry_card]},
         ]},
        {"component": "VCard", "props": {"variant": "outlined", "class": "mt-3"},
         "content": [
             {"component": "VCardTitle", "props": {
                 "class": "text-subtitle-1 py-2",
             }, "text": "站点任务设置"},
             {"component": "VDivider"},
             {"component": "VCardText", "content": site_cards or [{
                 "component": "div", "props": {"class": "text-medium-emphasis pa-3"},
                 "text": "请先在「启用站点」选择站点",
             }]},
         ]},
    ]}]

    model = dict(plugin.raw_config)
    model.update(plugin.config.to_dict())
    model["onlyonce"] = False
    for option in available:
        site = plugin.build_site(option["site"])
        for task in site.tasks:
            for control in task.controls(site):
                default = [] if control.kind == ControlKind.SELECT_MANY else (
                    "" if control.kind == ControlKind.SELECT_ONE else False
                )
                model.setdefault(control.key, default)
    return form, model
