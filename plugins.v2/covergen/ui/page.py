# input: PluginConfig + 封面历史数据
# output: get_page() 的 Vuetify JSON 组件列表
# pos: ui/ 页面构建层，替代原 357 行 get_page()
"""Vuetify 仪表盘页面构建。拆为 3 个 sub-page builder。"""
from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, Dict, List

from app.plugins.covergen.ui.form_utils import v_row, v_col, v_alert, v_card, v_btn


def _build_generate_subpage(*, enabled: bool, has_servers: bool,
                            cover_style: str, plugin_id: str) -> list:
    """封面生成控制面板。"""
    warnings = []
    if not enabled:
        warnings.append(v_alert("插件未启用，请先在设置页启用并保存", "warning"))
    if not has_servers:
        warnings.append(v_alert("未选择媒体服务器", "warning"))
    style_names = {
        "static_1": "静态1（卡片旋转）", "static_2": "静态2（底部标题）",
        "static_3": "静态3（九宫格）", "static_4": "静态4（全屏模糊）",
        "animated_1": "动画1（卡片翻转）", "animated_2": "动画2（帷幕切换）",
        "animated_3": "动画3（斜向滚动）", "animated_4": "动画4（全屏渐变）",
    }
    info = v_alert(f"当前风格：{style_names.get(cover_style, cover_style)}", "info")
    btn = v_row(v_col(
        v_btn("立即生成全部封面", click_api=f"plugin/{plugin_id}/generate_now"), md=4))
    return warnings + [info, btn]


def _build_history_subpage(*, covers: List[Dict[str, Any]], plugin_id: str) -> list:
    """历史封面网格。"""
    if not covers:
        return [v_alert("暂无历史封面记录")]
    grid = []
    for c in covers:
        src = f"api/v1/plugin/{plugin_id}/saved_cover_image?file={c.get('file', '')}"
        card = v_card(
            {"component": "VImg", "props": {"src": src, "height": 150, "cover": True}},
            {"component": "VCardText", "text": c.get("label", "")},
        )
        grid.append(v_col(card, cols=6, md=3))
    return [v_row(*grid)]


def _build_clean_subpage(*, plugin_id: str) -> list:
    """清理缓存面板。"""
    return [
        v_alert("清理操作不可撤销，请确认后再操作", "warning"),
        v_row(
            v_col(v_btn("清理图片缓存", color="error",
                        click_api=f"plugin/{plugin_id}/clean_images"), md=4),
            v_col(v_btn("清理字体缓存", color="error",
                        click_api=f"plugin/{plugin_id}/clean_fonts"), md=4),
        ),
    ]


def build_page(*, enabled: bool, has_servers: bool, cover_style: str,
               covers: List[Dict[str, Any]], plugin_id: str = "CoverGen") -> List[dict]:
    """构建完整 get_page() 返回值。"""
    try:
        return [
            *_build_generate_subpage(enabled=enabled, has_servers=has_servers,
                                     cover_style=cover_style, plugin_id=plugin_id),
            v_alert("历史封面", "info"),
            *_build_history_subpage(covers=covers, plugin_id=plugin_id),
            v_alert("清理缓存", "info"),
            *_build_clean_subpage(plugin_id=plugin_id),
        ]
    except Exception as e:
        return [v_alert(f"页面渲染失败：{e}", "error")]
