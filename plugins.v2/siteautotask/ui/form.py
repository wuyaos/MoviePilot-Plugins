"""按站点分组、每任务独立开关的配置页。"""
from typing import Dict, List, Tuple
try:
    from ..core.task_keys import site_task_key
except ImportError:  # 便于脱离 MoviePilot 包环境做单元测试
    from siteautotask_task_keys import site_task_key


def build_form(plugin) -> Tuple[List[dict], Dict]:
    sites = plugin.support_site_options()
    selected = set(plugin.config.chat_sites)
    site_sections = []
    for site in sites:
        if site.get("id") not in selected:
            continue
        task_rows = []
        tasks = site.get("tasks") or []
        for i in range(0, len(tasks), 3):
            group = tasks[i:i + 3]
            task_rows.append({
                "component": "VRow",
                "props": {"align": "center"},
                "content": [{
                    "component": "VCol",
                    "props": {"cols": 12, "md": max(3, 12 // len(group))},
                    "content": [{
                        "component": "VSwitch",
                        "props": {
                            "model": f"task_switches.{site_task_key(site, task)}",
                            "label": task.get("label", task["id"]),
                            "hint": task.get("hint", ""),
                        },
                    }],
                } for task in group],
            })
        site_sections.append({
            "component": "VCard",
            "props": {"variant": "outlined", "class": "mb-3"},
            "content": [
                {"component": "VCardTitle", "text": f"{site.get('name', '未知站点')} 任务设置"},
                {"component": "VCardText", "content": task_rows or [{"component": "div", "text": "暂无任务"}]},
            ],
        })

    fields = [
        ("enabled", "启用插件", "VSwitch"),
        ("notify", "开启通知", "VSwitch"),
        ("onlyonce", "立即运行一次", "VSwitch"),
        ("get_feedback", "获取喊话反馈", "VSwitch"),
        ("use_proxy", "使用系统代理", "VSwitch"),
    ]
    basics = []
    for model, label, component in fields:
        basics.append({
            "component": "VCol", "props": {"cols": 12, "md": 3},
            "content": [{"component": component, "props": {"model": model, "label": label}}],
        })

    form = [{
        "component": "VForm",
        "content": [
            {"component": "VCard", "props": {"variant": "outlined", "class": "mt-3"}, "content": [
                {"component": "VCardTitle", "text": "全局设置"},
                {"component": "VDivider"},
                {"component": "VCardText", "content": [
                    {"component": "VRow", "content": basics},
                    {"component": "VRow", "content": [
                        {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [{"component": "VTextField", "props": {"model": "cron", "label": "定时规则", "hint": "例如：30 9,21 * * *"}}]},
                        {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [{"component": "VTextField", "props": {"model": "history_days", "label": "历史保留天数", "type": "number"}}]},
                        {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [{"component": "VTextField", "props": {"model": "feedback_timeout", "label": "反馈等待秒数", "type": "number"}}]},
                    ]},
                    {"component": "VRow", "content": [{"component": "VCol", "props": {"cols": 12}, "content": [{"component": "VSelect", "props": {"model": "chat_sites", "label": "启用站点", "multiple": True, "chips": True, "items": sites, "itemTitle": "name", "itemValue": "id"}}]}]},
                ]},
            ]},
            {"component": "VCard", "props": {"variant": "outlined", "class": "mt-3"}, "content": [{"component": "VCardTitle", "text": "站点任务设置"}, {"component": "VCardText", "content": site_sections or [{"component": "div", "text": "请先选择站点"}]}]},
        ],
    }]
    return form, plugin.config.to_dict()
