"""媒体服务器增强 - 调度服务声明。

每个模块的定时任务独立构造：某个模块的 Cron 写错只丢弃该模块，
不影响其它模块注册，也不会让 ``get_service()`` 整体返回空列表。
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from apscheduler.triggers.cron import CronTrigger

from app.sdk.logging import logger

from ..modules.audit import service as audit_service
from ..modules.capabilities import service as capability_service
from ..modules.covers import service as cover_service
from ..modules.refresh import service as refresh_service

LOG_PREFIX = "【媒体服务器增强】"


def _cron_trigger(cron: str, module_title: str) -> Optional[CronTrigger]:
    """把 Cron 表达式解析为触发器。

    :param cron: 五段式 Cron 表达式
    :param module_title: 模块中文名，用于日志定位
    :return: 触发器对象，表达式无效时返回 None
    """
    text = str(cron or "").strip()
    if not text:
        return None
    try:
        return CronTrigger.from_crontab(text)
    except (ValueError, TypeError) as error:
        logger.error(f"{LOG_PREFIX}{module_title} 的 Cron 表达式无效，已跳过定时任务：{text}（{error}）")
        return None


def _service(service_id: str, name: str, trigger: CronTrigger,
             func: Callable[..., Any], plugin) -> Dict[str, Any]:
    """构造单条调度服务声明。

    :param service_id: 服务标识，宿主会拼上插件前缀
    :param name: 服务展示名
    :param trigger: 触发器
    :param func: 执行函数
    :param plugin: 插件实例，作为关键字参数注入
    :return: 调度服务声明字典
    """
    return {
        "id": service_id,
        "name": name,
        "trigger": trigger,
        "func": func,
        "func_kwargs": {"plugin": plugin},
    }


def build_plugin_services(plugin) -> List[Dict[str, Any]]:
    """按当前配置构造全部定时任务声明。

    :param plugin: 插件实例
    :return: 调度服务声明列表，可为空
    """
    if not getattr(plugin, "_enabled", False):
        return []

    plans: List[Tuple[str, str, str, Callable[..., Any], str]] = (
        (
            "MediaServerEnhanceRefresh",
            "媒体库定时刷新",
            getattr(plugin, "_refresh_cron", ""),
            refresh_service.run_scheduled,
            "refresh",
        ),
        (
            "MediaServerEnhanceAudit",
            "媒体库定时体检",
            getattr(plugin, "_audit_cron", ""),
            audit_service.run_scheduled,
            "audit",
        ),
        (
            "MediaServerEnhanceCover",
            "封面定时生成",
            getattr(plugin, "_covers_cron", ""),
            cover_service.run_scheduled,
            "covers",
        ),
        (
            "MediaServerEnhanceCapability",
            "服务端能力定时探测",
            getattr(plugin, "_capabilities_cron", ""),
            capability_service.run_scheduled,
            "capabilities",
        ),
    )

    services: List[Dict[str, Any]] = []
    for service_id, name, cron, func, module in plans:
        try:
            if not refresh_service.plugin_active(plugin, module):
                continue
            trigger = _cron_trigger(cron, name)
            if trigger is None:
                continue
            services.append(_service(service_id, name, trigger, func, plugin))
        except Exception as error:  # noqa: BLE001 - 单模块失败不得影响其它调度
            logger.error(f"{LOG_PREFIX}{name} 注册失败，已跳过：{error}")
    return services
