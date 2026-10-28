"""站点标签写入、临时标签回收与人工清理服务。"""

from typing import Dict, Iterable, List, Optional

from app.sdk.config import settings
from app.sdk.logging import logger

from ...adapter.moviepilot import generate_random_tag, get_site_indexer, get_url_domain, list_site_dicts
from ...utils.tag_cleanup import (
    TEMP_TAG_PREFIX,
    classify_tag,
    is_auto_removable,
    normalize_tags,
)
from ...utils.torrent_adapter import get_hash, get_label, get_torrent_name


def _active_temporary_tags(plugin) -> set:
    """返回当前进程仍用于确认任务的临时标签集合。"""
    active_tags = getattr(plugin, "_active_temporary_tags", None)
    if not isinstance(active_tags, set):
        active_tags = set()
        plugin._active_temporary_tags = active_tags
    return active_tags


def create_temporary_tag(plugin, length: int = 10) -> str:
    """生成带下载中心归属前缀的临时标签并登记为活动状态。"""
    tag = f"{TEMP_TAG_PREFIX}{generate_random_tag(length)}"
    _active_temporary_tags(plugin).add(tag)
    return tag


def forget_temporary_tag(plugin, tag: str) -> None:
    """结束临时标签的活动状态，不修改下载器标签。"""
    _active_temporary_tags(plugin).discard(str(tag or ""))


def release_temporary_tag(plugin, dl, torrent_hash: str, tag: str, source: str) -> bool:
    """从已确认的 qBittorrent 任务移除临时标签并删除空标签定义。"""
    success = False
    try:
        if not torrent_hash or not tag:
            return False
        success = bool(dl.remove_torrents_tag(ids=torrent_hash, tag=tag))
        if success:
            dl.delete_torrents_tag(ids=torrent_hash, tag=tag)
        else:
            logger.warning(f"【PT下载中心:站点标签】{source}：临时标签回收失败 hash={torrent_hash} tag={tag}")
        return success
    except Exception as err:
        logger.warning(f"【PT下载中心:站点标签】{source}：临时标签回收异常 hash={torrent_hash} tag={tag}: {err}")
        return False
    finally:
        forget_temporary_tag(plugin, tag)


def cleanup_temporary_tags_for_event(plugin, event) -> dict:
    """按下载新增事件清理来源或目标下载器当前任务上的新临时标签。"""
    event_data = getattr(event, "event_data", None)
    if not isinstance(event_data, dict):
        return {"handled": False, "reason": "invalid_event"}

    downloader_name = str(
        event_data.get("downloader")
        or event_data.get("downloader_name")
        or ""
    ).strip()
    selected_downloaders = normalize_tags((
        getattr(plugin, "_fromdownloader", ""),
        getattr(plugin, "_todownloader", ""),
    ))
    if not downloader_name or downloader_name not in selected_downloaders:
        return {
            "handled": False,
            "downloader": downloader_name,
            "reason": "downloader_not_selected",
        }

    torrent_hash = str(
        event_data.get("hash")
        or event_data.get("torrent_hash")
        or event_data.get("download_hash")
        or ""
    ).strip()
    if not torrent_hash:
        return {"handled": False, "downloader": downloader_name, "reason": "hash_missing"}

    service = plugin.service_info(downloader_name)
    if not service or str(getattr(service, "type", "")).lower() != "qbittorrent":
        return {
            "handled": False,
            "downloader": downloader_name,
            "hash": torrent_hash,
            "reason": "unsupported_downloader",
        }

    try:
        response = service.instance.get_torrents(ids=[torrent_hash])
        if isinstance(response, tuple) and len(response) == 2:
            torrents, error = response
        else:
            torrents, error = response, None
    except Exception as err:
        logger.warning(f"【PT下载中心:站点标签】下载新增事件：读取任务失败 downloader={downloader_name} hash={torrent_hash}: {err}")
        return {
            "handled": True,
            "downloader": downloader_name,
            "hash": torrent_hash,
            "reason": "torrent_read_failed",
        }

    if error or not torrents:
        return {
            "handled": True,
            "downloader": downloader_name,
            "hash": torrent_hash,
            "reason": "torrent_not_found" if not error else "torrent_read_failed",
        }

    torrent = next(
        (
            item for item in torrents
            if str(get_hash(item, "qbittorrent") or "").lower() == torrent_hash.lower()
        ),
        torrents[0],
    )
    current_hash = get_hash(torrent, "qbittorrent") or torrent_hash
    current_tags = normalize_tags(get_label(torrent, "qbittorrent"))
    if not current_tags:
        return {
            "handled": True,
            "downloader": downloader_name,
            "hash": current_hash,
            "removed": [],
            "reason": "no_tags",
        }

    managed_tags = _managed_tag_anchors(plugin)
    active_tags = _active_temporary_tags(plugin)
    event_tags_by_hash = {current_hash: current_tags}
    grouped_tags = None
    grouped_tags_by_hash = event_tags_by_hash
    removed = []
    failed = []
    for tag in sorted(current_tags, key=str.casefold):
        kind = classify_tag(
            tag=tag,
            hashes=[current_hash],
            torrent_tags_by_hash=event_tags_by_hash,
            managed_tags=managed_tags,
            active_tags=active_tags,
            site_prefix=str(getattr(plugin, "_tag_siteprefix", "") or ""),
        )

        # 旧式随机标签必须先确认不是多个任务共用的普通标签。
        if kind in {"legacy_temporary", "legacy_candidate"} and grouped_tags is None:
            all_torrents, all_error = _read_qb_torrents(service)
            if all_error:
                failed.append({"tag": tag, "kind": kind, "reason": all_error})
                grouped_tags = {}
                grouped_tags_by_hash = {}
                continue
            grouped_tags, grouped_tags_by_hash = _group_tags(all_torrents)

        if grouped_tags is not None and kind in {"legacy_temporary", "legacy_candidate"}:
            snapshot = grouped_tags.get(tag, {})
            kind = classify_tag(
                tag=tag,
                hashes=snapshot.get("hashes", []),
                torrent_tags_by_hash=grouped_tags_by_hash,
                managed_tags=managed_tags,
                active_tags=active_tags,
                site_prefix=str(getattr(plugin, "_tag_siteprefix", "") or ""),
            )

        if not is_auto_removable(kind):
            continue

        if release_temporary_tag(plugin, service.instance, current_hash, tag, "下载新增事件"):
            removed.append(tag)
        else:
            failed.append({"tag": tag, "kind": kind})

    if removed:
        logger.info(
            "【PT下载中心:站点标签】下载新增事件：自动移除临时标签 downloader=%s hash=%s tags=%s",
            downloader_name,
            current_hash,
            ",".join(removed),
        )
    return {
        "handled": True,
        "downloader": downloader_name,
        "hash": current_hash,
        "removed": removed,
        "failed": failed,
    }


def _managed_tag_anchors(plugin) -> set:
    """返回可证明旧随机标签来自下载中心的业务锚点标签。"""
    managed = normalize_tags(getattr(plugin, "_torrent_tags", []) or [])
    managed.update(normalize_tags(getattr(settings, "TORRENT_TAG", "") or ""))
    return managed


def _read_qb_torrents(service) -> tuple:
    """读取 qBittorrent 全量任务并统一错误结果。"""
    torrents, error = service.instance.get_torrents()
    if error:
        return [], "下载器任务读取失败"
    return torrents or [], ""


def _group_tags(torrents: Iterable[dict]) -> tuple:
    """按标签聚合任务 hash、计数和名称样本。"""
    grouped: Dict[str, dict] = {}
    torrent_tags_by_hash: Dict[str, set] = {}
    for torrent in torrents or []:
        torrent_hash = get_hash(torrent, "qbittorrent")
        if not torrent_hash:
            continue
        tags = normalize_tags(get_label(torrent, "qbittorrent"))
        torrent_tags_by_hash[torrent_hash] = tags
        torrent_name = get_torrent_name(torrent) or torrent_hash
        for tag in tags:
            item = grouped.setdefault(tag, {"hashes": [], "samples": []})
            item["hashes"].append(torrent_hash)
            if torrent_name not in item["samples"] and len(item["samples"]) < 3:
                item["samples"].append(torrent_name)
    return grouped, torrent_tags_by_hash


def _delete_empty_tag_definition(dl, tag: str, known_hashes: List[str]) -> bool:
    """仅在复查确认标签无人使用后删除 qBittorrent 全局标签定义。"""
    torrents, error = dl.get_torrents()
    if error:
        return False
    still_used = any(tag in normalize_tags(get_label(torrent, "qbittorrent")) for torrent in torrents or [])
    if still_used:
        return False
    return bool(dl.delete_torrents_tag(ids=known_hashes, tag=tag))


def _remove_tag_snapshot(dl, tag: str, hashes: Iterable[str]) -> dict:
    """只从扫描快照中的任务移除标签，并按需清除空标签定义。"""
    unique_hashes = sorted(normalize_tags(hashes))
    if not tag or not unique_hashes:
        return {"ok": False, "removed": 0, "definition_deleted": False}
    try:
        ok = bool(dl.remove_torrents_tag(ids=unique_hashes, tag=tag))
        definition_deleted = _delete_empty_tag_definition(dl, tag, unique_hashes) if ok else False
        return {
            "ok": ok,
            "removed": len(unique_hashes) if ok else 0,
            "definition_deleted": definition_deleted,
        }
    except Exception as err:
        logger.warning(f"【PT下载中心:站点标签】标签清理失败 tag={tag} count={len(unique_hashes)}: {err}")
        return {"ok": False, "removed": 0, "definition_deleted": False, "error": str(err)}


def scan_and_clean_tags(plugin, downloader_names: Iterable[str]) -> dict:
    """扫描所选下载器，自动移除明确的临时标签并返回其余标签快照。"""
    names = list(dict.fromkeys(normalize_tags(downloader_names)))
    if not names:
        return {"code": 1, "msg": "请至少选择一个下载器", "downloaders": [], "auto_removed": []}

    active_tags = set(_active_temporary_tags(plugin))
    managed_tags = _managed_tag_anchors(plugin)
    site_prefix = str(getattr(plugin, "_tag_siteprefix", "") or "")
    downloader_results = []
    auto_removed = []
    errors = []

    for downloader_name in names:
        service = plugin.service_info(downloader_name)
        if not service:
            errors.append({"downloader": downloader_name, "message": "下载器不可用"})
            continue
        if service.type != "qbittorrent":
            errors.append({"downloader": downloader_name, "message": "仅支持 qBittorrent 标签清理"})
            continue

        torrents, error_message = _read_qb_torrents(service)
        if error_message:
            errors.append({"downloader": downloader_name, "message": error_message})
            continue

        grouped, torrent_tags_by_hash = _group_tags(torrents)
        remaining = []
        for tag in sorted(grouped, key=str.casefold):
            snapshot = grouped[tag]
            kind = classify_tag(
                tag=tag,
                hashes=snapshot["hashes"],
                torrent_tags_by_hash=torrent_tags_by_hash,
                managed_tags=managed_tags,
                active_tags=active_tags,
                site_prefix=site_prefix,
            )
            item = {
                "tag": tag,
                "kind": kind,
                "count": len(set(snapshot["hashes"])),
                "hashes": sorted(set(snapshot["hashes"])),
                "samples": snapshot["samples"],
            }
            if is_auto_removable(kind):
                cleanup = _remove_tag_snapshot(service.instance, tag, item["hashes"])
                if cleanup["ok"]:
                    auto_removed.append({"downloader": downloader_name, **item, **cleanup})
                    continue
                item["cleanup_error"] = cleanup.get("error") or "自动清理失败"
            remaining.append(item)

        downloader_results.append({
            "name": downloader_name,
            "type": service.type,
            "task_count": len(torrents),
            "tags": remaining,
        })

    if auto_removed:
        logger.info(
            "【PT下载中心:站点标签】标签清理扫描：自动移除临时标签 %s 个，任务关联 %s 条",
            len(auto_removed),
            sum(item["removed"] for item in auto_removed),
        )
    code = 0 if downloader_results else 1
    return {
        "code": code,
        "msg": "扫描完成" if code == 0 else "未能扫描所选下载器",
        "downloaders": downloader_results,
        "auto_removed": auto_removed,
        "errors": errors,
    }


def execute_tag_cleanup(plugin, removals: Iterable[dict]) -> dict:
    """按前端确认的标签与任务 hash 快照执行人工清理。"""
    removal_items = [item for item in removals or [] if isinstance(item, dict)]
    if not removal_items:
        return {"code": 1, "msg": "没有需要清理的标签", "removed": [], "failed": []}

    active_tags = set(_active_temporary_tags(plugin))
    removed = []
    failed = []
    service_cache = {}
    for item in removal_items[:1000]:
        downloader_name = str(item.get("downloader") or "").strip()
        tag = str(item.get("tag") or "").strip()
        requested_hashes = sorted(normalize_tags(item.get("hashes") or []))[:5000]
        if not downloader_name or not tag or not requested_hashes:
            failed.append({"downloader": downloader_name, "tag": tag, "message": "清理参数不完整"})
            continue
        if tag in active_tags:
            failed.append({"downloader": downloader_name, "tag": tag, "message": "临时标签仍在使用"})
            continue

        service = service_cache.get(downloader_name)
        if service is None:
            service = plugin.service_info(downloader_name)
            service_cache[downloader_name] = service
        if not service or service.type != "qbittorrent":
            failed.append({"downloader": downloader_name, "tag": tag, "message": "下载器不可用或类型不支持"})
            continue

        torrents, error = service.instance.get_torrents(ids=requested_hashes)
        if error:
            failed.append({"downloader": downloader_name, "tag": tag, "message": "任务快照复核失败"})
            continue
        current_hashes = [
            get_hash(torrent, "qbittorrent")
            for torrent in torrents or []
            if tag in normalize_tags(get_label(torrent, "qbittorrent"))
        ]
        cleanup = _remove_tag_snapshot(service.instance, tag, current_hashes)
        result = {"downloader": downloader_name, "tag": tag, "hashes": current_hashes, **cleanup}
        if cleanup["ok"]:
            removed.append(result)
        else:
            result["message"] = cleanup.get("error") or "标签移除失败"
            failed.append(result)

    logger.info(
        "【PT下载中心:站点标签】标签清理执行：成功标签 %s 个，任务关联 %s 条，失败 %s 个",
        len(removed),
        sum(item["removed"] for item in removed),
        len(failed),
    )
    return {
        "code": 0 if removed and not failed else (2 if removed else 1),
        "msg": f"已清理 {len(removed)} 个标签，失败 {len(failed)} 个",
        "removed": removed,
        "failed": failed,
    }


def find_site_by_domain(domain: str) -> Optional[str]:
    """通过域名从 V3 站点数据库查找名称，索引模板作为回退。"""
    try:
        for site_info in list_site_dicts():
            site_domain = site_info.get("domain") or site_info.get("url") or ""
            site_domain_clean = get_url_domain(site_domain)
            if site_domain_clean and site_domain_clean == get_url_domain(domain):
                return site_info.get("name")
    except Exception:
        pass

    try:
        site_info = get_site_indexer(domain)
        if site_info:
            return site_info.get("name")
    except Exception:
        pass

    return None


def tag_torrent(plugin, dl, dl_type: str, torrent_hash: str, torrent_tags: list, trackers: list):
    """给种子打站点标签，返回三态：True 已打标/已存在，None 站点未识别（跳过，非失败），False 写入失败。"""
    try:
        # 通过 tracker 解析站点
        site_name = None
        for tracker in trackers:
            domain = None
            for key, mapped in plugin._tracker_mappings.items():
                if key in tracker:
                    domain = mapped
                    break
            if not domain:
                domain = get_url_domain(tracker)
            if not domain:
                continue
            # 从系统配置中查找匹配的站点
            custom_labels = getattr(plugin, "_custom_site_labels", None) or {}
            site_name = find_site_by_domain(domain) or custom_labels.get((domain or "").lower())
            if site_name:
                break

        if not site_name:
            logger.warning(f"【PT下载中心:站点标签】转移后标签：无法识别站点，跳过打标 hash={torrent_hash}")
            return None

        # 构造标签
        site_tag = (plugin._tag_siteprefix + site_name) if plugin._tag_siteprefix else site_name
        if site_tag in torrent_tags:
            logger.info(f"【PT下载中心:站点标签】转移后标签：标签已存在 hash={torrent_hash}")
            return True

        # 设置标签
        if dl_type == "qbittorrent":
            dl.set_torrents_tag(ids=torrent_hash, tags=[site_tag])
        else:
            dl.set_torrent_tag(ids=torrent_hash, tags=[site_tag])
        logger.info(f"【PT下载中心:站点标签】转移后标签成功: hash={torrent_hash} tag={site_tag}")
        return True
    except Exception as e:
        logger.error(f"【PT下载中心:站点标签】转移后标签失败 hash={torrent_hash}: {e}")
        return False


__all__ = (
    "cleanup_temporary_tags_for_event",
    "create_temporary_tag",
    "execute_tag_cleanup",
    "find_site_by_domain",
    "forget_temporary_tag",
    "release_temporary_tag",
    "scan_and_clean_tags",
    "tag_torrent",
    "DEFAULT_ALL_CAT",
    "DEFAULT_ALL_CAT_RENAME",
    "DEFAULT_TAG_CONFIG",
    "build_tag_config",
    "complement_history",
    "get_module_status",
    "parse_tracker_mappings",
    "parse_custom_site_labels",
    "process_download_added",
)

# DownloadSiteTagModNew-derived configuration and metadata completion.
DEFAULT_ALL_CAT = [
    "国漫", "日番", "纪录片", "综艺", "国产剧", "欧美剧", "日韩剧",
    "未分类", "动画电影", "华语电影", "现场", "外语电影",
]
DEFAULT_ALL_CAT_RENAME = [
    "动漫", "动漫", "纪录片", "综艺", "电视剧", "电视剧", "电视剧",
    "未分类", "电影", "电影", "现场", "电影",
]
DEFAULT_TRACKER_MAPPINGS = "\n".join((
    "chdbits.xyz -> ptchdbits.co",
    "agsvpt.trackers.work -> agsvpt.com",
    "tracker.cinefiles.info -> audiences.me",
))
DEFAULT_TAG_CONFIG = {
    "enable": False,
    "interval_cron": "5 4 * * *",
    "enable_media_tag": False,
    "enable_tag": True,
    "enable_category": False,
    "enable_del_tags": False,
    "downloaders": [],
    "all_cat": DEFAULT_ALL_CAT,
    "all_cat_rename": DEFAULT_ALL_CAT,
    "rename_type": False,
    "path_rename": None,
    "catprefix": "",
    "siteprefix": "",
    "tracker_mappings_str": DEFAULT_TRACKER_MAPPINGS,
    "custom_site_labels_str": "",
}


def parse_tracker_mappings(mapping_str: str) -> dict[str, str]:
    """解析每行 ``tracker域名 -> 映射域名``，忽略空行和注释。"""
    mappings = {}
    for raw_line in str(mapping_str or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "->" not in line:
            continue
        source, target = (part.strip() for part in line.split("->", 1))
        if source and target:
            mappings[source] = target
    return mappings


def parse_custom_site_labels(mapping_str: str) -> dict[str, str]:
    """解析每行 ``域名 -> 标签名`` 的自定义站点标签表（站点库未收录时兜底）。"""
    labels = {}
    for raw_line in str(mapping_str or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "->" not in line:
            continue
        domain, label = (part.strip() for part in line.split("->", 1))
        if domain and label:
            labels[domain.lower()] = label
    return labels


def build_tag_config(config: dict | None = None) -> dict:
    """按来源 ``get_form`` 默认值构建标签模块配置，不以 qnap 配置覆盖缺省值。"""
    result = dict(DEFAULT_TAG_CONFIG)
    result["all_cat"] = list(DEFAULT_ALL_CAT)
    result["all_cat_rename"] = list(DEFAULT_ALL_CAT)
    for key, value in (config or {}).items():
        if key in result and value is not None:
            result[key] = value
    result["downloaders"] = list(result.get("downloaders") or [])
    result["all_cat"] = list(result.get("all_cat") or DEFAULT_ALL_CAT)
    result["all_cat_rename"] = list(result.get("all_cat_rename") or result["all_cat"])
    result["tracker_mappings"] = parse_tracker_mappings(result.get("tracker_mappings_str", ""))
    result["custom_site_labels"] = parse_custom_site_labels(result.get("custom_site_labels_str", ""))
    result["category_mapping"] = dict(zip(result["all_cat"], result["all_cat_rename"]))
    return result


def _module_state(plugin) -> dict:
    state = getattr(plugin, "_site_tag_status", None)
    if not isinstance(state, dict):
        state = {"completed": 0, "skipped": 0, "matched": {}}
        plugin._site_tag_status = state
    state.setdefault("completed", 0)
    state.setdefault("skipped", 0)
    state.setdefault("matched", {})
    return state


def get_module_status(plugin=None) -> dict:
    """返回最近扫描补全数、跳过数和各下载器命中统计。"""
    if plugin is None:
        return {"completed": 0, "skipped": 0, "matched": {}}
    state = _module_state(plugin)
    return {
        "completed": int(state["completed"]),
        "skipped": int(state["skipped"]),
        "matched": dict(state["matched"]),
    }


def _torrent_value(torrent, name: str, default=None):
    if isinstance(torrent, dict):
        return torrent.get(name, default)
    return getattr(torrent, name, default)


def _torrent_trackers(torrent, service_type: str) -> list:
    trackers = _torrent_value(torrent, "trackers", []) or []
    if service_type == "qbittorrent":
        return [item.get("url") for item in trackers if isinstance(item, dict) and item.get("url")]
    return [getattr(item, "announce", "") for item in trackers if getattr(item, "announce", "")]


def _history_for_hash(torrent_hash: str):
    from ...adapter.moviepilot import get_download_history_by_hash
    return get_download_history_by_hash(torrent_hash)


def _category_from_media(plugin, history, config: dict, path: str | None = None):
    if config["rename_type"]:
        for raw_rule in str(config.get("path_rename") or "").splitlines():
            if "#" not in raw_rule:
                continue
            keyword, category = (part.strip() for part in raw_rule.split("#", 1))
            if keyword and category and keyword in (path or getattr(history, "path", "") or ""):
                return category
        return None
    source = getattr(history, "media_source", None)
    media_id = getattr(history, "media_id", None)
    media_type = getattr(history, "type", None)
    if not source or not media_id or not media_type or not getattr(plugin, "chain", None):
        return None
    media_info = plugin.chain.recognize_media(
        mtype=media_type, media_source=source, media_id=media_id,
    )
    category = getattr(media_info, "category", None) if media_info else None
    return config["category_mapping"].get(category, category) if category else None


def _apply_metadata(plugin, service, torrent, config: dict, context=None) -> dict:
    torrent_hash = str(_torrent_value(torrent, "hash", "") or _torrent_value(torrent, "hashString", ""))
    if not torrent_hash:
        return {"ok": False, "reason": "hash_missing"}
    history = _history_for_hash(torrent_hash)
    media_info = getattr(context, "media_info", None) if context else None
    title = getattr(history, "title", None) if history else None
    if not title and media_info:
        title = getattr(media_info, "title", None)
    current_tags = normalize_tags(get_label(torrent, service.type))
    trackers = _torrent_trackers(torrent, service.type) or (service.instance.get_trackers(torrent_hash) if torrent_hash and hasattr(service.instance, "get_trackers") else []) or []
    site_name = None
    for tracker in trackers:
        domain = next((mapped for key, mapped in config["tracker_mappings"].items() if key in tracker), None)
        custom_labels = config.get("custom_site_labels") or {}
        site_name = find_site_by_domain(domain or get_url_domain(tracker)) or custom_labels.get(
            (domain or get_url_domain(tracker) or "").lower()
        )
        if site_name:
            break
    tags = []
    if config["enable_tag"] and site_name:
        tags.append(f"{config['siteprefix']}{site_name}")
    if config["enable_media_tag"] and title:
        tags.append(str(title))
    category = None
    if config["enable_category"] and service.type == "qbittorrent":
        category = _category_from_media(plugin, history, config, _torrent_value(torrent, "save_path")) if history else None
    tags = [tag for tag in dict.fromkeys(tags) if tag and tag not in current_tags]
    current_category = _torrent_value(torrent, "category", "")
    if category == current_category:
        category = None
    if not tags and not category:
        return {"ok": True, "changed": False, "hash": torrent_hash, "site": site_name, "history": bool(history)}
    if tags:
        if service.type == "qbittorrent":
            service.instance.set_torrents_tag(ids=torrent_hash, tags=tags)
        else:
            service.instance.set_torrent_tag(ids=torrent_hash, tags=list(dict.fromkeys(current_tags + tags)))
    if category and service.type == "qbittorrent":
        try:
            torrent.setCategory(category=category)
        except Exception:
            service.instance.qbc.torrents_createCategory(name=category)
            torrent.setCategory(category=category)
    return {"ok": True, "changed": True, "hash": torrent_hash, "tags": tags, "category": category, "site": site_name, "history": bool(history)}

def _selected_services(plugin, config: dict):
    names = config["downloaders"]
    for name in names:
        service = plugin.service_info(name)
        if service and getattr(service, "instance", None):
            yield service


def complement_history(plugin, config: dict | None = None) -> dict:
    """扫描配置下载器并补全历史标签/分类；历史路径不覆盖已有 category。"""
    cfg = build_tag_config(config or getattr(plugin, "_site_tag_config", None))
    state = _module_state(plugin)
    result = {"completed": 0, "skipped": 0, "downloaders": {}}
    summary = {"history_hit": 0, "site_resolved": 0, "no_change": 0}
    for service in _selected_services(plugin, cfg):
        torrents, error = service.instance.get_torrents()
        if error:
            result["skipped"] += 1
            logger.warning(f"【PT下载中心:站点标签】 补全：下载器 {service.name} 获取种子失败，跳过")
            continue
        matched = 0
        for torrent in torrents or []:
            outcome = _apply_metadata(plugin, service, torrent, cfg)
            if outcome.get("history"):
                summary["history_hit"] += 1
            if outcome.get("site"):
                summary["site_resolved"] += 1
            if outcome.get("changed"):
                matched += 1
                result["completed"] += 1
                logger.info(
                    f"【PT下载中心:站点标签】 补全：{service.name} {outcome.get('hash', '')[:8]} "
                    f"tags={outcome.get('tags')} category={outcome.get('category')} site={outcome.get('site')}"
                )
            elif not outcome.get("ok"):
                result["skipped"] += 1
            else:
                summary["no_change"] += 1
        result["downloaders"][service.name] = matched
        state["matched"][service.name] = matched
        logger.info(
            f"【PT下载中心:站点标签】 补全：{service.name} 扫描 {len(torrents or [])} 条，"
            f"补全 {matched} 条，无变更 {summary['no_change']} 条"
        )
    logger.info(
        f"【PT下载中心:站点标签】 历史补全汇总：补全 {result['completed']}，跳过 {result['skipped']}，"
        f"历史命中 {summary['history_hit']}，站点解析 {summary['site_resolved']}，无变更 {summary['no_change']}"
    )
    state["completed"] = result["completed"]
    state["skipped"] = result["skipped"]
    if cfg["enable_del_tags"]:
        scan_and_clean_tags(plugin, cfg["downloaders"])
    return result


def process_download_added(plugin, event, config: dict | None = None) -> dict:
    """DownloadAdded 即时补全入口，使用事件 context 的媒体身份与标题。"""
    data = getattr(event, "event_data", None) or {}
    downloader = str(data.get("downloader") or data.get("downloader_name") or "").strip()
    torrent_hash = str(data.get("hash") or data.get("torrent_hash") or data.get("download_hash") or "").strip()
    cfg = build_tag_config(config or getattr(plugin, "_site_tag_config", None))
    if downloader not in cfg["downloaders"] or not torrent_hash:
        _module_state(plugin)["skipped"] += 1
        return {"ok": False, "reason": "downloader_or_hash_missing"}
    service = plugin.service_info(downloader)
    if not service or not getattr(service, "instance", None):
        _module_state(plugin)["skipped"] += 1
        return {"ok": False, "reason": "downloader_unavailable"}
    torrents, error = service.instance.get_torrents(ids=torrent_hash)
    if error or not torrents:
        _module_state(plugin)["skipped"] += 1
        return {"ok": False, "reason": "torrent_not_found"}
    outcome = _apply_metadata(plugin, service, torrents[0], cfg, data.get("context"))
    if outcome.get("changed"):
        _module_state(plugin)["completed"] += 1
    else:
        _module_state(plugin)["skipped"] += 1
    return outcome
