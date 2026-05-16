# input: 用户配置 dict（init_plugin 传入）、rule.yaml 站点模板
# output: HNRConfig 全局配置、SiteConfig 站点配置、SizeTier 按大小分级规则
# pos: 配置层，定义 H&R 规则的全部参数结构
"""H&R 助手配置模型。支持按站点独立配置、按种子大小分级、多条件 OR 判定。"""
from __future__ import annotations

import json
from enum import Enum
from typing import Dict, List, Optional, Union, get_args, get_origin

from pydantic import BaseModel, Field, root_validator, validator
from ruamel.yaml import YAML, YAMLError

from app.log import logger


class NotifyMode(Enum):
    NONE = "none"
    ON_ERROR = "on_error"
    ALWAYS = "always"


class SizeTier(BaseModel):
    """按种子大小分级的 H&R 规则（北洋园等）。"""
    max_size_gib: float = 0       # 种子大小上限（GiB），0 表示无上限
    hr_duration: float = 0        # 做种时间要求（小时）
    hr_deadline_days: float = 0   # 考核期（天）

    class Config:
        extra = "ignore"


class BaseConfig(BaseModel):
    """站点 H&R 规则基础字段。所有条件为 OR 关系，满足任一即通过。"""
    # ---- 做种时间条件 ----
    hr_duration: Optional[float] = None         # 要求做种时间（小时）
    additional_seed_time: Optional[float] = None # 附加做种时间（小时）
    # ---- 考核期 ----
    hr_deadline_days: Optional[float] = None     # 考核期（天），超期未满足则 OVERDUE
    # ---- 分享率条件 ----
    hr_ratio: Optional[float] = None             # 分享率 >= 此值即通过
    # ---- 上传量条件 ----
    hr_upload_multiplier: Optional[float] = None  # 上传量 >= 种子大小 * N 倍即通过（carpt: 10）
    hr_upload_gte_download: Optional[bool] = None  # 上传量 >= 下载量即通过（学校）
    # ---- 全站 H&R ----
    hr_active: Optional[bool] = False            # 全站 H&R，所有种子视为 H&R
    # ---- 按大小分级 ----
    hr_size_tiers: Optional[List[SizeTier]] = None  # 按种子大小匹配不同规则（北洋园）

    class Config:
        extra = "ignore"
        arbitrary_types_allowed = True

    @property
    def hr_seed_time(self) -> float:
        return (self.hr_duration or 0.0) + (self.additional_seed_time or 0.0)

    def get_tier_for_size(self, size_bytes: float) -> Optional[SizeTier]:
        """按种子大小匹配分级规则，返回第一个匹配的 tier。"""
        if not self.hr_size_tiers:
            return None
        size_gib = size_bytes / (1024 ** 3)
        for tier in sorted(self.hr_size_tiers, key=lambda t: t.max_size_gib or float("inf")):
            limit = tier.max_size_gib or float("inf")
            if size_gib <= limit:
                return tier
        return None

    def to_dict(self, **kwargs) -> dict:
        return json.loads(self.json(**kwargs))


class SiteConfig(BaseConfig):
    """单站点配置，继承全部规则字段，额外带站点名称。"""
    site_name: Optional[str] = None


class HNRConfig(BaseConfig):
    """全局配置，包含插件开关、调度、站点列表等运行时配置。"""
    enabled: Optional[bool] = False
    check_period: int = 10                       # 检查间隔（分钟）
    sites: List[int] = Field(default_factory=list)
    site_infos: Dict = Field(default_factory=dict)
    onlyonce: Optional[bool] = False
    notify: NotifyMode = NotifyMode.ALWAYS
    downloader: Optional[List[str]] = Field(default_factory=list)  # 下载器列表（支持多个）
    hit_and_run_tag: Optional[str] = "H&R"
    auto_cleanup_days: float = 15
    auto_discover: Optional[bool] = False        # 自动发现下载器中未纳管的种子
    auto_monitor: Optional[bool] = False
    brush_plugin: Optional[str] = None
    # ---- 站点独立配置 ----
    enable_site_config: Optional[bool] = False
    site_config_str: Optional[str] = None
    site_configs: Dict[str, SiteConfig] = Field(default_factory=dict)

    @root_validator(pre=True, allow_reuse=True)
    def _check_enums(cls, values):
        notify_val = values.get("notify")
        valid = {m.value for m in NotifyMode}
        if notify_val not in valid:
            values["notify"] = NotifyMode.ALWAYS
        return values

    @validator("auto_cleanup_days", pre=True, allow_reuse=True)
    def _default_cleanup(cls, v):
        return 15 if v is None else v

    def __init__(self, **data):
        # 预处理：空字符串转 None（让 Optional[float] 等字段取默认值）
        _clean_empty_strings(data)
        super().__init__(**data)
        self._process_site_configs()

    def _process_site_configs(self):
        if not self.enable_site_config:
            return
        if not self.site_config_str:
            logger.warning("已启用站点独立配置但未提供配置字符串，已禁用")
            self.enable_site_config = False
            return
        parsed = _parse_yaml(self.site_config_str)
        if not parsed:
            logger.error("YAML 解析失败，站点独立配置已禁用")
            self.enable_site_config = False
            return
        self.site_configs = {
            name: self._merge(cfg) for name, cfg in parsed.items()
        }

    def _merge(self, site_cfg: SiteConfig) -> SiteConfig:
        for field_name in SiteConfig.__fields__:
            if getattr(site_cfg, field_name, None) is None:
                default = getattr(self, field_name, SiteConfig.__fields__[field_name].default)
                setattr(site_cfg, field_name, default)
        return site_cfg

    def get_site_config(self, site_name: str) -> SiteConfig:
        if cfg := self.site_configs.get(site_name):
            return cfg
        base = {f: getattr(self, f) for f in self.__fields__
                if f in SiteConfig.__fields__}
        return SiteConfig(**base, site_name=site_name)


def _is_float_type(ft) -> bool:
    if ft is float:
        return True
    if get_origin(ft) is Union:
        return float in get_args(ft)
    return False


def _clean_empty_strings(data: dict):
    """将空字符串转为 None，避免 Pydantic V2 float/bool 解析失败。保留 str 字段的空字符串。"""
    # 需要转 None 的字段类型
    _numeric_fields = {
        "hr_duration", "additional_seed_time", "hr_deadline_days",
        "hr_ratio", "hr_upload_multiplier", "check_period",
        "auto_cleanup_days",
    }
    for k, v in data.items():
        if v == "" and k in _numeric_fields:
            data[k] = None


def _parse_yaml(yaml_str: str) -> Optional[Dict[str, SiteConfig]]:
    yaml = YAML(typ="safe")
    try:
        data = yaml.load(yaml_str)
        configs: Dict[str, SiteConfig] = {}
        for item in data:
            name = item.get("site_name")
            if not name:
                continue
            try:
                # 处理 size_tiers
                tiers_raw = item.pop("hr_size_tiers", None)
                cfg = SiteConfig(**item)
                if tiers_raw and isinstance(tiers_raw, list):
                    cfg.hr_size_tiers = [SizeTier(**t) for t in tiers_raw]
                configs[name] = cfg
            except Exception as e:
                logger.error(f"站点 {name} 配置无效，已跳过: {e}")
        return configs
    except YAMLError as e:
        logger.error(f"YAML 解析错误: {e}")
        return None
