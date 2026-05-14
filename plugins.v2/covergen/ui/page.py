# input: PluginConfig 状态 + 历史封面数据
# output: get_page() 详情面板（扁平布局：生成 + 历史 + 清理三段）
# pos: ui/ 详情页构建层，VCard 包裹统一风格
"""详情面板：VCard 包裹，三段式（生成 / 历史 / 清理）。"""
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
        "animated_5": "动画5（对角淡入淡出）",
    }
    gen_btn = {
        "component": "VBtn",
        "props": {"color": "primary", "variant": "elevated", "class": "mr-2", "prependIcon": "mdi-play"},
        "events": {"click": {"api": f"plugin/{plugin_id}/generate_now", "method": "post"}},
        "text": "立即生成全部封面",
    }
    return warnings + [
        v_row([v_col(12, {"component": "VChip", "props": {
            "color": "primary", "variant": "tonal", "prependIcon": "mdi-palette",
        }, "text": f"当前风格：{style_names.get(cover_style, cover_style)}"})]),
        v_row([v_col(4, gen_btn)]),
    ]


def _cover_card(c: Dict[str, Any]) -> dict:
    src = c.get("src", "")
    return {
        "component": "VCol",
        "props": {"cols": 6, "sm": 4, "md": 3},
        "content": [{
            "component": "VCard",
            "props": {"variant": "outlined", "class": "rounded-lg overflow-hidden"},
            "content": [
                {"component": "VImg", "props": {
                    "src": src, "aspect-ratio": "16/9", "cover": True, "height": 120,
                }},
                {"component": "VCardText", "props": {"class": "py-1 text-caption text-truncate"},
                 "text": c.get("label", "")},
            ],
        }],
    }


def _build_history(covers: List[Dict[str, Any]], plugin_id: str) -> list:
    valid_covers = [c for c in covers if c.get("src")]
    title = {"component": "div", "props": {
        "class": "text-subtitle-2 font-weight-medium text-medium-emphasis mt-2 mb-1",
    }, "text": f"📚 历史封面（{len(valid_covers)} 张）"}
    if not valid_covers:
        empty = {"component": "div", "props": {
            "class": "text-center text-medium-emphasis py-4",
        }, "text": "暂无历史封面，生成后将在此展示"}
        return [v_row([v_col(12, title)]), v_row([v_col(12, empty)])]

    first_row = valid_covers[:4]
    rest = valid_covers[4:]
    blocks = [
        v_row([v_col(12, title)]),
        {"component": "VRow", "props": {"dense": True}, "content": [_cover_card(c) for c in first_row]},
    ]
    if rest:
        blocks.append({
            "component": "VExpansionPanels",
            "props": {"variant": "accordion", "class": "mt-1"},
            "content": [{
                "component": "VExpansionPanel",
                "content": [
                    {"component": "VExpansionPanelTitle",
                     "props": {"class": "text-body-2"},
                     "text": f"展开更多历史封面（{len(rest)} 张）"},
                    {"component": "VExpansionPanelText",
                     "content": [{"component": "VRow", "props": {"dense": True},
                                  "content": [_cover_card(c) for c in rest]}]},
                ],
            }],
        })
    return blocks


def _build_clean(plugin_id: str) -> list:
    clean_img = {
        "component": "VBtn",
        "props": {"color": "warning", "variant": "tonal", "size": "small",
                  "prependIcon": "mdi-image-remove"},
        "events": {"click": {"api": f"plugin/{plugin_id}/clean_images", "method": "post"}},
        "text": "清理图片缓存",
    }
    clean_font = {
        "component": "VBtn",
        "props": {"color": "warning", "variant": "tonal", "size": "small",
                  "prependIcon": "mdi-format-clear", "class": "ml-2"},
        "events": {"click": {"api": f"plugin/{plugin_id}/clean_fonts", "method": "post"}},
        "text": "清理字体缓存",
    }
    return [v_row([v_col(6, clean_img), v_col(6, clean_font)])]


def _build_run_status(run_history, last_run=None) -> list:
    """最近执行情况：按运行汇总列表。"""
    def _get(obj, key, default=None):
        return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)

    history = run_history or []
    if history:
        rows = []
        for run in history:
            started = str(_get(run, "started_at", ""))[:19] or "-"
            finished = str(_get(run, "finished_at", ""))[:19] or started
            mode = _get(run, "mode", "") or "all"
            dry_run = _get(run, "dry_run", False)
            success = _get(run, "success", 0)
            failed = _get(run, "failed", 0)
            skipped = _get(run, "skipped", 0)
            status = "成功" if failed == 0 else "部分失败"
            status_color = "success" if failed == 0 else "error"
            rows.append({"component": "tr", "content": [
                {"component": "td", "text": finished},
                {"component": "td", "text": f"{mode}{' / 模拟' if dry_run else ''}"},
                {"component": "td", "text": f"成 {success} 败 {failed} 跳 {skipped}"},
                {"component": "td", "content": [{"component": "VChip", "props": {
                    "color": status_color, "variant": "tonal", "size": "small",
                }, "text": status}]},
            ]})
        table = {"component": "VTable", "props": {"density": "compact", "class": "mt-2"}, "content": [
            {"component": "thead", "content": [{"component": "tr", "content": [
                {"component": "th", "text": "时间"},
                {"component": "th", "text": "模式"},
                {"component": "th", "text": "统计"},
                {"component": "th", "text": "状态"},
            ]}]},
            {"component": "tbody", "content": rows},
        ]}
        return [v_row([{"component": "VCol", "props": {"cols": 12}, "content": [table]}])]

    if not last_run:
        return [v_row([v_col(12, {"component": "div", "props": {
            "class": "text-center text-medium-emphasis py-2",
        }, "text": "尚无执行记录"})])]

    success = _get(last_run, "success", 0)
    failed = _get(last_run, "failed", 0)
    skipped = _get(last_run, "skipped", 0)
    mode = _get(last_run, "mode", "")
    finished = _get(last_run, "finished_at", "")
    chips = [
        {"component": "VChip", "props": {"color": "success", "variant": "tonal", "size": "small", "class": "mr-1",
                                          "prependIcon": "mdi-check-circle"}, "text": f"成功 {success}"},
    ]
    if failed:
        chips.append({"component": "VChip", "props": {"color": "error", "variant": "tonal", "size": "small",
                                                       "class": "mr-1", "prependIcon": "mdi-close-circle"},
                      "text": f"失败 {failed}"})
    if skipped:
        chips.append({"component": "VChip", "props": {"color": "warning", "variant": "tonal", "size": "small",
                                                       "class": "mr-1", "prependIcon": "mdi-skip-next"},
                      "text": f"跳过 {skipped}"})
    chips.append({"component": "VChip", "props": {"variant": "text", "size": "small"},
                  "text": f"{mode} | {str(finished)[:19] if finished else '运行中'}"})
    return [v_row([{"component": "VCol", "props": {"cols": 12}, "content": chips}])]


def build_page(*, enabled: bool, has_servers: bool, cover_style: str,
               covers: List[Dict[str, Any]], plugin_id: str = "CoverGen",
               last_run=None, run_history=None) -> List[dict]:
    """构建详情面板（VCard 包裹：生成 + 历史 + 执行情况）。"""
    try:
        content = [
            *_build_generate(enabled=enabled, has_servers=has_servers,
                             cover_style=cover_style, plugin_id=plugin_id),
            *_build_history(covers, plugin_id),
            v_divider_section("📊 最近执行"),
            *_build_run_status(run_history, last_run),
        ]
        return [{
            "component": "VCard",
            "props": {"variant": "outlined", "class": "pa-3"},
            "content": content,
        }]
    except Exception as e:
        return [v_alert(f"页面渲染失败：{e}", "error")]
