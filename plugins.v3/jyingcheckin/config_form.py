"""聚影签到 - 配置页 Vuetify JSON 拼装（声明式，无 vue 联邦）。

参考 plugins.v2/dian115sign/config_form.py 的拼装风格。
"""

from typing import Any, Dict, List, Tuple


def build_form() -> Tuple[List[dict], Dict[str, Any]]:
    """返回插件配置表单 (conf, model 默认值)。"""

    def card(title_icon: str, title_color: str, title_text: str, rows: List[dict]) -> dict:
        return {
            "component": "VCard",
            "props": {"class": "mt-3"},
            "content": [
                {"component": "VCardTitle", "props": {"class": "d-flex align-center"}, "content": [
                    {"component": "VIcon", "props": {"color": title_color, "class": "mr-2"}, "text": title_icon},
                    {"component": "span", "text": title_text},
                ]},
                {"component": "VDivider"},
                {"component": "VCardText", "content": rows},
            ],
        }

    def col(md: int, component: dict) -> dict:
        return {"component": "VCol", "props": {"cols": 12, "md": md}, "content": [component]}

    def _props(model: str, label: str, kwargs: dict) -> dict:
        props = {"model": model, "label": label}
        for k, v in kwargs.items():
            props[k.replace("_", "-")] = v
        return props

    def textfield(model: str, label: str, **kwargs) -> dict:
        return {"component": "VTextField", "props": _props(model, label, kwargs)}

    def switch(model: str, label: str, color: str = "primary", **kwargs) -> dict:
        props = _props(model, label, kwargs)
        props["color"] = color
        return {"component": "VSwitch", "props": props}

    def alert(atype: str, text: str, **kwargs) -> dict:
        props = {"type": atype, "variant": "tonal", "text": text}
        for k, v in kwargs.items():
            props[k.rstrip("_").replace("_", "-")] = v
        return {"component": "VAlert", "props": props}

    def row(items: List[dict]) -> dict:
        return {"component": "VRow", "content": items}

    form = [
        {
            "component": "VForm",
            "content": [
                # ── 基础设置 ──
                card("mdi-cog", "primary", "基础设置", [
                    row([
                        col(3, switch("enabled", "启用插件", "primary")),
                        col(3, switch("notify", "发送通知", "info")),
                        col(3, switch("lucky_mode", "幸运签", "success")),
                        col(3, switch("onlyonce", "立即运行一次", "warning")),
                    ]),
                    row([
                        col(6, textfield("username", "聚影账号", placeholder="注册手机号或用户名")),
                        col(6, textfield("password", "密码", type="password")),
                    ]),
                    alert("info",
                          "账密登录换取 7 天有效 token，过期自动续登（站点支持多端登录，不影响浏览器会话）；"
                          "token 只存插件数据，不回写配置。", class_="mt-2"),
                ]),
                # ── 调度设置 ──
                card("mdi-clock-outline", "primary", "调度设置", [
                    row([
                        col(4, textfield("cron", "签到 Cron", placeholder="30 8 * * *")),
                        col(4, textfield("retry_count", "失败重试次数", type="number", min=0)),
                        col(4, textfield("retry_interval", "重试间隔（分钟）", type="number", min=1)),
                    ]),
                    alert("success",
                          "幸运签开启后每日抽取幸运签到（奖励随机）；缺少用户 ID 时自动降级普通签。"
                          "成功/已签/认证失败不进入重试链。", class_="mt-2"),
                ]),
            ],
        }
    ]

    import json
    from pathlib import Path

    defaults_path = Path(__file__).parent / "config_defaults.json"
    model = json.loads(defaults_path.read_text(encoding="utf-8"))
    return form, model
