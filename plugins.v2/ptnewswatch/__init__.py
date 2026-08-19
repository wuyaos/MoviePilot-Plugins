"""PTNewsWatch：PT 论坛、RSS 与 Atom 动态汇总。"""
from __future__ import annotations

from typing import Any

from app.plugins import _PluginBase

from .core.config import PluginConfig


class PTNewsWatch(_PluginBase):
    plugin_name = "PT 资讯动态监控"
    plugin_desc = "汇总 PT 论坛主题、RSS 与 Atom 新消息"
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/signin.png"
    plugin_version = "0.1.0"
    plugin_author = "wuyaos"
    author_url = "https://github.com/wuyaos"
    plugin_config_prefix = "ptnewswatch_"
    plugin_order = 37
    auth_level = 2

    def __init__(self):
        super().__init__()
        self.config = PluginConfig()

    def init_plugin(self, config: dict | None = None):
        self.config = PluginConfig.from_dict(config)

    def get_state(self) -> bool:
        return self.config.enabled

    @staticmethod
    def get_command() -> list[dict]:
        return []

    def get_api(self) -> list[dict]:
        return []

    def get_service(self) -> list[dict]:
        return []

    def get_form(self) -> tuple[list[dict], dict[str, Any]]:
        return ([{
            "component": "VAlert",
            "props": {
                "type": "info",
                "variant": "tonal",
                "text": "PTNewsWatch 模块化骨架已加载；来源抓取与页面将在后续阶段接入。",
            },
        }], self.config.to_dict())

    def get_page(self) -> list[dict]:
        return [{
            "component": "VAlert",
            "props": {
                "type": "info",
                "variant": "tonal",
                "text": "暂无运行数据。",
            },
        }]

    def stop_service(self):
        return None
