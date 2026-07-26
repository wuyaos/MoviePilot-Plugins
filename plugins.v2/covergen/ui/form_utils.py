# input: 无
# output: Vuetify JSON 组件工厂函数
# pos: ui/ 工具层，签名对齐 azkeepalive，消除 form/page 中的 dict 嵌套
"""Vuetify JSON 组件工厂。签名与 plugins.v2/azkeepalive/core/form_utils.py 一致。"""
from __future__ import annotations

from typing import Any, Dict, List


def v_row(cols: list) -> dict:
    return {"component": "VRow", "content": cols}


def v_col(md: int, content: dict, cols: int = 12) -> dict:
    return {"component": "VCol", "props": {"cols": cols, "md": md}, "content": [content]}


def v_switch(model: str, label: str, hint: str = "") -> dict:
    props: Dict[str, Any] = {"model": model, "label": label}
    if hint:
        props["hint"] = hint
        props["persistentHint"] = True
    return {"component": "VSwitch", "props": props}


def v_select(model: str, label: str, items: list, *, multiple: bool = False,
             chips: bool = False, clearable: bool = False) -> dict:
    props: Dict[str, Any] = {"model": model, "label": label, "items": items}
    if multiple:
        props["multiple"] = True
    if chips:
        props["chips"] = True
    if clearable:
        props["clearable"] = True
    return {"component": "VSelect", "props": props}


def v_text(model: str, label: str, placeholder: str = "", input_type: str = "") -> dict:
    props: Dict[str, Any] = {"model": model, "label": label}
    if placeholder:
        props["placeholder"] = placeholder
    if input_type:
        props["type"] = input_type
    return {"component": "VTextField", "props": props}


def v_textarea(model: str, label: str, *, rows: int = 8, placeholder: str = "") -> dict:
    return {"component": "VTextarea", "props": {
        "model": model, "label": label, "rows": rows,
        "placeholder": placeholder, "autoGrow": True, "variant": "outlined",
    }}


def v_alert(text: str, type_: str = "info", *, class_: str = "mb-3 mt-2") -> dict:
    return {"component": "VAlert", "props": {
        "type": type_, "variant": "tonal", "text": text, "class": class_,
    }}


def v_divider_section(text: str) -> dict:
    """带顶部/底部间距的分组小标题。"""
    return {"component": "VRow", "props": {"class": "mt-3"}, "content": [{
        "component": "VCol", "props": {"cols": 12, "class": "py-1"},
        "content": [{"component": "div", "props": {
            "class": "text-subtitle-2 font-weight-medium text-medium-emphasis pt-2 pb-1",
        }, "text": text}],
    }]}


def v_cron(model: str, label: str = "执行周期", placeholder: str = "") -> dict:
    props: Dict[str, Any] = {"model": model, "label": label}
    if placeholder:
        props["placeholder"] = placeholder
    return {"component": "VCronField", "props": props}


def v_tab(value: str, label: str, icon: str = "mdi-cog") -> dict:
    """构造 VTabs 内的单个 VTab。"""
    return {"component": "VTab", "props": {"value": value}, "content": [
        {"component": "VIcon", "props": {"icon": icon, "start": True}},
        {"component": "span", "text": label},
    ]}


def v_window_item(value: str, content: list) -> dict:
    """构造 VWindow 内的单个 VWindowItem（含 VCardText 内层）。"""
    return {"component": "VWindowItem", "props": {"value": value},
            "content": [{"component": "VCardText", "content": content}]}
