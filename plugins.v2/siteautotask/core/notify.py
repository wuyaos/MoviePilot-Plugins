"""通知渲染与发送。"""
from ..utils.feedback import NotificationIcons


def render_records(records):
    grouped = {}
    order = []
    for record in records:
        site = record.get("site") or "未知站点"
        if site not in grouped:
            grouped[site] = []
            order.append(site)
        icon = "✅" if record.get("success") else "❌"
        line = f"{icon} {record.get('task_label') or record.get('task_id')}: {record.get('status', '')}"
        feedback = record.get("feedback") or {}
        rewards = feedback.get("rewards") or record.get("rewards") or []
        for reward in rewards:
            line += f"\n  {NotificationIcons.get(reward.get('type', ''))} {reward.get('description', '')}"
        grouped[site].append(line)
    parts = []
    for site in order:
        parts.extend([f"🔔 {site}", *grouped[site], "────────────────────"])
    if parts and parts[-1].startswith("─"):
        parts.pop()
    return "\n".join(parts)


def send_summary(plugin, records):
    if records and plugin.config.notify:
        plugin.post_message(
            mtype=plugin.notification_type,
            title="站点自动任务执行汇总",
            text=render_records(records),
        )
