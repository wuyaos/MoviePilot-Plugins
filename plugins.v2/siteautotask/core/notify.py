"""通知渲染与发送。"""
from ..utils.feedback import NotificationIcons
from ..utils.display import display_record_lines, format_record_line


def render_records(records):
    """按站点两级分组；多消息喊话拆成独立任务行。"""
    grouped = {}
    order = []
    for record in records:
        site = record.get("site") or "未知站点"
        if site not in grouped:
            grouped[site] = []
            order.append(site)
        icon = "✅" if record.get("success") else "❌"
        for item in display_record_lines(record):
            grouped[site].append(
                f"   {icon} {format_record_line(item, NotificationIcons)}"
            )
    parts = []
    for site in order:
        if parts:
            parts.append("")
        parts.extend([f"🌐 {site}", *grouped[site]])
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
