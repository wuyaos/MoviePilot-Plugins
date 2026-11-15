"""媒体服务器增强 - 生命周期。

宿主调用 ``init_plugin`` 时先停掉上一轮的运行时残留（防抖定时器、待刷新缓冲），
再写入新配置，避免旧配置的定时器在新配置生效后继续触发。
"""

from __future__ import annotations

from typing import Any, Dict

from app.sdk.logging import logger

from ..modules.refresh import service as refresh_service
from ..utils.runtime import apply_runtime_config, current_config

LOG_PREFIX = "【媒体服务器增强】"


def stop_plugin(plugin) -> None:
    """释放插件持有的运行时资源。

    :param plugin: 插件实例
    """
    try:
        refresh_service.stop_timer(plugin)
    except Exception as error:  # noqa: BLE001 - 停止路径不得抛出
        logger.error(f"{LOG_PREFIX}停止防抖定时器失败：{error}")
    plugin._refresh_pending = {}


def initialize_plugin(plugin, config: Any = None) -> Dict[str, Any]:
    """初始化插件：清理残留 → 写入配置 → 记录启用状态。

    :param plugin: 插件实例
    :param config: 宿主传入的配置字典
    :return: 归一化后的配置
    """
    stop_plugin(plugin)
    normalized = apply_runtime_config(plugin, config)
    if normalized.get("enabled"):
        logger.info(f"{LOG_PREFIX}已启用，媒体服务器实例由宿主配置提供")
    else:
        logger.info(f"{LOG_PREFIX}总开关关闭，全部模块保持待命")
    return normalized


def runtime_summary(plugin) -> Dict[str, Any]:
    """汇总当前生效配置与模块开关，供诊断接口使用。

    :param plugin: 插件实例
    :return: 运行态摘要
    """
    config = current_config(plugin)
    modules = {
        module: refresh_service.plugin_active(plugin, module)
        for module in ("refresh", "audit", "covers", "capabilities")
    }
    return {
        "enabled": bool(config.get("enabled")),
        "notify": bool(config.get("notify")),
        "modules": modules,
        "config": config,
    }
