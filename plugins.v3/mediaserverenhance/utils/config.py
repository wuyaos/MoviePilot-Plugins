"""媒体服务器增强 - 配置常量、默认值与解析工具。

本模块只承载「配置的静态定义与解析」，不包含任何网络或文件 IO，
便于 core 层与 controller 层共享同一份默认值。
"""

from __future__ import annotations

import copy
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# ── 模块键 ──
MODULE_REFRESH = "refresh"
MODULE_AUDIT = "audit"
MODULE_COVERS = "covers"
MODULE_CAPABILITIES = "capabilities"

MODULE_KEYS: Tuple[str, ...] = (
    MODULE_REFRESH,
    MODULE_AUDIT,
    MODULE_COVERS,
    MODULE_CAPABILITIES,
)

MODULE_TITLES: Dict[str, str] = {
    MODULE_REFRESH: "服务器与刷新",
    MODULE_AUDIT: "媒体库体检",
    MODULE_COVERS: "封面工坊",
    MODULE_CAPABILITIES: "服务端能力",
}

# ── 巡检项定义：(键, 展示名, 说明) ──
AUDIT_CHECK_ITEMS: Tuple[Tuple[str, str, str], ...] = (
    ("missing_episode", "缺集 / 断季", "媒体库已入库季的集号不连续"),
    ("duplicate", "重复媒体 / 多版本", "同名同季同集出现多个条目"),
    ("empty_dir", "空壳目录", "条目目录内不存在可播放的媒体文件"),
    ("orphan_meta", "孤立旁车文件", "仅剩 nfo / 图片 / 字幕而缺视频的目录"),
    ("missing_image", "缺少封面图", "条目在服务器侧没有主图"),
    ("invalid_path", "失效路径", "服务器返回的路径在本地不存在"),
)

AUDIT_CHECK_KEYS: Tuple[str, ...] = tuple(item[0] for item in AUDIT_CHECK_ITEMS)

# ── 封面风格：(键, 展示名)，键必须与 modules/covers/render.py 的 STYLE_KEYS 一致 ──
COVER_STYLES: Tuple[Tuple[str, str], ...] = (
    ("poster", "底部渐变"),
    ("clean", "底部色条"),
    ("gradient", "侧栏竖条"),
)

COVER_STYLE_KEYS: Tuple[str, ...] = tuple(item[0] for item in COVER_STYLES)

# ── 默认配置 ──
PLUGIN_CONFIG_DEFAULTS: Dict[str, Any] = {
    # 通用
    "enabled": False,
    "observe_only": False,
    "notify": False,
    "history_limit": 300,
    "request_timeout": 30,
    # 服务器与刷新
    "refresh_enabled": False,
    "refresh_servers": [],
    "refresh_libraries": [],
    "refresh_on_transfer": True,
    "refresh_debounce_seconds": 30,
    "refresh_delay_seconds": 0,
    "refresh_recent_enabled": False,
    "refresh_recent_count": 20,
    "refresh_cron": "",
    # 媒体库体检
    "audit_enabled": False,
    "audit_servers": [],
    "audit_libraries": [],
    "audit_checks": list(AUDIT_CHECK_KEYS),
    "audit_max_items": 20000,
    "audit_cron": "",
    # 封面工坊
    "covers_enabled": False,
    "covers_servers": [],
    "covers_libraries": [],
    "covers_style": "poster",
    "covers_limit": 20,
    "covers_upload": False,
    "covers_font": "",
    "covers_output_dir": "",
    "covers_cron": "",
    # 服务端能力
    "capabilities_enabled": False,
    "capabilities_servers": [],
    "capabilities_watch": ["StrmAssistant", "神医"],
    "capabilities_cron": "",
}


def build_plugin_config_defaults() -> Dict[str, Any]:
    """返回可直接交给前端配置组件的默认配置副本。"""
    return copy.deepcopy(PLUGIN_CONFIG_DEFAULTS)


def normalize_config(raw: Any) -> Dict[str, Any]:
    """把任意来源的配置补齐为完整配置字典。

    :param raw: 配置字典，可能缺键、为 None 或不是字典
    :return: 以默认值为底、携带调用方覆盖值的完整配置
    """
    merged = build_plugin_config_defaults()
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key in merged:
                merged[key] = value
    return merged


def as_bool(value: Any, default: bool = False) -> bool:
    """把配置值宽松解析为布尔值。

    :param value: 原始配置值，可能来自 JSON、表单字符串或 YAML
    :param default: 无法判定时的回退值
    :return: 解析后的布尔值
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "y"}:
        return True
    if text in {"0", "false", "no", "off", "n", ""}:
        return False
    return default


def safe_int(value: Any, default: int, minimum: Optional[int] = None,
             maximum: Optional[int] = None) -> int:
    """把配置值解析为受上下界约束的整数。

    :param value: 原始配置值
    :param default: 解析失败时的回退值
    :param minimum: 允许的最小值，None 表示不限制
    :param maximum: 允许的最大值，None 表示不限制
    :return: 落在区间内的整数
    """
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        number = default
    if minimum is not None and number < minimum:
        number = minimum
    if maximum is not None and number > maximum:
        number = maximum
    return number


def as_list(value: Any) -> List[str]:
    """把配置值统一解析为去空的字符串列表。

    :param value: 列表、逗号分隔字符串或单个值
    :return: 去除首尾空白并过滤空项后的字符串列表
    """
    if value is None or value == "":
        return []
    if isinstance(value, str):
        parts: Iterable[Any] = value.replace("，", ",").split(",")
    elif isinstance(value, (list, tuple, set)):
        parts = value
    else:
        parts = [value]
    result: List[str] = []
    for part in parts:
        text = str(part).strip()
        if text and text not in result:
            result.append(text)
    return result


def parse_scope(entries: Sequence[str]) -> List[Tuple[str, str]]:
    """把 ``server|library_id`` 形式的范围配置解析为二元组列表。

    缺少分隔符的条目会被忽略，避免把服务器名误当媒体库标识使用。

    :param entries: 范围配置原始条目
    :return: ``(服务器名, 媒体库标识)`` 列表
    """
    parsed: List[Tuple[str, str]] = []
    for entry in entries or []:
        text = str(entry or "").strip()
        if "|" not in text and "::" not in text:
            continue
        separator = "|" if "|" in text else "::"
        server, _, library = text.partition(separator)
        server = server.strip()
        library = library.strip()
        if server and library and (server, library) not in parsed:
            parsed.append((server, library))
    return parsed


def scope_allows(entries: Sequence[str], server: str, library: Optional[str]) -> bool:
    """判断给定服务器与媒体库是否落在配置范围内。

    配置为空表示不限制；只配置服务器名时对该服务器全部媒体库放行。

    :param entries: 解析后的范围二元组列表
    :param server: 待判断的服务器名
    :param library: 待判断的媒体库标识，None 表示按服务器粒度判断
    :return: 命中范围时返回 True
    """
    if not entries:
        return True
    for item_server, item_library in entries:
        if item_server != server:
            continue
        if library is None or item_library == str(library):
            return True
    return False


def servers_allowed(servers: Sequence[str], name: str) -> bool:
    """判断服务器是否落在配置的服务器白名单内。

    :param servers: 服务器白名单，空表示不限制
    :param name: 待判断的服务器名
    :return: 命中白名单或白名单为空时返回 True
    """
    if not servers:
        return True
    return name in set(servers)
