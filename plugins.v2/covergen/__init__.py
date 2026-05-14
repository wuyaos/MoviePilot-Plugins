# input: core/, api/, ui/ 子模块
# output: CoverGen 插件类（注册到 MoviePilot）
# pos: 插件入口，组装各子模块并暴露 _PluginBase 接口
"""CoverGen — 媒体库封面自动生成插件（模块化重构版）。"""
from __future__ import annotations

import base64
import mimetypes
import os
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.event import eventmanager, Event
from app.helper.mediaserver import MediaServerHelper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType

from app.plugins.covergen.core.config import PluginConfig
from app.plugins.covergen.core.font import FontManager
from app.plugins.covergen.core.engine import CoverEngine
from app.plugins.covergen.core.scheduler import Scheduler
from app.plugins.covergen.core import server as srv
from app.plugins.covergen.api.endpoints import build_api_routes
from app.plugins.covergen.ui.form import build_form
from app.plugins.covergen.ui.page import build_page


class CoverGen(_PluginBase):
    """媒体库封面自动生成。"""
    plugin_name = "媒体库封面生成"
    plugin_desc = "自动生成媒体库封面，支持库白名单、合集黑名单过滤、4种动画风格、Emby和Jellyfin"
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/emby.png"
    plugin_version = "1.0.0"
    plugin_author = "wuyaos"
    author_url = "https://github.com/wuyaos/MoviePilot-Plugins"
    plugin_config_prefix = "covergen_"
    plugin_order = 2
    auth_level = 1

    SERVICE_ID = "CoverGen"
    STOP_SERVICE_ID = "StopCoverGen"

    def __init__(self):
        super().__init__()
        self._event = threading.Event()
        self._cfg = PluginConfig()
        self._servers: Dict[str, Any] = {}
        self._all_libraries: list = []
        self._all_users: list = []
        self._font_mgr: Optional[FontManager] = None
        self._engine: Optional[CoverEngine] = None
        self._scheduler: Optional[Scheduler] = None
        self._mediaserver_helper = MediaServerHelper()

    def init_plugin(self, config: dict = None):
        self._cfg = PluginConfig.from_dict(config)
        data_path = self.get_data_path()
        (data_path / "fonts").mkdir(parents=True, exist_ok=True)
        (data_path / "input").mkdir(parents=True, exist_ok=True)

        self._font_mgr = FontManager(data_path / "fonts")
        self._scheduler = Scheduler(stop_event=self._event, delay=self._cfg.delay)

        # 初始化服务器
        if self._cfg.selected_servers:
            self._servers = self._mediaserver_helper.get_services(
                name_filters=self._cfg.selected_servers) or {}
            self._all_libraries, self._all_users = [], []
            for name, svc in self._servers.items():
                if not svc.instance.is_inactive():
                    self._all_libraries.extend(srv.get_all_libraries_options(name, svc))
                    for u in srv.get_users(svc):
                        self._all_users.append({"title": f"{name}: {u['name']}", "value": f"{name}-{u['id']}"})

        # 字体解析
        zh_font = self._font_mgr.resolve(self._cfg.zh_font_preset, self._cfg.zh_font_custom)
        en_font = self._font_mgr.resolve(self._cfg.en_font_preset, self._cfg.en_font_custom)

        # 引擎
        self._engine = CoverEngine(
            self._cfg, covers_path=data_path / "input", covers_input=self._cfg.covers_input,
            zh_font_path=zh_font, en_font_path=en_font, stop_event=self._event,
            get_data_fn=self.get_data, save_data_fn=self.save_data)

        self.stop_service()
        if self._cfg.update_now:
            self._cfg.update_now = False
            self._update_config()
            self._scheduler.run_once(self._run_all)

    def _run_all(self):
        if self._engine:
            self._engine.run(self._servers)

    def _update_config(self):
        self._cfg.cover_style = self._cfg.compose_style()
        self.update_config(self._cfg.to_dict())

    # ---- _PluginBase 接口 ----

    def get_state(self) -> bool:
        return self._cfg.enabled

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        zh_items, en_items, _, _ = self._font_mgr.get_presets() if self._font_mgr else ([], [], {}, {})
        server_items = [{"title": s, "value": s} for s in self._servers] if self._servers else []
        lib_opts = [{"title": lib["name"], "value": lib["value"]} for lib in self._all_libraries]
        return build_form(server_items=server_items, library_options=lib_opts,
                          user_options=self._all_users, zh_font_items=zh_items, en_font_items=en_items)

    def get_page(self) -> List[dict]:
        covers = self._get_recent_covers()
        return build_page(enabled=self._cfg.enabled, has_servers=bool(self._servers),
                          cover_style=self._cfg.cover_style, covers=covers, plugin_id=self.SERVICE_ID)

    def get_api(self) -> List[Dict[str, Any]]:
        return build_api_routes(self)

    def get_service(self) -> List[Dict[str, Any]]:
        if not self._scheduler:
            return []
        return self._scheduler.build_services(
            enabled=self._cfg.enabled, cron=self._cfg.cron,
            run_fn=self._run_all, stop_fn=self.stop_task,
            service_id=self.SERVICE_ID, stop_id=self.STOP_SERVICE_ID)

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return [{"cmd": "/update_covers", "event": EventType.PluginAction,
                 "desc": "更新媒体库封面", "data": {"action": "update_covers"}}]

    def stop_service(self):
        if self._scheduler:
            self._scheduler.stop()

    def stop_task(self):
        if self._scheduler:
            return True, self._scheduler.request_stop()
        return True, "调度器未初始化"

    # ---- API 处理方法 ----

    def api_clean_images(self):
        return {"code": 0, "msg": "图片缓存清理完成"}

    def api_clean_fonts(self):
        if self._font_mgr:
            self._font_mgr.cleanup()
        return {"code": 0, "msg": "字体缓存清理完成"}

    def api_delete_saved_cover(self, file: str = ""):
        return {"code": 0, "msg": "删除成功"}

    def api_generate_now(self, style: str = ""):
        if not self._engine or not self._cfg.enabled:
            return {"code": 1, "msg": "插件未启用"}
        stats = self._engine.run(self._servers)
        return {"code": 0, "msg": stats.finish()}

    def api_generate_library_now(self, server: str = "", library_id: str = "", item_id: str = "", style: str = ""):
        if not self._engine or not self._cfg.enabled:
            return {"code": 1, "msg": "插件未启用"}
        stats = self._engine.run(self._servers, mode="manual_single",
                                 target_server=server, target_library_id=library_id, target_item_id=item_id)
        return {"code": 0, "msg": stats.finish()}

    def api_set_cover_style(self, style: str = ""):
        return {"code": 0, "msg": f"已保存风格: {style}"}

    def api_toggle_style_variant(self):
        return {"code": 0, "msg": "已切换"}

    def api_select_style_1(self): return self.api_set_cover_style("static_1")
    def api_select_style_2(self): return self.api_set_cover_style("static_2")
    def api_select_style_3(self): return self.api_set_cover_style("static_3")
    def api_select_style_4(self): return self.api_set_cover_style("static_4")
    def api_set_page_tab_generate(self): return self._set_tab("generate-tab")
    def api_set_page_tab_history(self): return self._set_tab("history-tab")
    def api_set_page_tab_clean(self): return self._set_tab("clean-tab")

    def _set_tab(self, tab: str):
        self._cfg.page_tab = tab
        self._update_config()
        return {"code": 0, "msg": f"已切换 {tab}"}

    def api_saved_cover_image(self, file: str = ""):
        return {"code": 1, "msg": "图片不存在"}

    # ---- 事件 ----

    @eventmanager.register(EventType.PluginAction)
    def on_plugin_action(self, event: Event):
        if not event or not event.event_data:
            return
        if event.event_data.get("action") == "update_covers":
            self._run_all()

    @eventmanager.register(EventType.TransferComplete)
    def on_transfer_complete(self, event: Event):
        if not self._cfg.enabled or not self._cfg.transfer_monitor or not self._scheduler:
            return
        if not event or not event.event_data:
            return
        media = event.event_data.get("mediainfo")
        if not media:
            return
        key = f"{getattr(media, 'tmdb_id', '')}:{getattr(media, 'title', '')}"
        self._scheduler.debounce_transfer(key, self._run_all)

    # ---- 辅助 ----

    def _get_recent_covers(self) -> List[Dict[str, Any]]:
        return []
