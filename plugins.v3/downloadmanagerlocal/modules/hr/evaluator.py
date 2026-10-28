"""H&R 达标判定：站点要求初始化与状态流转。"""

from __future__ import annotations

from typing import Optional

from .models import HrSiteRule, HrStatus, HrTask
from .rules import match_size_tier


def initialize_requirements(task: HrTask, rule: HrSiteRule) -> None:
    """按站点规则填充任务要求：分档命中时以分档为准，规则未提供的字段保持任务已有要求。"""
    tier = match_size_tier(rule, task.size)
    if tier:
        task.hr_duration = tier.hr_duration
        task.hr_deadline_days = tier.hr_deadline_days
    else:
        if rule.hr_duration is not None:
            task.hr_duration = rule.hr_duration
        if rule.hr_deadline_days is not None:
            task.hr_deadline_days = rule.hr_deadline_days
    if rule.additional_seed_time is not None:
        task.additional_seed_time = rule.additional_seed_time
    if rule.hr_ratio is not None:
        task.hr_ratio = rule.hr_ratio
    if rule.hr_upload_multiplier is not None:
        task.hr_upload_multiplier = rule.hr_upload_multiplier
    if rule.hr_upload_gte_download is not None:
        task.hr_upload_gte_download = rule.hr_upload_gte_download


def evaluate_task(task: HrTask, rule: HrSiteRule, now: float) -> Optional[HrStatus]:
    """判定任务状态；仅返回发生跃迁后的新状态，终态或状态未变化返回 None。"""
    if not task.hit_and_run:
        return None
    if task.hr_status not in (HrStatus.PENDING, HrStatus.IN_PROGRESS, HrStatus.NEEDS_SEEDING):
        return None
    initialize_requirements(task, rule)
    if task.meets_hr():
        new_status = HrStatus.COMPLIANT
    elif task.hr_deadline_days and task.hr_deadline_days > 0 and now > task.deadline_time:
        new_status = HrStatus.OVERDUE
    elif task.deleted:
        new_status = HrStatus.NEEDS_SEEDING
    else:
        new_status = HrStatus.IN_PROGRESS
    if new_status == task.hr_status:
        return None
    task.hr_status = new_status
    if new_status == HrStatus.COMPLIANT:
        task.hr_met_time = now
    return new_status


def seeding_progress(task: HrTask) -> float:
    """返回做种进度（0~1）：已做种时长与要求做种时长之比；无时长要求时按是否达标取值。"""
    required = task.required_hours()
    if required <= 0:
        return 1.0 if task.hr_status == HrStatus.COMPLIANT else 0.0
    return min((task.seeding_time or 0) / (required * 3600), 1.0)


__all__ = ("evaluate_task", "initialize_requirements", "seeding_progress")
