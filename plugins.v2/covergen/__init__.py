# input: core/, api/, ui/ 子模块
# output: CoverGen 插件类（注册到 MoviePilot；聚合 run_history / last_run_stats）
# pos: 插件入口，组装各子模块并暴露 _PluginBase 接口
"""CoverGen — 媒体库封面自动生成插件（模块化重构版）。"""
from __future__ import annotations

import base64
import mimetypes
import os
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

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
    plugin_desc = "自动生成媒体库封面，支持库白名单、合集黑名单过滤、5种动画风格、Emby和Jellyfin"
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/emby.png"
    plugin_version = "1.3.0"
    plugin_author = "wuyaos"
    author_url = "https://github.com/wuyaos"
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
        # update_now 与 dry_run 都是一次性开关：开启即运行一次，运行后自动关闭
        if self._cfg.update_now or self._cfg.dry_run:
            mode_label = "模拟" if self._cfg.dry_run else "正式"
            logger.info(f"【CoverGen】一次性运行触发（{mode_label}模式），运行后自动关闭开关")
            # 先以当前 cfg（含 dry_run）触发运行，再清开关并保存
            run_cfg = self._cfg
            self._cfg = PluginConfig.from_dict({**self._cfg.to_dict(),
                                                 "update_now": False, "dry_run": False})
            self._engine.cfg = run_cfg  # 让本次运行仍然按原 cfg（dry_run/update_now）执行
            self._update_config()
            self._scheduler.run_once(self._reset_engine_then_run)

    def _reset_engine_then_run(self):
        try:
            self._engine.run(self._servers, trigger="manual")
        finally:
            # 运行后恢复 engine.cfg 到当前已清开关的 cfg
            self._engine.cfg = self._cfg

    def _run_all(self, *, trigger: str = ""):
        if self._engine:
            self._engine.run(self._servers, trigger=trigger)

    def _update_config(self):
        self._cfg.cover_style = self._cfg.compose_style()
        self.update_config(self._cfg.to_dict())

    # ---- _PluginBase 接口 ----

    def get_state(self) -> bool:
        return self._cfg.enabled

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        zh_items, en_items, _, _ = self._font_mgr.get_presets() if self._font_mgr else ([], [], {}, {})
        # 选项始终列出所有可用媒体服务器（即使未选）
        try:
            all_services = self._mediaserver_helper.get_services() or {}
        except Exception:
            all_services = {}
        server_items = [{"title": n, "value": n} for n in all_services.keys()]
        lib_opts = [{"title": lib["name"], "value": lib["value"]} for lib in self._all_libraries]
        return build_form(server_items=server_items, library_options=lib_opts,
                          user_options=self._all_users, zh_font_items=zh_items, en_font_items=en_items)

    def get_page(self) -> List[dict]:
        covers = self._get_recent_covers()
        last_run = None
        run_history = []
        history = self.get_data("run_history")
        if isinstance(history, list):
            run_history = history
        if self._engine and hasattr(self._engine, '_last_stats') and self._engine._last_stats:
            last_run = self._engine._last_stats
        elif self._engine:
            # 从持久化恢复
            saved = self.get_data("last_run_stats")
            if saved and isinstance(saved, dict):
                try:
                    from app.plugins.covergen.core.engine import RunStats
                    last_run = RunStats(**saved)
                except Exception:
                    pass
        return build_page(enabled=self._cfg.enabled, has_servers=bool(self._servers),
                          cover_style=self._cfg.cover_style, covers=covers,
                          plugin_id=self.SERVICE_ID, last_run=last_run, run_history=run_history)

    def get_api(self) -> List[Dict[str, Any]]:
        return build_api_routes(self)

    def get_service(self) -> List[Dict[str, Any]]:
        if not self._scheduler:
            return []
        return self._scheduler.build_services(
            enabled=self._cfg.enabled, cron=self._cfg.cron,
            run_fn=self._run_all, stop_fn=self.stop_task,
            service_id=self.SERVICE_ID, stop_id=self.STOP_SERVICE_ID,
            run_kwargs={"trigger": "cron"})

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """注册远程命令（如 Bot 或 Webhook 触发）。"""
        return [
            {"cmd": "/update_covers", "event": EventType.PluginAction,
             "desc": "立即更新所有媒体库封面", "category": "媒体",
             "data": {"action": "update_covers"}},
            {"cmd": "/cover_clean_images", "event": EventType.PluginAction,
             "desc": "清理封面图片缓存", "category": "媒体",
             "data": {"action": "clean_images"}},
            {"cmd": "/cover_clean_fonts", "event": EventType.PluginAction,
             "desc": "清理字体缓存", "category": "媒体",
             "data": {"action": "clean_fonts"}},
        ]

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
        if not file:
            return {"code": 1, "msg": "参数缺失"}
        covers_dir = self._cfg.covers_output
        if not covers_dir:
            covers_dir = str(self.get_data_path() / "covers")
        # 只接受文件名（无路径分隔符），防止路径穿越
        safe_name = os.path.basename(file)
        if not safe_name or safe_name != file:
            return {"code": 1, "msg": "非法路径"}
        target = Path(covers_dir) / safe_name
        if not target.is_file():
            return {"code": 1, "msg": "图片不存在"}
        mime_type, _ = mimetypes.guess_type(str(target))
        if not mime_type:
            mime_type = "image/jpeg"
        try:
            from fastapi.responses import FileResponse
            return FileResponse(path=str(target), media_type=mime_type)
        except Exception:
            try:
                from starlette.responses import FileResponse
                return FileResponse(path=str(target), media_type=mime_type)
            except Exception as e:
                logger.error(f"【CoverGen】返回图片失败: {e}")
                return {"code": 1, "msg": "返回图片失败"}

    # ---- 事件 ----

    @eventmanager.register(EventType.PluginAction)
    def on_plugin_action(self, event: Event):
        if not event or not event.event_data:
            return
        action = event.event_data.get("action")
        if action == "update_covers":
            self._run_all(trigger="command")
        elif action == "clean_images":
            self.api_clean_images()
        elif action == "clean_fonts":
            self.api_clean_fonts()

    @eventmanager.register(EventType.TransferComplete)
    def on_transfer_complete(self, event: Event):
        if not self._cfg.enabled or not self._cfg.transfer_monitor or not self._scheduler:
            return
        if self._cfg.transfer_source != "transfer":
            return
        if not event or not event.event_data:
            return
        media = event.event_data.get("mediainfo")
        if not media:
            return
        title = getattr(media, "title", "") or "unknown"
        tmdb_id = getattr(media, "tmdb_id", "") or ""
        key = f"cover:{tmdb_id}:{title}"
        self._scheduler.debounce_transfer(key, self._run_all, trigger="transfer")

    @eventmanager.register(EventType.WebhookMessage)
    def on_webhook_message(self, event: Event):
        """监听媒体服务器 Webhook 入库事件，精确更新对应库。"""
        if not self._cfg.enabled or not self._cfg.transfer_monitor or not self._scheduler:
            return
        if self._cfg.transfer_source != "webhook":
            return
        if not event or not event.event_data:
            return
        event_info = event.event_data
        event_type = getattr(event_info, "event_type", "") or ""
        if event_type != "library.new":
            return
        item_name = getattr(event_info, "item_name", "") or "unknown"
        item_id = getattr(event_info, "item_id", "") or ""
        item_type = getattr(event_info, "item_type", "") or ""
        # 用相同 key 格式取消 TransferComplete 的兜底定时器
        tmdb_id = ""  # webhook 事件无 tmdb_id，用 item_name 匹配
        key = f"cover:{tmdb_id}:{item_name}"
        # 查找对应库并定向更新
        target_server, target_library_id = self._resolve_webhook_library(item_id)
        if target_server and target_library_id:
            self._scheduler.debounce_transfer(
                key, self._run_targeted,
                target_server=target_server, target_library_id=target_library_id,
                trigger="webhook")
        else:
            # 无法定位库，回退全量
            self._scheduler.debounce_transfer(key, self._run_all, trigger="webhook")

    def _run_targeted(self, *, target_server: str = "", target_library_id: str = "",
                      trigger: str = ""):
        """定向更新指定服务器的指定库。"""
        if self._engine:
            self._engine.run(self._servers, trigger=trigger,
                             target_server=target_server,
                             target_library_id=target_library_id)

    def _resolve_webhook_library(self, item_id: str) -> Tuple[str, str]:
        """通过 item_id 查询媒体服务器，定位所属库。返回 (server_name, library_id)。"""
        if not item_id or not self._servers:
            return "", ""
        for sname, service in self._servers.items():
            try:
                lib_id = srv.get_parent_library_id(service, item_id)
                if lib_id:
                    return sname, lib_id
            except Exception:
                continue
        return "", ""

    # ---- 辅助 ----

    @staticmethod
    def _sanitize_history_name(name: str) -> str:
        return re.sub(r'[^\w\-.]', '_', name) if name else "unknown"

    def _history_hidden_lib_ids(self) -> Set[str]:
        """解析历史封面中需要默认后置的黑名单用户可见库 ID。"""
        hidden: Set[str] = set()
        if not self._cfg.hide_user_blacklist_libraries or not self._cfg.exclude_users:
            return hidden
        for entry in self._cfg.exclude_users:
            if "-" not in entry:
                continue
            server, user_id = entry.split("-", 1)
            svc = self._servers.get(server)
            if not svc or not user_id:
                continue
            hidden.update(f"{server}-{lib_id}" for lib_id in srv.get_user_views(svc, {user_id}))
        return hidden

    def _history_library_value(self, filename: str) -> str:
        """从历史封面文件名匹配 server-library。"""
        for lib in self._all_libraries:
            value = str(lib.get("value") or "")
            name = str(lib.get("name") or "")
            if not value or ": " not in name:
                continue
            server_name, lib_name = name.split(": ", 1)
            prefix = f"{self._sanitize_history_name(server_name)}_{self._sanitize_history_name(lib_name)}_"
            if filename.startswith(prefix):
                return value
        return ""

    def _get_recent_covers(self) -> List[Dict[str, Any]]:
        """扫描历史封面输出目录，返回最近 N 张（base64 data URI）。"""
        covers_dir = self._cfg.covers_output
        if not covers_dir:
            data_path = self.get_data_path()
            covers_dir = str(data_path / "covers")
        os.makedirs(covers_dir, exist_ok=True)
        _mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                 ".gif": "image/gif", ".webp": "image/webp", ".apng": "image/apng"}
        results = []
        hidden_lib_ids = self._history_hidden_lib_ids()
        try:
            files = []
            for p in Path(covers_dir).iterdir():
                if not p.is_file():
                    continue
                ext = p.suffix.lower()
                if ext not in _mime:
                    continue
                lib_value = self._history_library_value(p.name)
                files.append((p, lib_value, p.stat().st_mtime))
            files.sort(key=lambda x: (1 if x[1] in hidden_lib_ids else 0, -x[2]))
            for f, lib_value, _ in files:
                ext = f.suffix.lower()
                try:
                    data = base64.b64encode(f.read_bytes()).decode("utf-8")
                    results.append({
                        "file": f.name,
                        "label": f.stem,
                        "library_value": lib_value,
                        "src": f"data:{_mime[ext]};base64,{data}",
                    })
                except Exception as e:
                    logger.debug(f"【CoverGen】读取封面文件失败: {f} -> {e}")
                if len(results) >= self._cfg.covers_page_history_limit:
                    break
        except Exception as e:
            logger.warning(f"【CoverGen】扫描历史封面失败: {e}")
        return results
