"""任务展示文本规范化。"""

TASK_TYPE_LABELS = {
    "checkin": "签到",
    "chat": "喊话",
    "claim": "申领",
    "exchange": "兑换",
    "medal": "勋章",
    "lottery": "抽奖",
    "generic": "任务",
}


def display_task_name(site_name, task_label):
    """移除任务标签开头重复的站点名。"""
    site = str(site_name or "").strip()
    label = str(task_label or "").strip()
    if not site or not label or not label.casefold().startswith(site.casefold()):
        return label
    short_name = label[len(site):].lstrip(" -_/：:")
    return short_name or label


def display_task(site_name, task_label, task_type):
    """输出不重复站点名和任务类型的展示名称。"""
    name = display_task_name(site_name, task_label)
    if not task_type:
        return name
    type_label = TASK_TYPE_LABELS.get(str(task_type).lower(), "任务")
    if any(label in name for label in TASK_TYPE_LABELS.values()):
        return name
    return f"[{type_label}] {name}"
