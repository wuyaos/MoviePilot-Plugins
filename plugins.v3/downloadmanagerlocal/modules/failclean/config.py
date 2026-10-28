"""整理失败清理的运行时配置解析。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .constants import FAILCLEAN_CONFIG_DEFAULTS

_BOOL_TRUE = {"1", "true", "yes", "on"}
_BOOL_FALSE = {"0", "false", "no", "off"}


@dataclass(frozen=True)
class FailCleanConfig:
    """整理失败清理的运行时配置。

    :ivar enabled: 模块总开关，关闭时不执行即时删除与巡检。
    :ivar notify: 是否发送源文件删除结果通知；巡检汇总通知同受此开关控制。
    :ivar cron: 巡检周期 cron 表达式。
    :ivar clean_repeat: 是否启用重复下载残留清理。
    :ivar retain_hours: 重复下载残留文件至少保留的小时数，最小 1。

    构造后的占位状态为关闭；运行时配置由 :func:`parse_failclean_config` 读取，
    缺省值取 FAILCLEAN_CONFIG_DEFAULTS（failcleanup_enabled 默认为 True）。
    """

    enabled: bool = False
    notify: bool = True
    cron: str = "0 */2 * * *"
    clean_repeat: bool = True
    retain_hours: int = 6


def parse_failclean_config(config: Optional[dict] = None) -> FailCleanConfig:
    """把插件配置字典解析为运行时配置，缺省键取 FAILCLEAN_CONFIG_DEFAULTS。"""
    source = config if isinstance(config, dict) else {}
    defaults = FAILCLEAN_CONFIG_DEFAULTS
    return FailCleanConfig(
        enabled=_as_bool(
            source.get("failcleanup_enabled"), defaults["failcleanup_enabled"]
        ),
        notify=_as_bool(source.get("failcleanup_notify"), defaults["failcleanup_notify"]),
        cron=str(source.get("failcleanup_cron") or defaults["failcleanup_cron"]).strip(),
        clean_repeat=_as_bool(
            source.get("failcleanup_clean_repeat"),
            defaults["failcleanup_clean_repeat"],
        ),
        retain_hours=_as_positive_int(
            source.get("failcleanup_retain_hours"),
            defaults["failcleanup_retain_hours"],
        ),
    )


def _as_bool(value, default: bool) -> bool:
    """兼容布尔、数字与常见字符串开关值，空值回退默认。"""
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in _BOOL_TRUE:
        return True
    if text in _BOOL_FALSE:
        return False
    return default


def _as_positive_int(value, default: int) -> int:
    """按来源语义把保留小时数收敛为不小于 1 的整数。"""
    try:
        hours = int(value)
    except (TypeError, ValueError):
        hours = default
    return max(hours, 1)


__all__ = ("FailCleanConfig", "parse_failclean_config")
