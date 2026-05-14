# input: plugin 实例（CoverGen）
# output: get_api() 可用的路由列表
# pos: api/ 统一路由层，消除原 40 处重复 dict
"""统一 API 路由构建。列表驱动 + 循环生成 /path 与 path 两版。"""
from __future__ import annotations

from typing import Any, Dict, List


def ok(msg: str = "success", data: Any = None) -> Dict[str, Any]:
    """统一成功响应。"""
    return {"code": 0, "msg": msg, "data": data}


def err(msg: str = "error") -> Dict[str, Any]:
    """统一失败响应。"""
    return {"code": 1, "msg": msg}


def build_api_routes(plugin) -> List[Dict[str, Any]]:
    """
    从 plugin 实例构建完整 API 路由表。
    每条路由自动生成带/不带前导斜杠两版。
    """
    # (path_suffix, endpoint_method, auth, methods, summary)
    specs = [
        ("clean_images", plugin.api_clean_images, "bear", ["POST"], "清理图片缓存"),
        ("clean_fonts", plugin.api_clean_fonts, "bear", ["POST"], "清理字体缓存"),
        ("delete_saved_cover", plugin.api_delete_saved_cover, "bear", ["POST", "GET"], "删除已保存封面"),
        ("generate_now", plugin.api_generate_now, "bear", ["POST", "GET"], "立即生成封面"),
        ("generate_library_now", plugin.api_generate_library_now, "bear", ["POST", "GET"], "生成指定库封面"),
        ("set_cover_style", plugin.api_set_cover_style, "bear", ["POST", "GET"], "保存封面风格"),
        ("toggle_style_variant", plugin.api_toggle_style_variant, "bear", ["POST"], "切换静态/动态"),
        ("select_style_1", plugin.api_select_style_1, "bear", ["POST"], "选择风格1"),
        ("select_style_2", plugin.api_select_style_2, "bear", ["POST"], "选择风格2"),
        ("select_style_3", plugin.api_select_style_3, "bear", ["POST"], "选择风格3"),
        ("select_style_4", plugin.api_select_style_4, "bear", ["POST"], "选择风格4"),
        ("set_page_tab_generate", plugin.api_set_page_tab_generate, "bear", ["POST"], "切换到生成页"),
        ("set_page_tab_history", plugin.api_set_page_tab_history, "bear", ["POST"], "切换到历史页"),
        ("set_page_tab_clean", plugin.api_set_page_tab_clean, "bear", ["POST"], "切换到清理页"),
        ("saved_cover_image", plugin.api_saved_cover_image, None, ["GET"], "获取已保存封面图片"),
    ]
    routes = []
    for suffix, endpoint, auth, methods, summary in specs:
        base = {"endpoint": endpoint, "methods": methods, "summary": summary}
        if auth:
            base["auth"] = auth
        routes.append({**base, "path": f"/{suffix}"})
        routes.append({**base, "path": suffix, "summary": f"{summary}(兼容)"})
    return routes
