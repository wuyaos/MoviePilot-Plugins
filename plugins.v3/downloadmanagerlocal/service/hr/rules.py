"""H&R 规则解析：插件配置、内置预设、站点独立 YAML 与按种子大小分档。

规则分层（v3.6.0）：自定义（启用中）> 内置预设 > 全局默认。
- 内置预设：`service/hr/presets.json`（只读，随代码发布）；
- 自定义层：`hr_site_config_str` YAML，同名站点整条覆写预设；
- 条目 `enabled: false` 为影子条目：屏蔽该站的预设与自定义，回退全局规则。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from app.sdk.logging import logger
from pydantic import ValidationError
from ruamel.yaml import YAML, YAMLError

from .constants import HR_CONFIG_DEFAULTS, HR_LOG_PREFIX, HR_NOTIFY_MODES
from .models import HrConfig, HrSiteRule, HrSizeTier

_MISSING = object()
_PRESETS_PATH = Path(__file__).resolve().parent / "presets.json"


def load_preset_rules() -> dict[str, HrSiteRule]:
    """加载内置验证预设（只读）；文件缺失或损坏时返回空表，不阻断运行。"""
    try:
        raw = json.loads(_PRESETS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        logger.error(f"{HR_LOG_PREFIX}内置预设加载失败，忽略：{error}")
        return {}
    rules: dict[str, HrSiteRule] = {}
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("site_name") or "").strip()
        if not name:
            continue
        try:
            rules[name] = HrSiteRule.model_validate(dict(item.get("rule") or {}))
        except ValidationError as error:
            logger.error(f"{HR_LOG_PREFIX}内置预设 {name} 无效，已跳过：{error}")
    return rules


def parse_hr_config(config: Optional[dict] = None) -> HrConfig:
    """把插件配置字典解析为 H&R 运行时配置，缺省键取 HR_CONFIG_DEFAULTS。"""
    source = config if isinstance(config, dict) else {}
    global_rule = HrSiteRule(
        hr_duration=_as_float_or_none(_pick(source, "hr_duration")),
        additional_seed_time=_as_float_or_none(_pick(source, "hr_additional_seed_time")),
        hr_deadline_days=_as_float_or_none(_pick(source, "hr_deadline_days")),
        hr_ratio=_as_float_or_none(_pick(source, "hr_ratio")),
        hr_upload_multiplier=_as_float_or_none(_pick(source, "hr_upload_multiplier")),
        hr_upload_gte_download=_parse_bool(_pick(source, "hr_upload_gte_download")),
        hr_active=_as_bool(_pick(source, "hr_active"), False),
        hr_size_tiers=_parse_size_tiers(_pick(source, "hr_size_tiers")),
    )
    enable_site_config = _as_bool(_pick(source, "hr_enable_site_config"), False)
    site_rules = {}
    if enable_site_config:
        site_rules = build_site_rules(_pick(source, "hr_site_config_str"), global_rule)

    return HrConfig(
        enabled=_as_bool(_pick(source, "hr_enabled"), False),
        protection_enabled=_as_bool(_pick(source, "hr_protection_enabled"), True),
        check_period=_as_positive_int(_pick(source, "hr_check_period"), 10),
        onlyonce=_as_bool(_pick(source, "hr_onlyonce"), False),
        notify=_as_notify_mode(_pick(source, "hr_notify")),
        downloaders=_as_str_list(_pick(source, "hr_downloader")),
        sites=_as_site_ids(_pick(source, "hr_sites")),
        hit_and_run_tag=str(_pick(source, "hr_hit_and_run_tag") or "H&R").strip(),
        auto_cleanup_days=_as_float(_pick(source, "hr_auto_cleanup_days"), 15.0),
        auto_discover=_as_bool(_pick(source, "hr_auto_discover"), False),
        brush_plugin=str(_pick(source, "hr_brush_plugin") or "").strip(),
        exclude_tags=_as_str_list(_pick(source, "hr_exclude_tags")),
        exclude_categories=_as_str_list(_pick(source, "hr_exclude_categories")),
        notify_summary_cron=str(_pick(source, "hr_notify_summary_cron") or "").strip(),
        global_rule=global_rule,
        site_rules=site_rules,
    )


def build_site_rules(site_config_str: Optional[str], global_rule: HrSiteRule) -> dict[str, HrSiteRule]:
    """合并内置预设与站点独立配置 YAML，并按全局规则回填未设置字段。

    合并语义（v3.6.0）：以内置预设为底，自定义 YAML 同名整条覆写；
    条目 `enabled: false` 为影子条目，屏蔽该站全部站点规则（回退全局）。
    """
    presets = load_preset_rules()
    rules: dict[str, HrSiteRule] = {
        name: apply_global_defaults(rule, global_rule)
        for name, rule in presets.items()
    }
    raw = str(site_config_str or "").strip()
    if not raw:
        if not rules:
            logger.warning(f"{HR_LOG_PREFIX}无内置预设且未提供站点独立配置，站点规则回退全局规则")
        return rules
    items = _load_yaml_list(raw)
    if items is None:
        logger.error(f"{HR_LOG_PREFIX}站点独立配置不可用，仅保留内置预设")
        return rules

    for item in items:
        if not isinstance(item, dict):
            logger.error(f"{HR_LOG_PREFIX}站点配置条目必须是键值对象，已跳过：{item!r}")
            continue
        name = str(item.get("site_name") or "").strip()
        if not name:
            logger.error(f"{HR_LOG_PREFIX}站点配置缺少 site_name，已跳过")
            continue
        try:
            rule = HrSiteRule.model_validate(dict(item))
        except ValidationError as error:
            logger.error(f"{HR_LOG_PREFIX}站点 {name} 配置无效，已跳过：{error}")
            continue
        if not rule.enabled:
            # 影子条目：无论内置是否存在，该站回退全局规则。
            rules.pop(name, None)
            continue
        rules[name] = apply_global_defaults(rule, global_rule)
    return rules


def apply_global_defaults(rule: HrSiteRule, global_rule: HrSiteRule) -> HrSiteRule:
    """仅回填未设置（None）字段，站点显式 false/0 保持原值。"""
    for field_name in HrSiteRule.model_fields:
        if getattr(rule, field_name) is None:
            setattr(rule, field_name, getattr(global_rule, field_name))
    return rule


def match_size_tier(rule: HrSiteRule, size_bytes: float) -> Optional[HrSizeTier]:
    """按正数上限递增匹配分档，0 表示无上限并置于末位，边界用 <=。"""
    tiers = rule.hr_size_tiers or []
    if not tiers:
        return None
    size_gib = float(size_bytes or 0) / (1024 ** 3)
    ordered = sorted(tiers, key=lambda tier: tier.max_size_gib if tier.max_size_gib > 0 else float("inf"))
    for tier in ordered:
        limit = tier.max_size_gib if tier.max_size_gib > 0 else float("inf")
        if size_gib <= limit:
            return tier
    return None


def _pick(source: dict, key: str) -> Any:
    """读取配置键；缺失或空串视为未设置，显式 false/0 保持原值。"""
    value = source.get(key, _MISSING)
    if value is _MISSING:
        return HR_CONFIG_DEFAULTS.get(key)
    if isinstance(value, str) and not value.strip():
        return HR_CONFIG_DEFAULTS.get(key)
    return value


def _load_yaml_list(raw: str) -> Optional[list]:
    """安全读取顶层为列表的 YAML；解析失败或类型不符时返回 None。"""
    yaml = YAML(typ="safe")
    try:
        data = yaml.load(raw)
    except YAMLError as error:
        logger.error(f"{HR_LOG_PREFIX}站点配置 YAML 解析失败：{error}")
        return None
    if not isinstance(data, list):
        logger.error(f"{HR_LOG_PREFIX}站点配置 YAML 顶层必须是列表，每项以 '-' 开头")
        return None
    return data


def _parse_bool(value: Any) -> Optional[bool]:
    """把配置值解析为布尔；识别不出布尔语义时返回 None。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes", "on"}:
            return True
        if text in {"false", "0", "no", "off"}:
            return False
        return None
    if value is None:
        return None
    return bool(value)


def _as_bool(value: Any, default: bool) -> bool:
    """把配置值转换为布尔，识别不出时取默认值。"""
    parsed = _parse_bool(value)
    return default if parsed is None else parsed


def _as_float(value: Any, default: float) -> float:
    """把配置值转换为浮点数，失败时取默认值。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_float_or_none(value: Any) -> Optional[float]:
    """把配置值转换为浮点数；空值或非法值返回 None（该条件不参与判定）。"""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_positive_int(value: Any, default: int) -> int:
    """把配置值转换为正整数，非正或非法时取默认值。"""
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _as_str_list(value: Any) -> list[str]:
    """把列表或逗号分隔字符串规范为非空字符串列表。"""
    raw_values = value if isinstance(value, (list, tuple, set)) else [value]
    result: list[str] = []
    for raw_value in raw_values:
        for part in str(raw_value or "").replace("，", ",").split(","):
            text = part.strip()
            if text and text not in result:
                result.append(text)
    return result


def _as_site_ids(value: Any) -> list[int]:
    """把站点白名单规范为站点 ID 列表，非数字项丢弃。"""
    raw_values = value if isinstance(value, (list, tuple, set)) else [value]
    result: list[int] = []
    for raw_value in raw_values:
        for part in str(raw_value or "").replace("，", ",").split(","):
            text = part.strip()
            if not text:
                continue
            try:
                site_id = int(float(text))
            except (TypeError, ValueError):
                logger.warning(f"{HR_LOG_PREFIX}站点白名单项 {text!r} 不是站点 ID，已忽略")
                continue
            if site_id not in result:
                result.append(site_id)
    return result


def _as_notify_mode(value: Any) -> str:
    """规范通知模式，非法值回退 always。"""
    mode = str(value or "").strip().lower()
    return mode if mode in HR_NOTIFY_MODES else "always"


def _parse_size_tiers(value: Any) -> Optional[list[HrSizeTier]]:
    """解析全局分档配置，接受分档列表或同结构 YAML 文本。"""
    if value is None:
        return None
    items = value
    if isinstance(value, str):
        items = _load_yaml_list(value) if value.strip() else None
    if not isinstance(items, list):
        logger.warning(f"{HR_LOG_PREFIX}全局分档配置必须是列表，已忽略：{value!r}")
        return None
    tiers: list[HrSizeTier] = []
    for item in items:
        if not isinstance(item, dict):
            logger.warning(f"{HR_LOG_PREFIX}全局分档条目必须是键值对象，已跳过：{item!r}")
            continue
        try:
            tiers.append(HrSizeTier.model_validate(dict(item)))
        except ValidationError as error:
            logger.warning(f"{HR_LOG_PREFIX}全局分档条目无效，已跳过：{error}")
    return tiers or None


__all__ = (
    "apply_global_defaults",
    "build_site_rules",
    "match_size_tier",
    "parse_hr_config",
)
