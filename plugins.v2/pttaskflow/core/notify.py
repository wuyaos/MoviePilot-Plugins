"""任务汇总通知。"""
from app.schemas import NotificationType


ICONS = {"上传量": "⬆️", "下载量": "⬇️", "魔力值": "✨", "VIP": "👑", "raw_feedback": "📝"}


def render_records(records):
    grouped = {}
    order = []
    for record in records:
        site = record.get("site") or "未知站点"
        if site not in grouped:
            grouped[site] = []
            order.append(site)
        icon = "✅" if record.get("success") else "❌"
        rewards = "；".join(
            f"{ICONS.get(item.get('type'), '📌')} {item.get('description', '')}".strip()
            for item in record.get("rewards") or [] if item.get("description")
        )
        detail = rewards or record.get("status") or "无详情"
        grouped[site].append(f"   {icon} {record.get('unit_label') or record.get('task_name')} -> {detail}")
    parts = []
    for site in order:
        if parts:
            parts.append("")
        parts.extend([f"🌐 {site}", *grouped[site]])
    return "\n".join(parts)


def send_summary(plugin, records, retry=False):
    if not records or not plugin.config.notify:
        return
    if retry and not plugin.config.retry_notify:
        return
    plugin.post_message(
        mtype=NotificationType.SiteMessage,
        title="PT任务流执行汇总" + ("（重试）" if retry else ""),
        text=render_records(records),
    )
