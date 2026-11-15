"""媒体服务器增强 - 配置到运行时属性的映射。

配置以扁平字典持久化（前端表单直接读写），运行时各模块通过插件私有属性读取。
本模块是两者之间唯一的换算点：改配置键名只需改这里的表。
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .config import as_bool, as_list, normalize_config, safe_int

# 配置键 → 运行时属性名
CONFIG_ATTRS: Dict[str, str] = {
    "enabled": "_enabled",
    "observe_only": "_observe_only",
    "notify": "_notify",
    "history_limit": "_history_limit",
    "request_timeout": "_request_timeout",
    "refresh_enabled": "_refresh_enabled",
    "refresh_servers": "_refresh_servers",
    "refresh_libraries": "_refresh_libraries",
    "refresh_on_transfer": "_refresh_on_transfer",
    "refresh_debounce_seconds": "_refresh_debounce_seconds",
    "refresh_delay_seconds": "_refresh_delay_seconds",
    "refresh_recent_enabled": "_refresh_recent_enabled",
    "refresh_recent_count": "_refresh_recent_count",
    "refresh_cron": "_refresh_cron",
    "audit_enabled": "_audit_enabled",
    "audit_servers": "_audit_servers",
    "audit_libraries": "_audit_libraries",
    "audit_checks": "_audit_checks",
    "audit_max_items": "_audit_max_items",
    "audit_cron": "_audit_cron",
    "covers_enabled": "_covers_enabled",
    "covers_servers": "_cover_servers",
    "covers_libraries": "_cover_libraries",
    "covers_style": "_cover_style",
    "covers_limit": "_cover_limit",
    "covers_upload": "_cover_upload",
    "covers_font": "_cover_font",
    "covers_output_dir": "_cover_output_dir",
    "covers_cron": "_covers_cron",
    "capabilities_enabled": "_capabilities_enabled",
    "capabilities_servers": "_capability_servers",
    "capabilities_watch": "_capability_watched",
    "capabilities_cron": "_capabilities_cron",
}

# 布尔型配置键
BOOL_KEYS: Tuple[str, ...] = (
    "enabled",
    "observe_only",
    "notify",
    "refresh_enabled",
    "refresh_on_transfer",
    "refresh_recent_enabled",
    "audit_enabled",
    "covers_enabled",
    "covers_upload",
    "capabilities_enabled",
)

# 字符串列表型配置键
LIST_KEYS: Tuple[str, ...] = (
    "refresh_servers",
    "refresh_libraries",
    "audit_servers",
    "audit_libraries",
    "audit_checks",
    "covers_servers",
    "covers_libraries",
    "capabilities_servers",
    "capabilities_watch",
)

# 整数型配置键及其上下界
INT_RANGES: Dict[str, Tuple[int, int, int]] = {
    "history_limit": (300, 20, 5000),
    "request_timeout": (30, 5, 300),
    "refresh_debounce_seconds": (30, 0, 3600),
    "refresh_delay_seconds": (0, 0, 86400),
    "refresh_recent_count": (20, 1, 200),
    "audit_max_items": (20000, 100, 200000),
    "covers_limit": (20, 1, 500),
}


def _coerce(key: str, value: Any) -> Any:
    """按配置键类型把原始值换算为运行时可用的类型。

    :param key: 配置键
    :param value: 原始配置值
    :return: 换算后的值
    """
    if key in BOOL_KEYS:
        return as_bool(value)
    if key in LIST_KEYS:
        return as_list(value)
    if key in INT_RANGES:
        default, minimum, maximum = INT_RANGES[key]
        return safe_int(value, default, minimum, maximum)
    if value is None:
        return ""
    return str(value).strip() if isinstance(value, str) else value


def apply_runtime_config(plugin, raw_config: Any) -> Dict[str, Any]:
    """把配置写入插件运行时属性，并返回归一化后的配置。

    :param plugin: 插件实例
    :param raw_config: 宿主传入的配置，可能为 None
    :return: 补齐默认值并完成类型换算的配置字典
    """
    normalized = normalize_config(raw_config)
    for key, attr in CONFIG_ATTRS.items():
        setattr(plugin, attr, _coerce(key, normalized.get(key)))
    plugin._config = {
        key: getattr(plugin, attr) for key, attr in CONFIG_ATTRS.items()
    }
    return dict(normalized)


def current_config(plugin) -> Dict[str, Any]:
    """读取插件当前生效的配置，缺失项回落到默认值。

    :param plugin: 插件实例
    :return: 归一化后的配置字典
    """
    stored = getattr(plugin, "_config", None)
    return normalize_config(stored if isinstance(stored, dict) else None)


def config_snapshot(plugin) -> List[Dict[str, Any]]:
    """构造配置项快照，供诊断与前端摘要展示。

    :param plugin: 插件实例
    :return: ``{key, value}`` 列表
    """
    config = current_config(plugin)
    return [{"key": key, "value": value} for key, value in config.items()]


def observe_only(plugin) -> bool:
    """返回插件是否处于观察模式。

    观察模式下体检等只读动作照常执行，刷新请求与封面上传等
    对媒体服务器的写操作全部跳过，只记录任务结果。

    :param plugin: 插件实例
    :return: 是否观察模式
    """
    return as_bool(getattr(plugin, "_observe_only", False))
