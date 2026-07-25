"""任务展示文本规范化。"""
import re

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
    """输出带方括号类型、且不重复站点名的任务名称。"""
    name = display_task_name(site_name, task_label)
    if not task_type:
        return name
    type_label = TASK_TYPE_LABELS.get(str(task_type).lower(), "任务")
    return f"[{type_label}] {name}"


def display_reward_text(rewards, icon_lookup):
    """保留原始反馈文本，并在前方加奖励类型图标。"""
    return "；".join(
        f"{icon_lookup.get(item.get('type', ''))} {item.get('description', '')}".strip()
        for item in rewards or []
        if item.get("description")
    )


def format_record_line(item, icon_lookup):
    """将拆分后的任务项格式化为统一的“任务 -> 结果”文本。"""
    reward_text = display_reward_text(item.get("rewards"), icon_lookup)
    suffix = reward_text or str(item.get("status") or "") or "无反馈"
    return f"{item['task']} -> {suffix}"


def display_record_lines(record):
    """拆分一条执行记录为展示行；多条喊话逐句呈现反馈。"""
    site = record.get("site") or ""
    task_type = str(record.get("task_type") or "").lower()
    rewards = (record.get("feedback") or {}).get("rewards") or record.get("rewards") or []
    if task_type != "chat":
        return [{
            "task": display_task(site, record.get("task_label") or record.get("task_id"), task_type),
            "status": str(record.get("status") or ""),
            "rewards": rewards,
        }]

    messages = list(record.get("messages") or [])
    if not messages:
        matched = re.search(r'已发送“(.+)”', str(record.get("status") or ""))
        messages = matched.group(1).split("；") if matched else []
    if not messages:
        return [{"task": "[喊话]", "status": "无反馈", "rewards": rewards}]

    mapped_rewards = {message: [] for message in messages}
    remaining_rewards = []
    for reward in rewards:
        description = str(reward.get("description") or "")
        matched_message = next(
            (message for message in messages if description.startswith(f"“{message}”：")),
            None,
        )
        if matched_message:
            copied = dict(reward)
            copied["description"] = description[len(matched_message) + 3:]
            mapped_rewards[matched_message].append(copied)
        else:
            remaining_rewards.append(reward)
    if remaining_rewards:
        mapped_rewards[messages[-1]].extend(remaining_rewards)

    return [{
        "task": f"[喊话] “{message}”",
        "status": "" if mapped_rewards[message] else "无反馈",
        "rewards": mapped_rewards[message],
    } for message in messages]
