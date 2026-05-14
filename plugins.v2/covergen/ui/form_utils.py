# input: 无
# output: Vuetify JSON 组件工厂函数
# pos: ui/ 工具层，消除 get_form/get_page 中的 dict 嵌套重复
"""Vuetify JSON 组件工厂。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def v_row(*children) -> dict:
    return {"component": "VRow", "content": list(children)}


def v_col(*children, cols: int = 12, md: int = 6) -> dict:
    return {"component": "VCol", "props": {"cols": cols, "md": md}, "content": list(children)}


def v_switch(model: str, label: str) -> dict:
    return {"component": "VSwitch", "props": {"model": model, "label": label, "hint": "", "persistent-hint": True}}


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


def v_text(model: str, label: str, *, placeholder: str = "", type_: str = "text",
           hint: str = "") -> dict:
    props: Dict[str, Any] = {"model": model, "label": label, "placeholder": placeholder, "type": type_}
    if hint:
        props["hint"] = hint
        props["persistent-hint"] = True
    return {"component": "VTextField", "props": props}


def v_alert(text: str, type_: str = "info", *, cls: str = "mb-3") -> dict:
    return {"component": "VAlert", "props": {"type": type_, "variant": "tonal", "text": text, "class": cls}}


def v_textarea(model: str, label: str, *, rows: int = 8, placeholder: str = "",
               auto_grow: bool = True) -> dict:
    return {"component": "VTextarea", "props": {
        "model": model, "label": label, "rows": rows, "placeholder": placeholder,
        "auto-grow": auto_grow, "variant": "outlined"}}


def v_tabs(model: str, items: List[Dict[str, str]]) -> dict:
    return {"component": "VTabs", "props": {"model": model, "style": "margin-top: 0px;"},
            "content": [{"component": "VTab", "props": {"value": it["value"]}, "text": it["title"]}
                        for it in items]}


def v_window(model: str, items: List[Dict[str, Any]]) -> dict:
    """items: [{value, content: [components]}]"""
    return {"component": "VWindow", "props": {"model": model},
            "content": [{"component": "VWindowItem", "props": {"value": it["value"]},
                         "content": it["content"]} for it in items]}


def v_card(*children, title: str = "", flat: bool = False) -> dict:
    props: Dict[str, Any] = {}
    if flat:
        props["flat"] = True
    content = list(children)
    if title:
        content.insert(0, {"component": "VCardTitle", "text": title})
    return {"component": "VCard", "props": props, "content": content}


def v_cron(model: str, label: str = "执行周期") -> dict:
    return {"component": "VCronField", "props": {"model": model, "label": label}}


def v_btn(text: str, *, color: str = "primary", variant: str = "elevated",
          click_api: str = "") -> dict:
    props: Dict[str, Any] = {"variant": variant, "color": color}
    if click_api:
        props["@click"] = f"api:{click_api}"
    return {"component": "VBtn", "props": props, "text": text}
