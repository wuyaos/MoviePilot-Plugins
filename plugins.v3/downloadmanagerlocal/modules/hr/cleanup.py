"""H&R 记录清理：只删除本地任务记录，不删除下载器任务与文件。"""

from __future__ import annotations

from .models import HrStatus, HrTask


def auto_cleanup(tasks: dict[str, HrTask], auto_cleanup_days: float, now: float) -> int:
    """清理已满足或已失踪超过 auto_cleanup_days 的记录，返回删除条数。"""
    if auto_cleanup_days <= 0:
        return 0
    threshold = auto_cleanup_days * 86400
    removable = [
        key
        for key, task in tasks.items()
        if not task.interlock_state and (
            task.hr_status == HrStatus.COMPLIANT
            and task.hr_met_time
            and now - task.hr_met_time > threshold
        )
        or (not task.interlock_state and task.deleted and task.deleted_time and now - task.deleted_time > threshold)
    ]
    for key in removable:
        del tasks[key]
    return len(removable)


__all__ = ("auto_cleanup",)
