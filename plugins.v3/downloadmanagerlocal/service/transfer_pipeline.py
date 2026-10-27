"""转移事务：持久记录源状态，目标确认完整后才允许删源。"""

import time

from app.sdk.logging import logger

from ..model.state import record_transfer_success
from .hr.guard import HrGuard

from .recheck import (
    _queue_key, load_seed_recheck_queue, save_seed_recheck_queue,
    ensure_seed_recheck_worker, seed_is_checking, seed_is_ready, seed_is_error,
    seed_is_timeout,
)
from ..utils.torrent_adapter import (
    get_torrent_state, is_torrent_active, supports_recheck, torrent_is_complete,
)


def save_transaction(plugin, item):
    """队列及来源索引使用同一事务内容，来源索引供同步删除关联目标。"""
    item["updated_at"] = time.time()
    queue = load_seed_recheck_queue(plugin)
    queue[_queue_key(item["downloader"], item["hash"])] = dict(item)
    save_seed_recheck_queue(plugin, queue)
    save_source_record(plugin, item)


def save_source_record(plugin, item):
    """保持基础插件的来源到目标映射字段。"""
    plugin.save_data(f"{item['source_downloader']}-{item['source_hash']}", {
        **item,
        "to_download": item["downloader"],
        "to_download_id": item["hash"],
        "transfer_state": item["phase"],
        "delete_source": item.get("source_deleted", False),
        "delete_duplicate": False,
    })


def delete_source(plugin, downloader_id, torrent_hash):
    """所有源任务删除共享 H&R 保护；绝不删除源数据文件。"""
    if HrGuard().is_protected(downloader_id, torrent_hash):
        stats = plugin.get_data("transfer_skip_stats") or {"hr_protected": 0}
        stats["hr_protected"] += 1
        plugin.save_data("transfer_skip_stats", stats)
        logger.info(f"【PT下载中心:转移做种】H&R 保护，保留源任务 {downloader_id}/{torrent_hash}")
        return "protected"
    service = plugin.service_info(downloader_id)
    if not service or not service.instance:
        return "retry"
    if service.instance.delete_torrents(delete_file=False, ids=[torrent_hash]) is False:
        return "retry"
    return "deleted"


def source_is_active(torrent, downloader_type):
    """仅记录需要在回滚时恢复的源活动状态（统一 qB/TR/rt 判定）。"""
    return is_torrent_active(torrent, downloader_type)


def begin_transfer(
    plugin, from_service, to_service, source_hash, torrent, add_target, stopped, *,
    fallback: bool = False,
    delete_source: Optional[bool] = None,
):
    """先落盘源状态再暂停/添加；异常统一进入可续办回滚。"""
    item = {
        "source": "transfer", "source_downloader": from_service.name,
        "source_hash": source_hash, "downloader": to_service.name, "hash": source_hash,
        "created_at": time.time(), "max_wait_minutes": plugin._seed_max_wait_minutes,
        "source_was_active": source_is_active(torrent, from_service.type),
        "pause_source": bool(getattr(plugin, "_pause_source", True)),
        "delete_source_requested": bool(plugin._deletesource if delete_source is None else delete_source),
        "autostart": bool(plugin._seed_autostart), "skipverify": bool(plugin._seed_skipverify),
        "phase": "source_pausing", "target_added": False,
        # 兜底扫描发起的转移单独计数，供「兜底成功」统计区分主链路。
        "fallback": bool(fallback),
    }
    save_transaction(plugin, item)
    try:
        if item["pause_source"]:
            if from_service.instance.stop_torrents(ids=[source_hash]) is False:
                raise RuntimeError("源下载器未确认暂停成功")
            deadline = time.monotonic() + 30
            while True:
                if stopped():
                    return False
                tasks, error = from_service.instance.get_torrents(ids=[source_hash])
                if error or tasks is None:
                    raise RuntimeError("源下载器暂停状态查询失败")
                if not tasks:
                    raise RuntimeError("源任务消失")
                if not source_is_active(tasks[0], from_service.type):
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError("源任务暂停超时")
                plugin._event.wait(1)
        if stopped():
            return False
        # hash 来自源 torrent；即使添加请求响应丢失，也可定位此次目标并回滚。
        item["phase"] = "adding"
        item["target_added"] = True
        save_transaction(plugin, item)
        download_id = add_target()
        if not download_id:
            raise RuntimeError("添加目标任务失败")
        item["hash"] = download_id
        item["phase"] = "target_added"
        save_transaction(plugin, item)
    except Exception as exc:
        item["phase"] = "rollback"
        item["error"] = str(exc)
        save_transaction(plugin, item)
        logger.error(f"【PT下载中心:转移做种】转移失败，等待回滚 {source_hash}: {exc}")
    finally:
        ensure_seed_recheck_worker(plugin)
    return item["phase"] == "target_added"


def rollback_transfer(plugin, item, target_service, stopped):
    """先删目标再恢复源，删除失败时不制造双端同时做种。"""
    if stopped():
        return False
    if item["target_added"]:
        if target_service.instance.delete_torrents(delete_file=False, ids=[item["hash"]]) is False:
            return False
        remaining, error = target_service.instance.get_torrents(ids=[item["hash"]])
        if error or remaining is None or remaining:
            return False
        item["target_added"] = False
        save_transaction(plugin, item)
    if item["pause_source"] and item["source_was_active"]:
        service = plugin.service_info(item["source_downloader"])
        if not service or not service.instance or stopped():
            return False
        if service.instance.start_torrents(ids=[item["source_hash"]]) is False:
            return False
    item["phase"] = "rolled_back"
    save_source_record(plugin, item)
    return True


def advance_transfer(plugin, item, service, task, stopped):
    """推进一次事务；返回 True 仅表示可从待办队列移除。"""
    if stopped():
        return False
    phase = item["phase"]
    if phase in ("source_pausing", "adding"):
        item["phase"] = "rollback"
    if item["phase"] == "rollback":
        return rollback_transfer(plugin, item, service, stopped)
    if task is None or (not item.get("target_confirmed") and seed_is_timeout(item, plugin._seed_max_wait_minutes)):
        item["error"] = "目标丢失或校验超时"
        item["phase"] = "rollback"
        if task is None:
            item["target_added"] = False
        save_transaction(plugin, item)
        return rollback_transfer(plugin, item, service, stopped)
    state = get_torrent_state(task, service.type)
    if seed_is_error(state, service.type) or (service.type == "transmission" and getattr(task, "error", 0)):
        item["phase"] = "rollback"
        item["error"] = "目标校验错误"
        save_transaction(plugin, item)
        return rollback_transfer(plugin, item, service, stopped)
    if phase == "target_added":
        if supports_recheck(service.type) and not (service.type == "qbittorrent" and item["skipverify"]):
            if service.instance.recheck_torrents(ids=[item["hash"]]) is False:
                item["phase"] = "rollback"
            else:
                item["phase"] = "verifying"
        else:
            item["phase"] = "verifying"
        save_transaction(plugin, item)
        # 不能用发起校验前读取的状态认定校验通过。
        return False
    if seed_is_checking(state, service.type) or not seed_is_ready(state, service.type, task):
        return False
    if phase != "target_ready":
        item["phase"] = "target_ready"
        save_transaction(plugin, item)
    if item["autostart"]:
        if stopped() or service.instance.start_torrents(ids=[item["hash"]]) is False:
            return False
        # 开始命令不是做种证据，下一轮回读目标活动状态才允许删源。
        if service.type == "qbittorrent":
            active = state in ("uploading", "stalledUP", "forcedUP")
        elif service.type == "rtorrent":
            # rt 没有 uploading/seeding 文本状态：以「已完成且在活动」作为做种证据。
            active = torrent_is_complete(task, "rtorrent") and is_torrent_active(task, "rtorrent")
        else:
            active = str(state) == "seeding"
        if not active:
            return False
    item["target_confirmed"] = True
    from .transfer import post_transfer_process
    if stopped() or not post_transfer_process(plugin, service, item["hash"]):
        return False
    if item["delete_source_requested"]:
        if stopped():
            return False
        result = delete_source(plugin, item["source_downloader"], item["source_hash"])
        if result == "retry":
            return False
        item["source_deleted"] = result == "deleted"
        item["hr_protected"] = result == "protected"
    item["phase"] = "completed"
    save_source_record(plugin, item)
    record_transfer_success(plugin, 1, fallback=bool(item.get("fallback")))
    return True
