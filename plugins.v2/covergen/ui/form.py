# input: PluginConfig + 库列表/用户列表/字体预设
# output: get_form() 的 (components, defaults) 元组
# pos: ui/ 表单构建层，VCard+VTabs+VDivider+VWindow 包装，避免 tab/content 重叠
"""Vuetify 配置表单构建。结构对齐 plugins.v2/mediacovergeneratorcustom。"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.plugins.covergen.ui.form_utils import (
    v_row, v_col, v_switch, v_select, v_text, v_alert, v_textarea, v_cron,
    v_tab, v_window_item, v_divider_section,
)


def _build_basic_tab(server_items: list) -> list:
    return [
        v_row([
            v_col(3, v_switch("enabled", "启用插件")),
            v_col(3, v_switch("update_now", "立即运行一次")),
            v_col(3, v_switch("transfer_monitor", "入库后自动更新")),
            v_col(3, v_switch("dry_run", "模拟运行")),
        ]),
        v_row([
            v_col(6, v_select("selected_servers", "媒体服务器", server_items, multiple=True, chips=True)),
            v_col(6, v_cron("cron", "执行周期", "留空则不定时执行")),
        ]),
        v_row([
            v_col(4, v_select("sort_by", "排序方式", [
                {"title": "随机", "value": "Random"},
                {"title": "最新添加", "value": "DateCreated"},
                {"title": "按名称", "value": "SortName"},
                {"title": "最新剧集", "value": "LatestEpisodeDate"},
            ])),
            v_col(4, v_text("delay", "入库延迟(秒)", input_type="number")),
            v_col(4, v_text("library_update_retry", "重试次数", input_type="number")),
        ]),
    ]


def _build_title_tab() -> list:
    return [
        v_alert("YAML格式：库名: [主标题, 副标题, 颜色(可选)]。特殊字符的库名需用双引号包裹"),
        v_row([v_col(12, v_textarea("title_config", "标题配置(YAML)", rows=12,
                                     placeholder="电影: [电影, Movies]\n电视剧: [追剧, TV Shows, '#FF5722']"))]),
    ]


def _style_preview_src(idx: int) -> str:
    """风格预览图（指向本仓库 images/ 目录，需要手动放置 style_1-5.jpeg）。"""
    return f"https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/images/style_{idx}.jpeg"


def _style_preview_cards() -> dict:
    """5 个风格预览卡，2 行布局。"""
    styles = [
        (1, "风格1", "static_1"), (2, "风格2", "static_2"),
        (3, "风格3", "static_3"), (4, "风格4", "static_4"),
        (5, "风格5", "static_5"),
    ]
    cards = []
    for idx, name, _ in styles:
        cards.append(v_col(2, {
            "component": "VCard",
            "props": {"variant": "flat", "elevation": 2, "class": "cursor-pointer"},
            "events": {"click": {"api": f"plugin/CoverGen/select_style_{idx}", "method": "post"}},
            "content": [
                {"component": "VImg", "props": {
                    "src": _style_preview_src(idx),
                    "aspect-ratio": "16/9", "cover": True,
                }},
                {"component": "VCardText",
                 "props": {"class": "py-2 text-center"},
                 "text": name},
            ],
        }))
    return v_row(cards)


def _build_style_tab() -> list:
    return [
        v_alert("点击下方风格卡片可快速切换；下面的选项控制更细参数"),
        _style_preview_cards(),
        v_row([
            v_col(6, v_select("cover_style_base", "风格模板", [
                {"title": "风格1（卡片旋转）", "value": "static_1"},
                {"title": "风格2（底部标题）", "value": "static_2"},
                {"title": "风格3（九宫格）", "value": "static_3"},
                {"title": "风格4（全屏模糊）", "value": "static_4"},
                {"title": "风格5（对角分割）", "value": "static_5"},
            ])),
            v_col(6, v_select("cover_style_variant", "动画模式", [
                {"title": "静态", "value": "static"},
                {"title": "动态", "value": "animated"},
            ])),
        ]),
        v_row([
            v_col(4, v_select("resolution", "分辨率", [
                {"title": "1080p", "value": "1080p"},
                {"title": "720p", "value": "720p"},
                {"title": "480p", "value": "480p"},
            ])),
            v_col(4, v_text("blur_size", "模糊强度", input_type="number")),
            v_col(4, v_text("color_ratio", "颜色比例", input_type="number")),
        ]),
        v_row([
            v_col(4, v_switch("use_primary", "优先使用海报图")),
            v_col(4, v_switch("multi_1_blur", "九宫格模糊背景")),
            v_col(4, v_text("title_scale", "标题缩放", input_type="number")),
        ]),
        v_divider_section("🎬 动画参数（仅动态模式生效）"),
        v_row([
            v_col(3, v_text("animation_duration", "动画时长(秒)", input_type="number")),
            v_col(3, v_text("animation_fps", "帧率", input_type="number")),
            v_col(3, v_select("animation_format", "格式", [
                {"title": "APNG", "value": "apng"},
                {"title": "GIF", "value": "gif"},
            ])),
            v_col(3, v_select("animation_reduce_colors", "减色", [
                {"title": "关闭", "value": "off"},
                {"title": "中等", "value": "medium"},
                {"title": "强", "value": "strong"},
            ])),
        ]),
        v_row([
            v_col(4, v_select("animation_scroll", "滚动方向", [
                {"title": "交替", "value": "alternate"},
                {"title": "向下", "value": "down"},
                {"title": "向上", "value": "up"},
                {"title": "反向交替", "value": "alternate_reverse"},
            ])),
            v_col(4, v_text("animated_2_image_count", "动画图片数(3-9)", input_type="number")),
            v_col(4, v_select("animated_2_departure_type", "离场方式", [
                {"title": "飞出", "value": "fly"},
                {"title": "淡出", "value": "fade"},
                {"title": "交叉淡入淡出", "value": "crossfade"},
            ])),
        ]),
    ]


def _build_font_tab(zh_items: list, en_items: list) -> list:
    return [
        v_row([
            v_col(6, v_select("zh_font_preset", "主标题字体", zh_items)),
            v_col(6, v_select("en_font_preset", "副标题字体", en_items)),
        ]),
        v_row([
            v_col(6, v_text("zh_font_custom", "主标题自定义(URL/路径)", "留空使用预设")),
            v_col(6, v_text("en_font_custom", "副标题自定义(URL/路径)", "留空使用预设")),
        ]),
        v_row([
            v_col(4, v_text("zh_font_size", "主标题字号", input_type="number")),
            v_col(4, v_text("en_font_size", "副标题字号", input_type="number")),
            v_col(4, v_text("zh_font_offset", "主标题偏移", input_type="number")),
        ]),
        v_row([
            v_col(6, v_text("title_spacing", "标题间距", input_type="number")),
            v_col(6, v_text("en_line_spacing", "副标题行距", input_type="number")),
        ]),
    ]


def _build_filter_tab(library_options: list, user_options: list) -> list:
    return [
        v_alert("黑名单：选中的库/合集来源/用户将被排除（需先选择媒体服务器保存后才能选择）"),
        v_row([v_col(12, v_select("exclude_libraries", "库黑名单", library_options,
                                   multiple=True, chips=True, clearable=True))]),
        v_row([
            v_col(6, v_select("exclude_boxsets", "合集来源库黑名单", library_options,
                              multiple=True, chips=True, clearable=True)),
            v_col(6, v_select("exclude_users", "用户黑名单", user_options,
                              multiple=True, chips=True, clearable=True)),
        ]),
    ]


def _build_other_tab() -> list:
    return [
        v_row([
            v_col(6, v_text("covers_input", "自定义图片输入目录")),
            v_col(6, v_text("covers_output", "历史封面输出目录")),
        ]),
        v_row([
            v_col(4, v_switch("save_recent_covers", "保存历史封面")),
            v_col(4, v_text("covers_history_limit_per_library", "每库保留数", input_type="number")),
            v_col(4, v_text("covers_page_history_limit", "页面显示数", input_type="number")),
        ]),
        v_row([
            v_col(6, v_select("bg_color_mode", "背景色模式", [
                {"title": "自动", "value": "auto"},
                {"title": "自定义", "value": "custom"},
            ])),
            v_col(6, v_text("custom_bg_color", "自定义背景色", "#FF5722 / rgb(255,87,34)")),
        ]),
    ]


_TAB_DEFS = [
    ("basic-tab", "基础设置", "mdi-cog"),
    ("title-tab", "标题设置", "mdi-format-title"),
    ("style-tab", "风格选择", "mdi-palette-swatch"),
    ("font-tab", "字体设置", "mdi-format-size"),
    ("filter-tab", "过滤设置", "mdi-filter-variant"),
    ("other-tab", "其他设置", "mdi-tune"),
]


def build_form(*, server_items: list, library_options: list, user_options: list,
               zh_font_items: list, en_font_items: list) -> Tuple[List[dict], Dict[str, Any]]:
    """构建完整 get_form() 返回值。"""
    tab_model = "tab"
    builders = {
        "basic-tab": _build_basic_tab(server_items),
        "title-tab": _build_title_tab(),
        "style-tab": _build_style_tab(),
        "font-tab": _build_font_tab(zh_font_items, en_font_items),
        "filter-tab": _build_filter_tab(library_options, user_options),
        "other-tab": _build_other_tab(),
    }
    components = [{
        "component": "VCard",
        "props": {"variant": "outlined"},
        "content": [
            {"component": "VTabs",
             "props": {"model": tab_model, "grow": True, "color": "primary"},
             "content": [v_tab(v, label, icon) for v, label, icon in _TAB_DEFS]},
            {"component": "VDivider"},
            {"component": "VWindow", "props": {"model": tab_model},
             "content": [v_window_item(v, builders[v]) for v, _, _ in _TAB_DEFS]},
        ],
    }]
    defaults = {
        "tab": "basic-tab", "enabled": False, "update_now": False,
        "transfer_monitor": True, "cron": "", "delay": 60, "selected_servers": [],
        "sort_by": "Random", "cover_style_base": "static_1", "cover_style_variant": "static",
        "resolution": "480p", "blur_size": 50, "color_ratio": 0.8,
        "use_primary": False, "multi_1_blur": True, "title_scale": 1.0,
        "animation_duration": 8, "animation_fps": 24, "animation_format": "apng",
        "animation_scroll": "alternate", "animation_reduce_colors": "medium",
        "animated_2_image_count": 6, "animated_2_departure_type": "fly",
        "zh_font_preset": "chaohei", "en_font_preset": "EmblemaOne",
        "zh_font_custom": "", "en_font_custom": "",
        "zh_font_size": 170, "en_font_size": 75,
        "zh_font_offset": "", "title_spacing": "", "en_line_spacing": "",
        "title_config": "", "exclude_libraries": [], "exclude_boxsets": [],
        "exclude_users": [], "covers_input": "", "covers_output": "",
        "save_recent_covers": True, "covers_history_limit_per_library": 10,
        "covers_page_history_limit": 50, "bg_color_mode": "auto",
        "custom_bg_color": "", "dry_run": False, "library_update_retry": 1,
    }
    return components, defaults
