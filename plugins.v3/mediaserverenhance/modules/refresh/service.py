"""服务器与刷新模块。

负责入库后刷新、最近媒体刷新、定时补扫与手动刷新，并把每次执行写入统一任务时间线。
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

from app.sdk.logging import logger

from ...adapter import mediaserver
from ...utils import store
from ...utils.config import as_bool, as_list, safe_int, servers_allowed
from ...utils.runtime import observe_only

MODULE = "refresh"

# 同一进程内最多累积的待刷新条目，防止事件风暴撑爆内存
MAX_PENDING_ITEMS = 500


def _pending(plugin) -> Dict[str, Dict[str, Any]]:
    """返回实例级待刷新条目缓冲。"""
    pending = getattr(plugin, "_refresh_pending", None)
    if not isinstance(pending, dict):
        pending = {}
        plugin._refresh_pending = pending
    return pending


def _lock(plugin) -> threading.RLock:
    """返回实例级刷新缓冲锁。"""
    lock = getattr(plugin, "_refresh_lock", None)
    if lock is None:
        lock = threading.RLock()
        plugin._refresh_lock = lock
    return lock


def configured_servers(plugin, override: Optional[List[str]] = None) -> List[str]:
    """解析本次刷新涉及的服务器清单。

    :param plugin: 插件实例
    :param override: 调用方显式指定的服务器，优先于配置
    :return: 去重后的服务器名称列表
    """
    names = as_list(override) or as_list(getattr(plugin, "_refresh_servers", None))
    if names:
        return names
    return [row["name"] for row in mediaserver.list_server_configs() if row.get("enabled")]


def enabled_servers(plugin, override: Optional[List[str]] = None) -> List[str]:
    """返回过滤掉已停用项后的服务器清单。

    :param plugin: 插件实例
    :param override: 调用方显式指定的服务器
    :return: 可参与刷新的服务器名称列表
    """
    known = {row["name"]: row for row in mediaserver.list_server_configs(include_disabled=True)}
    result: List[str] = []
    for name in configured_servers(plugin, override):
        row = known.get(name)
        if not row:
            continue
        if not servers_allowed(as_list(getattr(plugin, "_refresh_servers", None)), name):
            continue
        if not row.get("enabled") and not override:
            continue
        result.append(name)
    return result


def build_payload_from_event(event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """从入库事件数据构造刷新请求。

    :param event_data: ``TransferComplete`` 的 ``event_data``
    :return: 刷新请求字典；缺少媒体信息时返回 None
    """
    if not isinstance(event_data, dict):
        return None
    media = event_data.get("mediainfo")
    if not media:
        return None
    transfer = event_data.get("transferinfo")
    target_dir = getattr(transfer, "target_diritem", None) if transfer else None
    target_item = getattr(transfer, "target_item", None) if transfer else None
    path = ""
    for candidate in (target_dir, target_item):
        candidate_path = getattr(candidate, "path", None) if candidate else None
        if candidate_path:
            path = str(candidate_path)
            break
    media_type = getattr(media, "type", None)
    type_text = getattr(media_type, "value", None) or str(media_type or "")
    return {
        "title": getattr(media, "title", "") or "",
        "year": getattr(media, "year", "") or "",
        "type": type_text,
        "category": getattr(media, "category", "") or "",
        "path": path,
    }


def enqueue_transfer(plugin, event_data: Dict[str, Any]) -> None:
    """把一次入库事件并入防抖缓冲，并在窗口结束后统一刷新。

    :param plugin: 插件实例
    :param event_data: ``TransferComplete`` 的 ``event_data``
    """
    if not as_bool(getattr(plugin, "_refresh_on_transfer", True)):
        return
    payload = build_payload_from_event(event_data)
    if not payload:
        return
    key = "|".join(
        str(payload.get(field) or "")
        for field in ("title", "year", "type", "path")
    )
    with _lock(plugin):
        pending = _pending(plugin)
        if len(pending) >= MAX_PENDING_ITEMS:
            logger.warning("【媒体服务器增强】待刷新条目超过上限，丢弃最旧的一条")
            oldest = next(iter(pending), None)
            if oldest is not None:
                pending.pop(oldest, None)
        pending[key] = payload
    schedule_flush(plugin)


def schedule_flush(plugin) -> None:
    """安排一次防抖刷新，重复调用会顺延窗口。

    :param plugin: 插件实例
    """
    window = safe_int(getattr(plugin, "_refresh_debounce_seconds", 30), 30, 0, 3600)
    timer = getattr(plugin, "_refresh_timer", None)
    if timer is not None:
        try:
            timer.cancel()
        except Exception:  # noqa: BLE001 - 已触发的定时器取消失败不影响新窗口
            pass
    new_timer = threading.Timer(max(1, window), _flush_callback, args=(plugin,))
    new_timer.daemon = True
    plugin._refresh_timer = new_timer
    new_timer.start()


def _flush_callback(plugin) -> None:
    """定时器回调：把缓冲条目提交为一次刷新任务。"""
    try:
        flush_pending(plugin, trigger="入库事件")
    except Exception as error:  # noqa: BLE001 - 后台线程异常只记录，不影响宿主
        logger.error(f"【媒体服务器增强】防抖刷新执行失败：{error}")


def stop_timer(plugin) -> None:
    """停止未触发的防抖定时器。

    :param plugin: 插件实例
    """
    timer = getattr(plugin, "_refresh_timer", None)
    if timer is None:
        return
    try:
        timer.cancel()
    except Exception:  # noqa: BLE001 - 停止流程不应抛错
        pass
    plugin._refresh_timer = None


def flush_pending(plugin, trigger: str = "入库事件") -> Optional[Dict[str, Any]]:
    """清空缓冲并对目标服务器发起刷新。

    :param plugin: 插件实例
    :param trigger: 触发来源说明
    :return: 任务记录；缓冲为空时返回 None
    """
    with _lock(plugin):
        pending = _pending(plugin)
        if not pending:
            return None
        payloads = list(pending.values())
        pending.clear()
    return run_refresh(plugin, payloads, trigger=trigger, only_configured=True)


def run_refresh(plugin, payloads: List[Dict[str, Any]], trigger: str = "手动",
                servers: Optional[List[str]] = None,
                only_configured: bool = False,
                root_refresh: bool = False) -> Dict[str, Any]:
    """对目标服务器执行一次刷新并记录任务。

    :param plugin: 插件实例
    :param payloads: 刷新请求列表，``root_refresh`` 为真时可为空
    :param trigger: 触发来源说明
    :param servers: 显式指定的服务器清单
    :param only_configured: 是否只使用配置中的服务器白名单
    :param root_refresh: 是否强制整库刷新
    :return: 任务记录字典
    """
    started = time.time()
    targets = enabled_servers(plugin, servers if not only_configured else None)
    job = store.build_job(
        MODULE,
        "root_refresh" if root_refresh else "refresh",
        trigger=trigger,
        total=len(targets),
        detail={"payloads": len(payloads)},
    )
    if not targets:
        store.finish_job(job, "skipped", "没有可用的媒体服务器")
        store.append_job(plugin, job, history_limit(plugin))
        return job
    if observe_only(plugin):
        store.finish_job(
            job, "observed",
            f"观察模式：已分析 {len(payloads) or '整库'} 刷新请求，跳过 {len(targets)} 台服务器的真实刷新",
            success=len(targets),
        )
        job["detail"]["duration_ms"] = store.elapsed_ms(started)
        store.append_job(plugin, job, history_limit(plugin))
        _notify(plugin, job)
        return job

    success = 0
    failed = 0
    messages: List[str] = []
    for name in targets:
        try:
            if root_refresh or not payloads:
                ok, message = mediaserver.refresh_server(name, [])
            else:
                ok, message = mediaserver.refresh_server(name, payloads)
        except Exception as error:  # noqa: BLE001 - 单台服务器失败不影响其它服务器
            ok, message = False, str(error)
        if ok:
            success += 1
        else:
            failed += 1
        messages.append(f"{name}: {message}")
    status = "success" if failed == 0 else ("failed" if success == 0 else "partial")
    if status == "partial":
        job["status"] = "partial"
    store.finish_job(job, status, "；".join(messages), success=success, failed=failed)
    job["detail"]["duration_ms"] = store.elapsed_ms(started)
    store.append_job(plugin, job, history_limit(plugin))
    write_refresh_state(plugin, status, trigger)
    _notify(plugin, job)
    return job


def run_recent_refresh(plugin, trigger: str = "最近媒体") -> Dict[str, Any]:
    """复用宿主最近入库列表发起一次刷新。

    :param plugin: 插件实例
    :param trigger: 触发来源说明
    :return: 任务记录字典
    """
    count = safe_int(getattr(plugin, "_refresh_recent_count", 20), 20, 1, 500)
    payloads: List[Dict[str, Any]] = []
    for name in enabled_servers(plugin):
        service = mediaserver.get_service(name)
        instance = getattr(service, "instance", None) if service else None
        loader = getattr(instance, "get_latest", None) if instance else None
        if not callable(loader):
            continue
        try:
            latest = loader(num=count) or []
        except Exception as error:  # noqa: BLE001 - 单台服务器读取失败不影响其它服务器
            logger.warning(f"【媒体服务器增强】读取 {name} 最近入库失败：{error}")
            continue
        for item in latest:
            payloads.append(
                {
                    "title": getattr(item, "title", "") or "",
                    "year": getattr(item, "year", "") or "",
                    "type": getattr(getattr(item, "type", None), "value", None)
                    or str(getattr(item, "type", "") or ""),
                    "category": "",
                    "path": getattr(item, "path", "") or "",
                }
            )
    if not payloads:
        job = store.build_job(MODULE, "recent_refresh", trigger=trigger)
        store.finish_job(job, "skipped", "未读取到最近入库条目")
        store.append_job(plugin, job, history_limit(plugin))
        return job
    return run_refresh(plugin, payloads, trigger=trigger)


def run_scheduled(plugin) -> None:
    """定时任务入口：按配置执行最近媒体刷新与整库补扫。"""
    if not plugin_active(plugin, MODULE):
        return
    try:
        if as_bool(getattr(plugin, "_refresh_recent_enabled", False)):
            run_recent_refresh(plugin, trigger="定时刷新")
        else:
            run_refresh(plugin, [], trigger="定时补扫", root_refresh=True)
    except Exception as error:  # noqa: BLE001 - 定时任务异常不向宿主抛出
        logger.error(f"【媒体服务器增强】定时刷新失败：{error}")


def plugin_active(plugin, module: str) -> bool:
    """判断模块是否处于可运行状态。

    :param plugin: 插件实例
    :param module: 模块键
    :return: 总开关与模块开关同时打开时返回 True
    """
    if not as_bool(getattr(plugin, "_enabled", False)):
        return False
    return as_bool(getattr(plugin, f"_{module}_enabled", False))


def history_limit(plugin) -> int:
    """返回任务历史保留条数。"""
    return safe_int(getattr(plugin, "_history_limit", 300), 300, 20, 5000)


def write_refresh_state(plugin, status: str, trigger: str) -> None:
    """记录最近一次刷新状态，供总览页展示。

    :param plugin: 插件实例
    :param status: 任务终态
    :param trigger: 触发来源
    """
    store.write_value(
        plugin,
        store.REFRESH_STATE_KEY,
        {"time": store.now_text(), "status": status, "trigger": trigger},
    )


def _notify(plugin, job: Dict[str, Any]) -> None:
    """在结果失败或部分失败时推送通知。

    :param plugin: 插件实例
    :param job: 任务记录
    """
    if not as_bool(getattr(plugin, "_notify", False)):
        return
    if job.get("status") == "success":
        return
    try:
        plugin.post_message(
            title="【媒体服务器增强】媒体库刷新",
            text=f"状态：{job.get('status')}\n说明：{job.get('message')}",
        )
    except Exception as error:  # noqa: BLE001 - 通知失败不影响任务结果
        logger.warning(f"【媒体服务器增强】刷新通知发送失败：{error}")
