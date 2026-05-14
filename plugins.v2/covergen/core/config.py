# input: dict 配置（来自 _PluginBase 的 get_config()）
# output: PluginConfig dataclass 实例（校验后的强类型配置）
# pos: core/ 配置层，统一所有配置字段的默认值、解析与校验
"""
CoverGen 插件配置层。

集中所有配置字段，避免原插件 130 行散乱的 config.get() + try/except cast。
通过 @dataclass + __post_init__ 统一校验、clamp、字段迁移。
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Tuple


# ---------- 常量 ----------

VALID_RESOLUTIONS = ("1080p", "720p", "480p")
VALID_STYLES = (
    "static_1", "static_2", "static_3", "static_4", "static_5",
    "animated_1", "animated_2", "animated_3", "animated_4", "animated_5",
)
VALID_VARIANTS = ("static", "animated")
VALID_BASE_STYLES = ("static_1", "static_2", "static_3", "static_4", "static_5")
VALID_SCROLL = ("down", "up", "alternate", "alternate_reverse")
VALID_FORMAT = ("apng", "gif")
VALID_REDUCE_COLORS = ("off", "medium", "strong")
VALID_DEPARTURE = ("fly", "fade", "crossfade")
VALID_BG_MODE = ("auto", "custom", "config")
VALID_PAGE_TAB = ("generate-tab", "history-tab", "clean-tab")
VALID_TITLE_MODE = ("json", "simple")

# 旧风格名 → 新风格名（一次性迁移）
LEGACY_STYLE_MAP = {"single_1": "static_1", "single_2": "static_2", "multi_1": "static_3"}


# ---------- 工具函数 ----------

def _cast(value: Any, target_type: type, default: Any) -> Any:
    """安全类型转换，失败返回 default。"""
    try:
        return target_type(value)
    except (ValueError, TypeError):
        return default


def _clamp(value: Any, low: float, high: float, default: float, cast: type = int) -> Any:
    """转换并夹紧到 [low, high]，失败用 default。"""
    parsed = _cast(value, cast, default)
    return max(low, min(high, parsed))


def _pick(value: Any, allowed: Tuple[str, ...], default: str) -> str:
    """白名单选择，未命中用 default。"""
    return value if value in allowed else default


# ---------- 主配置 ----------

@dataclass
class PluginConfig:
    """CoverGen 插件全量配置。"""

    # 基础开关
    enabled: bool = False
    update_now: bool = False
    transfer_monitor: bool = True
    cron: str = ""
    delay: int = 60

    # 媒体服务器
    selected_servers: List[str] = field(default_factory=list)
    all_libraries: List[Dict[str, Any]] = field(default_factory=list)
    sort_by: str = "Random"

    # 路径与素材
    covers_output: str = ""
    covers_input: str = ""

    # 标题
    title_config: str = ""
    title_edit_mode: str = "json"
    title_simple_library: str = ""
    title_simple_main: str = ""
    title_simple_sub: str = ""
    title_simple_bg: str = ""

    # 字体
    zh_font_url: str = ""
    en_font_url: str = ""
    zh_font_path: str = ""
    en_font_path: str = ""
    zh_font_custom: str = ""
    en_font_custom: str = ""
    zh_font_preset: str = "chaohei"
    en_font_preset: str = "EmblemaOne"
    zh_font_size: int = 170
    en_font_size: int = 75
    zh_font_offset: str = ""
    title_spacing: str = ""
    en_line_spacing: str = ""
    title_scale: float = 1.0

    # 风格
    cover_style: str = "static_1"
    cover_style_base: str = "static_1"
    cover_style_variant: str = "static"
    multi_1_blur: bool = True
    blur_size: int = 50
    color_ratio: float = 0.8
    use_primary: bool = False

    # 分辨率
    resolution: str = "480p"
    custom_width: int = 1920
    custom_height: int = 1080

    # 动画
    animation_duration: int = 8
    animation_scroll: str = "alternate"
    animation_fps: int = 24
    animation_format: str = "apng"
    animation_resolution: str = "320x180"
    animation_reduce_colors: str = "medium"
    animated_2_image_count: int = 6
    animated_2_departure_type: str = "fly"

    # 背景色
    bg_color_mode: str = "auto"
    custom_bg_color: str = ""

    # 过滤
    exclude_libraries: List[str] = field(default_factory=list)
    exclude_boxsets: List[str] = field(default_factory=list)
    exclude_users: List[str] = field(default_factory=list)

    # 历史与清理
    clean_images: bool = False
    clean_fonts: bool = False
    save_recent_covers: bool = True
    covers_history_limit_per_library: int = 10
    covers_page_history_limit: int = 50

    # 运行控制
    dry_run: bool = False
    library_update_retry: int = 1
    manual_server: str = ""
    manual_library_id: str = ""
    manual_item_id: str = ""

    # UI
    page_tab: str = "generate-tab"

    # 迁移标志
    style_naming_v2: bool = True

    # ---------- 校验 ----------

    def __post_init__(self):
        """统一校验、夹紧、白名单回退。"""
        # 风格迁移
        if self.cover_style in LEGACY_STYLE_MAP:
            self.cover_style = LEGACY_STYLE_MAP[self.cover_style]
        self.cover_style = _pick(self.cover_style, VALID_STYLES, "static_1")
        self.cover_style_base = _pick(self.cover_style_base, VALID_BASE_STYLES, "static_1")
        self.cover_style_variant = _pick(self.cover_style_variant, VALID_VARIANTS, "static")

        # 字符串白名单
        self.resolution = _pick(self.resolution, VALID_RESOLUTIONS, "480p")
        self.animation_scroll = _pick(self.animation_scroll, VALID_SCROLL, "alternate")
        # webp 已停用 → gif
        if self.animation_format == "webp":
            self.animation_format = "gif"
        self.animation_format = _pick(self.animation_format, VALID_FORMAT, "apng")
        self.animation_resolution = "320x180"  # 固定，原插件硬编码
        if isinstance(self.animation_reduce_colors, bool):
            self.animation_reduce_colors = "medium" if self.animation_reduce_colors else "off"
        self.animation_reduce_colors = _pick(self.animation_reduce_colors, VALID_REDUCE_COLORS, "medium")
        self.animated_2_departure_type = _pick(self.animated_2_departure_type, VALID_DEPARTURE, "fly")
        self.bg_color_mode = _pick(self.bg_color_mode, VALID_BG_MODE, "auto")
        self.page_tab = _pick(self.page_tab, VALID_PAGE_TAB, "generate-tab")
        self.title_edit_mode = _pick(self.title_edit_mode, VALID_TITLE_MODE, "json")

        # 数值夹紧
        self.delay = _cast(self.delay, int, 60)
        self.blur_size = _cast(self.blur_size, int, 50)
        self.color_ratio = _cast(self.color_ratio, float, 0.8)
        self.title_scale = _cast(self.title_scale, float, 1.0)
        self.zh_font_size = _cast(self.zh_font_size, int, 170)
        self.en_font_size = _cast(self.en_font_size, int, 75)
        self.animation_duration = _cast(self.animation_duration, int, 8)
        self.animation_fps = _cast(self.animation_fps, int, 24)
        self.animated_2_image_count = _clamp(self.animated_2_image_count, 3, 9, 5, int)
        self.covers_history_limit_per_library = _clamp(self.covers_history_limit_per_library, 1, 100, 10, int)
        self.covers_page_history_limit = _clamp(self.covers_page_history_limit, 1, 500, 50, int)
        self.library_update_retry = _clamp(self.library_update_retry, 1, 5, 1, int)

        # 字符串 strip
        self.manual_server = (self.manual_server or "").strip()
        self.manual_library_id = (self.manual_library_id or "").strip()
        self.manual_item_id = (self.manual_item_id or "").strip()

    # ---------- 派生属性 ----------

    @property
    def is_single_image_style(self) -> bool:
        return self.cover_style in ("static_1", "static_2", "static_4", "static_5")

    @property
    def required_items(self) -> int:
        if self.cover_style in ("static_3", "animated_3"):
            return 9
        if self.cover_style in ("animated_1", "animated_2", "animated_4"):
            return self.animated_2_image_count
        return 1

    def compose_style(self) -> str:
        """根据 base + variant 合成完整风格名。
        如果 base 没有对应的 animated 实现，自动回落到 static。"""
        base = _pick(self.cover_style_base, VALID_BASE_STYLES, "static_1")
        variant = _pick(self.cover_style_variant, VALID_VARIANTS, "static")
        suffix = base.split("_")[-1]
        if variant == "static":
            return base
        candidate = f"animated_{suffix}"
        # animated_5 暂未实现，回落到 static_5
        return candidate if candidate in VALID_STYLES else base

    # ---------- 序列化 ----------

    @classmethod
    def from_dict(cls, data: Dict[str, Any] | None) -> "PluginConfig":
        """从原始 dict 构造，未知键忽略、缺失键用默认值。"""
        if not data:
            return cls()
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)

    def to_dict(self) -> Dict[str, Any]:
        """导出为 dict，供 update_config 持久化。"""
        return asdict(self)
