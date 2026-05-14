# input: PluginConfig + server/image_io/render/font 模块
# output: CoverEngine（封面生成调度）、RunStats（结构化统计）
# pos: core/ 核心引擎，调度库遍历→筛选→下载→渲染→上传
"""封面生成引擎。拆分原 5200 行 __init__.py 中的调度逻辑。"""
from __future__ import annotations

import datetime
from app.log import logger
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
        self._last_stats: Optional[RunStats] = None

    # ---- 主调度 ----

    def run(self, servers: dict, *, mode: str = "all", target_server: str = "",
            target_library_id: str = "", target_item_id: str = "") -> RunStats:
        stats = RunStats(started_at=datetime.datetime.now().isoformat(), mode=mode,
                         dry_run=self.cfg.dry_run)
        self.stop_event.clear()
        self._title_cache = render.parse_title_config(self.cfg.title_config) if self.cfg.title_config else {}
        logger.info(f"{LOG_PREFIX} ═══ 开始封面更新任务 ═══ 模式={mode} 风格={self.cfg.cover_style} "
                    f"dry_run={self.cfg.dry_run} 服务器数={len(servers)}")

        for sname, service in servers.items():
            if target_server and sname != target_server:
                continue
            libraries = srv.get_libraries(service)
            if not libraries:
                logger.warning(f"{LOG_PREFIX} 服务器 {sname} 库列表为空，跳过")
                continue
            logger.info(f"{LOG_PREFIX} ── 服务器 {sname} ── 共 {len(libraries)} 个库")
            for lib in libraries:
                if self.stop_event.is_set():
                    logger.info(f"{LOG_PREFIX} 收到停止信号，中断任务")
                    stats.finish()
                    return stats
                lid = srv.get_library_id(service, lib)
                if target_library_id and str(lid) != str(target_library_id):
                    continue
                lname = lib.get("Name", "")
                lib_key = f"{sname}-{lid}"
                if lib_key in (self.cfg.exclude_libraries or []):
                    logger.info(f"{LOG_PREFIX} ⊘ {sname}：{lname} 在排除列表中，跳过")
                    stats.record(sname, lname, str(lid), "skipped", "excluded")
                    continue
                if self.cfg.dry_run:
                    logger.info(f"{LOG_PREFIX} [DRY_RUN] {sname}：{lname} ({lid}) 模拟生成（不实际上传）")
                    stats.record(sname, lname, str(lid), "success", "dry_run")
                    continue
                ok = False
                reason = ""
                for attempt in range(1, self.cfg.library_update_retry + 1):
                    logger.info(f"{LOG_PREFIX} → {sname}：{lname} 开始处理 (尝试 {attempt}/{self.cfg.library_update_retry})")
                    ok, reason = self._process_library(service, sname, lib, target_item_id)
                    if ok:
                        logger.info(f"{LOG_PREFIX} ✓ {sname}：{lname} 封面更新成功")
                        break
                    if attempt < self.cfg.library_update_retry:
                        logger.warning(f"{LOG_PREFIX} ↻ {sname}：{lname} 失败，准备重试 ({attempt + 1}/{self.cfg.library_update_retry})")
                if not ok:
                    logger.warning(f"{LOG_PREFIX} ✗ {sname}：{lname} 封面更新失败（原因：{reason}）")
                stats.record(sname, lname, str(lid), "success" if ok else "failed", reason)
        summary = stats.finish()
        self._last_stats = stats
        if self._save_data:
            try:
                self._save_data("last_run_stats", stats.model_dump())
            except Exception:
                pass
        logger.info(f"{LOG_PREFIX} ═══ 任务结束 ═══ {summary}")
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
            def _save_cb(b64, ext):
                import base64 as b64mod
                covers_dir = str(self.cfg.covers_output) if self.cfg.covers_output else str(self.covers_path.parent / "covers")
                os.makedirs(covers_dir, exist_ok=True)
                safe_s = self._sanitize(sname)
                safe_l = self._sanitize(lib.get("Name", ""))
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                fp = os.path.join(covers_dir, f"{safe_s}_{safe_l}_{ts}.{ext}")
                Path(fp).write_bytes(b64mod.b64decode(b64))
                logger.info(f"{LOG_PREFIX} 封面已保存: {fp}")
            ok = image_io.upload_library_image(service, lib, data, on_save_local=_save_cb)
            return ok, "updated" if ok else "upload_failed"
        return False, "generate_failed"

    # ---- 筛选与下载 ----

    def _generate_from_server(self, service, lib: dict, title: Tuple[str, str]):
        lid = srv.get_library_id(service, lib)
        sname = service.name if hasattr(service, 'name') else ""
        sort_by = self.cfg.sort_by or "Random"
        # 根据库类型决定 IncludeItemTypes
        coll_type = (lib.get("CollectionType") or "").lower()
        lib_type = (lib.get("Type") or "").lower()
        if coll_type == "playlists" or lib_type == "playlist":
            return self._handle_playlist_library(service, lib, title)
        if coll_type == "boxsets" or lib_type == "boxset":
            return self._handle_boxset_library(service, lib, title)
        if coll_type == "music":
            inc = "MusicAlbum,Audio"
        else:
            inc = "Movie,Series"
        items_raw = srv.get_items_batch(service, lid, limit=self.cfg.required_items * 3,
                                        include_types=inc, sort_by=sort_by)
        if not items_raw:
            logger.warning(f"{LOG_PREFIX} {sname}：{lib.get('Name')} 拉取项目为空 (type={coll_type or lib_type})")

        seen: Set[str] = set()
        valid = self._filter_items(items_raw, seen)
        if not valid:
            logger.warning(f"{LOG_PREFIX} {sname}：{lib.get('Name')} 筛选后无有效项目")
            return False
        if self.cfg.is_single_image_style:
            return self._process_single(service, lib, title, valid[0])
        return self._process_grid(service, lib, title, valid[:self.cfg.required_items])

    def _get_excluded_boxset_ids(self, service, sname: str) -> Set[str]:
        """解析 exclude_boxsets + exclude_users 配置，查询需排除的合集 ID。"""
        excluded: Set[str] = set()
        # 来源库黑名单
        if self.cfg.exclude_boxsets:
            source_lib_ids: Set[str] = set()
            for entry in self.cfg.exclude_boxsets:
                if "-" in entry:
                    parts = entry.split("-", 1)
                    if parts[0] == sname:
                        source_lib_ids.add(parts[1])
                else:
                    source_lib_ids.add(entry)
            if source_lib_ids:
                found = srv.get_boxsets_by_libraries(service, source_lib_ids)
                excluded.update(found)
                logger.info(f"{LOG_PREFIX} [来源库黑名单] 排除合集 {len(found)} 个")
        # 用户黑名单
        if self.cfg.exclude_users:
            user_ids: Set[str] = set()
            for entry in self.cfg.exclude_users:
                if "-" in entry:
                    parts = entry.split("-", 1)
                    if parts[0] == sname:
                        user_ids.add(parts[1])
                else:
                    user_ids.add(entry)
            if user_ids:
                found = srv.get_boxsets_by_users(service, user_ids)
                excluded.update(found)
                logger.info(f"{LOG_PREFIX} [用户黑名单] 排除合集 {len(found)} 个")
        return excluded

    def _handle_boxset_library(self, service, lib: dict, title) -> Optional[str]:
        """合集库专用：排除黑名单合集后，从子项取图。"""
        lid = srv.get_library_id(service, lib)
        sname = service.name if hasattr(service, 'name') else ""
        sort_by = self.cfg.sort_by or "Random"

        excluded_ids = self._get_excluded_boxset_ids(service, sname)

        all_boxsets = srv.get_items_batch(service, lid, limit=99999,
                                          include_types="BoxSet,Movie", sort_by=sort_by)
        if not all_boxsets:
            logger.warning(f"{LOG_PREFIX} {sname}：{lib.get('Name')} 合集库无 BoxSet")
            return False

        if excluded_ids:
            before = len(all_boxsets)
            all_boxsets = [b for b in all_boxsets
                           if str(b.get("Id") or b.get("ItemId") or "") not in excluded_ids]
            logger.info(f"{LOG_PREFIX} [合集过滤] {sname}：{lib.get('Name')} "
                        f"过滤 {before - len(all_boxsets)} 个合集，剩余 {len(all_boxsets)} 个")

        seen: Set[str] = set()
        valid = []
        for boxset in all_boxsets:
            if len(valid) >= self.cfg.required_items:
                break
            bs_id = boxset.get("Id") or boxset.get("ItemId")
            if not bs_id:
                continue
            children = srv.get_items_batch(service, bs_id, limit=20,
                                           include_types="Movie,Series,Episode", sort_by=sort_by)
            valid.extend(self._filter_items(children, seen))

        if not valid:
            logger.warning(f"{LOG_PREFIX} {sname}：{lib.get('Name')} 合集库筛选后无有效项目")
            return False
        if self.cfg.is_single_image_style:
            return self._process_single(service, lib, title, valid[0])
        return self._process_grid(service, lib, title, valid[:self.cfg.required_items])

    def _handle_playlist_library(self, service, lib: dict, title) -> Optional[str]:
        """播放列表库专用：先尝试 playlist 本身图片，再取子项。"""
        lid = srv.get_library_id(service, lib)
        sname = service.name if hasattr(service, 'name') else ""
        sort_by = self.cfg.sort_by or "Random"

        playlists = srv.get_items_batch(service, lid, limit=50,
                                        include_types="Playlist,Audio,MusicAlbum,Movie,Series,Episode",
                                        sort_by=sort_by)
        if not playlists:
            logger.warning(f"{LOG_PREFIX} {sname}：{lib.get('Name')} 播放列表库为空")
            return False

        seen: Set[str] = set()
        valid = list(self._filter_items(playlists, seen))

        if len(valid) < self.cfg.required_items:
            for pl in playlists:
                if len(valid) >= self.cfg.required_items:
                    break
                pl_id = pl.get("Id") or pl.get("ItemId")
                if not pl_id:
                    continue
                children = srv.get_items_batch(service, pl_id, limit=20,
                                               include_types="Audio,MusicAlbum,Movie,Series,Episode",
                                               sort_by=sort_by)
                valid.extend(self._filter_items(children, seen))

        if not valid:
            logger.warning(f"{LOG_PREFIX} {sname}：{lib.get('Name')} 播放列表筛选后无有效项目")
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

    def _generate(self, sname: str, lname: str, title, image_path: Optional[str] = None) -> Optional[str]:
        if not self.zh_font or not self.en_font:
            logger.error(f"{LOG_PREFIX} 字体缺失")
            return None
        # title 可能是 (zh, en) 或 (zh, en, color)；统一拆开
        if isinstance(title, (list, tuple)) and len(title) >= 3:
            title_pair = (title[0], title[1])
            config_bg_color = title[2]
        else:
            title_pair = (title[0] if isinstance(title, (list, tuple)) else title,
                          title[1] if isinstance(title, (list, tuple)) and len(title) > 1 else "")
            config_bg_color = None
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
              "config_color": config_bg_color}
        logger.info(f"{LOG_PREFIX} 渲染封面 {sname}：{lname} | 风格={self.cfg.cover_style} | "
                    f"分辨率={self.cfg.resolution} | 主标题='{title_pair[0]}' 副标题='{title_pair[1]}'")

        return render.dispatch_style(
            self.cfg.cover_style, image_path=image_path, library_dir=lib_dir, title=title_pair,
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
