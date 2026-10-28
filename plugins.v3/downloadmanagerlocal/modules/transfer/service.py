"""转移做种服务实现。"""

import os
import time
from pathlib import Path
from typing import Any, Optional

from app.schemas import ServiceInfo
from app.schemas.types import MessageType
from app.sdk.config import settings
from app.sdk.logging import logger

from ...adapter.moviepilot import is_downloader_type
from ...utils.name_cleaner import is_dirty_renamed_torrent_name
from ...utils.torrent_adapter import get_label, get_save_path, get_torrent_name, get_tracker_urls
from .recheck import _queue_lock, load_seed_recheck_queue, ensure_seed_recheck_worker, seed_is_ready, seed_is_error
from .pipeline import begin_transfer, delete_source
from ..rename.service import _get_torrent_content_name, build_rename_config, resolve_retry_original_name
from ..sitetag.service import create_temporary_tag, forget_temporary_tag, release_temporary_tag
from .tasks import load_transfer_tasks, notify_fromtorrentpath_deprecated
from .payload_export import get_torrent_payloads

_AUTOMATIC_DELAY_TRIGGER_SOURCES = frozenset({"兜底扫描", "事件驱动"})


def _transfer_stopped(plugin, generation: int) -> bool:
    """识别停止信号与已失效批次，避免重新初始化清除旧批次的取消。"""
    event = getattr(plugin, "_event", None)
    return (
        int(getattr(plugin, "_transfer_stop_generation", 0) or 0) != generation
        or (event is not None and event.is_set())
    )


def _transfer_delay_status(
    plugin,
    torrent,
    dl_type: str,
    trigger_source: str,
    now_timestamp: Optional[float] = None,
) -> tuple[bool, Optional[float], int]:
    """判断自动转移是否仍需等待完成延迟，并返回年龄与延迟分钟数。"""
    try:
        delay_minutes = max(1, int(getattr(plugin, "_delay_minutes", 25) or 25))
    except (TypeError, ValueError):
        delay_minutes = 25

    if trigger_source not in _AUTOMATIC_DELAY_TRIGGER_SOURCES or dl_type != "qbittorrent":
        return False, None, delay_minutes

    try:
        completion_on = float(torrent.get("completion_on") or 0)
    except (AttributeError, TypeError, ValueError):
        return False, None, delay_minutes
    if completion_on <= 0:
        return False, None, delay_minutes

    current_timestamp = time.time() if now_timestamp is None else float(now_timestamp)
    age_minutes = (current_timestamp - completion_on) / 60
    return age_minutes < delay_minutes, age_minutes, delay_minutes


def validate_config(plugin) -> bool:
    """校验转移做种任务配置可用性。"""
    if not load_transfer_tasks(plugin):
        logger.warning("【PT下载中心:转移做种】尚未配置转移任务，请检查配置")
        return False
    return True

def download_torrent(plugin, service: ServiceInfo, content: bytes,
                     save_path: str, torrent, stop_generation: Optional[int] = None,
                     task: Optional[dict] = None, source_hash: str = "") -> Optional[str]:
    """添加目标任务前核对所属批次仍有效。"""
    generation = int(getattr(plugin, "_transfer_stop_generation", 0) or 0) if stop_generation is None else stop_generation
    if _transfer_stopped(plugin, generation):
        return None
    if not service or not service.instance:
        return None
    downloader = service.instance
    from_type = getattr(plugin.service_info((task or {}).get("from_downloader") or plugin._fromdownloader), "type", None)
    if is_downloader_type("qbittorrent", service=service):
        tag = create_temporary_tag(plugin)
        torrent_hash = None
        try:
            if bool((task or {}).get("keep_tag", plugin._remainoldtag)):
                torrent_labels = plugin.get_label(torrent, from_type)
                new_tag = list(set(torrent_labels + plugin._torrent_tags + [tag]))
            else:
                new_tag = plugin._torrent_tags + [tag]
            if bool((task or {}).get("keep_category", plugin._remainoldcat)):
                torrent_category = plugin.get_category(torrent, from_type)
            else:
                torrent_category = None
            if _transfer_stopped(plugin, generation):
                return None
            state = downloader.add_torrent(content=content,
                                           download_dir=save_path,
                                           is_paused=True,
                                           tag=new_tag,
                                           category=torrent_category,
                                           is_skip_checking=plugin._seed_skipverify)
            if not state:
                return None
            torrent_hash = downloader.get_torrent_id_by_tag(tags=tag)
            if not torrent_hash:
                logger.error(f"【PT下载中心:转移做种】{downloader} 下载任务添加成功，但获取任务信息失败！")
                return None
            return torrent_hash
        finally:
            if torrent_hash:
                release_temporary_tag(plugin, downloader, torrent_hash, tag, "转移做种")
            else:
                forget_temporary_tag(plugin, tag)
    elif is_downloader_type("transmission", service=service):
        if bool((task or {}).get("keep_tag", plugin._remainoldtag)):
            torrent_labels = plugin.get_label(torrent, from_type)
            new_tag = list(set(torrent_labels + plugin._torrent_tags))
        else:
            new_tag = plugin._torrent_tags
        if _transfer_stopped(plugin, generation):
            return None
        torrent = downloader.add_torrent(content=content,
                                         download_dir=save_path,
                                         is_paused=True,
                                         labels=new_tag)
        if not torrent:
            return None
        else:
            return torrent.hashString

    elif is_downloader_type("rtorrent", service=service):
        tag = create_temporary_tag(plugin)
        torrent_hash = None
        try:
            if bool((task or {}).get("keep_tag", plugin._remainoldtag)):
                torrent_labels = plugin.get_label(torrent, from_type)
                new_tag = list(set(torrent_labels + plugin._torrent_tags + [tag]))
            else:
                new_tag = plugin._torrent_tags + [tag]
            if _transfer_stopped(plugin, generation):
                return None
            # rt 无类别概念，仅写 d.custom1 标签；暂停添加后由管线完成校验与启动。
            if not downloader.add_torrent(content=content,
                                          download_dir=save_path,
                                          is_paused=True,
                                          tags=new_tag):
                logger.error(f"【PT下载中心:转移做种】{downloader} rTorrent 添加任务失败")
                return None
            # 该接口找到任务后会自行移除查询用的临时标签。
            torrent_hash = downloader.get_torrent_id_by_tag(tags=tag)
            if not torrent_hash:
                logger.error(f"【PT下载中心:转移做种】{downloader} 下载任务添加成功，但获取任务信息失败！")
                return None
            return torrent_hash
        finally:
            if torrent_hash:
                release_temporary_tag(plugin, downloader, torrent_hash, tag, "转移做种")
            else:
                forget_temporary_tag(plugin, tag)

    logger.error("【PT下载中心:转移做种】不支持的下载器类型")
    return None


def post_transfer_process(plugin, to_service: ServiceInfo, torrent_hash: str,
                          stop_generation: Optional[int] = None):
    """目标任务后处理逐步响应停止信号。"""
    generation = int(getattr(plugin, "_transfer_stop_generation", 0) or 0) if stop_generation is None else stop_generation
    if _transfer_stopped(plugin, generation):
        return False
    if not torrent_hash or not to_service or not to_service.instance:
        return False

    dl = to_service.instance
    dl_type = to_service.type

    try:
        torrents, error = dl.get_torrents(ids=[torrent_hash])
        if error or not torrents:
            logger.warning(f"【PT下载中心:转移做种】转移后处理：无法获取种子信息 hash={torrent_hash}")
            return False
        torrent = torrents[0]
        # 宿主下载器模块对 qB 返回 dict、对 TR/rt 在部分版本返回对象或 dict，
        # 统一走适配器读取，避免 `.name` 直接取属性在 dict 形态下抛 AttributeError。
        torrent_name = get_torrent_name(torrent)
        torrent_tags = get_label(torrent, dl_type)
        trackers = get_tracker_urls(torrent, dl_type)
        save_path = get_save_path(torrent, dl_type)
    except Exception as e:
        logger.error(f"【PT下载中心:转移做种】转移后处理：获取种子信息失败 hash={torrent_hash}: {e}")
        return False

    if not torrent_name:
        return False

    if _transfer_stopped(plugin, generation):
        return False
    if not getattr(plugin, "_transfer_rename_enabled", False):
        logger.info("【PT下载中心:转移做种】转移后重命名未启用（transfer_rename_enabled），跳过补刀")
    elif dl_type != "qbittorrent":
        logger.info(f"【PT下载中心:转移做种】目的端 {dl_type} 不适用转移后重命名（仅支持 qB 显示名改名），跳过补刀")
    elif plugin._rename_enabled:
        plugin._rename_torrent(dl, dl_type, torrent_hash, torrent_name, save_path)

    if _transfer_stopped(plugin, generation):
        return False
    if plugin._tag_enabled:
        tag_result = plugin._tag_torrent(dl, dl_type, torrent_hash, torrent_tags, trackers)
        if tag_result is False:
            logger.error(f"【PT下载中心:转移做种】站点标签写入失败 hash={torrent_hash}")
        elif tag_result is None:
            logger.warning(f"【PT下载中心:转移做种】站点未识别，跳过站点标签 hash={torrent_hash}")
    return True


def transfer(plugin, trigger_source: str = "手动/定时"):
    """事件、定时与续办共用队列锁，确保同一源任务单飞。"""
    with _queue_lock(plugin):
        return _transfer_impl(plugin, trigger_source)


def _transfer_impl(plugin, trigger_source: str):
    """转移做种多任务引擎：遍历全部启用任务执行。"""
    logger.info(f"【PT下载中心:转移做种】开始转移做种任务，触发来源：{trigger_source} ...")
    generation = int(getattr(plugin, "_transfer_stop_generation", 0) or 0)
    if _transfer_stopped(plugin, generation):
        return

    ensure_seed_recheck_worker(plugin)
    notify_fromtorrentpath_deprecated(plugin)

    tasks = load_transfer_tasks(plugin)
    if not tasks:
        logger.info("【PT下载中心:转移做种】没有启用的转移任务，跳过")
        return
    logger.info(f"【PT下载中心:转移做种】启用任务 {len(tasks)} 个：{[t['name'] for t in tasks]}")

    totals: dict = {"success": 0, "fail": 0, "skip": 0, "del_dup": 0, "notify": False}
    for task in tasks:
        if _transfer_stopped(plugin, generation):
            logger.info("【PT下载中心:转移做种】转移服务停止")
            break
        try:
            _run_task(plugin, task, trigger_source, generation, totals)
        except Exception as err:
            logger.error(f"【PT下载中心:转移做种】任务「{task['name']}」执行异常：{err}")
            totals["fail"] += 1

    if totals["notify"] and plugin._notify:
        stopped = _transfer_stopped(plugin, generation)
        plugin.post_message(
            mtype=MessageType.SiteMessage,
            title="【转移做种任务已停止】" if stopped else "【转移做种任务执行完成】",
            parse_mode="plain",
            text=(f"任务数：{len(tasks)}，已提交校验：{totals['success']}，"
                  f"失败：{totals['fail']}，跳过：{totals['skip']}，删除重复：{totals['del_dup']}")
        )
    if _transfer_stopped(plugin, generation):
        logger.info("【PT下载中心:转移做种】转移做种任务已停止，未继续执行重命名补刀")
        return
    logger.info("【PT下载中心:转移做种】转移做种任务执行完成")


def _run_task(plugin, task: dict, trigger_source: str, generation: int, totals: dict):
    """执行单个转移任务（筛选 → 批量网络导出 → 逐种子提交目的端）。"""
    task_name = task["name"]
    from_service = plugin.service_info(task["from_downloader"])
    to_service = plugin.service_info(task["to_downloader"])
    from_downloader: Optional[Any] = from_service.instance if from_service else None
    to_downloader: Optional[Any] = to_service.instance if to_service else None
    if not from_downloader or not to_downloader:
        logger.warning(f"【PT下载中心:转移做种】任务「{task_name}」源/目的下载器不可用，跳过")
        return

    torrents = from_downloader.get_completed_torrents()
    if torrents:
        logger.info(f"【PT下载中心:转移做种】任务「{task_name}」源 {from_service.name} 已做种的种子数：{len(torrents)}")
    else:
        logger.info(f"【PT下载中心:转移做种】任务「{task_name}」源 {from_service.name} 没有已做种的种子")
        return

    trans_torrents = []
    for torrent in torrents[:max(1, int(getattr(plugin, "_scan_limit", 500)))]:
        if _transfer_stopped(plugin, generation):
            logger.info("【PT下载中心:转移做种】转移服务停止")
            return

        hash_str = plugin.get_hash(torrent, from_service.type)
        save_path = plugin.get_save_path(torrent, from_service.type)

        should_wait, age_minutes, delay_minutes = _transfer_delay_status(
            plugin,
            torrent,
            from_service.type,
            trigger_source,
        )
        if should_wait:
            logger.info(
                f"【PT下载中心:转移做种】任务「{task_name}」种子 {hash_str} 完成仅 {age_minutes:.1f} 分钟，"
                f"不足延迟 {delay_minutes} 分钟，跳过"
            )
            continue

        if task["no_paths"]:
            nopath_skip = False
            for nopath in task["no_paths"].split('\n'):
                if save_path and os.path.normpath(save_path).startswith(os.path.normpath(nopath)):
                    logger.info(f"【PT下载中心:转移做种】任务「{task_name}」种子 {hash_str} 保存路径 {save_path} 不需要转移，跳过 ...")
                    nopath_skip = True
                    break
            if nopath_skip:
                continue

        torrent_labels = plugin.get_label(torrent, from_service.type)
        torrent_category = plugin.get_category(torrent, from_service.type)
        is_torrent_labels_empty = torrent_labels == [''] or torrent_labels == [] or torrent_labels is None
        if is_torrent_labels_empty:
            torrent_labels = []

        if task["include_category"]:
            if torrent_category not in task["include_category"].split(','):
                logger.info(f"【PT下载中心:转移做种】任务「{task_name}」种子 {hash_str} 不含有转移分类 {task['include_category']}，跳过 ...")
                continue
        if is_torrent_labels_empty:
            if not task["empty_label_ok"]:
                continue
        else:
            if task["exclude_labels"]:
                is_skip = False
                for label in task["exclude_labels"].split(','):
                    if label in torrent_labels:
                        logger.info(f"【PT下载中心:转移做种】任务「{task_name}」种子 {hash_str} 含有不转移标签 {label}，跳过 ...")
                        is_skip = True
                        break
                if is_skip:
                    continue
            if task["include_labels"]:
                is_skip = False
                for label in task["include_labels"].split(','):
                    if label not in torrent_labels:
                        logger.info(f"【PT下载中心:转移做种】任务「{task_name}」种子 {hash_str} 不含有转移标签 {label}，跳过 ...")
                        is_skip = True
                        break
                if is_skip:
                    continue

        trans_torrents.append({
            "hash": hash_str,
            "save_path": save_path,
            "torrent": torrent
        })

    if not trans_torrents:
        logger.info(f"【PT下载中心:转移做种】任务「{task_name}」没有需要转移的种子")
        return

    logger.info(f"【PT下载中心:转移做种】任务「{task_name}」需要转移的种子数：{len(trans_torrents)}")
    payloads = get_torrent_payloads(
        plugin, from_service.type, from_service.name, from_service,
        [item["hash"] for item in trans_torrents],
    )
    if not payloads:
        logger.warning(
            f"【PT下载中心:转移做种】任务「{task_name}」源端网络导出全部失败（type={from_service.type}）"
        )

    total = len(trans_torrents)
    success = 0
    fail = 0
    skip = 0
    del_dup = 0

    for torrent_item in trans_torrents:
        if _transfer_stopped(plugin, generation):
            break
        source_hash = torrent_item["hash"]
        content = payloads.get(source_hash)
        if not content:
            logger.warning(f"【PT下载中心:转移做种】任务「{task_name}」种子 {source_hash[:8]} 网络导出失败，跳过")
            fail += 1
            continue

        pending = load_seed_recheck_queue(plugin)
        if any(item.get("source_downloader") == from_service.name and
               item.get("source_hash") == source_hash and
               item.get("downloader") == to_service.name for item in pending.values()):
            logger.info(
                f"【PT下载中心:转移做种】任务「{task_name}」{source_hash[:8]} "
                f"已在发往 {to_service.name} 的待校验队列中，跳过"
            )
            skip += 1
            continue
        previous = plugin.get_data(f"{from_service.name}-{source_hash}") or {}

        torrent_info, poll_error = to_downloader.get_torrents(ids=[source_hash])
        if _transfer_stopped(plugin, generation):
            break
        if poll_error or torrent_info is None:
            logger.warning(f"【PT下载中心:转移做种】任务「{task_name}」目标任务查询失败，保留源任务：{source_hash[:8]}")
            fail += 1
            continue
        if torrent_info:
            # 历史记录只在目的下载器确实仍持有该任务时才算完成：目标被删后必须能重新转移。
            if previous.get("to_download") == to_service.name and previous.get("transfer_state") in ("completed", "stopped_after_add"):
                logger.info(f"【PT下载中心:转移做种】任务「{task_name}」{source_hash[:8]} 已转移过且目的仍在（{previous.get('transfer_state')}），跳过")
                skip += 1
                continue
            if task["delete_duplicate"]:
                target = torrent_info[0]
                state = target.get("state") if to_service.type == "qbittorrent" else target.status
                if not seed_is_ready(state, to_service.type, target) or seed_is_error(state, to_service.type) or (to_service.type == "transmission" and getattr(target, "error", 0)):
                    skip += 1
                    continue
                if _transfer_stopped(plugin, generation):
                    break
                logger.info(f"【PT下载中心:转移做种】任务「{task_name}」删除重复的源下载器任务（不含文件）：{source_hash[:8]} ...")
                result = delete_source(plugin, from_service.name, source_hash)
                if result == "retry":
                    fail += 1
                elif result == "protected":
                    skip += 1
                else:
                    del_dup += 1
            else:
                logger.info(f"【PT下载中心:转移做种】任务「{task_name}」{source_hash[:8]} 已在目的下载器中，跳过 ...")
                skip += 1
            continue

        download_dir = plugin.convert_save_path(torrent_item.get('save_path'),
                                                task["from_path"],
                                                task["to_path"])
        if not download_dir:
            logger.error(f"【PT下载中心:转移做种】任务「{task_name}」转换保存路径失败：{torrent_item.get('save_path')}")
            fail += 1
            continue

        if _transfer_stopped(plugin, generation):
            break
        logger.info(f"【PT下载中心:转移做种】任务「{task_name}」添加转移做种任务到下载器 {to_service.name}：{source_hash[:8]}")
        submitted = begin_transfer(
            plugin, from_service, to_service, source_hash, torrent_item["torrent"],
            add_target=lambda c=content, dd=download_dir, t=torrent_item["torrent"], h=source_hash: download_torrent(
                plugin, service=to_service, content=c,
                save_path=dd, torrent=t,
                stop_generation=generation,
                task=task, source_hash=h,
            ),
            stopped=lambda: _transfer_stopped(plugin, generation),
            fallback=trigger_source in _AUTOMATIC_DELAY_TRIGGER_SOURCES,
            delete_source=task.get("delete_source"),
        )
        if submitted:
            success += 1
        else:
            fail += 1

    totals["success"] += success
    totals["fail"] += fail
    totals["skip"] += skip
    totals["del_dup"] += del_dup
    if trans_torrents:
        totals["notify"] = True
    logger.info(
        f"【PT下载中心:转移做种】任务「{task_name}」本轮完成：总数 {total}，"
        f"已提交校验 {success}，失败 {fail}，跳过 {skip}，删除重复 {del_dup}"
    )

    if _transfer_stopped(plugin, generation):
        return
    if not getattr(plugin, "_transfer_rename_enabled", False):
        return
    if to_service.type != "qbittorrent":
        logger.info(
            f"【PT下载中心:转移做种】任务「{task_name}」目的端 {to_service.type} 不适用转移后重命名"
            "（仅支持 qB 显示名改名），跳过补刀"
        )
        return
    plugin._retry_failed_renames(to_service)

def _rename_retry_downloaders(plugin) -> list:
    """一键补刀的目标下载器与定时扫描保持一致：优先 rename_downloaders，旧单链路 todownloader 作回退。"""
    rename_config = build_rename_config(getattr(plugin, "_rename_config", None))
    downloaders = [
        str(item).strip() for item in (rename_config.get("downloader") or []) if str(item).strip()
    ]
    if not downloaders:
        legacy = str(getattr(plugin, "_todownloader", "") or "").strip()
        if legacy:
            downloaders = [legacy]
    return downloaders


def retry_pending_renames(plugin):
    """独立补刀重命名，避免转移扫描提前返回时跳过旧污染记录修复。"""
    downloaders = _rename_retry_downloaders(plugin)
    if not downloaders:
        return {"code": 1, "msg": "未配置目标下载器", "history": 0, "dirty": 0, "total": 0}
    try:
        history_count = 0
        dirty_count = 0
        attempted = 0
        failed = 0
        skipped = 0
        errors = []
        unavailable = []
        for downloader_name in downloaders:
            to_service = plugin.service_info(downloader_name)
            if not to_service or not to_service.instance:
                unavailable.append(str(downloader_name))
                logger.warning(
                    f"【PT下载中心:重命名】目标下载器不可用，跳过补刀：{downloader_name}"
                )
                continue
            history_result = plugin._retry_failed_renames(to_service) or {}
            dirty_result = retry_dirty_torrent_names(plugin, to_service) or {}
            history_count += int(history_result.get("success", 0) or 0)
            dirty_count += int(dirty_result.get("success", 0) or 0)
            attempted += int(history_result.get("attempted", 0) or 0) + int(dirty_result.get("attempted", 0) or 0)
            failed += int(history_result.get("failed", 0) or 0) + int(dirty_result.get("failed", 0) or 0)
            skipped += int(history_result.get("skipped", 0) or 0) + int(dirty_result.get("skipped", 0) or 0)
            errors += list(history_result.get("errors", []) or []) + list(dirty_result.get("errors", []) or [])
        if unavailable and len(unavailable) == len(downloaders):
            return {"code": 1, "msg": "目标下载器不可用，已跳过补刀", "history": 0, "dirty": 0, "total": 0}
        total = history_count + dirty_count
        code = 0 if failed == 0 else (2 if total > 0 else 1)
        return {
            "code": code,
            "msg": f"补刀完成：成功 {total} 个，失败 {failed} 个，跳过 {skipped} 个",
            "history": history_count,
            "dirty": dirty_count,
            "total": total,
            "attempted": attempted,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
        }
    except Exception as e:
        logger.error(f"【PT下载中心:转移做种】转移做种兜底服务：重命名补刀失败: {e}")
        return {"code": 1, "msg": f"补刀失败: {e}", "history": 0, "dirty": 0, "total": 0, "attempted": 0, "failed": 1, "skipped": 0, "errors": [str(e)]}


def retry_dirty_torrent_names(plugin, to_service: ServiceInfo):
    """扫描目标下载器当前任务名，补刀不在历史记录里的副标题污染任务。"""
    result = {"attempted": 0, "success": 0, "failed": 0, "skipped": 0, "errors": []}
    if not plugin._rename_enabled or not to_service or not to_service.instance:
        return result
    dl = to_service.instance
    dl_type = to_service.type
    try:
        torrents, _ = dl.get_torrents()
    except Exception as e:
        logger.error(f"【PT下载中心:转移做种】转移做种兜底服务：获取目标下载器任务失败: {e}")
        return result
    if not torrents:
        return result

    for torrent in torrents:
        torrent_name = get_torrent_name(torrent)
        if not is_dirty_renamed_torrent_name(torrent_name):
            continue
        torrent_hash = plugin.get_hash(torrent, dl_type)
        if not torrent_hash:
            logger.warning(f"【PT下载中心:转移做种】转移做种兜底服务：发现副标题污染任务但无 hash，跳过重命名 name={torrent_name}")
            continue
        is_archived = getattr(plugin, "is_rename_archived", None)
        if callable(is_archived) and is_archived(torrent_hash):
            result["skipped"] += 1
            continue
        result["attempted"] += 1
        save_path = plugin.get_save_path(torrent, dl_type)
        logger.info(f"【PT下载中心:转移做种】转移做种兜底服务：发现脏种子名，补刀处理 hash={torrent_hash} name={torrent_name}")
        try:
            retry_name = resolve_retry_original_name(
                plugin,
                torrent_hash,
                torrent_name,
                _get_torrent_content_name(torrent, dl_type),
            )
            if not retry_name:
                logger.warning(f"【PT下载中心:转移做种】转移做种兜底服务：原始发布名污染且无可信候选，跳过重命名 hash={torrent_hash}")
                record_failure = getattr(plugin, "record_rename_failure", None)
                if callable(record_failure):
                    record_failure(torrent_hash, torrent_name, "NO_TRUSTED_SOURCE", "原始发布名污染且无可信候选")
                result["failed"] += 1
                result["errors"].append(f"{torrent_hash}: 无可信原始名称")
                continue
            if plugin._rename_torrent(
                dl, dl_type, torrent_hash,
                retry_name,
                save_path
            ):
                result["success"] += 1
            else:
                result["failed"] += 1
                result["errors"].append(f"{torrent_hash}: 重命名失败")
        except Exception as e:
            logger.error(f"【PT下载中心:转移做种】转移做种兜底服务：脏种子名补刀失败 hash={torrent_hash} name={torrent_name}: {e}")
            result["failed"] += 1
            result["errors"].append(f"{torrent_hash}: {e}")
            record_failure = getattr(plugin, "record_rename_failure", None)
            if callable(record_failure):
                record_failure(torrent_hash, torrent_name, "RENAME_API_FAILED", str(e))
    if result["success"]:
        logger.info(f"【PT下载中心:转移做种】转移做种兜底服务：脏种子名补刀完成，成功 {result['success']} 个，失败 {result['failed']} 个")
    if result["skipped"]:
        logger.info(f"【PT下载中心:转移做种】转移做种兜底服务：跳过已归档补刀记录 {result['skipped']} 个")
    return result


def fallback_transfer(plugin):
    """转移做种兜底扫描包装函数"""
    retry_pending_renames(plugin)
    transfer(plugin, trigger_source="兜底扫描")


def delayed_transfer(plugin):
    """事件延迟转移执行入口"""
    transfer(plugin, trigger_source="事件驱动")


__all__ = (
    "delayed_transfer",
    "download_torrent",
    "fallback_transfer",
    "post_transfer_process",
    "retry_pending_renames",
    "transfer",
    "validate_config",
    "load_transfer_tasks",
    "notify_fromtorrentpath_deprecated",
)
