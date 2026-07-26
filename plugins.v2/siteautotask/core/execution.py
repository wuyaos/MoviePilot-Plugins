"""执行单元模型与键生成。

统一单任务、CLAIM、勋章、喊话的执行键，用于当天去重和重试。
旧历史无 execution_key 时按 domain:task_id 回退。
"""
from typing import Optional


def execution_key(domain: str, task_id: str, unit_id: Optional[str] = None) -> str:
    """生成执行键：domain:task_id 或 domain:task_id:unit_id。"""
    base = f"{domain}:{task_id}"
    return f"{base}:{unit_id}" if unit_id else base


def record_execution_key(record: dict) -> str:
    """从历史记录提取执行键，旧记录回退到 domain:task_id。"""
    key = record.get("execution_key")
    if key:
        return key
    domain = record.get("domain") or ""
    task_id = record.get("task_id") or ""
    unit_id = record.get("unit_id")
    return execution_key(domain, task_id, unit_id) if unit_id else execution_key(domain, task_id)


def is_terminal_success(record: dict) -> bool:
    """判断记录是否为当天终态成功；旧记录回退到 success 字段。"""
    terminal = record.get("terminal_success")
    if terminal is not None:
        return bool(terminal)
    return bool(record.get("success"))


def is_retryable_failure(record: dict) -> bool:
    """判断记录是否为可重试的技术失败。"""
    retryable = record.get("retryable")
    if retryable is not None:
        return bool(retryable) and not record.get("success")
    return not record.get("success")
