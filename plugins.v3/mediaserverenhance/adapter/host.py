"""媒体服务器增强 - 宿主插件状态探测。

用于与其他插件的共存裁决（如封面工坊与 CoverGen 互斥）。
懒加载宿主 PluginManager，失败时按「未安装」处理，不阻断插件自身初始化。
"""

from __future__ import annotations

from typing import Any, Dict

from app.sdk.logging import logger

LOG_PREFIX = "【媒体服务器增强】"


def installed_plugin_state(plugin_id: str) -> Dict[str, Any]:
    """查询宿主侧另一插件的安装与启用状态。

    :param plugin_id: 插件标识（如 ``CoverGen``）
    :return: ``{"installed": 是否已安装, "enabled": 是否已启用, "version": 版本或空串}``
    """
    state: Dict[str, Any] = {"installed": False, "enabled": False, "version": ""}
    try:
        from app.sdk.plugin import PluginManager

        manager = PluginManager()
        instance = (getattr(manager, "running_plugins", None) or {}).get(plugin_id)
        config = manager.get_plugin_config(plugin_id) or {}
        version = str(getattr(instance, "plugin_version", "") or config.get("version") or "")
        installed = instance is not None or bool(config)
        enabled = False
        if isinstance(config, dict):
            enabled = bool(config.get("enabled"))
        if not enabled and instance is not None:
            getter = getattr(instance, "get_state", None)
            enabled = bool(getter()) if callable(getter) else False
        state.update(installed=installed, enabled=enabled, version=version)
    except Exception as error:  # noqa: BLE001 - 探测失败按未安装处理并记录
        logger.debug(f"{LOG_PREFIX}查询宿主插件 {plugin_id} 状态失败：{error}")
    return state
