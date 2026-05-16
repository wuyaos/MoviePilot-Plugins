# input: helper.py (TorrentHelper), entities.py (TorrentTask, HNRStatus), config.py (HNRConfig, SiteConfig)
# output: check() 定时检查、auto_discover() 自动发现、状态更新逻辑
# pos: 核心调度层，驱动 H&R 状态流转
"""H&R 检查器：定时扫描下载器种子状态，更新 H&R 进度，自动发现未纳管种子。"""
from __future__ import annotations

import time
import threading
from typing import Any, Callable, Dict, List, Optional, Set

from app.log import logger

from app.plugins.pthitandrun.config import HNRConfig, SiteConfig
from app.plugins.pthitandrun.entities import HNRStatus, TaskType, TorrentHistory, TorrentTask
from app.plugins.pthitandrun.helper import TorrentHelper

LOG_PREFIX = "【PtH&R】"
lock = threading.Lock()


class HNRChecker:
    """H&R 状态检查与自动发现（多下载器）。"""

    def __init__(self, *, config: HNRConfig, helpers: Dict[str, TorrentHelper],
                 get_data: Callable, save_data: Callable,
                 send_message: Optional[Callable] = None):
        self._cfg = config
        self._helpers = helpers  # downloader_name -> TorrentHelper
        self._get_data = get_data
        self._save_data = save_data
        self._send_message = send_message

    def _get_helper(self, name: str) -> Optional[TorrentHelper]:
        """按名称获取 helper，兜底返回第一个。"""
        if name and name in self._helpers:
            return self._helpers[name]
        return next(iter(self._helpers.values()), None) if self._helpers else None

    # ---- 公开接口 ----

    def check(self):
        """定时检查所有 H&R 任务状态。"""
        if not self._helpers:
            return
        with lock:
            self._do_check()

    def auto_discover(self):
        """扫描所有下载器，将未纳管的种子纳入 H&R 管理。"""
        if not self._cfg.auto_discover or not self._helpers:
            return
        with lock:
            self._do_discover()

    # ---- 内部：检查 ----

    def _do_check(self):
        logger.info(f"{LOG_PREFIX}开始检查 H&R 任务...")
        tasks = self._load_tasks()
        if not tasks:
            logger.info(f"{LOG_PREFIX}无 H&R 任务需要检查")
            return

        # 汇总所有下载器的种子
        torrent_map: Dict[str, Any] = {}
        hash_to_dl: Dict[str, str] = {}  # hash -> downloader_name
        for dl_name, th in self._helpers.items():
            for t in (th.get_torrents() or []):
                h = th.get_torrent_hash(t)
                if h:
                    torrent_map[h] = t
                    hash_to_dl[h] = dl_name

        logger.info(f"{LOG_PREFIX}共 {len(tasks)} 个 H&R 任务，下载器共 {len(torrent_map)} 个种子")

        for h, task in tasks.items():
            torrent = torrent_map.get(h)
            if torrent:
                dl_name = hash_to_dl.get(h, "")
                th = self._get_helper(dl_name)
                if th:
                    self._update_task_stats(task, torrent, th)
                # 补填历史任务缺失的 downloader
                if not task.downloader and dl_name:
                    task.downloader = dl_name
            elif not task.deleted:
                task.deleted = True
                task.deleted_time = time.time()
                logger.info(f"{LOG_PREFIX}种子已从下载器删除: {task.identifier}")

            self._update_hr_status(task)

        # 清理过期记录
        self._auto_cleanup(tasks)
        # 保存
        self._save_tasks(tasks)
        logger.info(f"{LOG_PREFIX}H&R 检查完成")

    def _update_task_stats(self, task: TorrentTask, torrent: Any, th: TorrentHelper):
        """从下载器更新种子的实时统计。"""
        info = th.get_torrent_info(torrent)
        task.seeding_time = info.get("seeding_time", 0)
        task.ratio = info.get("ratio", 0)
        task.uploaded = info.get("uploaded", 0)
        task.downloaded = info.get("downloaded", 0)

    def _update_hr_status(self, task: TorrentTask):
        """根据当前统计更新 H&R 状态。"""
        if not task.hit_and_run:
            return
        if task.hr_status != HNRStatus.IN_PROGRESS:
            return

        site_cfg = self._cfg.get_site_config(task.site_name or "")
        additional = site_cfg.additional_seed_time or 0

        # 按种子大小分级覆盖
        tier = site_cfg.get_tier_for_size(task.size)
        if tier:
            task.hr_duration = tier.hr_duration
            task.hr_deadline_days = tier.hr_deadline_days

        if task.meets_hr(additional_seed_time=additional):
            task.hr_status = HNRStatus.COMPLIANT
            task.hr_met_time = time.time()
            self._remove_tag(task)
            logger.info(f"{LOG_PREFIX}已满足 H&R: {task.identifier}")
            self._notify(task, "【H&R 已完成】")
        elif time.time() > task.deadline_time:
            task.hr_status = HNRStatus.OVERDUE
            logger.warning(f"{LOG_PREFIX}H&R 已过期: {task.identifier}")
            self._notify(task, "【H&R 已过期】", warn=True)
        elif task.deleted:
            task.hr_status = HNRStatus.NEEDS_SEEDING
            logger.warning(f"{LOG_PREFIX}需要做种: {task.identifier}")
            self._notify(task, "【H&R 需要做种】", warn=True)

    # ---- 内部：自动发现 ----

    def _do_discover(self):
        logger.info(f"{LOG_PREFIX}开始自动发现未纳管种子...")
        tasks = self._load_tasks()
        known_hashes: Set[str] = set(tasks.keys())
        discovered = 0

        for dl_name, th in self._helpers.items():
            for torrent in (th.get_torrents() or []):
                h = th.get_torrent_hash(torrent)
                if not h or h in known_hashes:
                    continue
                site_id, site_name = TorrentHelper.get_site_by_torrent(torrent)
                if not site_id or site_id not in self._cfg.sites:
                    continue
                info = th.get_torrent_info(torrent)
                site_cfg = self._cfg.get_site_config(site_name or "")

                task = TorrentTask(
                    hash=h,
                    site=site_id,
                    site_name=site_name,
                    title=info.get("title", ""),
                    size=info.get("total_size", 0),
                    time=info.get("add_on", 0) or time.time(),
                    hit_and_run=True,
                    task_type=TaskType.DISCOVERED,
                    seeding_time=info.get("seeding_time", 0),
                    ratio=info.get("ratio", 0),
                    uploaded=info.get("uploaded", 0),
                    downloaded=info.get("downloaded", 0),
                    downloader=dl_name,
                )
                self._init_hr_params(task, site_cfg)
                task.hr_status = HNRStatus.IN_PROGRESS
                tasks[h] = task
                self._set_tag(task)
                known_hashes.add(h)
                discovered += 1

        if discovered:
            self._save_tasks(tasks)
            logger.info(f"{LOG_PREFIX}自动发现 {discovered} 个新种子纳入 H&R 管理")
        else:
            logger.info(f"{LOG_PREFIX}未发现新的未纳管种子")

    # ---- 初始化 H&R 参数 ----

    def init_task(self, task: TorrentTask):
        """为新任务初始化 H&R 参数并设置标签。"""
        site_cfg = self._cfg.get_site_config(task.site_name or "")
        self._init_hr_params(task, site_cfg)

        if not task.hit_and_run and not site_cfg.hr_active:
            return False

        task.hit_and_run = True
        task.hr_status = HNRStatus.IN_PROGRESS
        self._set_tag(task)
        return True

    def _init_hr_params(self, task: TorrentTask, site_cfg: SiteConfig):
        """从站点配置填充任务的 H&R 参数。"""
        # 按大小分级
        tier = site_cfg.get_tier_for_size(task.size)
        if tier:
            task.hr_duration = tier.hr_duration
            task.hr_deadline_days = tier.hr_deadline_days
        else:
            task.hr_duration = site_cfg.hr_duration
            task.hr_deadline_days = site_cfg.hr_deadline_days
        task.hr_ratio = site_cfg.hr_ratio
        task.hr_upload_multiplier = site_cfg.hr_upload_multiplier
        task.hr_upload_gte_download = site_cfg.hr_upload_gte_download

    # ---- 标签 ----

    def _set_tag(self, task: TorrentTask):
        tag = self._cfg.hit_and_run_tag
        if tag and task.hash:
            th = self._get_helper(task.downloader or "")
            if th:
                th.set_torrent_tag(task.hash, [tag])

    def _remove_tag(self, task: TorrentTask):
        tag = self._cfg.hit_and_run_tag
        if tag and task.hash:
            th = self._get_helper(task.downloader or "")
            if th:
                th.remove_torrent_tag(task.hash, [tag])

    # ---- 清理 ----

    def _auto_cleanup(self, tasks: Dict[str, TorrentTask]):
        if self._cfg.auto_cleanup_days <= 0:
            return
        threshold = self._cfg.auto_cleanup_days * 86400
        now = time.time()
        to_remove = []
        for h, task in tasks.items():
            if task.hr_status == HNRStatus.COMPLIANT and task.hr_met_time:
                if now - task.hr_met_time > threshold:
                    to_remove.append(h)
            elif task.deleted and task.deleted_time:
                if now - task.deleted_time > threshold:
                    to_remove.append(h)
        for h in to_remove:
            del tasks[h]
        if to_remove:
            logger.info(f"{LOG_PREFIX}自动清理 {len(to_remove)} 条过期记录")

    # ---- 通知 ----

    def _notify(self, task: TorrentTask, title: str, warn: bool = False):
        if not self._send_message:
            return
        from app.plugins.pthitandrun.config import NotifyMode
        if self._cfg.notify == NotifyMode.NONE:
            return
        if self._cfg.notify == NotifyMode.ON_ERROR and not warn:
            return
        msg = (f"站点: {task.site_name}\n"
               f"种子: {task.identifier}\n"
               f"做种: {(task.seeding_time or 0) / 3600:.1f}h\n"
               f"分享率: {task.ratio:.2f}\n"
               f"截止: {task.formatted_deadline()}")
        self._send_message(title=title, text=msg)

    # ---- 持久化 ----

    def _load_tasks(self) -> Dict[str, TorrentTask]:
        raw = self._get_data("torrents")
        if not raw or not isinstance(raw, dict):
            return {}
        result = {}
        for k, v in raw.items():
            try:
                result[k] = TorrentTask.parse_raw(v) if isinstance(v, str) else TorrentTask(**v)
            except Exception:
                continue
        return result

    def _save_tasks(self, tasks: Dict[str, TorrentTask]):
        self._save_data("torrents", {k: v.to_dict() for k, v in tasks.items()})

    def save_task(self, task: TorrentTask):
        """保存单个任务（事件处理时用）。"""
        tasks = self._load_tasks()
        if task.hash:
            tasks[task.hash] = task
        self._save_tasks(tasks)
