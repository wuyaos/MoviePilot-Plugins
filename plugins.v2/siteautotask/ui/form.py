"""按站点分组、每任务独立开关的配置页。"""
from typing import Dict, List, Tuple
try:
    from ..core.task_keys import site_task_key, claim_task_key
except ImportError:  # 便于脱离 MoviePilot 包环境做单元测试
    from siteautotask_task_keys import site_task_key, claim_task_key

# 任务类型固定排序：开关类在前，CLAIM 下拉垫底
_TASK_TYPE_ORDER = {
    "checkin": 0, "chat": 1, "exchange": 2, "medal": 3, "lottery": 4, "generic": 5, "claim": 9,
}


def _task_sort_key(task):
    return (_TASK_TYPE_ORDER.get(task.get("task_type", "generic"), 6), task.get("name", ""))


def _switch(model, label, md=3, **props):
    return {"component": "VCol", "props": {"cols": 12, "md": md},
            "content": [{"component": "VSwitch", "props": {"model": model, "label": label, "hide-details": "auto", "density": "comfortable", **props}}]}


def _text(model, label, md=3, **props):
    return {"component": "VCol", "props": {"cols": 12, "md": md},
            "content": [{"component": "VTextField", "props": {"model": model, "label": label, "hide-details": "auto", "density": "comfortable", **props}}]}


def _subcard(title, rows):
    """全局设置内的嵌套小卡片。"""
    return {
        "component": "VCard",
        "props": {"variant": "flat", "class": "mb-3", "border": True},
        "content": [
            {"component": "VCardTitle", "props": {"class": "text-subtitle-1 font-weight-bold text-primary pa-2"}, "text": title},
            {"component": "VCardText", "props": {"class": "px-3 pb-2 pt-0"}, "content": rows},
        ],
    }


def build_form(plugin) -> Tuple[List[dict], Dict]:
    sites = plugin.support_site_options()

    site_cards = []
    for site in sites:
        if site.get("id") not in set(plugin.config.chat_sites):
            continue
        tasks = site.get("tasks") or []
        site_name = site.get("name", "未知站点")
        site_url = (site.get("url") or "").strip()
        task_cols = []
        for task in sorted(tasks, key=_task_sort_key):
            if task.get("task_type") in ("claim", "medal") and task.get("claim_options"):
                # CLAIM 任务单选下拉；MEDAL 任务按 claim_multiple 决定是否多选
                is_multiple = bool(task.get("claim_multiple"))
                select_props = {
                    "model": claim_task_key(site, task), "label": task.get("label", task["id"]),
                    "hide-details": "auto",
                    "items": task.get("claim_options", []), "itemTitle": "label", "itemValue": "id",
                    "clearable": True, "placeholder": "不购买" if is_multiple else "不申领",
                }
                if is_multiple:
                    select_props["multiple"] = True
                    select_props["chips"] = True
                task_cols.append({
                    "component": "VCol", "props": {"cols": 12, "md": 4},
                    "content": [{"component": "VSelect", "props": select_props}],
                })
            else:
                task_cols.append({
                    "component": "VCol", "props": {"cols": 12, "md": 4},
                    "content": [{"component": "VSwitch", "props": {
                        "model": site_task_key(site, task), "label": task.get("label", task["id"]),
                        "hint": task.get("hint", ""), "density": "compact", "hide-details": "auto"}}],
                })
        site_cards.append({
            "component": "VCard",
            "props": {"variant": "outlined", "class": "mb-3"},
            "content": [
                {"component": "VCardTitle", "props": {"class": "text-subtitle-1 font-weight-bold text-primary pa-2 d-flex align-center"},
                 "content": [
                     {"component": "VBtn", "props": {
                         "href": site_url, "target": "_blank", "variant": "text",
                         "color": "primary", "class": "text-subtitle-1 font-weight-bold pa-0 ma-0",
                         "prepend-icon": "mdi-open-in-new",
                     }, "text": site_name} if site_url else
                     {"component": "span", "text": site_name},
                 ]},
                {"component": "VDivider"},
                {"component": "VCardText", "content": [{
                    "component": "VRow", "props": {"class": "mb-2"},
                    "content": task_cols or [{"component": "div", "props": {"class": "text-medium-emphasis pa-2"}, "text": "暂无任务"}],
                }]},
            ],
        })

    # 基础子卡片
    base_card = _subcard("基础", [
        {"component": "VRow", "props": {"class": "mb-2"}, "content": [
            _switch("enabled", "启用插件", md=3), _switch("onlyonce", "立即运行一次", md=3),
            _switch("notify", "开启通知", md=3), _switch("use_proxy", "使用系统代理", md=3),
        ]},
        {"component": "VRow", "props": {"class": "mb-2"}, "content": [
            _text("cron", "定时规则", md=4, hint="例如：30 9,21 * * *"),
            _text("medal_cron", "勋章续购定时", md=4, hint="留空=跟随主定时；例如：0 8 * * *"),
            _text("history_days", "历史保留天数", md=4, type="number"),
        ]},
        {"component": "VRow", "content": [
            {"component": "VCol", "props": {"cols": 12}, "content": [{"component": "VSelect", "props": {
                "model": "chat_sites", "label": "启用站点", "multiple": True, "chips": True,
                "items": sites, "itemTitle": "name", "itemValue": "id", "hide-details": "auto"}}]},
        ]},
    ])

    # 喊话子卡片
    chat_card = _subcard("喊话", [
        {"component": "VRow", "content": [
            _switch("get_feedback", "获取喊话反馈", md=4),
            _text("feedback_timeout", "反馈等待秒数", md=4, type="number"),
            _text("interval_cnt", "消息间隔秒数", md=4, type="number"),
        ]},
        {"component": "VRow", "props": {"class": "mb-2"}, "content": [
            _text("zm_cooldown", "织梦冷却(秒)", md=4, type="number", hint="织梦喊话24h调度的短时冷却，防止重复触发，默认3600"),
        ]},
    ])

    # 重试子卡片
    retry_card = _subcard("重试", [
        {"component": "VRow", "content": [
            _switch("retry_notify", "重试结果通知", md=4),
            _text("retry_count", "重试次数", md=4, type="number"),
            _text("retry_interval", "重试间隔(分钟)", md=4, type="number"),
        ]},
    ])

    site_section_content = site_cards if site_cards else [{"component": "div", "props": {"class": "text-medium-emphasis pa-3"}, "text": "请先在「启用站点」选择站点"}]

    form = [{
        "component": "VForm",
        "content": [{
            "component": "VCard",
            "props": {"variant": "outlined", "class": "mt-3"},
            "content": [
                {"component": "VCardTitle", "props": {"class": "text-subtitle-1 py-2"}, "text": "全局设置"},
                {"component": "VDivider"},
                {"component": "VCardText", "props": {"class": "pt-3"}, "content": [base_card, chat_card, retry_card]},
            ],
        }, {
            "component": "VCard",
            "props": {"variant": "outlined", "class": "mt-3"},
            "content": [
                {"component": "VCardTitle", "props": {"class": "text-subtitle-1 py-2"}, "text": "站点任务设置"},
                {"component": "VDivider"},
                {"component": "VCardText", "content": site_section_content},
            ],
        }],
    }]
    # 预置所有可配置任务的默认值，确保前端表单 model 完整
    model = plugin.config.to_dict()
    for site in sites:
        for task in site.get("tasks") or []:
            if task.get("task_type") in ("claim", "medal") and task.get("claim_options"):
                model.setdefault(claim_task_key(site, task), [] if task.get("claim_multiple") else "")
            else:
                model.setdefault(site_task_key(site, task), False)
    return form, model
