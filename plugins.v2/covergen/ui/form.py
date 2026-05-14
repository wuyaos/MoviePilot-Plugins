# input: PluginConfig + 库列表/用户列表/字体预设
# output: get_form() 的 (components, defaults) 元组
# pos: ui/ 表单构建层，替代原 1262 行 get_form()
"""Vuetify 配置表单构建。拆为 5 个 tab builder。"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.plugins.covergen.ui.form_utils import (
    v_row, v_col, v_switch, v_select, v_text, v_alert, v_textarea,
    v_tabs, v_window, v_card, v_cron,
)


def _build_basic_tab(server_items: list) -> list:
    return [
        v_row(
            v_col(v_switch("enabled", "启用插件"), md=3),
            v_col(v_switch("update_now", "立即运行一次"), md=3),
            v_col(v_switch("transfer_monitor", "入库后自动更新"), md=3),
            v_col(v_switch("dry_run", "模拟运行"), md=3),
        ),
        v_row(
            v_col(v_select("selected_servers", "媒体服务器", server_items, multiple=True, chips=True), md=6),
            v_col(v_cron("cron"), md=6),
        ),
        v_row(
            v_col(v_select("sort_by", "排序方式", [
                {"title": "随机", "value": "Random"},
                {"title": "最新添加", "value": "DateCreated"},
                {"title": "按名称", "value": "SortName"},
                {"title": "最新剧集", "value": "LatestEpisodeDate"},
            ]), md=4),
            v_col(v_text("delay", "入库延迟(秒)", type_="number"), md=4),
            v_col(v_text("library_update_retry", "重试次数", type_="number"), md=4),
        ),
    ]


def _build_title_tab() -> list:
    return [
        v_alert("YAML格式：库名: [主标题, 副标题, 颜色(可选)]。特殊字符的库名需用双引号包裹"),
        v_row(v_col(v_textarea("title_config", "标题配置(YAML)", rows=12,
                               placeholder="电影: [电影, Movies]\n电视剧: [追剧, TV Shows, '#FF5722']"), cols=12, md=12)),
    ]


def _build_style_tab() -> list:
    return [
        v_row(
            v_col(v_select("cover_style_base", "风格模板", [
                {"title": "风格1（卡片旋转）", "value": "static_1"},
                {"title": "风格2（底部标题）", "value": "static_2"},
                {"title": "风格3（九宫格）", "value": "static_3"},
                {"title": "风格4（全屏模糊）", "value": "static_4"},
                {"title": "风格5（对角分割）", "value": "static_5"},
            ]), md=6),
            v_col(v_select("cover_style_variant", "动画模式", [
                {"title": "静态", "value": "static"},
                {"title": "动态", "value": "animated"},
            ]), md=6),
        ),
        v_row(
            v_col(v_select("resolution", "分辨率", [
                {"title": "1080p", "value": "1080p"},
                {"title": "720p", "value": "720p"},
                {"title": "480p", "value": "480p"},
            ]), md=4),
            v_col(v_text("blur_size", "模糊强度", type_="number"), md=4),
            v_col(v_text("color_ratio", "颜色比例", type_="number"), md=4),
        ),
        v_row(
            v_col(v_switch("use_primary", "优先使用海报图"), md=4),
            v_col(v_switch("multi_1_blur", "九宫格模糊背景"), md=4),
            v_col(v_text("title_scale", "标题缩放", type_="number"), md=4),
        ),
        v_alert("动画参数（仅动态模式生效）", "info"),
        v_row(
            v_col(v_text("animation_duration", "动画时长(秒)", type_="number"), md=3),
            v_col(v_text("animation_fps", "帧率", type_="number"), md=3),
            v_col(v_select("animation_format", "格式", [
                {"title": "APNG", "value": "apng"},
                {"title": "GIF", "value": "gif"},
            ]), md=3),
            v_col(v_select("animation_reduce_colors", "减色", [
                {"title": "关闭", "value": "off"},
                {"title": "中等", "value": "medium"},
                {"title": "强", "value": "strong"},
            ]), md=3),
        ),
        v_row(
            v_col(v_select("animation_scroll", "滚动方向", [
                {"title": "交替", "value": "alternate"},
                {"title": "向下", "value": "down"},
                {"title": "向上", "value": "up"},
                {"title": "反向交替", "value": "alternate_reverse"},
            ]), md=4),
            v_col(v_text("animated_2_image_count", "动画图片数(3-9)", type_="number"), md=4),
            v_col(v_select("animated_2_departure_type", "离场方式", [
                {"title": "飞出", "value": "fly"},
                {"title": "淡出", "value": "fade"},
                {"title": "交叉淡入淡出", "value": "crossfade"},
            ]), md=4),
        ),
    ]


def _build_font_tab(zh_items: list, en_items: list) -> list:
    return [
        v_row(
            v_col(v_select("zh_font_preset", "主标题字体", zh_items), md=6),
            v_col(v_select("en_font_preset", "副标题字体", en_items), md=6),
        ),
        v_row(
            v_col(v_text("zh_font_custom", "主标题自定义(URL/路径)", placeholder="留空使用预设"), md=6),
            v_col(v_text("en_font_custom", "副标题自定义(URL/路径)", placeholder="留空使用预设"), md=6),
        ),
        v_row(
            v_col(v_text("zh_font_size", "主标题字号", type_="number"), md=4),
            v_col(v_text("en_font_size", "副标题字号", type_="number"), md=4),
            v_col(v_text("zh_font_offset", "主标题偏移", type_="number"), md=4),
        ),
        v_row(
            v_col(v_text("title_spacing", "标题间距", type_="number"), md=6),
            v_col(v_text("en_line_spacing", "副标题行距", type_="number"), md=6),
        ),
    ]


def _build_filter_tab(library_options: list, user_options: list) -> list:
    return [
        v_alert("黑名单：选中的库/合集来源/用户将被排除"),
        v_row(
            v_col(v_select("exclude_libraries", "库黑名单", library_options,
                           multiple=True, chips=True, clearable=True), md=12),
        ),
        v_row(
            v_col(v_select("exclude_boxsets", "合集来源库黑名单", library_options,
                           multiple=True, chips=True, clearable=True), md=6),
            v_col(v_select("exclude_users", "用户黑名单", user_options,
                           multiple=True, chips=True, clearable=True), md=6),
        ),
    ]


def _build_other_tab() -> list:
    return [
        v_row(
            v_col(v_text("covers_input", "自定义图片输入目录"), md=6),
            v_col(v_text("covers_output", "历史封面输出目录"), md=6),
        ),
        v_row(
            v_col(v_switch("save_recent_covers", "保存历史封面"), md=4),
            v_col(v_text("covers_history_limit_per_library", "每库保留数", type_="number"), md=4),
            v_col(v_text("covers_page_history_limit", "页面显示数", type_="number"), md=4),
        ),
        v_row(
            v_col(v_select("bg_color_mode", "背景色模式", [
                {"title": "自动", "value": "auto"},
                {"title": "自定义", "value": "custom"},
            ]), md=6),
            v_col(v_text("custom_bg_color", "自定义背景色", placeholder="#FF5722 / rgb(255,87,34)"), md=6),
        ),
    ]


def build_form(*, server_items: list, library_options: list, user_options: list,
               zh_font_items: list, en_font_items: list) -> Tuple[List[dict], Dict[str, Any]]:
    """构建完整 get_form() 返回值。"""
    tab_model = "_tab"
    tabs_def = [
        {"title": "基础设置", "value": "basic-tab"},
        {"title": "标题设置", "value": "title-tab"},
        {"title": "风格选择", "value": "style-tab"},
        {"title": "字体设置", "value": "font-tab"},
        {"title": "过滤设置", "value": "filter-tab"},
        {"title": "其他设置", "value": "other-tab"},
    ]
    window_items = [
        {"value": "basic-tab", "content": _build_basic_tab(server_items)},
        {"value": "title-tab", "content": _build_title_tab()},
        {"value": "style-tab", "content": _build_style_tab()},
        {"value": "font-tab", "content": _build_font_tab(zh_font_items, en_font_items)},
        {"value": "filter-tab", "content": _build_filter_tab(library_options, user_options)},
        {"value": "other-tab", "content": _build_other_tab()},
    ]
    components = [v_card(v_tabs(tab_model, tabs_def), v_window(tab_model, window_items))]
    defaults = {
        "_tab": "basic-tab", "enabled": False, "update_now": False,
        "transfer_monitor": True, "cron": "", "delay": 60,
        "selected_servers": [], "sort_by": "Random",
        "cover_style_base": "static_1", "cover_style_variant": "static",
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
