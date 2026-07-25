"""通知渲染与发送。"""
from ..utils.feedback import NotificationIcons
from ..utils.display import display_task


def render_records(records):
    grouped = {}
    order = []
    for record in records:
        site = record.get("site") or "未知站点"
        if site not in grouped:
            grouped[site] = []
            order.append(site)
        icon = "✅" if record.get("success") else "❌"
        task_name = display_task(
            site,
            record.get("task_label") or record.get("task_id"),
            record.get("task_type"),
        )
        line = f"{icon} {task_name}：{record.get('status', '')}"
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


def send_summary(plugin, records, is_retry=False):
    """发送任务汇总通知。

    is_retry=True 时仅当 retry_notify 开启才发送，避免重试轰炸。
    """
    if not records:
        return
    if not plugin.config.notify:
        return
    if is_retry and not plugin.config.retry_notify:
        return
    plugin.post_message(
        mtype=plugin.notification_type,
        title="站点自动任务执行汇总" + ("（重试）" if is_retry else ""),
        text=render_records(records),
    )
