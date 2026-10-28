"""下载中心调度服务注册构造。"""

from typing import Any, Dict, List

from apscheduler.triggers.cron import CronTrigger

from app.sdk.logging import logger

from .autoremove.constants import REMOVER_SERVICE_ID, REMOVER_SERVICE_NAME
from .failclean.constants import (
    FAILCLEAN_LOG_PREFIX,
    FAILCLEAN_REPEAT_SERVICE_ID,
    FAILCLEAN_REPEAT_SERVICE_NAME,
)
from .hr.constants import (
    HR_CHECK_SERVICE_ID,
    HR_CHECK_SERVICE_NAME,
    HR_DISCOVER_SERVICE_ID,
    HR_DISCOVER_SERVICE_NAME,
    HR_LOG_PREFIX,
    HR_SUMMARY_SERVICE_ID,
    HR_SUMMARY_SERVICE_NAME,
)
from .rename import scan_renames
from .site_tag import complement_history


def build_plugin_services(plugin) -> List[Dict[str, Any]]:
    """根据插件运行状态构造 MoviePilot 调度服务声明。"""
    services = []

    if plugin._transfer_active and plugin._transfer_fallback_enabled:
        services.append({
            "id": "TorrentTransferFallback",
            "name": "转移做种兜底服务",
            "trigger": "interval",
            "func": plugin._fallback_transfer,
            "kwargs": {"minutes": plugin._transfer_fallback_interval_minutes}
        })

    services.extend(_build_hr_services(plugin))
    services.extend(_build_autoremove_services(plugin))
    services.extend(_build_failclean_services(plugin))
    services.extend(_build_site_tag_services(plugin))
    services.extend(_build_rename_services(plugin))

    return services


def _build_autoremove_services(plugin) -> List[Dict[str, Any]]:
    """按自动删种运行时配置构造定时执行服务声明。"""
    service = getattr(plugin, "_autoremove_service", None)
    if service is None or not service.config.enabled or not service.config.cron:
        return []
    try:
        trigger = CronTrigger.from_crontab(service.config.cron)
    except ValueError as error:
        logger.error(f"【PT下载中心】Cron 无效，已禁用该服务：{service.config.cron}（{error}）")
        return []
    return [{
        "id": REMOVER_SERVICE_ID,
        "name": REMOVER_SERVICE_NAME,
        "trigger": trigger,
        "func": service.run_cycle,
        "func_kwargs": {"trigger_source": "定时"},
    }]


def _build_failclean_services(plugin) -> List[Dict[str, Any]]:
    """按整理失败清理配置构造重复残留巡检服务声明。"""
    service = getattr(plugin, "_failclean_service", None)
    if service is None or not service.config.enabled or not service.config.clean_repeat:
        return []
    try:
        trigger = CronTrigger.from_crontab(service.config.cron)
    except ValueError as error:
        logger.error(f"【PT下载中心】{FAILCLEAN_LOG_PREFIX}Cron 无效，已禁用该服务：{service.config.cron}（{error}）")
        return []
    return [{
        "id": FAILCLEAN_REPEAT_SERVICE_ID,
        "name": FAILCLEAN_REPEAT_SERVICE_NAME,
        "trigger": trigger,
        "func": service.cleanup_repeat_sources,
        "func_kwargs": {},
    }]


def _build_site_tag_services(plugin) -> List[Dict[str, Any]]:
    """按站点标签增强配置构造历史扫描补全服务声明。"""
    config = getattr(plugin, "_site_tag_config", None)
    if not isinstance(config, dict) or not config.get("enable") or not config.get("interval_cron"):
        return []
    try:
        trigger = CronTrigger.from_crontab(config["interval_cron"])
    except ValueError as error:
        logger.error(f"【PT下载中心:站点标签】Cron 无效，已禁用该服务：{config['interval_cron']}（{error}）")
        return []
    return [{
        "id": "DownloadCenterSiteHistory",
        "name": "站点标签历史补全",
        "trigger": trigger,
        "func": complement_history,
        "func_kwargs": {"plugin": plugin},
    }]


def _build_rename_services(plugin) -> List[Dict[str, Any]]:
    """按命名补刀配置构造周期扫描重命名服务声明。"""
    config = getattr(plugin, "_rename_config", None)
    if not isinstance(config, dict) or not config.get("enabled") or not config.get("cron_enabled"):
        return []
    cron = str(config.get("cron") or "")
    if not cron:
        return []
    try:
        trigger = CronTrigger.from_crontab(cron)
    except ValueError as error:
        logger.error(f"【PT下载中心:重命名】Cron 无效，已禁用该服务：{cron}（{error}）")
        return []
    return [{
        "id": "DownloadCenterRenameScan",
        "name": "命名补刀扫描",
        "trigger": trigger,
        "func": scan_renames,
        "func_kwargs": {"plugin": plugin},
    }]


def _build_hr_services(plugin) -> List[Dict[str, Any]]:
    """按 H&R 运行时配置构造状态检查、自动发现与每日汇总服务声明。"""
    service = getattr(plugin, "_hr_service", None)
    if service is None or not service.config.enabled:
        return []

    services = [{
        "id": HR_CHECK_SERVICE_ID,
        "name": HR_CHECK_SERVICE_NAME,
        "trigger": "interval",
        "func": service.check_tasks,
        "kwargs": {"minutes": service.config.check_period},
    }]

    if service.config.auto_discover:
        services.append({
            "id": HR_DISCOVER_SERVICE_ID,
            "name": HR_DISCOVER_SERVICE_NAME,
            "trigger": "interval",
            "func": service.discover_tasks,
            "kwargs": {"minutes": service.config.check_period * 2},
        })

    cron = service.config.notify_summary_cron
    trigger = _hr_summary_trigger(cron)
    if trigger is not None:
        services.append({
            "id": HR_SUMMARY_SERVICE_ID,
            "name": HR_SUMMARY_SERVICE_NAME,
            "trigger": trigger,
            "func": service.send_summary,
            "func_kwargs": {},
        })

    return services


def _hr_summary_trigger(cron: str):
    """把汇总通知 cron 解析为触发器；无效 cron 只禁用该服务并记录错误。"""
    if not cron:
        return None
    try:
        return CronTrigger.from_crontab(cron)
    except ValueError as error:
        logger.error(f"【PT下载中心】{HR_LOG_PREFIX}汇总通知 Cron 无效，已禁用该服务：{cron}（{error}）")
        return None
