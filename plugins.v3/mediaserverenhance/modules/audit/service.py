"""媒体库体检模块。

只读巡检媒体库条目与本地文件，产出问题清单，不做任何删除或写入动作。
"""

from __future__ import annotations

import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from app.schemas.mediaserver import MediaServerItem
from app.sdk.logging import logger

from ...adapter import mediaserver
from ...utils import store
from ...utils.config import as_bool, as_list, parse_scope, safe_int, scope_allows
from ..refresh.service import history_limit, plugin_active

MODULE = "audit"

# 判定“这是视频”的扩展名白名单，含 STRM 以便云盘场景生效
VIDEO_SUFFIXES = frozenset(
    {
        ".mp4", ".mkv", ".ts", ".m2ts", ".avi", ".mov", ".wmv", ".flv",
        ".webm", ".iso", ".strm", ".rmvb", ".rm", ".m4v", ".mpg", ".mpeg", ".vob",
    }
)
IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp"})
META_SUFFIXES = frozenset({".nfo", ".xml", ".srt", ".ass", ".ssa", ".sup", ".sub"})

# 单条目目录扫描上限，避免巨量文件拖垮体检
SCAN_FILE_LIMIT = 2000
SCAN_DEPTH_LIMIT = 3

CHECK_TYPES = (
    "missing_episode",
    "duplicate",
    "empty_dir",
    "orphan_meta",
    "invalid_path",
    "missing_image",
)


def _config_checks(plugin) -> Set[str]:
    """返回配置启用的问题检查项集合。"""
    configured = as_list(getattr(plugin, "_audit_checks", None))
    if configured:
        return {str(item) for item in configured}
    return set(CHECK_TYPES)


def _selected_servers(plugin, override: Optional[Sequence[str]] = None) -> List[str]:
    """解析体检涉及的服务器清单。"""
    explicit = as_list(override)
    if explicit:
        return explicit
    configured = as_list(getattr(plugin, "_audit_servers", None))
    if configured:
        return configured
    return [row["name"] for row in mediaserver.list_server_configs() if row.get("enabled")]


def _selected_libraries(plugin, override: Optional[Sequence[str]] = None) -> List[Tuple[str, str]]:
    """解析体检的媒体库范围（``server|library_id``），空列表表示不限。"""
    explicit = as_list(override)
    raw = explicit if explicit else as_list(getattr(plugin, "_audit_libraries", None))
    return parse_scope(raw)


def _scan_dir(root: str) -> Tuple[bool, List[str]]:
    """快速扫描一个媒体目录。

    :param root: 目录路径
    :return: (是否存在, 相对文件名列表)
    """
    target = Path(root)
    if not target.exists():
        return False, []
    if target.is_file():
        return True, [target.name]
    names: List[str] = []
    stack: List[Tuple[Path, int]] = [(target, 0)]
    while stack and len(names) < SCAN_FILE_LIMIT:
        current, depth = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    names.append(entry.name)
                    if len(names) >= SCAN_FILE_LIMIT:
                        break
                    try:
                        if entry.is_dir(follow_symlinks=False) and depth + 1 <= SCAN_DEPTH_LIMIT:
                            stack.append((Path(entry.path), depth + 1))
                    except OSError:
                        continue
        except OSError:
            continue
    return True, names


def _classify(names: Sequence[str]) -> Tuple[bool, bool, bool]:
    """把目录内文件名归类。

    :param names: 文件名列表
    :return: (是否有视频, 是否有图片, 是否有元数据)
    """
    has_video = False
    has_image = False
    has_meta = False
    for name in names:
        suffix = Path(name).suffix.lower()
        if suffix in VIDEO_SUFFIXES:
            has_video = True
        elif suffix in IMAGE_SUFFIXES:
            has_image = True
        elif suffix in META_SUFFIXES:
            has_meta = True
        if has_video and has_image and has_meta:
            break
    return has_video, has_image, has_meta


def _season_gaps(seasoninfo: Any) -> List[Tuple[int, List[int]]]:
    """计算每季内部的缺集号。

    :param seasoninfo: ``MediaServerItem.seasoninfo``
    :return: [(季号, 缺失集号列表), ...]
    """
    gaps: List[Tuple[int, List[int]]] = []
    if not isinstance(seasoninfo, dict):
        return gaps
    for season, episodes in seasoninfo.items():
        try:
            numbers = sorted({int(value) for value in (episodes or [])})
        except (TypeError, ValueError):
            continue
        if len(numbers) < 2:
            continue
        present = set(numbers)
        missing = [value for value in range(numbers[0], numbers[-1] + 1) if value not in present]
        if missing:
            try:
                season_no = int(season)
            except (TypeError, ValueError):
                season_no = 0
            gaps.append((season_no, missing))
    return gaps


def _lib_field(library: Any, key: str) -> str:
    """读取媒体库字段，兼容字典与对象两种形态。

    :param library: 媒体库信息
    :param key: 字段名
    :return: 字段文本，缺失时为空串
    """
    if isinstance(library, dict):
        return str(library.get(key) or "")
    return str(getattr(library, key, "") or "")


def _issue(issue_type: str, server: str, library: Any, item: Optional[MediaServerItem] = None,
           detail: str = "", path: str = "") -> Dict[str, Any]:
    """构造一条问题记录。

    :param issue_type: 问题类型
    :param server: 服务器名称
    :param library: 媒体库信息
    :param item: 命中的媒体条目
    :param detail: 问题说明
    :param path: 命中路径
    :return: 问题字典
    """
    return {
        "issue_type": issue_type,
        "server": server,
        "library": _lib_field(library, "id"),
        "library_name": _lib_field(library, "name"),
        "item_id": getattr(item, "item_id", "") or "",
        "title": getattr(item, "title", "") or "",
        "year": str(getattr(item, "year", "") or ""),
        "detail": detail,
        "path": path or (getattr(item, "path", "") or ""),
    }


def _iter_items(server: str, library: Any, remaining: int) -> List[MediaServerItem]:
    """分页读取媒体库条目。

    :param server: 服务器名称
    :param library: 媒体库信息
    :param remaining: 本次最多读取的条目数
    :return: 条目列表；读取失败时抛出异常（由调用方记入报告）
    """
    library_id = _lib_field(library, "id")
    if not library_id:
        return []
    # 生成器惰性求值：异常只在 list() 物化时抛出，这里必须让异常原样外抛，
    # 由 run_audit 的 try 记入报告 errors，防止服务器故障被误判为空库
    return list(mediaserver.iter_library_items(server, library_id, remaining))

def run_audit(plugin, servers: Optional[Sequence[str]] = None,
              libraries: Optional[Sequence[str]] = None,
              checks: Optional[Sequence[str]] = None,
              max_items: Optional[int] = None,
              trigger: str = "手动") -> Dict[str, Any]:
    """执行一次只读体检并保存报告。

    :param plugin: 插件实例
    :param servers: 指定服务器，缺省用配置
    :param libraries: 指定媒体库，缺省用配置
    :param checks: 指定检查项，缺省用配置
    :param max_items: 本次最多扫描条目数
    :param trigger: 触发来源说明
    :return: 体检报告字典
    """
    started = time.time()
    check_set = {str(item) for item in checks} if checks else _config_checks(plugin)
    server_names = _selected_servers(plugin, servers)
    library_filter = _selected_libraries(plugin, libraries)
    budget = safe_int(max_items or getattr(plugin, "_audit_max_items", 20000), 20000, 100, 200000)

    job = store.build_job(MODULE, "audit", trigger=trigger, total=len(server_names))
    report: Dict[str, Any] = {
        "time": store.now_text(),
        "duration_ms": 0,
        "scanned_libraries": 0,
        "scanned_items": 0,
        "truncated": False,
        "counts": {},
        "issues": [],
        "errors": [],
    }
    if not server_names:
        store.finish_job(job, "skipped", "没有可用的媒体服务器")
        store.append_job(plugin, job, history_limit(plugin))
        store.write_value(plugin, store.AUDIT_REPORT_KEY, report)
        return report

    issues: List[Dict[str, Any]] = []
    counts: Dict[str, int] = defaultdict(int)
    scanned = 0
    offline: List[str] = []
    for name in server_names:
        online, reason = mediaserver.server_online(name)
        if not online:
            # 服务器不可达时不能当「空库」静默跳过，必须留下可读错误
            offline.append(f"{name}: 服务器不可用（{reason}）")
            report["errors"].append(offline[-1])
            continue
        # strict：在线但媒体库列表读取失败必须记入 errors，防止「登录后宕机」静默 success
        try:
            libraries_of_server = mediaserver.list_libraries(name, strict=True) or []
        except Exception as error:  # noqa: BLE001 - 单台服务器失败不影响其它服务器
            report["errors"].append(f"{name}: 媒体库列表读取失败（{error}）")
            continue
        if not libraries_of_server:
            # 宿主 get_librarys 会吞网络异常返回空列表，用活性探测区分「真空库」与「宕机」
            probe = mediaserver.probe_server_plugins(name)
            if probe.get("reachable") is False:
                report["errors"].append(
                    f"{name}: 服务器无响应（{probe.get('error')}），媒体库读取结果不可信"
                )
                continue
        for library in libraries_of_server:
            library_name = _lib_field(library, "name")
            if not scope_allows(library_filter, name, _lib_field(library, "id")):
                continue
            if scanned >= budget:
                report["truncated"] = True
                break
            try:
                items = _iter_items(name, library, budget - scanned)
            except Exception as error:  # noqa: BLE001 - 单个库读取失败不影响其它库
                report["errors"].append(f"{name}/{library_name}: {error}")
                continue
            report["scanned_libraries"] += 1
            scanned += len(items)
            lib_issues = _audit_library(name, library, items, check_set)
            for entry in lib_issues:
                counts[entry["issue_type"]] += 1
            issues.extend(lib_issues)
        if report["truncated"]:
            break

    report["issues"] = issues
    report["counts"] = dict(counts)
    report["scanned_items"] = scanned
    report["duration_ms"] = store.elapsed_ms(started)
    store.write_value(plugin, store.AUDIT_REPORT_KEY, report)
    total_issues = len(issues)
    if report["errors"]:
        # 有错误必须反映在状态里：全部失败即 failed，部分失败即 partial
        status = "failed" if scanned == 0 and not report["scanned_libraries"] else "partial"
    else:
        status = "success"
    message = f"扫描 {scanned} 条，发现 {total_issues} 个问题"
    if library_filter and not report["scanned_libraries"] and not report["errors"]:
        # 范围配置了但零命中：与「干净」区分开，提示配置可能失配
        message += "（配置的媒体库范围未匹配到任何库，请检查范围设置）"
    if report["errors"]:
        message += f"，{len(report['errors'])} 个错误"
    store.finish_job(
        job,
        status,
        message,
        success=report["scanned_libraries"],
        failed=len(report["errors"]),
        total=report["scanned_libraries"],
    )
    job["detail"] = {"issues": total_issues, "duration_ms": report["duration_ms"]}
    store.append_job(plugin, job, history_limit(plugin))
    _notify(plugin, report, total_issues)
    return report



_TYPE_ALIASES: Dict[str, str] = {
    "movie": "movie",
    "电影": "movie",
    "series": "tv",
    "show": "tv",
    "tv": "tv",
    "电视剧": "tv",
}


def _item_kind(item: MediaServerItem) -> str:
    """把条目类型归一成 movie / tv / 空串。

    宿主各服务器适配层返回的 ``item_type`` 可能是 Emby 原始值（Movie/Series）、
    Jellyfin 同构值或宿主统一中文值（电影/电视剧），体检判定只认归一后的类型。

    :param item: 媒体条目
    :return: 归一类型；无法识别返回空串
    """
    value = getattr(item, "item_type", None)
    if value is None:
        return ""
    text = str(getattr(value, "value", value) or "").strip()
    if not text:
        return ""
    return _TYPE_ALIASES.get(text, _TYPE_ALIASES.get(text.lower(), ""))


def _audit_library(server: str, library: Any, items: Sequence[MediaServerItem],
                   checks: Set[str]) -> List[Dict[str, Any]]:
    """对单个媒体库执行全部启用的检查项。

    :param server: 服务器名称
    :param library: 媒体库信息
    :param items: 库内条目
    :param checks: 启用的检查项
    :return: 问题列表
    """
    results: List[Dict[str, Any]] = []
    video_groups: Dict[Tuple[str, str], List[MediaServerItem]] = defaultdict(list)
    for item in items:
        item_type = _item_kind(item)
        if item_type in {"movie", "tv"}:
            video_groups[(item_type, f"{getattr(item, 'title', '')}|{getattr(item, 'year', '')}")].append(item)


    # 缺集：季内集号不连续；季集信息按需向服务器查询
    if "missing_episode" in checks:
        for item in items:
            if _item_kind(item) != "tv":
                continue
            seasoninfo = mediaserver.fetch_season_episodes(
                server,
                str(getattr(item, "item_id", "") or ""),
                title=str(getattr(item, "title", "") or ""),
                year=getattr(item, "year", None),
            )
            for season, missing in _season_gaps(seasoninfo):
                preview = ", ".join(str(value) for value in missing[:20])
                more = " 等" if len(missing) > 20 else ""
                results.append(
                    _issue(
                        "missing_episode",
                        server,
                        library,
                        item,
                        detail=f"第 {season} 季缺 {len(missing)} 集：{preview}{more}",
                    )
                )
    # 重复：同名同年同类型出现多条
    type_labels = {"movie": "电影", "tv": "电视剧"}
    if "duplicate" in checks:
        for (item_type, key), group in video_groups.items():
            if len(group) < 2:
                continue
            titles = "；".join(
                f"{getattr(entry, 'path', '') or getattr(entry, 'item_id', '')}" for entry in group[:5]
            )
            results.append(
                _issue(
                    "duplicate",
                    server,
                    library,
                    group[0],
                    detail=f"{type_labels.get(item_type, item_type)}同名条目 {len(group)} 条：{titles}",
                )
            )

    need_path_checks = bool({"empty_dir", "orphan_meta", "invalid_path", "missing_image"} & checks)
    if not need_path_checks:
        return results

    for item in items:
        path = getattr(item, "path", "") or ""
        if not path:
            continue
        exists, names = _scan_dir(path)
        if "invalid_path" in checks and not exists:
            results.append(_issue("invalid_path", server, library, item, detail="条目路径不存在", path=path))
            continue
        if not exists:
            continue
        has_video, has_image, has_meta = _classify(names)
        if "empty_dir" in checks and not has_video:
            results.append(
                _issue(
                    "empty_dir",
                    server,
                    library,
                    item,
                    detail=f"目录内没有可播放的视频文件（{len(names)} 个文件）",
                    path=path,
                )
            )
        elif "orphan_meta" in checks and has_meta and not has_video:
            results.append(_issue("orphan_meta", server, library, item, detail="只剩元数据/字幕文件", path=path))
        if "missing_image" in checks and not has_image:
            # 本地没有图片文件时向服务器复核：服务端抓图的条目本地常无图片文件
            remote_image = mediaserver.fetch_primary_image(
                server, str(getattr(item, "item_id", "") or ""), max_width=240
            )
            if remote_image:
                continue
            results.append(_issue("missing_image", server, library, item, detail="服务器与本地目录均无封面", path=path))
    return results


def run_scheduled(plugin) -> None:
    """定时体检入口。"""
    if not plugin_active(plugin, MODULE):
        return
    try:
        run_audit(plugin, trigger="定时体检")
    except Exception as error:  # noqa: BLE001 - 定时任务异常只记录
        logger.error(f"【媒体服务器增强】定时体检失败：{error}")


def latest_report(plugin) -> Dict[str, Any]:
    """读取最近一次体检报告。"""
    return store.read_snapshot(plugin, store.AUDIT_REPORT_KEY) or {
        "time": "",
        "counts": {},
        "issues": [],
        "errors": [],
        "scanned_items": 0,
        "scanned_libraries": 0,
        "duration_ms": 0,
        "truncated": False,
    }


def _notify(plugin, report: Dict[str, Any], total_issues: int) -> None:
    """体检发现新问题时推送通知。"""
    if not as_bool(getattr(plugin, "_notify", False)):
        return
    if total_issues <= 0:
        return
    counts = report.get("counts") or {}
    lines = [f"{key}: {value}" for key, value in sorted(counts.items())]
    try:
        plugin.post_message(
            title="【媒体服务器增强】媒体库体检",
            text=f"发现 {total_issues} 个问题\n" + "\n".join(lines[:10]),
        )
    except Exception as error:  # noqa: BLE001 - 通知失败不影响体检结果
        logger.warning(f"【媒体服务器增强】体检通知发送失败：{error}")
