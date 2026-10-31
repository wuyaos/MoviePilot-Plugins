"""转移事务：持久记录源状态，目标确认完整后才允许删源。"""

import time
from typing import Optional

from app.sdk.logging import logger

from ...model.state import record_transfer_success
from ..hr.guard import SKIP_PATH_TRANSFER_SOURCE, HrGuard

from .recheck import (
    _queue_key, _queue_lock, load_seed_recheck_queue, save_seed_recheck_queue,
    ensure_seed_recheck_worker, seed_is_checking, seed_is_ready, seed_is_error,
    seed_is_timeout,
)
from ...utils.torrent_adapter import (
    get_torrent_state, is_torrent_active, normalize_hash, skipverify_applies,
    get_torrent_name, supports_recheck, torrent_is_complete,
)

# 同一颗源种子最多尝试 3 次：计数跨事务累计（存进来源记录，见 save_source_record），
# 在**回滚完成后**加一——回滚本体的重试不算失败次数。
# 达到上限置终态 "failed"，不再被自动轮次选中（跳过点见 service._run_task）。
# 复位途径：手动触发一次「转移做种」（/transfer_run）——视为用户明确要求重试，计数清零。
MAX_TRANSFER_ATTEMPTS = 3

def transfer_is_abandoned(previous: dict, manual: bool = False) -> bool:
    """该源种子是否已放弃（连续失败达上限），自动轮次应跳过。

    手动触发（数据页「立即转移」）不算放弃：它会重置计数后重试，所以这里必须返回 False，
    否则用户手动点一次也救不回来。放在 pipeline 而非 service，是为了让这条判据可被
    夹具直接加载的真实模块单测覆盖（service 依赖面太广，难以单独加载）。
    """
    if manual:
        return False
    return (
        (previous or {}).get("transfer_state") == "failed"
        and int((previous or {}).get("attempts", 0) or 0) >= MAX_TRANSFER_ATTEMPTS
    )


def save_transaction(plugin, item):
    """队列及来源索引使用同一事务内容，来源索引供同步删除关联目标。"""
    _preserve_history_hidden(plugin, item)
    item["updated_at"] = time.time()
    queue = load_seed_recheck_queue(plugin)
    queue[_queue_key(item["downloader"], item["hash"])] = dict(item)
    save_seed_recheck_queue(plugin, queue)
    save_source_record(plugin, item)


def _preserve_history_hidden(plugin, item):
    """Display suppression belongs to this transaction, never permanently to a source hash."""
    previous = plugin.get_data(f"{item['source_downloader']}-{item['source_hash']}") or {}
    if previous.get("created_at") == item.get("created_at") and previous.get("history_hidden"):
        item["history_hidden"] = True


def save_source_record(plugin, item):
    """保持基础插件的来源到目标映射字段。"""
    _preserve_history_hidden(plugin, item)
    plugin.save_data(f"{item['source_downloader']}-{item['source_hash']}", {
        **item,
        "to_download": item["downloader"],
        "to_download_id": item["hash"],
        "transfer_state": item["phase"],
        "delete_source": item.get("source_deleted", False),
        "delete_duplicate": False,
    })


def transfer_observe_skip(plugin, action: str, detail: str = "") -> bool:
    """转移写边界：只登记预览，不改事务进度或下载器。"""
    from ...utils.config import observe_only

    if not observe_only(plugin, "transfer"):
        return False
    from ...utils.config import record_observe_preview
    record_observe_preview(plugin, "transfer", f"{action}：{detail}")
    logger.info(f"【PT下载中心:转移做种】观察模式，仅预览不写入：{action} {detail}")
    return True


def delete_source(plugin, downloader_id, torrent_hash, *, authorized=False,
                  target_verified=False, operation_id=None):
    """所有源任务删除共享 H&R 保护；绝不删除源数据文件。"""
    if transfer_observe_skip(plugin, "删除源任务", f"{downloader_id}/{torrent_hash}"):
        return "protected"
    guard = HrGuard()
    interlock = None
    denied = False
    service = plugin.service_info(downloader_id)
    permit = dict(source="transfer_source", operation_id=operation_id, authorized=authorized)
    hr_service = getattr(plugin, "_hr_service", None)
    task = hr_service.get_task(downloader_id, torrent_hash) if hr_service is not None else None
    # A prior reservation must not fall through merely because release removed protection.
    reserved = bool(task and task.interlock_state)
    if (hr_service is not None and service and service.instance
            and (reserved or (authorized is True and guard.is_protected(downloader_id, torrent_hash)))):
        from ..hr.interlock import HrInterlock

        interlock = HrInterlock(hr_service)
        try:
            result = interlock.release(downloader_id, torrent_hash, **permit,
                                       target_verified=target_verified)
            if result["state"] != "released":
                logger.warning(f"【PT下载中心:转移做种】H&R 解除未获许可：{result}")
                return "protected"
        except PermissionError as error:
            logger.info(f"【PT下载中心:转移做种】H&R 删源拒绝：{error}")
            denied = True
    if guard.should_skip(SKIP_PATH_TRANSFER_SOURCE, downloader_id, torrent_hash):
        # 读改写与并发轮次互斥，避免并发 transfer 轮次丢计数（锁与 seed_recheck 的轮次读改写同一把，取法需容错旧实例）。
        with _queue_lock(plugin):
            stats = plugin.get_data("transfer_skip_stats") or {"hr_protected": 0}
            stats["hr_protected"] += 1
            plugin.save_data("transfer_skip_stats", stats)
        reason = "H&R 保护状态无法确认" if guard.unconfirmed else "H&R 保护"
        logger.info(f"【PT下载中心:转移做种】{reason}，保留源任务 {downloader_id}/{torrent_hash}")
        return "protected"
    if denied:
        return "protected"
    if not service or not service.instance:
        # 静默返回 "retry" 会让「源种没删」既无日志也无线索：2026-10-28 排查
        # 「delete_source=True 但源种还在」时，三条分支全无日志，白耗一轮。
        logger.warning(f"【PT下载中心:转移做种】删源跳过：下载器不可用 {downloader_id}/{torrent_hash}")
        return "retry"
    if interlock is not None:
        try:
            result = interlock.begin_delete(downloader_id, torrent_hash, **permit)
        except PermissionError as error:
            logger.info(f"【PT下载中心:转移做种】H&R 删除许可拒绝：{error}")
            return "protected"
        if result["state"] != "deleting":
            return "protected"
    success = False
    try:
        success = service.instance.delete_torrents(delete_file=False, ids=[torrent_hash]) is not False
    finally:
        if interlock is not None:
            interlock.finish_delete(downloader_id, torrent_hash, **permit, success=success)
    if not success:
        logger.warning(f"【PT下载中心:转移做种】删源失败：下载器拒绝删除 {downloader_id}/{torrent_hash}")
        return "retry"
    logger.info(f"【PT下载中心:转移做种】已删除源任务（不含文件）{downloader_id}/{torrent_hash}")
    return "deleted"


def source_is_active(torrent, downloader_type):
    """仅记录需要在回滚时恢复的源活动状态（统一 qB/TR/rt 判定）。"""
    return is_torrent_active(torrent, downloader_type)


def begin_transfer(
    plugin, from_service, to_service, source_hash, torrent, add_target, stopped, *,
    fallback: bool = False,
    delete_source: Optional[bool] = None,
    attempts: Optional[int] = None,
):
    """先落盘源状态再暂停/添加；异常统一进入可续办回滚。"""
    if transfer_observe_skip(plugin, "暂停源并添加目标", str(source_hash)):
        return False
    if attempts is None:
        # 调用方未显式给出失败次数时，从来源记录续算，避免主链路漏传导致计数静默清零。
        previous = plugin.get_data(f"{from_service.name}-{source_hash}") or {}
        attempts = int(previous.get("attempts", 0) or 0)
    item = {
        "source": "transfer", "source_downloader": from_service.name,
        "source_hash": source_hash, "downloader": to_service.name, "hash": source_hash,
        # 转移发起时的源种子名：仅供数据页展示，缺失时为空串（不参与任何业务判定）。
        "source_name": get_torrent_name(torrent),
        "created_at": time.time(), "max_wait_minutes": plugin._seed_max_wait_minutes,
        "source_was_active": source_is_active(torrent, from_service.type),
        "pause_source": bool(getattr(plugin, "_pause_source", True)),
        "delete_source_requested": (plugin._deletesource if delete_source is None else delete_source) is True,
        "autostart": bool(plugin._seed_autostart), "skipverify": bool(plugin._seed_skipverify),
        "phase": "source_pausing", "target_added": False,
        # 失败次数跨事务累计。未显式传入（None）时从来源记录续算——不能默认 0，否则调用方
        # 漏传就把计数静默清零、上限永不生效。手动触发由 service 显式传 0 表示重置。
        "attempts": max(0, int(attempts)),
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
        item["hash"] = normalize_hash(download_id)
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
    if transfer_observe_skip(plugin, "回滚转移（原地等待）", str(item.get("source_hash", ""))):
        return False
    if item.get("phase") in ("failed", "rolled_back"):
        return True
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
    # 失败次数在回滚**完成后**累计：回滚本体（删目标/恢复源）的重试不计入失败次数，
    # 否则一次失败的多次回滚轮次会把计数吃满。
    item["attempts"] = int(item.get("attempts", 0) or 0) + 1
    if item["attempts"] >= MAX_TRANSFER_ATTEMPTS:
        item["phase"] = "failed"
        from ...model.state import record_transfer_failure
        with plugin._seed_recheck_lock:
            previous = plugin.get_data(f"{item['source_downloader']}-{item['source_hash']}") or {}
            if previous.get("created_at") == item.get("created_at") and previous.get("failed_at"):
                item["failed_at"] = previous["failed_at"]
            if not item.get("failed_at"):
                item["failed_at"] = time.time()
                record_transfer_failure(plugin)
            save_source_record(plugin, item)
        logger.error(
            f"【PT下载中心:转移做种】已放弃该种子：连续失败 {item['attempts']} 次"
            f"（上限 {MAX_TRANSFER_ATTEMPTS}），自动轮次不再重试 "
            f"{item['source_hash'][:8]} → {item['downloader']}，最后原因："
            f"{item.get('error') or '未记录'}；手动触发一次「转移做种」可按新计数重试"
        )
        return True
    item["phase"] = "rolled_back"
    save_source_record(plugin, item)
    return True


def advance_transfer(plugin, item, service, task, stopped):
    """推进一次事务；返回 True 仅表示可从待办队列移除。"""
    if stopped():
        return False
    if transfer_observe_skip(plugin, "续办转移（原地等待）", str(item.get("source_hash", ""))):
        return False
    phase = item["phase"]
    if phase in ("source_pausing", "adding"):
        item["phase"] = "rollback"
        item["error"] = "事务中断：暂停/添加阶段未完成"
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
        if item["skipverify"] and skipverify_applies(service.type):
            # 跳过校验：qB 添加时已带 is_skip_checking，rt 不主动触发校验。
            logger.info(f"【PT下载中心】目标端跳过校验（{service.type}）"
                        f"{item['hash'][:8]}，不做校验等待")
            item["phase"] = "verifying"
        elif supports_recheck(service.type):
            if service.instance.recheck_torrents(ids=[item["hash"]]) is False:
                item["phase"] = "rollback"
                item["error"] = "目的端拒绝发起校验"
            else:
                logger.info(f"【PT下载中心】目标端发起校验（{service.type}）"
                            f"{item['hash'][:8]}，等待校验完成")
                item["phase"] = "verifying"
                # Persist accepted verification, never infer it from target_confirmed/skipverify.
                item["target_verification_started"] = True
        elif service.type == "rtorrent":
            # rt 无校验 API：启动目的端任务即触发 rtorrent 自动哈希校验。
            if service.instance.start_torrents(ids=[item["hash"]]) is False:
                return False
            logger.info(f"【PT下载中心】rt 目标端启动触发校验：{item['hash'][:8]}")
            item["phase"] = "verifying"
            item["target_verification_started"] = True
        else:
            item["phase"] = "verifying"
        save_transaction(plugin, item)
        # 不能用发起校验前读取的状态认定校验通过。
        return False
    # ── 判据一：目的端数据是否已到齐（与「自动开始」无关；源是唯一完整副本，没到齐就不动源）──
    # 完整度证据来源：qB 的状态后缀（UP=完整 / DL=未完整，含 progress）；TR 的 percent_done；
    # rt 的 d.complete。
    # 实测（2026-10-28，qB 5.x）：跳过校验**不会谎报字节数**——元数据声明 4MiB、磁盘只有 1MiB 时
    # 报 stalledDL / progress=0.25 / completed=1048576 / amount_left=3145728，即 progress 与
    # completed 都基于真实磁盘字节。故 qB 侧无需再自行比对元数据长度。
    # 例外：rt 跳过校验时 rt 不触发哈希校验，d.complete 恒为 0、不能当完整度证据；该组合的完整度
    # 改由「自动开始 + 回读活动状态」承担（见判据二与下面的零证据兜底）。
    rt_unchecked = bool(item["skipverify"] and service.type == "rtorrent")
    if not rt_unchecked and not seed_is_ready(state, service.type, task):
        # 「校验中/排队」是正常等待而非异常，按 info 记；只有真未完整才值得 warning。
        if seed_is_checking(state, service.type):
            logger.info(
                f"【PT下载中心:转移做种】目标端仍在校验/排队，等待 hash={item['hash'][:8]} "
                f"type={service.type} state={state}"
            )
        else:
            logger.warning(
                f"【PT下载中心:转移做种】目的端数据未确认完整，暂不删源 hash={item['hash'][:8]} "
                f"type={service.type} state={state}"
            )
        return False
    if phase != "target_ready":
        item["phase"] = "target_ready"
        save_transaction(plugin, item)
    if item["autostart"]:
        if stopped() or service.instance.start_torrents(ids=[item["hash"]]) is False:
            return False
        # 开始命令不是做种证据，下一轮回读目标活动状态才允许删源。
        if not _target_seeding(item, task, state, service):
            return False
    elif rt_unchecked and not seed_is_ready(state, service.type, task):
        # 跳过校验旁路的是「等待校验」，不是「完整度」：rt 若已自行报完整（d.complete 成立），
        # 上面的兜底不触发，按正常路径确认删源。
        # 兜底条件：rt 跳过校验（不触发校验 → d.complete 不成立）且未自动开始（活动状态证据
        # 不可用）。两个开关同开时没有任何可信的完整度来源，宁可不删源并说清怎么放行。
        logger.warning(
            f"【PT下载中心:转移做种】目的端数据未确认完整，暂不删源 hash={item['hash'][:8]} "
            f"type=rtorrent skipverify=True autostart=False（该组合无可信完整度证据："
            f"rt 跳过校验则不触发哈希校验，未自动开始则无法以活动状态为证据）；"
            f"放行办法：打开该任务的「自动开始」，或关闭「跳过校验」让 rt 启动触发校验"
        )
        return False
    item["target_confirmed"] = True
    # Count confirmed target once, independently of source deletion and its retries.
    with plugin._seed_recheck_lock:
        previous = plugin.get_data(f"{item['source_downloader']}-{item['source_hash']}") or {}
        counted = (previous.get("created_at") == item.get("created_at")
                   and previous.get("success_counted"))
        if not item.get("success_counted") and not counted:
            record_transfer_success(plugin, 1, fallback=bool(item.get("fallback")))
        item["success_counted"] = True
        save_transaction(plugin, item)
    from .service import post_transfer_process
    if stopped() or not post_transfer_process(plugin, service, item["hash"]):
        return False
    if item["delete_source_requested"]:
        if stopped():
            return False
        result = delete_source(
            plugin, item["source_downloader"], item["source_hash"],
            authorized=getattr(plugin, "_hr_enabled", False) is True,
            target_verified=bool(item.get("target_verification_started") and not item["skipverify"]),
            operation_id="transfer:{}:{}:{}".format(item["downloader"], item["hash"], item.get("created_at", 0)),
        )
        if result == "retry":
            item["delete_source_pending"] = True
            save_transaction(plugin, item)
            return False
        item["source_deleted"] = result == "deleted"
        item["hr_protected"] = result == "protected"
    item["delete_source_pending"] = bool(item["delete_source_requested"] and not item.get("source_deleted"))
    item["phase"] = "completed"
    save_source_record(plugin, item)
    return True


def _target_seeding(item, task, state, service):
    """目的端「在做种」的证据——只在自动开始时才需要（开始命令本身不是证据）。

    三种下载器的活动口径集中在这里，调用点不再内联分支：
    - qB：uploading / stalledUP / forcedUP（DL 后缀与暂停态都不算）
    - rt：没有 uploading/seeding 文本状态，用「活动 + 已完成」；跳过校验时 rt 不触发哈希
      校验、d.complete 不成立，此时只能以活动状态为证据（原式里的 skipverify_applies("rtorrent")
      恒为 True，已去）
    - TR：seeding
    """
    if service.type == "qbittorrent":
        return state in ("uploading", "stalledUP", "forcedUP")
    if service.type == "rtorrent":
        return is_torrent_active(task, "rtorrent") and (
            torrent_is_complete(task, "rtorrent") or bool(item["skipverify"])
        )
    return str(state) == "seeding"
