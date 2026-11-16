"""媒体服务器增强 - 运行历史与快照持久化。

所有键都通过 ``plugin.save_data`` / ``plugin.get_data`` 写入插件私有存储，
宿主会按插件 ID 隔离，插件之间不会互相覆盖。
"""

from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

# 任务记录（所有模块共用一条时间线）
JOBS_KEY = "job_history"
# 最近一次体检报告
AUDIT_REPORT_KEY = "audit_report"
# 最近一次服务端能力探测结果
CAPABILITIES_KEY = "capabilities_snapshot"
# 封面生成历史
COVER_HISTORY_KEY = "cover_history"
# 刷新运行态（最近刷新时间、待处理批次）
REFRESH_STATE_KEY = "refresh_state"
# 最近媒体服务器 webhook 事件（只记录不动作）
WEBHOOK_KEY = "webhook_events"
# webhook 事件保留条数（与 AGENTS.md/提交说明口径一致）
WEBHOOK_LIMIT = 50

DEFAULT_HISTORY_LIMIT = 300


def now_text() -> str:
    """返回当前时间的展示文本。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_text() -> str:
    """返回当前日期文本，用于同一天任务统计。"""
    return datetime.now().strftime("%Y-%m-%d")


def new_job_id() -> str:
    """生成任务记录标识。"""
    return uuid.uuid4().hex[:16]


def read_value(plugin, key: str, default: Any = None) -> Any:
    """读取插件私有存储中的值。

    :param plugin: 插件实例
    :param key: 存储键
    :param default: 读取失败或为空时的回退值
    :return: 存储内容
    """
    try:
        value = plugin.get_data(key)
    except Exception:  # noqa: BLE001 - 存储异常不应中断页面渲染
        return default
    return default if value is None else value


def write_value(plugin, key: str, value: Any) -> None:
    """写入插件私有存储。

    :param plugin: 插件实例
    :param key: 存储键
    :param value: 可 JSON 序列化的值
    """
    try:
        plugin.save_data(key, value)
    except Exception:  # noqa: BLE001 - 存储异常不应中断业务主流程
        pass


def load_jobs(plugin) -> List[Dict[str, Any]]:
    """读取任务记录列表。"""
    value = read_value(plugin, JOBS_KEY, [])
    return value if isinstance(value, list) else []


def append_job(plugin, job: Dict[str, Any], limit: int = DEFAULT_HISTORY_LIMIT) -> None:
    """把一条任务记录追加到时间线并裁剪历史长度。

    :param plugin: 插件实例
    :param job: 任务记录字典
    :param limit: 保留的最大记录数
    """
    # 任务时间线由并发事件线程与定时任务共同写入，read-modify-write 全程持锁
    with _plugin_lock(plugin, "_jobs_lock"):
        jobs = load_jobs(plugin)
        jobs.insert(0, job)
        keep = limit if limit and limit > 0 else DEFAULT_HISTORY_LIMIT
        write_value(plugin, JOBS_KEY, jobs[:keep])


def clear_jobs(plugin, module: str = "") -> int:
    """清空任务记录。

    :param plugin: 插件实例
    :param module: 只清理指定模块，空串表示全部
    :return: 被清理的记录数
    """
    with _plugin_lock(plugin, "_jobs_lock"):
        jobs = load_jobs(plugin)
        if not module:
            write_value(plugin, JOBS_KEY, [])
            return len(jobs)
        remaining = [job for job in jobs if job.get("module") != module]
        write_value(plugin, JOBS_KEY, remaining)
    return len(jobs) - len(remaining)


def today_job_stats(plugin) -> Dict[str, int]:
    """统计当天的任务数与失败数。

    :param plugin: 插件实例
    :return: 含 today 与 failed 的计数字典
    """
    today = today_text()
    today_count = 0
    failed_count = 0
    for job in load_jobs(plugin):
        started = str(job.get("started_at") or "")
        if started.startswith(today):
            today_count += 1
        if job.get("status") == "failed":
            failed_count += 1
    return {"today": today_count, "failed": failed_count}


def build_job(module: str, action: str, trigger: str = "", **fields: Any) -> Dict[str, Any]:
    """构造一条标准任务记录。

    :param module: 模块键
    :param action: 动作名
    :param trigger: 触发来源
    :param fields: 附加字段，覆盖默认值
    :return: 任务记录字典
    """
    job: Dict[str, Any] = {
        "job_id": new_job_id(),
        "module": module,
        "action": action,
        "trigger": trigger,
        "status": "running",
        "message": "",
        "server": "",
        "library": "",
        "total": 0,
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "started_at": now_text(),
        "finished_at": "",
        "detail": {},
    }
    job.update(fields or {})
    return job


def finish_job(job: Dict[str, Any], status: str, message: str = "", **counts: int) -> Dict[str, Any]:
    """补齐任务记录的结束状态并返回同一字典。

    :param job: 任务记录字典
    :param status: 终态，``success`` / ``failed`` / ``skipped``
    :param message: 结果说明
    :param counts: 成功、失败、跳过计数
    :return: 更新后的任务记录
    """
    job["status"] = status
    job["message"] = message
    job["finished_at"] = now_text()
    for key, value in (counts or {}).items():
        if key in {"total", "success", "failed", "skipped"} and value is not None:
            job[key] = int(value)
    return job


def elapsed_ms(started: float) -> int:
    """把起始时间戳换算为已耗时毫秒。

    :param started: ``time.time()`` 起始值
    :return: 非负毫秒数
    """
    return max(0, int((time.time() - started) * 1000))


def read_snapshot(plugin, key: str) -> Dict[str, Any]:
    """读取字典型快照。

    :param plugin: 插件实例
    :param key: 存储键
    :return: 快照字典，缺失或类型不符时返回空字典
    """
    value = read_value(plugin, key, {})
    return value if isinstance(value, dict) else {}


def merge_history(existing: List[Dict[str, Any]], entry: Dict[str, Any],
                  limit: int = 200) -> List[Dict[str, Any]]:
    """把新记录插入历史列表头部并裁剪长度。

    :param existing: 既有历史列表
    :param entry: 新记录
    :param limit: 保留条数上限
    :return: 新的历史列表
    """
    rows = [entry, *(existing or [])]
    return rows[: max(1, limit)]


def read_list(plugin, key: str) -> List[Dict[str, Any]]:
    """读取列表型快照。

    :param plugin: 插件实例
    :param key: 存储键
    :return: 列表，缺失或类型不符时返回空列表
    """
    value = read_value(plugin, key, [])
    return value if isinstance(value, list) else []


def first_text(*values: Optional[Any]) -> str:
    """按顺序返回第一个非空文本。

    :param values: 候选值
    :return: 首个非空文本，全部为空时返回空串
    """
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def record_webhook(plugin, entry: Dict[str, Any]) -> None:
    """记录一条媒体服务器 webhook 事件，超出上限时裁剪。

    webhook 只做记录与展示，本插件不基于 webhook 执行删除等破坏性动作。
    事件线程可能并发触发，read-modify-write 全程持实例级锁。

    :param plugin: 插件实例
    :param entry: ``{time, channel, event, summary}`` 字典
    """
    with _plugin_lock(plugin, "_webhook_lock"):
        rows = read_list(plugin, WEBHOOK_KEY)
        write_value(plugin, WEBHOOK_KEY, merge_history(rows, entry, WEBHOOK_LIMIT))


def _plugin_lock(plugin, attr: str):
    """返回挂在插件实例上的互斥锁，缺失时创建（模块级读改写保护）。"""
    lock = getattr(plugin, attr, None)
    if lock is None:
        lock = threading.RLock()
        setattr(plugin, attr, lock)
    return lock


def read_webhooks(plugin) -> List[Dict[str, Any]]:
    """读取最近记录的 webhook 事件列表。

    :param plugin: 插件实例
    :return: 事件字典列表，最新在前
    """
    return read_list(plugin, WEBHOOK_KEY)
