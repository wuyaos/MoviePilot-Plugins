# input: core/, api/, ui/ 子模块
# output: CoverGen 插件类（注册到 MoviePilot；聚合 run_history / last_run_stats）
# pos: 插件入口，组装各子模块并暴露 _PluginBase 接口
"""CoverGen — 媒体库封面自动生成插件（模块化重构版）。"""
from __future__ import annotations

import datetime as dt
import base64
import hashlib
import mimetypes
import os
import re
import shutil
import threading
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.event import eventmanager, Event
from app.helper.mediaserver import MediaServerHelper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType

from .core.config import PluginConfig
from .core.font import FontManager
from .core.engine import CoverEngine
from .core.scheduler import Scheduler
from .core import server as srv
from .api.endpoints import build_api_routes
from .ui.form import build_form
from .ui.page import build_page


class CoverGen(_PluginBase):
    """媒体库封面自动生成。"""
    plugin_name = "媒体库封面生成"
    plugin_desc = "自动生成媒体库封面，支持库白名单、合集黑名单过滤、5种动画风格、Emby和Jellyfin"
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/emby.png"
    plugin_version = "1.4.5"
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
        if self._cfg.clean_images or self._cfg.clean_fonts:
            if self._cfg.clean_images:
                self.api_clean_images()
            if self._cfg.clean_fonts:
                self.api_clean_fonts()
            self._cfg.clean_images = False
            self._cfg.clean_fonts = False
            self._update_config()

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
                    from .core.engine import RunStats
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
            {"cmd": "/cover_update", "event": EventType.PluginAction,
             "desc": "立即更新所有媒体库封面", "category": "媒体",
             "data": {"action": "cover_update"}},
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
        removed = 0
        for directory in self._image_cache_dirs():
            removed += self._clean_directory(directory)
        return {"code": 0, "msg": f"图片缓存清理完成，删除 {removed} 项"}

    def api_clean_fonts(self):
        if self._font_mgr:
            self._font_mgr.cleanup()
        return {"code": 0, "msg": "字体缓存清理完成"}

    def api_delete_saved_cover(self, file: str = ""):
        target = self._safe_saved_cover_path(file)
        if not target:
            return {"code": 1, "msg": "图片不存在或路径非法"}
        try:
            target.unlink(missing_ok=True)
            return {"code": 0, "msg": "删除成功"}
        except Exception as e:
            logger.warning(f"【CoverGen】删除历史封面失败: {target} -> {e}")
            return {"code": 1, "msg": "删除失败"}

    def api_generate_now(self, style: str = ""):
        if not self._engine or not self._cfg.enabled:
            return {"code": 1, "msg": "插件未启用"}
        stats = self._engine.run(self._servers)
        return {"code": 0, "msg": stats.message or stats.finish()}

    def api_generate_library_now(self, server: str = "", library_id: str = "", item_id: str = "", style: str = ""):
        if not self._engine or not self._cfg.enabled:
            return {"code": 1, "msg": "插件未启用"}
        stats = self._engine.run(self._servers, mode="manual_single",
                                 target_server=server, target_library_id=library_id, target_item_id=item_id)
        return {"code": 0, "msg": stats.message or stats.finish()}

    def api_set_cover_style(self, style: str = ""):
        from .core.config import VALID_STYLES
        style = (style or "").strip()
        if style not in VALID_STYLES:
            return {"code": 1, "msg": "不支持的风格"}
        if style.startswith("animated_"):
            self._cfg.cover_style_base = f"static_{style.rsplit('_', 1)[-1]}"
            self._cfg.cover_style_variant = "animated"
        else:
            self._cfg.cover_style_base = style
            self._cfg.cover_style_variant = "static"
        self._cfg.cover_style = self._cfg.compose_style()
        if self._engine:
            self._engine.cfg = self._cfg
        self._update_config()
        return {"code": 0, "msg": f"已保存风格: {self._cfg.cover_style}"}

    def api_toggle_style_variant(self):
        self._cfg.cover_style_variant = "animated" if self._cfg.cover_style_variant == "static" else "static"
        self._cfg.cover_style = self._cfg.compose_style()
        if self._engine:
            self._engine.cfg = self._cfg
        self._update_config()
        return {"code": 0, "msg": f"已切换为 {self._cfg.cover_style}"}

    def api_select_style_1(self): return self.api_set_cover_style("static_1")
    def api_select_style_2(self): return self.api_set_cover_style("static_2")
    def api_select_style_3(self): return self.api_set_cover_style("static_3")
    def api_select_style_4(self): return self.api_set_cover_style("static_4")
    def api_select_style_5(self): return self.api_set_cover_style("static_5")
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
        target = self._safe_saved_cover_path(file)
        if not target:
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
        if action == "cover_update":
            self._run_all(trigger="command")
        elif action == "clean_images":
            self.api_clean_images()
        elif action == "clean_fonts":
            self.api_clean_fonts()

    @eventmanager.register(EventType.TransferComplete)
    def on_transfer_complete(self, event: Event):
        if not self._cfg.enabled or not self._cfg.transfer_monitor or not self._scheduler:
            return
        if not event or not event.event_data:
            return
        media = event.event_data.get("mediainfo")
        if not media:
            return
        title = getattr(media, "title", "") or "unknown"
        logger.info(f"【CoverGen】TransferComplete 触发：{title}，合并到全局防抖队列")
        self._scheduler.debounce_transfer("cover:transfer:batch", self._run_all, trigger="transfer")

    # ---- 辅助 ----

    @staticmethod
    def _is_image_filename(name: str) -> bool:
        return Path(name).suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".apng"}

    def _covers_dir(self) -> Path:
        return Path(self._cfg.covers_output) if self._cfg.covers_output else self.get_data_path() / "covers"

    def _safe_saved_cover_path(self, file: str = "") -> Optional[Path]:
        if not file:
            return None
        safe_name = os.path.basename(file)
        if safe_name != file or not self._is_image_filename(safe_name):
            return None
        target = self._covers_dir() / safe_name
        try:
            base = self._covers_dir().resolve()
            resolved = target.resolve()
            if base not in resolved.parents and resolved != base:
                return None
        except Exception:
            return None
        return target if target.is_file() else None

    def _image_cache_dirs(self) -> List[Path]:
        return [self.get_data_path() / "input", self._history_thumbs_dir()]

    def _clean_directory(self, directory: Path) -> int:
        removed = 0
        try:
            directory.mkdir(parents=True, exist_ok=True)
            for entry in directory.iterdir():
                try:
                    if entry.is_dir():
                        shutil.rmtree(entry)
                    else:
                        entry.unlink(missing_ok=True)
                    removed += 1
                except Exception as e:
                    logger.warning(f"【CoverGen】清理缓存失败: {entry} -> {e}")
        except Exception as e:
            logger.warning(f"【CoverGen】扫描缓存目录失败: {directory} -> {e}")
        return removed

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

    def _history_thumbs_dir(self) -> Path:
        return self.get_data_path() / "history_thumbs"

    @staticmethod
    def _history_thumb_key(path: Path, *, size: int, mtime_ns: int) -> str:
        raw = f"{path.name}|{size}|{mtime_ns}".encode("utf-8", "ignore")
        return hashlib.md5(raw).hexdigest()

    def _history_thumb_src(self, path: Path, *, size: int, mtime_ns: int) -> str:
        """返回历史封面缩略图 data URI，避免详情页请求受保护的插件图片接口。"""
        thumbs_dir = self._history_thumbs_dir()
        thumb = thumbs_dir / f"{self._history_thumb_key(path, size=size, mtime_ns=mtime_ns)}.jpg"
        try:
            if not thumb.is_file():
                thumbs_dir.mkdir(parents=True, exist_ok=True)
                from PIL import Image, ImageOps

                with Image.open(path) as img:
                    try:
                        img.seek(0)
                    except Exception:
                        pass
                    img = ImageOps.exif_transpose(img)
                    if img.mode in ("RGBA", "LA", "P"):
                        img = img.convert("RGBA")
                        background = Image.new("RGBA", img.size, (24, 24, 24, 255))
                        background.alpha_composite(img)
                        img = background.convert("RGB")
                    elif img.mode != "RGB":
                        img = img.convert("RGB")
                    img.thumbnail((480, 270), Image.LANCZOS)
                    buffer = BytesIO()
                    img.save(buffer, format="JPEG", quality=82, optimize=True)
                    thumb.write_bytes(buffer.getvalue())
            data = thumb.read_bytes()
            if not data:
                return ""
            return f"data:image/jpeg;base64,{base64.b64encode(data).decode('ascii')}"
        except Exception as e:
            logger.warning(f"【CoverGen】生成历史封面缩略图失败: {path.name} -> {e}")
            return ""

    def _get_recent_covers(self) -> List[Dict[str, Any]]:
        """扫描历史封面输出目录，返回最近 N 张元数据和本地缩略图。"""
        covers_dir = self._cfg.covers_output
        if not covers_dir:
            data_path = self.get_data_path()
            covers_dir = str(data_path / "covers")
        os.makedirs(covers_dir, exist_ok=True)
        image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".apng"}
        results = []
        hidden_lib_ids = self._history_hidden_lib_ids()

        def _size_label(size: int) -> str:
            if size >= 1024 * 1024:
                return f"{size / 1024 / 1024:.1f} MB"
            return f"{max(1, size // 1024)} KB"

        try:
            files = []
            for p in Path(covers_dir).iterdir():
                if not p.is_file():
                    continue
                ext = p.suffix.lower()
                if ext not in image_exts:
                    continue
                lib_value = self._history_library_value(p.name)
                stat = p.stat()
                files.append((p, lib_value, stat.st_mtime, stat.st_mtime_ns, stat.st_size))
            files.sort(key=lambda x: (1 if x[1] in hidden_lib_ids else 0, -x[2]))
            for f, lib_value, mtime, mtime_ns, size in files:
                ext = f.suffix.lower()
                results.append({
                    "file": f.name,
                    "label": f.stem,
                    "library_value": lib_value,
                    "src": self._history_thumb_src(f, size=size, mtime_ns=mtime_ns),
                    "ext": ext.lstrip(".").upper(),
                    "size": _size_label(size),
                    "mtime": dt.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"),
                })
                if len(results) >= self._cfg.covers_page_history_limit:
                    break
        except Exception as e:
            logger.warning(f"【CoverGen】扫描历史封面失败: {e}")
        return results
