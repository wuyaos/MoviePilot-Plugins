# input: 无 | output: Vuetify JSON 构建辅助函数 | pos: 表单组件工厂

def v_row(cols: list) -> dict:
    return {"component": "VRow", "content": cols}

def v_col(md: int, content: dict) -> dict:
    return {"component": "VCol", "props": {"cols": 12, "md": md}, "content": [content]}

def v_switch(model: str, label: str) -> dict:
    return {"component": "VSwitch", "props": {"model": model, "label": label}}

def v_select(model: str, label: str, items: list) -> dict:
    return {"component": "VSelect", "props": {"model": model, "label": label, "items": items}}

def v_text(model: str, label: str, placeholder: str = "", input_type: str = "") -> dict:
    props: dict = {"model": model, "label": label}
    if placeholder:
        props["placeholder"] = placeholder
    if input_type:
        props["type"] = input_type
    return {"component": "VTextField", "props": props}

def v_cron(model: str, label: str, placeholder: str = "") -> dict:
    props: dict = {"model": model, "label": label}
    if placeholder:
        props["placeholder"] = placeholder
    props["hint"] = "5位cron表达式，留空则每天9-23点随机执行一次"
    return {"component": "VCronField", "props": props}
