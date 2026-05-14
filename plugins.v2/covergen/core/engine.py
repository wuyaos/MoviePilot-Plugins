# input: PluginConfig + server/image_io/render/font 模块
# output: CoverEngine（封面生成调度）、RunStats（结构化统计）
# pos: core/ 核心引擎，调度库遍历→筛选→下载→渲染→上传
"""封面生成引擎。拆分原 5200 行 __init__.py 中的调度逻辑。"""
from __future__ import annotations

import datetime
import logging
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field

from app.plugins.covergen.core.config import PluginConfig
from app.plugins.covergen.core import server as srv
from app.plugins.covergen.core import image_io
from app.plugins.covergen.core import render
from app.plugins.covergen.utils.image_manager import ResolutionConfig

logger = logging.getLogger(__name__)
LOG_PREFIX = "【CoverGen】"


class LibraryResult(BaseModel):
    """单库处理结果。"""
    server: str
    name: str
    id: str
    status: str  # success / failed / skipped
    reason: str = ""


class RunStats(BaseModel):
    """一次任务运行的结构化统计（Pydantic，便于 API 序列化）。"""
    started_at: str = ""
    finished_at: str = ""
    mode: str = "all"
    dry_run: bool = False
    success: int = 0
    failed: int = 0
    skipped: int = 0
    libraries: List[LibraryResult] = Field(default_factory=list)
    errors: Dict[str, int] = Field(default_factory=dict)

    def record(self, server: str, name: str, lid: str, status: str, reason: str = ""):
        self.libraries.append(LibraryResult(server=server, name=name, id=lid,
                                             status=status, reason=reason))
        if status == "success":
            self.success += 1
        elif status == "failed":
            self.failed += 1
            key = reason or "unknown"
            self.errors[key] = self.errors.get(key, 0) + 1
        else:
            self.skipped += 1

    def finish(self) -> str:
        self.finished_at = datetime.datetime.now().isoformat()
        return f"成功 {self.success}，失败 {self.failed}，跳过 {self.skipped}"


class CoverEngine:
    """封面生成调度引擎。"""

    def __init__(self, cfg: PluginConfig, *, covers_path: Path, covers_input: str,
                 zh_font_path: Optional[Path], en_font_path: Optional[Path],
                 stop_event: threading.Event, get_data_fn=None, save_data_fn=None):
        self.cfg = cfg
        self.covers_path = covers_path
        self.covers_input = covers_input
        self.zh_font = zh_font_path
        self.en_font = en_font_path
        self.stop_event = stop_event
        self._lock = threading.Lock()
        self._updating = set()
        self._title_cache: Optional[dict] = None
        self._get_data = get_data_fn
        self._save_data = save_data_fn

    # ---- 主调度 ----

    def run(self, servers: dict, *, mode: str = "all", target_server: str = "",
            target_library_id: str = "", target_item_id: str = "") -> RunStats:
        stats = RunStats(started_at=datetime.datetime.now().isoformat(), mode=mode,
                         dry_run=self.cfg.dry_run)
        self.stop_event.clear()
        self._title_cache = render.parse_title_config(self.cfg.title_config) if self.cfg.title_config else {}

        for sname, service in servers.items():
            if target_server and sname != target_server:
                continue
            libraries = srv.get_libraries(service)
            if not libraries:
                logger.warning(f"{LOG_PREFIX} 服务器 {sname} 库列表为空")
                continue
            for lib in libraries:
                if self.stop_event.is_set():
                    stats.finish()
                    return stats
                lid = srv.get_library_id(service, lib)
                if target_library_id and str(lid) != str(target_library_id):
                    continue
                lname = lib.get("Name", "")
                lib_key = f"{sname}-{lid}"
                if lib_key in (self.cfg.exclude_libraries or []):
                    stats.record(sname, lname, str(lid), "skipped", "excluded")
                    continue
                if self.cfg.dry_run:
                    stats.record(sname, lname, str(lid), "success", "dry_run")
                    continue
                ok = False
                reason = ""
                for attempt in range(1, self.cfg.library_update_retry + 1):
                    ok, reason = self._process_library(service, sname, lib, target_item_id)
                    if ok:
                        break
                    if attempt < self.cfg.library_update_retry:
                        logger.warning(f"{LOG_PREFIX} {sname}:{lname} 重试 {attempt + 1}/{self.cfg.library_update_retry}")
                stats.record(sname, lname, str(lid), "success" if ok else "failed", reason)
        stats.finish()
        logger.info(f"{LOG_PREFIX} {stats.finish()}")
        return stats

    # ---- 单库处理 ----

    def _process_library(self, service, sname: str, lib: dict,
                         target_item_id: str = "") -> Tuple[bool, str]:
        lname = lib.get("Name", "")
        title = self._resolve_title(lname)
        image_path = self._check_custom_image(lname)

        if image_path:
            data = self._generate(sname, lname, title, image_path=image_path)
        elif target_item_id:
            item = srv.get_item_by_id(service, target_item_id)
            if not item:
                return False, "item_not_found"
            data = self._process_single(service, lib, title, item)
        else:
            data = self._generate_from_server(service, lib, title)
        if data:
            ok = image_io.upload_library_image(service, lib, data)
            return ok, "updated" if ok else "upload_failed"
        return False, "generate_failed"

    # ---- 筛选与下载 ----

    def _generate_from_server(self, service, lib: dict, title: Tuple[str, str]):
        lid = srv.get_library_id(service, lib)
        sort_by = self.cfg.sort_by or "Random"
        inc = "Movie,Series" if not self.cfg.is_single_image_style else "Movie,Series"
        items_raw = srv.get_items_batch(service, lid, limit=self.cfg.required_items * 3,
                                        include_types=inc, sort_by=sort_by)
        seen: Set[str] = set()
        valid = self._filter_items(items_raw, seen)
        if not valid:
            return False
        if self.cfg.is_single_image_style:
            return self._process_single(service, lib, title, valid[0])
        return self._process_grid(service, lib, title, valid[:self.cfg.required_items])

    def _filter_items(self, items: List[dict], seen: Set[str]) -> List[dict]:
        out = []
        for item in items:
            url = render.get_image_url(item, self.cfg.cover_style, self.cfg.use_primary)
            if not url:
                continue
            ck = render.build_content_key(item)
            ik = render.build_image_key(url)
            if (ck and ck in seen) or (ik and ik in seen):
                continue
            out.append(item)
            if ck:
                seen.add(ck)
            if ik:
                seen.add(ik)
        return out

    def _process_single(self, service, lib, title, item) -> Optional[str]:
        url = render.get_image_url(item, self.cfg.cover_style, self.cfg.use_primary)
        if not url:
            return None
        path = image_io.download_image(service, url, str(self.covers_path), lib["Name"], count=1,
                                       sanitize_fn=self._sanitize)
        return self._generate(service.name if hasattr(service, 'name') else "", lib["Name"],
                              title, image_path=path) if path else None

    def _process_grid(self, service, lib, title, items: List[dict]) -> Optional[str]:
        lname = lib["Name"]

        def _dl(args):
            i, item = args
            url = render.get_image_url(item, self.cfg.cover_style, self.cfg.use_primary)
            if not url:
                return None
            return image_io.download_image(service, url, str(self.covers_path), lname,
                                           count=i + 1, sanitize_fn=self._sanitize)

        with ThreadPoolExecutor(max_workers=4) as pool:
            paths = list(pool.map(_dl, enumerate(items)))
        paths = [p for p in paths if p]
        if not paths:
            return None
        return self._generate(service.name if hasattr(service, 'name') else "", lname, title)

    # ---- 渲染 ----

    def _generate(self, sname: str, lname: str, title: Tuple[str, str],
                  image_path: Optional[str] = None) -> Optional[str]:
        if not self.zh_font or not self.en_font:
            logger.error(f"{LOG_PREFIX} 字体缺失")
            return None
        res_cfg = ResolutionConfig(self.cfg.resolution)
        scale = self.cfg.title_scale if self.cfg.title_scale > 0 else 1.0
        is_anim = self.cfg.cover_style.startswith("animated")
        zh_sz = float(self.cfg.zh_font_size) * scale if is_anim else res_cfg.get_font_size(self.cfg.zh_font_size) * scale
        en_sz = float(self.cfg.en_font_size) * scale if is_anim else res_cfg.get_font_size(self.cfg.en_font_size) * scale
        offset = (float(self.cfg.zh_font_offset or 0),
                  float(self.cfg.title_spacing or 40) * scale,
                  float(self.cfg.en_line_spacing or 40) * scale)
        safe = self._sanitize(lname)
        lib_dir = (Path(self.covers_input) / safe if self.covers_input and image_path
                   else Path(self.covers_path) / safe)
        bg = {"mode": self.cfg.bg_color_mode, "custom_color": self.cfg.custom_bg_color,
              "config_color": self._resolve_title(lname)[2] if len(self._resolve_title(lname)) > 2 else None}

        return render.dispatch_style(
            self.cfg.cover_style, image_path=image_path, library_dir=lib_dir, title=title,
            font_path=(str(self.zh_font), str(self.en_font)),
            font_size=(zh_sz, en_sz), font_offset=offset,
            blur_size=self.cfg.blur_size, color_ratio=self.cfg.color_ratio,
            resolution_config=res_cfg, bg_color_config=bg, multi_blur=self.cfg.multi_1_blur,
            animation_duration=self.cfg.animation_duration, animation_scroll=self.cfg.animation_scroll,
            animation_fps=self.cfg.animation_fps, animation_format=self.cfg.animation_format,
            animation_reduce_colors=self.cfg.animation_reduce_colors,
            image_count=self.cfg.animated_2_image_count,
            departure_type=self.cfg.animated_2_departure_type, stop_event=self.stop_event)

    # ---- 辅助 ----

    def _resolve_title(self, lname: str) -> Tuple[str, str, Optional[str]]:
        zh, en, color = render.lookup_title(lname, self._title_cache)
        zh = zh.strip() or lname or "媒体库"
        return zh, en.strip(), color

    def _check_custom_image(self, lname: str) -> Optional[str]:
        if not self.covers_input:
            return None
        safe = self._sanitize(lname)
        d = os.path.join(self.covers_input, safe)
        if not os.path.isdir(d):
            return None
        for f in sorted(os.listdir(d)):
            if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
                return os.path.join(d, f)
        return None

    @staticmethod
    def _sanitize(name: str) -> str:
        return re.sub(r'[^\w\-.]', '_', name) if name else "unknown"
