"""种子重命名服务实现。"""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.modules.filemanager.transhandler import TransHandler
from app.schemas.types import MediaType, MessageType
from app.sdk.logging import logger
from app.sdk.media import MetaBase, MetaInfo, resolve_media_identity
from bencode import bdecode

from ..adapter.moviepilot import get_download_history_by_hash
from ..model.state import RENAME_RECORDS_KEY
from ..service.archive import serialized_rename_state
from ..utils.name_cleaner import (
    clean_torrent_original_name,
    collect_retry_rename_hashes,
    is_polluted_original_name,
)
from ..utils.tag_cleanup import normalize_tags
from ..utils.torrent_adapter import get_hash, get_label, get_save_path, get_torrent_name, get_tracker_urls


def _tr_rename(dl, torrent_hash: str, torrent_name: str, new_name) -> None:
    """Transmission 重命名：rename_torrent_path 会联动顶层目录/文件名，与 qB torrents_rename 语义一致。

    服务端 torrent-rename-path 的 ids 只接受数字 id，需先按 hashString 换取。"""
    trc = getattr(dl, "trc", None)
    if not trc:
        raise RuntimeError("Transmission 客户端未就绪")
    torrents = trc.get_torrents(ids=torrent_hash)
    if not torrents:
        raise RuntimeError(f"Transmission 未找到种子 hash={torrent_hash}")
    trc.rename_torrent_path(torrents[0].id, str(torrent_name), str(new_name))


def _set_meta_attr(meta: MetaBase, attr: str, value: str) -> None:
    """安全设置媒体识别元数据对象的字符串字段。"""
    try:
        if hasattr(meta, attr):
            setattr(meta, attr, value)
    except Exception:
        pass


def _clean_meta_for_rename(meta: MetaBase) -> None:
    """清理元数据中会污染重命名结果的副标题字段。"""
    if not meta:
        return
    for attr in ("title", "org_string", "original_name"):
        value = getattr(meta, attr, None)
        if value:
            _set_meta_attr(meta, attr, clean_torrent_original_name(str(value)))
    for attr in ("subtitle", "description"):
        _set_meta_attr(meta, attr, "")


def _build_rename_meta(torrent_name: str, downloadhis=None) -> MetaInfo:
    """优先用当前种子原始名构造元数据，缺少季集时再补用下载历史。"""
    current_name = clean_torrent_original_name(torrent_name).strip()
    history_name = ""
    if downloadhis:
        history_torrent_name = getattr(downloadhis, "torrent_name", "")
        history_name = clean_torrent_original_name(history_torrent_name).strip()

    source_name = current_name or history_name or str(torrent_name or "").strip()
    meta = MetaInfo(title=source_name, subtitle="")
    if not downloadhis or getattr(downloadhis, "type", "") != MediaType.TV.value:
        return meta

    history_season = str(getattr(downloadhis, "seasons", "") or "").strip()
    history_episode = str(getattr(downloadhis, "episodes", "") or "").strip()
    if not history_season and not history_episode:
        return meta

    # 用历史字段构造一个仅含季集的补充元数据，避免改写当前种子的标题。
    history_meta = MetaInfo(title=f"{history_season}{history_episode}", subtitle="")
    for attr in (
        "begin_season",
        "end_season",
        "total_season",
        "begin_episode",
        "end_episode",
        "total_episode",
    ):
        if getattr(meta, attr, None) is None:
            value = getattr(history_meta, attr, None)
            if value is not None:
                setattr(meta, attr, value)
    return meta


def format_torrent_name(template_string: str, meta: MetaBase, mediainfo) -> Optional[str]:
    """根据 Jinja2 模板格式化种子名称"""
    _clean_meta_for_rename(meta)
    handler = TransHandler()
    rename_dict = handler.get_naming_dict(meta=meta, mediainfo=mediainfo)
    path = handler.get_rename_path(template_string, rename_dict)
    return path.as_posix() if path else None


@serialized_rename_state
def save_rename_record(plugin, torrent_hash: str, original_name: str, after_name: str,
                       success: bool, reason: str = ""):
    """保存重命名记录"""
    records = plugin.get_data(RENAME_RECORDS_KEY) or {}
    records[torrent_hash] = {
        "hash": torrent_hash,
        "original_name": original_name,
        "after_name": after_name,
        "success": success,
        "reason": reason,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    plugin.save_data(RENAME_RECORDS_KEY, records)
    if success:
        clear_state = getattr(plugin, "clear_rename_retry_state", None)
        if callable(clear_state):
            clear_state(torrent_hash)
    elif reason:
        record_failure = getattr(plugin, "record_rename_failure", None)
        if callable(record_failure):
            record_failure(torrent_hash, after_name or original_name, reason=reason)


def get_failed_rename_hashes(plugin) -> set:
    """获取所有需补刀的种子 hash：失败记录 + 已成功但 original_name 被副标题污染的记录"""
    records = plugin.get_data(RENAME_RECORDS_KEY) or {}
    retry_hashes = collect_retry_rename_hashes(records)
    is_archived = getattr(plugin, "is_rename_archived", None)
    if not callable(is_archived):
        return retry_hashes
    return {torrent_hash for torrent_hash in retry_hashes if not is_archived(torrent_hash)}


def _get_bencoded_value(mapping, key: str):
    """从 bencode 字典中兼容读取 str/bytes 两种键。"""
    if not isinstance(mapping, dict):
        return None
    if key in mapping:
        return mapping.get(key)
    return mapping.get(key.encode("utf-8"))


def _to_text(value) -> str:
    """将 bencode 字段值转换为可用于识别的文本。"""
    if value is None:
        return ""
    if isinstance(value, bytes):
        for encoding in ("utf-8", "gb18030"):
            try:
                return value.decode(encoding).strip()
            except UnicodeDecodeError:
                continue
        return value.decode("utf-8", errors="ignore").strip()
    return str(value).strip()


def _add_original_name_candidate(
    candidates: list,
    seen: set,
    value,
    source: str = "",
    base_score: int = 0,
) -> None:
    """添加去重后的原始名称候选，并保留污染与来源信息。"""
    raw = _to_text(value)
    candidate = clean_torrent_original_name(raw).strip()
    if candidate and candidate not in seen:
        candidates.append({
            "name": candidate,
            "raw": raw,
            "source": source,
            "base_score": base_score,
            "polluted": is_polluted_original_name(raw),
        })
        seen.add(candidate)


def _add_torrent_file_candidates(candidates: list, seen: set, plugin, torrent_hash: str) -> None:
    """从源 .torrent 文件中添加原始发布名候选。"""
    source_dir = str(getattr(plugin, "_fromtorrentpath", "") or "").strip()
    hash_text = str(torrent_hash or "").strip()
    if not source_dir or not hash_text:
        return
    torrent_file = Path(source_dir) / f"{hash_text}.torrent"
    if not torrent_file.exists():
        return
    try:
        torrent_data = bdecode(torrent_file.read_bytes())
        info = _get_bencoded_value(torrent_data, "info")
        _add_original_name_candidate(
            candidates, seen, _get_bencoded_value(info, "name"), "torrent_info", 12
        )

        files = _get_bencoded_value(info, "files") or []
        if isinstance(files, list):
            for file_info in files:
                path_parts = (
                    _get_bencoded_value(file_info, "path.utf-8")
                    or _get_bencoded_value(file_info, "path")
                )
                if isinstance(path_parts, list) and path_parts:
                    if len(path_parts) > 1:
                        _add_original_name_candidate(candidates, seen, path_parts[0], "torrent_folder", 18)
                    _add_original_name_candidate(
                        candidates, seen, Path(_to_text(path_parts[-1])).stem, "torrent_file", 8
                    )
                elif path_parts:
                    _add_original_name_candidate(
                        candidates, seen, Path(_to_text(path_parts)).stem, "torrent_file", 8
                    )
    except Exception as e:
        logger.warning(f"【PT下载中心:命名补刀】读取原始种子名失败 hash={hash_text} file={torrent_file}: {e}")


def _add_rename_record_candidates(candidates: list, seen: set, plugin, torrent_hash: str) -> None:
    """从重命名历史中添加原始名候选。"""
    try:
        records = plugin.get_data(RENAME_RECORDS_KEY) or {}
    except Exception:
        return
    record = records.get(str(torrent_hash or ""))
    if not isinstance(record, dict):
        return
    _add_original_name_candidate(candidates, seen, record.get("original_name"), "rename_record_original", 4)
    _add_original_name_candidate(candidates, seen, record.get("after_name"), "rename_record_after", 2)


def _add_download_history_candidates(candidates: list, seen: set, torrent_hash: str) -> None:
    """从下载历史中添加原始种子名候选。"""
    try:
        downloadhis = get_download_history_by_hash(torrent_hash)
    except Exception:
        return
    if not downloadhis:
        return
    _add_original_name_candidate(candidates, seen, downloadhis.torrent_name, "download_history", 6)


def _path_name_candidate(value) -> str:
    """从下载器内容路径中提取适合识别的文件夹名或文件名。"""
    text = _to_text(value).replace("\\", "/").strip().rstrip("/")
    if not text:
        return ""
    name = Path(text).name
    if Path(name).suffix.lower() in {".mkv", ".mp4", ".avi", ".ts", ".m2ts", ".torrent"}:
        return Path(name).stem
    return name


def _get_torrent_content_name(torrent, dl_type: str) -> str:
    """从下载器任务中提取内容根目录名。"""
    if dl_type == "qbittorrent":
        for key in ("content_path", "root_path"):
            candidate = _path_name_candidate(torrent.get(key))
            if candidate:
                return candidate
    candidate = _path_name_candidate(getattr(torrent, "download_dir", ""))
    if candidate and candidate != _to_text(getattr(torrent, "name", "")):
        return candidate
    return ""


def _build_original_name_candidate_items(
    plugin,
    torrent_hash: str,
    current_name: str = "",
    content_name: str = "",
) -> list:
    """收集补刀可用的原始发布名候选。"""
    candidates = []
    seen = set()
    _add_torrent_file_candidates(candidates, seen, plugin, torrent_hash)
    _add_download_history_candidates(candidates, seen, str(torrent_hash or ""))
    _add_rename_record_candidates(candidates, seen, plugin, torrent_hash)
    _add_original_name_candidate(candidates, seen, content_name, "content_path", 20)
    _add_original_name_candidate(candidates, seen, current_name, "current_torrent", 0)
    return candidates


def _get_original_torrent_name_candidates(plugin, torrent_hash: str) -> list:
    """读取源 .torrent 中可用于识别的原始名称候选。"""
    return [item["name"] for item in _build_original_name_candidate_items(plugin, torrent_hash)]


def _score_original_name_candidate(value) -> int:
    """根据发布名特征和污染特征给候选原始名称打分。"""
    if isinstance(value, dict):
        text = str(value.get("name") or "")
        raw = str(value.get("raw") or "")
        score = int(value.get("base_score") or 0)
        polluted = bool(value.get("polluted"))
    else:
        text = str(value or "")
        raw = text
        score = 0
        polluted = is_polluted_original_name(raw)
    upper = text.upper()
    release_tokens = (
        "S0", "S1", "S2", "S3", "2160P", "1080P", "720P", "WEB",
        "BLURAY", "H264", "H265", "HEVC", "AVC", "AAC",
    )
    has_release_marker = any(token in upper for token in release_tokens)
    if has_release_marker:
        score += 10
    candidate_polluted = is_polluted_original_name(text)
    if candidate_polluted:
        score -= 20
    elif polluted and not has_release_marker:
        score -= 12
    elif polluted:
        score -= 2
    score += min(len(text), 120) // 20
    return score


def _get_original_torrent_name(
    plugin,
    torrent_hash: str,
    current_name: str = "",
    content_name: str = "",
) -> str:
    """读取源 .torrent 中最适合用于识别的原始发布名。"""
    candidates = _build_original_name_candidate_items(plugin, torrent_hash, current_name, content_name)
    if not candidates:
        return ""
    best = max(candidates, key=_score_original_name_candidate)
    if _score_original_name_candidate(best) < 8:
        logger.warning(
            f"【PT下载中心:命名补刀】原始发布名候选置信度过低，跳过自动补刀 hash={torrent_hash} "
            f"candidate={best.get('name')}"
        )
        return ""
    return str(best.get("name") or "")


def resolve_retry_original_name(
    plugin,
    torrent_hash: str,
    current_name: str,
    content_name: str = "",
) -> str:
    """为补刀解析可信原始发布名，无法确认时返回空字符串。"""
    candidate = _get_original_torrent_name(plugin, torrent_hash, current_name, content_name)
    if candidate:
        return candidate
    if is_polluted_original_name(current_name):
        logger.warning(f"【PT下载中心:命名补刀】补刀跳过重命名：原始发布名污染且无可信候选 hash={torrent_hash} name={current_name}")
        return ""
    return clean_torrent_original_name(current_name).strip()



def rename_torrent(plugin, dl, dl_type: str, torrent_hash: str, torrent_name: str, save_path: str) -> bool:
    """重命名单个种子，持久化记录并返回实际是否成功。"""
    if dl_type == "rtorrent":
        # rt 客户端未提供可用的名称修改接口，跳过且不计入失败记录。
        logger.info(f"【PT下载中心:命名补刀】rTorrent 不支持重命名，跳过 hash={torrent_hash}")
        return False
    try:
        # 排除目录检查
        if plugin._rename_exclude_dirs:
            for d in plugin._rename_exclude_dirs.split("\n"):
                if d and d in str(save_path):
                    logger.info(f"【PT下载中心:命名补刀】命中排除目录 {d}，跳过 hash={torrent_hash}")
                    save_rename_record(plugin, torrent_hash, torrent_name, torrent_name, False, "命中排除目录")
                    return False

        # 历史只提供媒体身份，季集优先从当前种子原始名解析
        downloadhis = get_download_history_by_hash(torrent_hash)
        if downloadhis:
            logger.info(
                f"【PT下载中心:命名补刀】找到下载历史记录，使用当前种子名保留季集: "
                f"{clean_torrent_original_name(torrent_name).strip() or torrent_name}"
            )
            meta = _build_rename_meta(torrent_name, downloadhis)
            media_source, media_id = resolve_media_identity(
                media_source=getattr(downloadhis, "media_source", None),
                media_id=getattr(downloadhis, "media_id", None),
            )
            recognize_kwargs = {
                "meta": meta,
                "mtype": MediaType(downloadhis.type),
            }
            if media_source and media_id:
                recognize_kwargs.update(
                    media_source=media_source,
                    media_id=media_id,
                )
            media_info = plugin.chain.recognize_media(**recognize_kwargs)
            if media_info:
                template = plugin._rename_movie_format if media_info.type == MediaType.MOVIE else plugin._rename_tv_format
                new_name = format_torrent_name(template, meta, media_info)
                if new_name and str(new_name) != torrent_name:
                    if dl_type == "qbittorrent":
                        dl.qbc.torrents_rename(torrent_hash=torrent_hash, new_torrent_name=str(new_name))
                    elif dl_type == "transmission":
                        _tr_rename(dl, torrent_hash, torrent_name, new_name)
                    elif hasattr(dl, "rename_torrent"):
                        dl.rename_torrent(torrent_hash, str(new_name))
                    else:
                        logger.warning(
                            f"【PT下载中心:命名补刀】下载器类型不支持重命名，跳过(历史) hash={torrent_hash} type={type(dl).__name__}"
                        )
                        save_rename_record(plugin, torrent_hash, torrent_name, str(new_name), False, "下载器不支持重命名")
                        return False
                    logger.info(f"【PT下载中心:命名补刀】转移后重命名成功(历史): {torrent_name} → {new_name}")
                    save_rename_record(plugin, torrent_hash, torrent_name, str(new_name), True, "")
                    return True
                else:
                    logger.info("【PT下载中心:命名补刀】转移后重命名(历史): 名称未变化或格式化失败，回退到种子名解析")

        # 回退：解析种子名称
        cleaned_torrent_name = clean_torrent_original_name(torrent_name).strip()
        meta = MetaInfo(cleaned_torrent_name or torrent_name)
        if not meta or not meta.title:
            logger.warning(f"【PT下载中心:命名补刀】元数据获取失败 hash={torrent_hash} name={torrent_name}")
            save_rename_record(plugin, torrent_hash, torrent_name, torrent_name, False, "元数据获取失败")
            return False

        # TMDB 识别
        media_info = plugin.chain.recognize_media(meta=meta)
        if not media_info:
            logger.warning(f"【PT下载中心:命名补刀】媒体识别失败 hash={torrent_hash} name={torrent_name}")
            save_rename_record(plugin, torrent_hash, torrent_name, torrent_name, False, "媒体识别失败")
            return False

        # 选择模板
        template = plugin._rename_movie_format if media_info.type == MediaType.MOVIE else plugin._rename_tv_format
        new_name = format_torrent_name(template, meta, media_info)
        if not new_name:
            logger.warning(f"【PT下载中心:命名补刀】格式化结果为空 hash={torrent_hash}")
            save_rename_record(plugin, torrent_hash, torrent_name, torrent_name, False, "格式化结果为空")
            return False
        if str(new_name) == torrent_name:
            logger.info(f"【PT下载中心:命名补刀】名称未变化 hash={torrent_hash}")
            save_rename_record(plugin, torrent_hash, torrent_name, str(new_name), True, "名称未变化")
            return True

        # 执行重命名
        if dl_type == "qbittorrent":
            dl.qbc.torrents_rename(torrent_hash=torrent_hash, new_torrent_name=str(new_name))
        elif dl_type == "transmission":
            _tr_rename(dl, torrent_hash, torrent_name, new_name)
        elif hasattr(dl, "rename_torrent"):
            dl.rename_torrent(torrent_hash, str(new_name))
        else:
            logger.warning(
                f"【PT下载中心:命名补刀】下载器类型不支持重命名，跳过 hash={torrent_hash} type={type(dl).__name__}"
            )
            save_rename_record(plugin, torrent_hash, torrent_name, str(new_name), False, "下载器不支持重命名")
            return False
        logger.info(f"【PT下载中心:命名补刀】转移后重命名成功: {torrent_name} → {new_name}")
        save_rename_record(plugin, torrent_hash, torrent_name, str(new_name), True, "")
        return True
    except Exception as e:
        logger.error(f"【PT下载中心:命名补刀】转移后重命名失败 hash={torrent_hash}: {e}")
        save_rename_record(plugin, torrent_hash, torrent_name, torrent_name, False, str(e))
        return False


def retry_failed_renames(plugin, to_service):
    """对目标下载器中之前重命名失败的种子进行补刀并返回逐项统计。"""
    summary = _retry_summary()
    if not plugin._rename_enabled and not plugin._tag_enabled:
        return summary
    failed_hashes = get_failed_rename_hashes(plugin)
    if not failed_hashes:
        return summary

    if not to_service or not to_service.instance:
        summary["failed"] = len(failed_hashes)
        summary["errors"].append("目标下载器不可用")
        return summary

    dl = to_service.instance
    dl_type = to_service.type
    try:
        torrents, _ = dl.get_torrents(ids=list(failed_hashes))
        if not torrents:
            return summary
        for torrent in torrents:
            th = get_hash(torrent, dl_type)
            if th not in failed_hashes:
                continue
            is_archived = getattr(plugin, "is_rename_archived", None)
            if callable(is_archived) and is_archived(th):
                logger.info(f"【PT下载中心:命名补刀】补刀跳过归档记录 hash={th}")
                summary["skipped"] += 1
                continue
            summary["attempted"] += 1
            tn = get_torrent_name(torrent)
            sp = get_save_path(torrent, dl_type)
            tags = get_label(torrent, dl_type)
            trackers = get_tracker_urls(torrent, dl_type)
            logger.info(f"【PT下载中心:命名补刀】补刀处理: hash={th} name={tn}")
            item_success = True
            if plugin._rename_enabled:
                retry_name = resolve_retry_original_name(plugin, th, tn, _get_torrent_content_name(torrent, dl_type))
                if retry_name:
                    rename_success = bool(rename_torrent(plugin, dl, dl_type, th, retry_name, sp))
                else:
                    save_rename_record(plugin, th, tn, tn, False, "原始发布名污染，无法可靠补刀")
                    rename_success = False
                if not rename_success:
                    item_success = False
                    summary["errors"].append(f"{th}: 重命名失败")
            if plugin._tag_enabled:
                from .site_tag import tag_torrent
                tag_result = tag_torrent(plugin, dl, dl_type, th, tags, trackers)
                if tag_result is False:
                    item_success = False
                    summary["errors"].append(f"{th}: 站点标签失败")
                elif tag_result is None:
                    # 站点未识别属可接受情形：计入 warning，不拉低补刀成功率
                    summary["warnings"].append(f"{th}: 站点未识别，跳过站点标签")
            if item_success:
                summary["success"] += 1
            else:
                summary["failed"] += 1
        if summary["success"] > 0:
            logger.info(f"【PT下载中心:命名补刀】补刀完成，成功 {summary['success']} 个，失败 {summary['failed']} 个")
        return summary
    except Exception as e:
        logger.error(f"【PT下载中心:命名补刀】补刀失败: {e}")
        summary["errors"].append(str(e))
        return summary


def _retry_summary() -> dict:
    """构造批量补刀统计，成功数与失败数严格对应实际返回值。"""
    return {"attempted": 0, "success": 0, "failed": 0, "skipped": 0, "errors": [], "warnings": []}


def _get_torrent_name(torrent, dl_type):
    """按下载器类型读取当前种子名称。"""
    return get_torrent_name(torrent)


def _get_tracker_urls(torrent, dl_type):
    """按下载器类型提取有效 tracker URL 列表。"""
    return get_tracker_urls(torrent, dl_type)


def retry_rename_by_hash(plugin, to_service, torrent_hash: str):
    """对目标下载器中的单个种子执行补刀（重命名+站点标签）。"""
    hash_text = str(torrent_hash or "").strip()
    if not hash_text:
        return {"code": 1, "msg": "缺少 hash 参数", "hash": ""}
    if not plugin._rename_enabled and not plugin._tag_enabled:
        return {"code": 1, "msg": "重命名和站点标签均未启用，已跳过补刀", "hash": hash_text}
    if not to_service or not to_service.instance:
        record_failure = getattr(plugin, "record_rename_failure", None)
        if callable(record_failure):
            record_failure(hash_text, "", "DOWNLOADER_UNAVAILABLE", "目标下载器不可用")
        return {"code": 1, "msg": "目标下载器不可用，已跳过补刀", "hash": hash_text}

    dl = to_service.instance
    dl_type = to_service.type
    try:
        torrents, _ = dl.get_torrents(ids=[hash_text])
        if not torrents:
            record_failure = getattr(plugin, "record_rename_failure", None)
            if callable(record_failure):
                record_failure(hash_text, "", "TASK_NOT_FOUND", "未在目标下载器找到该种子")
            return {"code": 1, "msg": "未在目标下载器找到该种子", "hash": hash_text}

        for torrent in torrents:
            current_hash = get_hash(torrent, dl_type)
            if current_hash != hash_text:
                continue

            torrent_name = _get_torrent_name(torrent, dl_type)
            if not torrent_name:
                return {"code": 1, "msg": "种子名称为空，无法补刀", "hash": hash_text}

            save_path = get_save_path(torrent, dl_type)
            torrent_tags = get_label(torrent, dl_type)
            trackers = _get_tracker_urls(torrent, dl_type)
            logger.info(f"【PT下载中心:命名补刀】单条补刀处理: hash={hash_text} name={torrent_name}")

            rename_succeeded = True
            if plugin._rename_enabled:
                retry_name = resolve_retry_original_name(
                    plugin,
                    hash_text,
                    torrent_name,
                    _get_torrent_content_name(torrent, dl_type),
                )
                if not retry_name:
                    record_failure = getattr(plugin, "record_rename_failure", None)
                    if callable(record_failure):
                        record_failure(hash_text, torrent_name, "NO_TRUSTED_SOURCE", "原始发布名污染，无法可靠补刀")
                    return {"code": 1, "msg": "原始发布名污染，无法可靠补刀", "hash": hash_text}
                rename_succeeded = plugin._rename_torrent(
                        dl, dl_type, hash_text,
                        retry_name,
                        save_path
                    )
            if plugin._tag_enabled:
                plugin._tag_torrent(dl, dl_type, hash_text, torrent_tags, trackers)

            if not rename_succeeded:
                record = (plugin.get_data(RENAME_RECORDS_KEY) or {}).get(hash_text) or {}
                reason = record.get("reason") or "重命名未完成"
                return {"code": 1, "msg": f"补刀失败：{reason}", "hash": hash_text}

            clear_state = getattr(plugin, "clear_rename_retry_state", None)
            if callable(clear_state):
                clear_state(hash_text)
            return {"code": 0, "msg": "补刀完成", "hash": hash_text}

        record_failure = getattr(plugin, "record_rename_failure", None)
        if callable(record_failure):
            record_failure(hash_text, "", "TASK_NOT_FOUND", "未在目标下载器找到该种子")
        return {"code": 1, "msg": "未在目标下载器找到该种子", "hash": hash_text}
    except Exception as e:
        logger.error(f"【PT下载中心:命名补刀】单条补刀失败 hash={hash_text}: {e}")
        record_failure = getattr(plugin, "record_rename_failure", None)
        if callable(record_failure):
            record_failure(hash_text, "", "UNKNOWN_ERROR", str(e))
        return {"code": 1, "msg": f"补刀失败: {e}", "hash": hash_text}


# ── 重命名模块配置与来源过滤契约（来源 RenameTorrentVue）──
RENAME_TAG = "已重命名"

RENAME_FLAT_CONFIG_KEYS = {
    "enabled": "rename_enabled",
    "notify": "rename_notify",
    "cron_enabled": "rename_cron_enabled",
    "on_download_added": "rename_on_download_added",
    "downloader": "rename_downloaders",
    "exclude_dirs": "rename_exclude_dirs",
    "hash_white_list": "rename_hash_white_list",
    "exclude_tags": "rename_exclude_tags",
    "include_tags": "rename_include_tags",
    "cron": "rename_cron",
    "add_tag_after_rename": "rename_add_tag_after_rename",
    "movie_format_torrent_name": "rename_movie_format",
    "tv_format_torrent_name": "rename_tv_format",
    "event_debounce_seconds": "rename_event_debounce_seconds",
}

DEFAULT_RENAME_CONFIG = {
    "enabled": True,
    "notify": False,
    "cron_enabled": False,
    "on_download_added": True,
    "downloader": [],
    "exclude_dirs": "",
    "hash_white_list": "",
    "exclude_tags": "已重命名",
    "include_tags": "",
    "cron": "",
    "add_tag_after_rename": False,
    "movie_format_torrent_name": (
        "{{ title }}{% if year %} ({{ year }}){% endif %} - {{original_name}}"
    ),
    "tv_format_torrent_name": (
        "{{ title }}{% if year %} ({{ year }}){% endif %}"
        "{% if season_episode %} - {{season_episode}}{% endif %} - {{original_name}}"
    ),
    "event_debounce_seconds": 3,
}
"""重命名模块发布默认值，即来源 RenameTorrentVue.get_form 表单默认值；qnap 私有覆盖见 RENAME_QNAP_CONFIG，仅作行为证据。"""

RENAME_QNAP_CONFIG = {
    "rename_notify": True,
    "rename_cron_enabled": True,
    "rename_on_download_added": True,
    "rename_downloaders": ["QB1"],
    "rename_exclude_tags": "",
    "rename_exclude_dirs": "/share/Data6/bt/rss",
    "rename_add_tag_after_rename": True,
}
"""qnap 现役 RenameTorrentVue 配置中与表单默认不同的键（对应来源字段 notify/cron_enabled/event_enabled/downloader/exclude_tags/exclude_dirs/add_tag_after_rename）；仅作行为证据，不进入发布默认值。"""


def build_rename_flat_defaults() -> dict:
    """返回供宿主配置页合并的 rename_* 扁平默认值。"""
    return {
        flat_key: DEFAULT_RENAME_CONFIG[name]
        for name, flat_key in RENAME_FLAT_CONFIG_KEYS.items()
    }


def _safe_positive_int(value, default: int) -> int:
    """把防抖秒数收敛为不小于 1 的整数。"""
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return int(default)


def _clean_downloaders(value) -> list:
    """把下载器配置规范为去重后的名称列表。"""
    if isinstance(value, str):
        raw_items = re.split(r"[,\n]", value)
    elif isinstance(value, (list, tuple, set)):
        raw_items = list(value)
    else:
        raw_items = []
    result = []
    for item in raw_items:
        name = str(item or "").strip()
        if name and name not in result:
            result.append(name)
    return result


def build_rename_config(config=None) -> dict:
    """按来源 get_form 默认值构建重命名模块配置，兼容扁平 rename_* 键。"""
    source = config if isinstance(config, dict) else {}
    result = dict(DEFAULT_RENAME_CONFIG)
    for name, flat_key in RENAME_FLAT_CONFIG_KEYS.items():
        if flat_key in source:
            value = source.get(flat_key)
        elif name in source:
            value = source.get(name)
        else:
            continue
        if value is not None:
            result[name] = value
    result["downloader"] = _clean_downloaders(result.get("downloader"))
    result["event_debounce_seconds"] = _safe_positive_int(
        result.get("event_debounce_seconds"),
        DEFAULT_RENAME_CONFIG["event_debounce_seconds"],
    )
    return result


def _config_dirs(value) -> list:
    """按行拆分配置中的排除目录。"""
    return [line.strip() for line in str(value or "").splitlines() if line.strip()]


def _config_tags(value) -> list:
    """按逗号或换行拆分标签配置并去重。"""
    result = []
    for part in re.split(r"[,\n]", str(value or "")):
        tag = part.strip()
        if tag and tag not in result:
            result.append(tag)
    return result


def _config_hashes(value) -> set:
    """按逗号或空白拆分 hash 白名单并转为小写集合。"""
    return {
        token.strip().lower()
        for token in re.split(r"[,\s]+", str(value or ""))
        if token.strip()
    }


def passes_rename_filters(rename_config: dict, torrent_hash: str, torrent_tags,
                          save_path: str) -> tuple:
    """按来源顺序判断候选：目录排除→hash 白名单→排除标签→包含标签。"""
    for exclude_dir in _config_dirs(rename_config.get("exclude_dirs")):
        if exclude_dir in str(save_path or ""):
            return False, f"命中排除目录：{exclude_dir}"

    whitelist = _config_hashes(rename_config.get("hash_white_list"))
    if whitelist and str(torrent_hash or "").strip().lower() not in whitelist:
        return False, "不在 hash 白名单"

    current_tags = {str(tag).strip() for tag in (torrent_tags or []) if str(tag).strip()}
    excluded = current_tags & set(_config_tags(rename_config.get("exclude_tags")))
    if excluded:
        return False, f"命中排除标签：{'、'.join(sorted(excluded))}"

    include_tags = _config_tags(rename_config.get("include_tags"))
    if include_tags and not (current_tags & set(include_tags)):
        return False, "未命中包含标签"

    return True, ""


def _new_rename_bucket() -> dict:
    """新建一路触发来源的统计桶。"""
    return {"renamed": 0, "failed": 0, "skipped": 0}


def _new_rename_status() -> dict:
    """新建重命名模块的进程内状态结构。"""
    return {
        "renamed": 0,
        "failed": 0,
        "skipped": 0,
        "last_run": "",
        "event": _new_rename_bucket(),
        "cron": _new_rename_bucket(),
    }


def _rename_module_state(plugin) -> dict:
    """返回重命名模块的进程内统计，首次访问时初始化。"""
    state = getattr(plugin, "_rename_status", None)
    if not isinstance(state, dict):
        state = _new_rename_status()
        plugin._rename_status = state
    state.setdefault("renamed", 0)
    state.setdefault("failed", 0)
    state.setdefault("skipped", 0)
    state.setdefault("last_run", "")
    state.setdefault("event", _new_rename_bucket())
    state.setdefault("cron", _new_rename_bucket())
    return state


def record_rename_module_result(plugin, trigger: str, renamed: int, failed: int, skipped: int) -> None:
    """累计一次扫描或事件的重命名结果，按触发来源分别统计。"""
    state = _rename_module_state(plugin)
    state["renamed"] += renamed
    state["failed"] += failed
    state["skipped"] += skipped
    bucket = state["event"] if trigger == "event" else state["cron"]
    bucket["renamed"] += renamed
    bucket["failed"] += failed
    bucket["skipped"] += skipped
    state["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_module_status(plugin=None) -> dict:
    """返回最近重命名数、失败数及事件/定时各自统计。"""
    if plugin is None:
        return _new_rename_status()
    state = _rename_module_state(plugin)
    return {
        "renamed": int(state["renamed"]),
        "failed": int(state["failed"]),
        "skipped": int(state["skipped"]),
        "last_run": state.get("last_run", ""),
        "event": dict(state["event"]),
        "cron": dict(state["cron"]),
    }


def add_rename_tag(plugin, dl, dl_type: str, torrent_hash: str, torrent_tags,
                   rename_config: dict) -> bool:
    """成功后按配置补打“已重命名”标签，失败只记录而不重跑重命名。"""
    if not rename_config.get("add_tag_after_rename"):
        return False
    try:
        if dl_type == "qbittorrent":
            dl.set_torrents_tag(ids=torrent_hash, tags=[RENAME_TAG])
        else:
            merged = list(dict.fromkeys(normalize_tags(torrent_tags) + [RENAME_TAG]))
            dl.set_torrent_tag(ids=torrent_hash, tags=merged)
        return True
    except Exception as err:  # noqa: BLE001  # 下载器写入结果由其实现决定
        logger.warning(f"【PT下载中心:命名补刀】重命名后补打标签失败 hash={torrent_hash}: {err}")
        return False


def notify_rename_result(plugin, trigger: str, rename_config: dict, result: dict) -> bool:
    """按配置发送一次重命名结果通知。"""
    if not rename_config.get("notify"):
        return False
    renamed = int(result.get("renamed", 0) or 0)
    failed = int(result.get("failed", 0) or 0)
    if not renamed and not failed:
        return False
    try:
        plugin.post_message(
            mtype=MessageType.SiteMessage,
            title="【下载中心重命名结果】",
            parse_mode="plain",
            text=(
                f"触发：{trigger}\n"
                f"重命名成功：{renamed}，失败：{failed}，"
                f"跳过：{int(result.get('skipped', 0) or 0)}"
            ),
        )
        return True
    except Exception as err:  # noqa: BLE001  # 通知发送由宿主实现决定
        logger.warning(f"【PT下载中心:命名补刀】重命名结果通知发送失败：{err}")
        return False


def rename_candidate(plugin, service, rename_config: dict, torrent) -> str:
    """对单个候选种子执行过滤与重命名，返回 renamed / failed / skipped。"""
    dl = service.instance
    dl_type = service.type
    if dl_type == "rtorrent":
        # rt 不支持改名：按 skipped 计，不进入失败统计。
        return "skipped"
    torrent_hash = get_hash(torrent, dl_type)
    if not torrent_hash:
        return "skipped"
    torrent_name = _get_torrent_name(torrent, dl_type)
    save_path = get_save_path(torrent, dl_type)
    torrent_tags = get_label(torrent, dl_type)
    allowed, reason = passes_rename_filters(rename_config, torrent_hash, torrent_tags, save_path)
    if not allowed:
        logger.info(f"【PT下载中心:命名补刀】重命名跳过 hash={torrent_hash}：{reason}")
        return "skipped"
    if rename_torrent(plugin, dl, dl_type, torrent_hash, torrent_name, save_path):
        add_rename_tag(plugin, dl, dl_type, torrent_hash, torrent_tags, rename_config)
        return "renamed"
    return "failed"


def _get_renamed_hashes(plugin) -> set:
    """读取已成功重命名的 hash 集合，用于跳过已处理种子。"""
    records = plugin.get_data(RENAME_RECORDS_KEY) or {}
    if not isinstance(records, dict):
        return set()
    return {
        str(torrent_hash)
        for torrent_hash, record in records.items()
        if isinstance(record, dict) and record.get("success")
    }


def scan_renames(plugin) -> dict:
    """周期扫描来源下载器，按模板重命名尚未处理的种子。"""
    rename_config = build_rename_config(getattr(plugin, "_rename_config", None))
    result = {"renamed": 0, "failed": 0, "skipped": 0, "downloaders": {}}
    if not rename_config["enabled"]:
        return result

    processed = _get_renamed_hashes(plugin)
    # 失败项重试开关（rename_retry）已移除：定时扫描沿用发布默认语义——不重试失败项，
    # 重试走数据页「一键补刀」（POST /retry_renames）。
    pending = get_failed_rename_hashes(plugin)
    is_archived = getattr(plugin, "is_rename_archived", None)

    for downloader_name in rename_config["downloader"]:
        service = plugin.service_info(downloader_name)
        if not service or not getattr(service, "instance", None):
            logger.warning(f"【PT下载中心:命名补刀】重命名跳过：下载器不可用 {downloader_name}")
            result["downloaders"][downloader_name] = {
                "renamed": 0, "failed": 0, "skipped": 0, "reason": "downloader_unavailable",
            }
            result["skipped"] += 1
            continue
        torrents, error = service.instance.get_torrents()
        if error:
            logger.warning(f"【PT下载中心:命名补刀】重命名跳过：读取任务失败 {downloader_name}: {error}")
            result["downloaders"][downloader_name] = {
                "renamed": 0, "failed": 0, "skipped": 0, "reason": str(error),
            }
            continue
        bucket = {"renamed": 0, "failed": 0, "skipped": 0}
        for torrent in torrents or []:
            torrent_hash = get_hash(torrent, service.type)
            if not torrent_hash:
                continue
            if torrent_hash in processed or torrent_hash in pending:
                bucket["skipped"] += 1
                continue
            if callable(is_archived) and is_archived(torrent_hash):
                bucket["skipped"] += 1
                continue
            bucket[rename_candidate(plugin, service, rename_config, torrent)] += 1
        result["downloaders"][downloader_name] = bucket
        result["renamed"] += bucket["renamed"]
        result["failed"] += bucket["failed"]
        result["skipped"] += bucket["skipped"]

    record_rename_module_result(plugin, "cron", result["renamed"], result["failed"], result["skipped"])
    notify_rename_result(plugin, "定时重命名", rename_config, result)
    return result


__all__ = (
    "DEFAULT_RENAME_CONFIG",
    "RENAME_FLAT_CONFIG_KEYS",
    "RENAME_QNAP_CONFIG",
    "RENAME_TAG",
    "add_rename_tag",
    "build_rename_config",
    "build_rename_flat_defaults",
    "format_torrent_name",
    "get_failed_rename_hashes",
    "get_module_status",
    "notify_rename_result",
    "passes_rename_filters",
    "record_rename_module_result",
    "rename_candidate",
    "rename_torrent",
    "retry_failed_renames",
    "retry_rename_by_hash",
    "save_rename_record",
    "scan_renames",
)
