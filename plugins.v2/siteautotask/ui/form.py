"""按站点分组、每任务独立开关的配置页。"""
from typing import Dict, List, Tuple
try:
    from ..core.task_keys import site_task_key
except ImportError:  # 便于脱离 MoviePilot 包环境做单元测试
    from siteautotask_task_keys import site_task_key


def build_form(plugin) -> Tuple[List[dict], Dict]:
    sites = plugin.support_site_options()
    selected = set(plugin.config.chat_sites)

    site_cards = []
    for site in sites:
        if site.get("id") not in selected:
            continue
        tasks = site.get("tasks") or []
        site_name = site.get("name", "未知站点")

        # 任务开关：每行 3 个
        task_cols = []
        for task in tasks:
            task_cols.append({
                "component": "VCol",
                "props": {"cols": 12, "md": 4},
                "content": [{
                    "component": "VSwitch",
                    "props": {
                        "model": site_task_key(site, task),
                        "label": task.get("label", task["id"]),
                        "hint": task.get("hint", ""),
                        "density": "compact",
                        "hide-details": "auto",
                    },
                }],
            })

        site_cards.append({
            "component": "VCard",
            "props": {"variant": "outlined", "class": "mb-3"},
            "content": [
                {"component": "VCardTitle", "props": {"class": "text-subtitle-1 py-2"}, "text": site_name},
                {"component": "VDivider"},
                {"component": "VCardText", "content": [{
                    "component": "VRow",
                    "props": {"dense": True},
                    "content": task_cols or [{"component": "div", "props": {"class": "text-medium-emphasis pa-2"}, "text": "暂无任务"}],
                }]},
            ],
        })

    # 全局开关：全部放一起
    switches = [
        ("enabled", "启用插件"),
        ("notify", "开启通知"),
        ("retry_notify", "重试结果通知"),
        ("get_feedback", "获取喊话反馈"),
        ("use_proxy", "使用系统代理"),
        ("onlyonce", "立即运行一次"),
    ]
    switch_cols = [{
        "component": "VCol",
        "props": {"cols": 12, "md": 2},
        "content": [{"component": "VSwitch", "props": {"model": m, "label": l, "density": "compact", "hide-details": "auto"}}],
    } for m, l in switches]

    # 文本类配置
    text_cols = [
        {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [{"component": "VTextField", "props": {"model": "cron", "label": "定时规则", "hint": "例如：30 9,21 * * *", "density": "compact", "hide-details": "auto"}}]},
        {"component": "VCol", "props": {"cols": 12, "md": 2}, "content": [{"component": "VTextField", "props": {"model": "history_days", "label": "历史保留天数", "type": "number", "density": "compact", "hide-details": "auto"}}]},
        {"component": "VCol", "props": {"cols": 12, "md": 2}, "content": [{"component": "VTextField", "props": {"model": "feedback_timeout", "label": "反馈等待秒数", "type": "number", "density": "compact", "hide-details": "auto"}}]},
        {"component": "VCol", "props": {"cols": 12, "md": 2}, "content": [{"component": "VTextField", "props": {"model": "retry_count", "label": "重试次数", "type": "number", "density": "compact", "hide-details": "auto"}}]},
        {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [{"component": "VTextField", "props": {"model": "retry_interval", "label": "重试间隔(分钟)", "type": "number", "density": "compact", "hide-details": "auto"}}]},
    ]

    site_section_content = site_cards if site_cards else [{"component": "div", "props": {"class": "text-medium-emphasis pa-3"}, "text": "请先在「启用站点」选择站点"}]

    form = [{
        "component": "VForm",
        "content": [{
            "component": "VCard",
            "props": {"variant": "outlined", "class": "mt-3"},
            "content": [
                {"component": "VCardTitle", "props": {"class": "text-subtitle-1 py-2"}, "text": "全局设置"},
                {"component": "VDivider"},
                {"component": "VCardText", "content": [
                    {"component": "VRow", "props": {"dense": True}, "content": switch_cols},
                    {"component": "VRow", "props": {"dense": True}, "content": text_cols},
                    {"component": "VRow", "props": {"dense": True}, "content": [
                        {"component": "VCol", "props": {"cols": 12}, "content": [{"component": "VSelect", "props": {"model": "chat_sites", "label": "启用站点", "multiple": True, "chips": True, "items": sites, "itemTitle": "name", "itemValue": "id", "density": "compact", "hide-details": "auto"}}]},
                    ]},
                ]},
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
    # 预置所有可配置任务开关的默认值，确保前端表单 model 完整
    model = plugin.config.to_dict()
    for site in sites:
        for task in site.get("tasks") or []:
            model.setdefault(site_task_key(site, task), False)
    return form, model
