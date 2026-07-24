"""运行数据页：任务状态与反馈奖励一体展示。"""
from ..utils.feedback import NotificationIcons


def _text(value):
    return "" if value is None else str(value)


def build_page(plugin):
    history = plugin.history.latest(10)
    rows = []
    for run in history:
        for record in run.get("records", []):
            feedback = record.get("feedback") or {}
            rewards = feedback.get("rewards") or record.get("rewards") or []
            reward_text = "；".join(
                f"{NotificationIcons.get(r.get('type', ''))} {_text(r.get('description'))}"
                for r in rewards
            )
            rows.append({
                "date": run.get("date") or record.get("date"),
                "site": record.get("site"),
                "task": record.get("task_label") or record.get("task_id"),
                "status": ("成功" if record.get("success") else "失败") + "：" + _text(record.get("status")),
                "feedback": reward_text,
            })

    headers = [
        {"title": "时间", "key": "date"},
        {"title": "站点", "key": "site"},
        {"title": "任务", "key": "task"},
        {"title": "状态", "key": "status"},
        {"title": "反馈奖励", "key": "feedback"},
    ]
    return [{
        "component": "VCard",
        "props": {"class": "mt-3"},
        "content": [
            {"component": "VCardTitle", "text": "站点任务运行历史"},
            {"component": "VCardText", "content": [{
                "component": "VDataTable",
                "props": {"headers": headers, "items": rows, "itemsPerPage": 20, "density": "compact"},
            }]},
        ],
    }]
