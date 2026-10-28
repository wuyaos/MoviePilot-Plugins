"""自动删种配置解析：插件配置字典 → RemoverConfig。"""

from __future__ import annotations

from typing import Any, Optional

from .constants import REMOVER_CONFIG_DEFAULTS
from .models import RemoverConfig

_MISSING = object()


def parse_remover_config(config: Optional[dict] = None) -> RemoverConfig:
    """把插件配置字典解析为自动删种运行时配置；键缺失时取 REMOVER_CONFIG_DEFAULTS。

    空串是条件键的有效值（该条件不启用），因此只有键缺失才回退默认值，显式空值不被覆盖。
    """
    source = config if isinstance(config, dict) else {}

    def value(key: str) -> Any:
        raw = source.get(key, _MISSING)
        return REMOVER_CONFIG_DEFAULTS.get(key) if raw is _MISSING else raw

    return RemoverConfig(
        enabled=as_bool(value("remover_enabled"), False),
        notify=as_bool(value("remover_notify"), False),
        action=_as_text(value("remover_action")),
        downloaders=_as_str_list(value("remover_downloaders")),
        cron=_as_text(value("remover_cron")),
        samedata=as_bool(value("remover_samedata"), False),
        mponly=as_bool(value("remover_mponly"), False),
        size=_as_text(value("remover_size")),
        ratio=_as_text(value("remover_ratio")),
        time=_as_text(value("remover_time")),
        upspeed=_as_text(value("remover_upspeed")),
        labels=_as_text(value("remover_labels")),
        pathkeywords=_as_text(value("remover_pathkeywords")),
        trackerkeywords=_as_text(value("remover_trackerkeywords")),
        errorkeywords=_as_text(value("remover_errorkeywords")),
        torrentstates=_as_text(value("remover_torrentstates")),
        torrentcategorys=_as_text(value("remover_torrentcategorys")),
    )


def as_bool(value: Any, default: bool = False) -> bool:
    """把配置值转换为布尔，识别不出时取默认值。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes", "on"}:
            return True
        if text in {"false", "0", "no", "off"}:
            return False
        return default
    if value is None:
        return default
    return bool(value)


def _as_text(value: Any) -> str:
    """把配置值规范为去空白的字符串。"""
    if value is None:
        return ""
    return str(value).strip()


def _as_str_list(value: Any) -> list[str]:
    """把列表或逗号分隔字符串规范为非空字符串列表，保持原始顺序。"""
    raw_values = value if isinstance(value, (list, tuple, set)) else [value]
    result: list[str] = []
    for raw_value in raw_values:
        for part in str(raw_value or "").replace("，", ",").split(","):
            text = part.strip()
            if text and text not in result:
                result.append(text)
    return result


__all__ = ("as_bool", "parse_remover_config")
