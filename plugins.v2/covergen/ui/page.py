# input: PluginConfig 状态 + 历史封面数据
# output: get_page() 详情面板（扁平布局：生成 + 历史 + 清理三段）
# pos: ui/ 详情页构建层，扁平布局（get_page 无表单上下文，VTabs model 不响应）
"""详情面板：扁平三段式（生成 / 历史 / 清理）。"""
from __future__ import annotations

from typing import Any, Dict, List

from app.plugins.covergen.ui.form_utils import v_row, v_col, v_alert, v_divider_section


def _build_generate(*, enabled: bool, has_servers: bool, cover_style: str, plugin_id: str) -> list:
    warnings = []
    if not enabled:
        warnings.append(v_alert("插件未启用，请先在设置页启用并保存", "warning"))
    if not has_servers:
        warnings.append(v_alert("未选择媒体服务器", "warning"))
    style_names = {
        "static_1": "静态1（卡片旋转）", "static_2": "静态2（底部标题）",
        "static_3": "静态3（九宫格）", "static_4": "静态4（全屏模糊）",
        "static_5": "静态5（对角分割）",
        "animated_1": "动画1（卡片翻转）", "animated_2": "动画2（帷幕切换）",
        "animated_3": "动画3（斜向滚动）", "animated_4": "动画4（全屏渐变）",
    }
    gen_btn = {
        "component": "VBtn",
        "props": {"color": "primary", "variant": "elevated", "class": "mr-2"},
        "events": {"click": {"api": f"plugin/{plugin_id}/generate_now", "method": "post"}},
        "text": "立即生成全部封面",
    }
    return warnings + [
        v_alert(f"当前风格：{style_names.get(cover_style, cover_style)}"),
        v_row([v_col(4, gen_btn)]),
    ]


def _build_history(covers: List[Dict[str, Any]], plugin_id: str) -> list:
    if not covers:
        return [v_alert("暂无历史封面记录")]
    cards = []
    for c in covers:
        src = f"api/v1/plugin/{plugin_id}/saved_cover_image?file={c.get('file', '')}"
        cards.append({
            "component": "VCol",
            "props": {"cols": 12, "sm": 6, "md": 3},
            "content": [{
                "component": "VCard",
                "props": {"variant": "flat", "elevation": 2, "class": "rounded-lg"},
                "content": [
                    {"component": "VImg", "props": {"src": src, "aspect-ratio": "16/9", "cover": True}},
                    {"component": "VCardText", "props": {"class": "py-2"}, "text": c.get("label", "")},
                ],
            }],
        })
    return [v_row(cards)]


def _build_clean(plugin_id: str) -> list:
    clean_img = {
        "component": "VBtn",
        "props": {"color": "error", "variant": "elevated", "class": "mr-2"},
        "events": {"click": {"api": f"plugin/{plugin_id}/clean_images", "method": "post"}},
        "text": "清理图片缓存",
    }
    clean_font = {
        "component": "VBtn",
        "props": {"color": "error", "variant": "elevated"},
        "events": {"click": {"api": f"plugin/{plugin_id}/clean_fonts", "method": "post"}},
        "text": "清理字体缓存",
    }
    return [
        v_alert("清理操作不可撤销，请确认后再操作", "warning"),
        v_row([v_col(3, clean_img), v_col(3, clean_font)]),
    ]


def build_page(*, enabled: bool, has_servers: bool, cover_style: str,
               covers: List[Dict[str, Any]], plugin_id: str = "CoverGen") -> List[dict]:
    """构建扁平详情面板（生成 + 历史 + 清理三段）。"""
    try:
        return [
            *_build_generate(enabled=enabled, has_servers=has_servers,
                             cover_style=cover_style, plugin_id=plugin_id),
            v_divider_section("📚 历史封面"),
            *_build_history(covers, plugin_id),
            v_divider_section("🧹 清理缓存"),
            *_build_clean(plugin_id),
        ]
    except Exception as e:
        return [v_alert(f"页面渲染失败：{e}", "error")]
