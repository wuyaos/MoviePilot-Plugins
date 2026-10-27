"""做种校验服务边界，承载入口层以外的做种校验运行时逻辑。"""

from __future__ import annotations

import threading
import time
from typing import Any

from app.sdk.logging import logger

from ..model.state import SEED_RECHECK_QUEUE_KEY

from ..utils.torrent_adapter import get_torrent_state, torrent_is_complete


def _queue_lock(plugin) -> threading.RLock:
    """获取做种校验队列锁，兼容未声明该属性的测试替身。"""
    lock = getattr(plugin, "_seed_recheck_queue_lock", None)
    if lock is None:
        lock = getattr(plugin, "_seed_recheck_lock", None)
        if lock is None:
            lock = threading.RLock()
            plugin._seed_recheck_lock = lock
        plugin._seed_recheck_queue_lock = lock
    return lock


def _queue_key(downloader: str, hash_text: str) -> str:
    """构造下载器隔离的队列身份。"""
    return f"{str(downloader or '').strip()}::{str(hash_text or '').strip().lower()}"


def _normalize_queue(value) -> dict:
    """把旧版按 hash 的队列迁移为下载器加 hash 的键。"""
    if not isinstance(value, dict):
        return {}
    normalized = {}
    for old_key, raw_item in value.items():
        if not isinstance(raw_item, dict):
            continue
        item = dict(raw_item)
        if item.get("source") != "transfer" or not item.get("source_downloader"):
            continue
        hash_text = str(item.get("hash") or old_key or "").strip()
        downloader = str(item.get("downloader") or "").strip()
        if not hash_text or not downloader:
            continue
        key = _queue_key(downloader, hash_text)
        existing = normalized.get(key)
        if existing is None or float(item.get("updated_at") or 0) >= float(existing.get("updated_at") or 0):
            item["hash"] = hash_text
            item["downloader"] = downloader
            item["updated_at"] = float(item.get("updated_at") or item.get("created_at") or time.time())
            normalized[key] = item
    return normalized


def load_seed_recheck_queue(plugin):
    """读取持久化做种校验队列。"""
    with _queue_lock(plugin):
        return _normalize_queue(plugin.get_data(SEED_RECHECK_QUEUE_KEY))


def save_seed_recheck_queue(plugin, queue):
    """保存持久化做种校验队列。"""
    with _queue_lock(plugin):
        plugin.save_data(SEED_RECHECK_QUEUE_KEY, _normalize_queue(queue))


def ensure_seed_recheck_worker(plugin):
    """确保按需做种校验 worker 已启动。"""
    with plugin._seed_recheck_lock:
        event = getattr(plugin, "_event", None)
        if event is not None and event.is_set():
            return
        if plugin._seed_recheck_running:
            stop_event = getattr(plugin, "_seed_recheck_stop_event", None)
            plugin._seed_recheck_restart_pending = True
            return
        plugin._seed_recheck_running = True
        plugin._seed_recheck_restart_pending = False
        stop_event = threading.Event()
        plugin._seed_recheck_stop_event = stop_event
        thread = threading.Thread(
            target=seed_recheck_loop,
            args=(plugin, stop_event),
            name="DownloadManagerSeedRecheck",
            daemon=True,
        )
        plugin._seed_recheck_thread = thread
        try:
            thread.start()
        except Exception:
            plugin._seed_recheck_running = False
            plugin._seed_recheck_thread = None
            plugin._seed_recheck_stop_event = None
            raise
    logger.info("【PT下载中心:做种校验】按需 worker 已启动")


def stop_seed_recheck_worker(plugin, join_timeout: float = 10.0) -> bool:
    """停止并等待做种校验 worker，阻止停止后的下载器写操作。"""
    with _queue_lock(plugin):
        plugin._seed_recheck_restart_pending = False
        thread = getattr(plugin, "_seed_recheck_thread", None)
        stop_event = getattr(plugin, "_seed_recheck_stop_event", None)
        if stop_event is not None:
            stop_event.set()
    if thread is None:
        return False
    if thread is not threading.current_thread() and thread.is_alive():
        thread.join(timeout=max(0.0, float(join_timeout)))
    if not thread.is_alive():
        with getattr(plugin, "_seed_recheck_lock", threading.RLock()):
            if getattr(plugin, "_seed_recheck_thread", None) is thread:
                plugin._seed_recheck_thread = None
            if getattr(plugin, "_seed_recheck_stop_event", None) is stop_event:
                plugin._seed_recheck_stop_event = None
    if thread.is_alive():
        logger.error("【PT下载中心:做种校验】worker 停止超时，下载器请求可能仍在执行")
        return False
    return True


def seed_recheck_loop(plugin, stop_event=None):
    """持续处理做种校验队列，直到队列清空或插件停用。"""
    stop_event = stop_event or getattr(plugin, "_seed_recheck_stop_event", None) or threading.Event()
    try:
        while plugin._enabled and not stop_event.is_set():
            queue = load_seed_recheck_queue(plugin)
            if not queue:
                logger.info("【PT下载中心:做种校验】队列已清空，worker 退出")
                break
            try:
                process_seed_recheck_once(plugin, queue, stop_event=stop_event)
            except Exception as exc:
                logger.error(f"【PT下载中心:做种校验】处理队列失败: {exc}")
            if stop_event.wait(max(0.1, float(getattr(plugin, "_seed_check_interval", 60) or 60))):
                break
    finally:
        with plugin._seed_recheck_lock:
            plugin._seed_recheck_running = False
            if getattr(plugin, "_seed_recheck_thread", None) is threading.current_thread():
                plugin._seed_recheck_thread = None
            if getattr(plugin, "_seed_recheck_stop_event", None) is stop_event:
                plugin._seed_recheck_stop_event = None
            restart = bool(getattr(plugin, "_seed_recheck_restart_pending", False) and plugin._enabled)
            plugin._seed_recheck_restart_pending = False
        if restart and load_seed_recheck_queue(plugin):
            ensure_seed_recheck_worker(plugin)


def process_seed_recheck_once(plugin, queue, stop_event=None):
    """仅推进带源身份的转移事务，不再扫描任意暂停任务。"""
    from .transfer_pipeline import advance_transfer
    stop_event = stop_event or getattr(plugin, "_seed_recheck_stop_event", None)
    def stopped():
        return (stop_event is not None and stop_event.is_set()) or plugin._event.is_set()
    changed = False
    with _queue_lock(plugin):
        queue.clear()
        queue.update(load_seed_recheck_queue(plugin))
        for key, item in list(queue.items()):
            if stopped():
                break
            if item.get("source") != "transfer" or not item.get("source_downloader"):
                continue
            service = plugin.service_info(item["downloader"])
            if not service or not service.instance:
                continue
            try:
                torrents, error = service.instance.get_torrents(ids=[item["hash"]])
                if error or torrents is None:
                    continue
                task = next((t for t in torrents if str(plugin.get_hash(t, service.type)).lower() == item["hash"].lower()), None)
                if advance_transfer(plugin, item, service, task, stopped):
                    queue.pop(key, None)
                changed = True
            except Exception as exc:
                if item["phase"] in ("target_added", "verifying"):
                    item["phase"] = "rollback"
                    item["error"] = str(exc)
                logger.error(f"【PT下载中心:做种校验】转移流水线：{key} 推进失败，保留续办: {exc}")
        save_seed_recheck_queue(plugin, queue)
    return changed


def seed_should_remove_missing(item):
    """判断下载器缺失任务是否应从校验队列移除。"""
    elapsed = (time.time() - item.get("created_at", 0)) / 60
    return elapsed > max(item.get("max_wait_minutes", 120), 30)


def seed_is_checking(state, downloader_type):
    """判断种子是否仍处于校验或移动等不可开始状态。"""
    if downloader_type == "qbittorrent":
        return state in ["checkingUP", "checkingDL", "checkingResumeData", "checking", "queuedUP", "queuedDL", "moving"]
    if downloader_type == "rtorrent":
        # rt 宿主客户端无 recheck_torrents，不存在需要等待的校验阶段。
        return False
    return str(state) in ("checking", "check pending") or bool(getattr(state, "checking", False))


def seed_is_ready(state, downloader_type, torrent=None):
    """判断种子是否已校验完成并可开始做种。"""
    if downloader_type == "qbittorrent":
        return state in ["pausedUP", "stoppedUP", "completed", "uploading", "stalledUP", "forcedUP"]
    if downloader_type == "rtorrent":
        # rt 无显式 recheck：以 d.complete 或完成度作为校验完成证据。
        return torrent_is_complete(torrent, "rtorrent")
    percent_done = getattr(torrent, "percent_done", getattr(state, "percent_done", 0))
    return str(state) in ("stopped", "seeding", "seed pending") and percent_done == 1


def seed_is_error(state, downloader_type):
    """判断种子是否处于需要计入失败次数的错误状态。"""
    if downloader_type == "qbittorrent":
        return state in ["missingFiles", "error", "unknown"]
    return False


def seed_is_timeout(item, max_wait_minutes):
    """判断校验任务是否已超过最大等待时间。"""
    elapsed = (time.time() - item.get("created_at", 0)) / 60
    return elapsed > item.get("max_wait_minutes", max_wait_minutes)


def run_recheck_cycle(plugin) -> None:
    """转移内部续办入口；不再提供独立校验扫描。"""
    ensure_seed_recheck_worker(plugin)


def sweep_paused_seed_tasks(plugin, check_services):
    """保留入口层委托签名，处理范围限定为持久转移事务。"""
    ensure_seed_recheck_worker(plugin)


def can_seed_paused_torrent(torrent, downloader_type):
    """供转移使用的目标完整性判断。"""
    state = get_torrent_state(torrent, downloader_type)
    return seed_is_ready(state, downloader_type, torrent)
