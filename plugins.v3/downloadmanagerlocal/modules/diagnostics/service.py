"""下载管理插件诊断服务实现。"""

from datetime import datetime
from pathlib import Path

from app.sdk.logging import logger

from ...utils.config import module_faults, module_observe_flags, observe_previews
from ...model.state import RENAME_RECORDS_KEY
from ...utils.name_cleaner import is_dirty_renamed_torrent_name


def _bool_text(value) -> str:
    """将布尔开关状态转换为详情页展示文本。"""
    return "已开启" if bool(value) else "未开启"


def _service_status(plugin, name: str) -> dict:
    """检查指定下载器配置和连接状态。"""
    result = {
        "name": name or "",
        "configured": bool(name),
        "available": False,
        "type": "",
        "message": "未配置",
    }
    if not name:
        return result
    try:
        service = plugin.service_info(name)
        if not service or not service.instance:
            result["message"] = "不可用"
            return result
        result.update({
            "available": True,
            "type": service.type or "",
            "message": "连接正常",
        })
        return result
    except Exception as e:
        logger.warning(f"【PT下载中心】诊断：检查下载器 {name} 失败: {e}")
        result["message"] = str(e)
        return result


def _rename_history_stats(plugin, recent_limit: int = 5) -> dict:
    """统计重命名历史中的成功、失败和脏名称记录。

    recent_limit 只影响返回的最近失败样本条数，供数据页按请求上限展示。
    """
    records = plugin.get_data(RENAME_RECORDS_KEY) or {}
    items = list(records.values())
    success_count = sum(1 for item in items if item.get("success"))
    failed_items = [item for item in items if not item.get("success")]
    dirty_count = sum(
        1
        for item in items
        if is_dirty_renamed_torrent_name(item.get("original_name"))
        or is_dirty_renamed_torrent_name(item.get("after_name"))
    )
    recent_failures = sorted(
        failed_items,
        key=lambda item: item.get("time", ""),
        reverse=True,
    )[: max(1, int(recent_limit or 5))]
    return {
        "total": len(items),
        "success": success_count,
        "failed": len(failed_items),
        "dirty": dirty_count,
        "recent_failures": [
            {
                "time": item.get("time", ""),
                "hash": item.get("hash", ""),
                "reason": item.get("reason", "") or "未知原因",
                "name": item.get("original_name", "") or item.get("after_name", ""),
            }
            for item in recent_failures
        ],
    }


def _cleanup_stats(plugin, archive_stats: dict) -> dict:
    """统计各模块可清理数据量，供数据页清理入口在确认前显示数量。

    口径与 controller/handlers.py::_cleanup_actions 的清理条数一致；
    constants 键名懒导入，避免诊断模块顶层依赖模块包。
    """
    from ..autoremove.constants import REMOVER_STATE_DATA_KEY
    from ..autoremove.history import history_removed_count
    from ..failclean.constants import FAILCLEAN_STATUS_DATA_KEY
    from ..failclean.history import history_removed_count as failclean_history_removed_count
    from ...model.state import TRANSFER_SKIP_STATS_KEY, TRANSFER_STATS_KEY

    stats = plugin.get_data(TRANSFER_STATS_KEY) or {}
    skip_stats = plugin.get_data(TRANSFER_SKIP_STATS_KEY) or {}
    return {
        "rename_archive": int(archive_stats.get("archived", 0) or 0),
        "rename_history": len(plugin.get_data(RENAME_RECORDS_KEY) or {}),
        "transfer_stats": len(stats) + len(skip_stats),
        "autoremove_state": history_removed_count(plugin.get_data(REMOVER_STATE_DATA_KEY)),
        "failclean_state": failclean_history_removed_count(plugin.get_data(FAILCLEAN_STATUS_DATA_KEY)),
    }


def _path_exists(path_text: str) -> bool:
    """安全判断配置路径是否存在。"""
    if not path_text:
        return False
    try:
        return Path(path_text).exists()
    except Exception:
        return False


def _check(label: str, status: str, detail: str) -> dict:
    """构造详情页健康检查项。"""
    return {"label": label, "status": status, "detail": detail}
def _module_switch_checks(plugin) -> list[dict]:
    """消费裸开关快照：区分「插件停用」与「模块停用」（快照由 core/config.py 写入）。"""
    switches = getattr(plugin, "_module_switches", None)
    if not isinstance(switches, dict) or not switches:
        return []
    entries = [f"{name}={'开' if on else '关'}" for name, on in sorted(switches.items())]
    on_count = sum(1 for on in switches.values() if on)
    if on_count == len(switches):
        status = "ok"
    elif on_count:
        status = "warn"
    else:
        status = "off"
    return [_check("模块开关（裸值）", status, " / ".join(entries))]


def _module_fault_checks(plugin) -> list[dict]:
    """消费模块运行异常快照：与「模块开关（裸值）」并列，页面据此区分「关闭」与「故障」。"""
    faults = module_faults(plugin)
    if not faults:
        return []
    entries = [f"{name}：{reason}" for name, reason in sorted(faults.items())]
    return [_check("模块运行异常", "error", " / ".join(entries))]


def _first_enabled_task(plugin):
    """v3.9.0 多任务形态：取第一个启用任务做诊断投影；无则回退旧平铺字段。"""
    from ..transfer.tasks import load_transfer_tasks

    tasks = load_transfer_tasks(plugin)
    for task in tasks:
        if task.get("enabled"):
            return {
                "from_downloader": task.get("from_downloader") or "",
                "to_downloader": task.get("to_downloader") or "",
            }
    return {
        "from_downloader": getattr(plugin, "_fromdownloader", "") or "",
        "to_downloader": getattr(plugin, "_todownloader", "") or "",
    }


MODULE_DETAIL_ITEM_LIMIT = 20
"""数据页模块明细每条列表最多展示的条目数，与观察预览同量级。"""


MODULE_DETAIL_LIMIT_CHOICES = (20, 50, 100, 200)
"""数据页可选的明细条数上限白名单；查询参数只接受这些值，避免超大 payload。"""


def resolve_detail_limit(value) -> int:
    """把请求里的明细上限归一到白名单值；缺失或非法值回到默认 20。"""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return MODULE_DETAIL_ITEM_LIMIT
    return number if number in MODULE_DETAIL_LIMIT_CHOICES else MODULE_DETAIL_ITEM_LIMIT

SKIP_STAT_LABELS = (
    ("transfer_source", "转移源种子"),
    ("auto_remove", "自动删种"),
    ("transfer_failure", "整理失败"),
    ("sync_delete", "同步删除"),
)
"""H&R 保护闸门跳过统计的四类来源，与各模块 status 口径一致。"""


def _count(value) -> int:
    """把计数器值安全转成非负整数。"""
    try:
        number = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def _time_text(value) -> str:
    """把秒级时间戳转成可读文本，缺失或非法值返回空串。"""
    try:
        stamp = float(value or 0)
    except (TypeError, ValueError):
        return ""
    if stamp <= 0:
        return ""
    return datetime.fromtimestamp(stamp).strftime("%Y-%m-%d %H:%M:%S")


def _row(label: str, value) -> dict:
    """构造明细的一行标签值。"""
    return {"label": label, "value": "" if value is None else str(value)}


def _detail(title: str, rows, items=None, error: str = "", detail_limit: int = MODULE_DETAIL_ITEM_LIMIT,
            total: int | None = None) -> dict:
    """构造单模块明细块：先过滤有效条目，再统计总数，最后按上限截断。

    ``total`` 用于「列表只取样本、但真实条数更多」的模块（如重命名失败归档）；
    不传时以过滤后的条目数为总数。返回块在原有 title/rows/items/error 之外
    增加 total/limit/truncated，前端据此提示「仅显示前 N 条，共 M 条」。
    """
    limit = resolve_detail_limit(detail_limit)
    valid = [item for item in list(items or []) if isinstance(item, dict)]
    count = max(len(valid), _count(total)) if total is not None else len(valid)
    shown = valid[:limit]
    return {
        "title": title,
        "rows": [row for row in rows if isinstance(row, dict)],
        "items": shown,
        "error": error,
        "total": count,
        "limit": limit,
        "truncated": count > len(shown),
    }


def _text_item(title, meta) -> dict:
    """构造明细列表项。"""
    return {"title": str(title or ""), "meta": str(meta or "")}


def _candidate_item(row) -> dict:
    """把候选/任务条目压缩成标题 + 元信息两段。"""
    if not isinstance(row, dict):
        return _text_item(row, "")
    meta = " · ".join(
        part
        for part in (
            str(row.get("site") or ""),
            str(row.get("state") or row.get("status") or ""),
            str(row.get("size_text") or ""),
            str(row.get("reason") or ""),
        )
        if part
    )
    return _text_item(row.get("name") or row.get("torrent_hash") or row.get("hash"), meta)


def _observe_of(plugin, module: str) -> bool:
    """读取模块观察开关快照（core/config.py 初始化时落盘，只读不改）。"""
    flags = getattr(plugin, "_module_observe_only", None)
    if isinstance(flags, dict):
        return bool(flags.get(module))
    return False


def _skip_stat_rows(skip_stats) -> list[dict]:
    """把 H&R 保护闸门跳过统计展开成四行。"""
    data = skip_stats if isinstance(skip_stats, dict) else {}
    return [_row(f"跳过（{label}）", _count(data.get(key))) for key, label in SKIP_STAT_LABELS]


def _transfer_detail(plugin, detail_limit: int = MODULE_DETAIL_ITEM_LIMIT) -> dict:
    """转移做种明细：启用状态与成功/兜底/跳过计数。"""
    from ...model.state import TRANSFER_SKIP_STATS_KEY, load_transfer_stats

    stats = load_transfer_stats(plugin)
    rows = [
        _row("转移做种", _bool_text(getattr(plugin, "_transfer_enabled", False))),
        _row("调度状态", _bool_text(getattr(plugin, "_transfer_active", False))),
        _row("兜底重试", _bool_text(getattr(plugin, "_transfer_fallback_enabled", False))),
        _row("观察模式", _bool_text(_observe_of(plugin, "transfer"))),
        _row("今日成功", _count(stats.get("today_success"))),
        _row("累计成功", _count(stats.get("success_total"))),
        _row("今日兜底", _count(stats.get("today_fallback"))),
        _row("兜底成功", _count(stats.get("fallback_success"))),
        *_skip_stat_rows(plugin.get_data(TRANSFER_SKIP_STATS_KEY)),
    ]
    return _detail("转移做种", rows, detail_limit=detail_limit)


def _rename_detail(plugin, history: dict, archive_stats: dict,
                   detail_limit: int = MODULE_DETAIL_ITEM_LIMIT) -> dict:
    """种子重命名明细：本轮计数、归档水位与最近失败原因。"""
    from ..rename.service import get_module_status

    status = get_module_status(plugin)
    status = status if isinstance(status, dict) else {}
    rows = [
        _row("种子重命名", _bool_text(getattr(plugin, "_rename_enabled", False))),
        _row("观察模式", _bool_text(_observe_of(plugin, "rename"))),
        _row("最近运行", status.get("last_run") or "尚未运行"),
        _row("本次成功", _count(status.get("renamed"))),
        _row("本次失败", _count(status.get("failed"))),
        _row("本次跳过", _count(status.get("skipped"))),
        _row("定时批次", "进行中" if getattr(plugin, "_rename_batch_running", False) else "空闲"),
        _row("历史记录", _count(history.get("total"))),
        _row(
            "失败归档",
            f"{_count(archive_stats.get('archived'))} / 阈值 {_count(archive_stats.get('threshold'))}",
        ),
    ]
    items = [
        _text_item(
            row.get("name") or row.get("hash"),
            " · ".join(part for part in (str(row.get("time") or ""), str(row.get("reason") or "")) if part),
        )
        for row in (history.get("recent_failures") or [])
        if isinstance(row, dict)
    ]
    return _detail("种子重命名", rows, items, detail_limit=detail_limit,
                   total=_count(history.get("failed")))


def _sitetag_detail(plugin, detail_limit: int = MODULE_DETAIL_ITEM_LIMIT) -> dict:
    """站点标签明细：补全计数与命中站点分布。"""
    from ..sitetag.service import get_module_status

    status = get_module_status(plugin)
    status = status if isinstance(status, dict) else {}
    matched = status.get("matched")
    matched = matched if isinstance(matched, dict) else {}
    rows = [
        _row("站点标签", _bool_text(getattr(plugin, "_tag_enabled", False))),
        _row("观察模式", _bool_text(_observe_of(plugin, "tag"))),
        _row("补全完成", _count(status.get("completed"))),
        _row("跳过", _count(status.get("skipped"))),
        _row("命中站点数", len(matched)),
    ]
    items = [_text_item(site, f"{_count(count)} 个任务") for site, count in matched.items()]
    return _detail("站点标签", rows, items, detail_limit=detail_limit)


def _hr_detail(plugin, detail_limit: int = MODULE_DETAIL_ITEM_LIMIT) -> dict:
    """H&R 管理明细：状态汇总、保护闸门与任务列表。"""
    service = getattr(plugin, "_hr_service", None)
    if service is None:
        return _detail("H&R 管理", [_row("状态", "未启用或初始化失败")], detail_limit=detail_limit)
    info = service.get_service_infos()
    info = info if isinstance(info, dict) else {}
    summary = info.get("summary")
    summary = summary if isinstance(summary, dict) else {}
    rows = [
        _row("H&R 管理", _bool_text(getattr(plugin, "_hr_enabled", False))),
        _row("观察模式", _bool_text(_observe_of(plugin, "hr"))),
        _row("任务总数", _count(summary.get("total"))),
        _row("待做种", _count(summary.get("needs_seeding"))),
        _row("做种中", _count(summary.get("in_progress"))),
        _row("已达标", _count(summary.get("compliant"))),
        _row("超期", _count(summary.get("overdue"))),
        _row("已删除", _count(summary.get("deleted"))),
        _row("保护闸门", _bool_text(summary.get("protection_enabled"))),
        *_skip_stat_rows(summary.get("skip_stats")),
    ]
    items = [_candidate_item(task) for task in (info.get("tasks") or [])]
    return _detail("H&R 管理", rows, items, detail_limit=detail_limit)


def _autoremove_detail(plugin, detail_limit: int = MODULE_DETAIL_ITEM_LIMIT) -> dict:
    """自动删种明细：最近一轮计数、动作与候选列表。"""
    service = getattr(plugin, "_autoremove_service", None)
    status = service.get_module_status() if service is not None else {}
    status = status if isinstance(status, dict) else {}
    rows = [
        _row("自动删种", _bool_text(getattr(plugin, "_remover_enabled", False))),
        _row("观察模式", _bool_text(bool(status.get("observe_only")) or _observe_of(plugin, "autoremove"))),
        _row("动作", status.get("action") or ""),
        _row("最近运行", _time_text(status.get("last_run_at")) or "尚未运行"),
        _row("触发来源", status.get("last_trigger") or ""),
        _row("候选", _count(status.get("candidates"))),
        _row("暂停", _count(status.get("paused"))),
        _row("删除种子", _count(status.get("deleted"))),
        _row("删除文件", _count(status.get("deleted_files"))),
        _row("跳过（H&R 保护）", _count(status.get("skipped_protected"))),
        _row("跳过（种子缺失）", _count(status.get("skipped_missing"))),
        _row("失败", _count(status.get("failed"))),
        _row("配置错误", status.get("config_error") or ""),
    ]
    items = [_candidate_item(row) for row in (status.get("candidate_list") or [])]
    return _detail("自动删种", rows, items, detail_limit=detail_limit)


def _failclean_detail(plugin, detail_limit: int = MODULE_DETAIL_ITEM_LIMIT) -> dict:
    """失败清理明细：巡检/事件/累计三段计数与保留期。"""
    service = getattr(plugin, "_failclean_service", None)
    status = service.get_module_status() if service is not None else {}
    status = status if isinstance(status, dict) else {}
    scan = status.get("scan")
    scan = scan if isinstance(scan, dict) else {}
    event = status.get("event")
    event = event if isinstance(event, dict) else {}
    total = status.get("total")
    total = total if isinstance(total, dict) else {}
    rows = [
        _row("失败清理", _bool_text(getattr(plugin, "_failcleanup_enabled", False))),
        _row("观察模式", _bool_text(_observe_of(plugin, "failclean"))),
        _row("最近巡检", _time_text(status.get("last_scan_time")) or "尚未运行"),
        _row("巡检触发", status.get("last_scan_trigger") or ""),
        _row("保留期（小时）", _count(status.get("retain_hours"))),
        _row(
            "本轮扫描 / 清理 / 失败 / 跳过",
            " / ".join(str(_count(scan.get(key))) for key in ("scanned", "cleaned", "failed", "skipped")),
        ),
        _row(
            "事件删除 / 失败 / 跳过",
            " / ".join(str(_count(event.get(key))) for key in ("deleted", "failed", "skipped")),
        ),
        _row(
            "累计清理 / 失败 / 跳过",
            " / ".join(str(_count(total.get(key))) for key in ("cleaned", "failed", "skipped")),
        ),
        *_skip_stat_rows(status.get("skip_stats")),
    ]
    return _detail("失败清理", rows, detail_limit=detail_limit)


def _uploadlimit_detail(plugin, detail_limit: int = MODULE_DETAIL_ITEM_LIMIT) -> dict:
    """上传限速明细：服务状态、管理规模与配额分配。"""
    from ..uploadlimit.service import get_upload_limit_status

    status = get_upload_limit_status(plugin)
    status = status if isinstance(status, dict) else {}
    rate = _count(status.get("upload_rate_bps"))
    rate_text = f"{rate / 1024:.1f} KB/s" if rate else "0 KB/s"
    rows = [
        _row("上传限速", _bool_text(getattr(plugin, "_upload_limit_enabled", False))),
        _row("服务状态", status.get("service_status") or ""),
        _row("观察模式", _bool_text(_observe_of(plugin, "upload_limit"))),
        _row("模式", status.get("mode") or ""),
        _row("原因", status.get("reason") or ""),
        _row("管理种子", _count(status.get("managed_torrents"))),
        _row("宽限种子", _count(status.get("grace_torrents"))),
        _row("上传中", _count(status.get("uploading_torrents"))),
        _row("探测中", _count(status.get("probing_torrents"))),
        _row("受保护", _count(status.get("protected_torrents"))),
        _row("当前上传速率", rate_text),
        _row("已分配额度", f"{_count(status.get('allocated_kib'))} KiB"),
        _row("周期", _count(status.get("cycle"))),
        _row("最近运行", _time_text(status.get("last_run_at")) or "尚未运行"),
        _row("态异常", status.get("state_error") or ""),
    ]
    items = [_candidate_item(row) for row in (status.get("sites") or [])]
    items += [_text_item(error, "") for error in (status.get("errors") or [])]
    return _detail("上传限速", rows, items, detail_limit=detail_limit)


def _module_details(plugin, rename_history: dict, archive_stats: dict,
                    detail_limit: int = MODULE_DETAIL_ITEM_LIMIT) -> dict:
    """构造七个模块的数据页明细块。

    单模块读取失败只在该模块明细里记 error，不影响其他模块（模块隔离）：
    关闭或初始化失败的模块会给出显式提示，而不是让整个数据页报错。
    """
    builders = (
        ("transfer", "转移做种", lambda: _transfer_detail(plugin, detail_limit)),
        ("rename", "种子重命名", lambda: _rename_detail(plugin, rename_history, archive_stats, detail_limit)),
        ("tag", "站点标签", lambda: _sitetag_detail(plugin, detail_limit)),
        ("hr", "H&R 管理", lambda: _hr_detail(plugin, detail_limit)),
        ("autoremove", "自动删种", lambda: _autoremove_detail(plugin, detail_limit)),
        ("failclean", "失败清理", lambda: _failclean_detail(plugin, detail_limit)),
        ("upload_limit", "上传限速", lambda: _uploadlimit_detail(plugin, detail_limit)),
    )
    details = {}
    for key, title, builder in builders:
        try:
            details[key] = builder()
        except Exception as error:  # noqa: BLE001 - 单模块异常必须隔离
            details[key] = _detail(title, [], error=f"{type(error).__name__}: {error}", detail_limit=detail_limit)
    return details


def build_diagnostics(plugin, detail_limit: int = MODULE_DETAIL_ITEM_LIMIT):
    """构建只读诊断摘要，供详情页展示。"""
    task_view = _first_enabled_task(plugin)
    from_service = _service_status(plugin, task_view["from_downloader"])
    to_service = _service_status(plugin, task_view["to_downloader"])
    source_path_exists = _path_exists(getattr(plugin, "_fromtorrentpath", ""))
    transfer_ready = bool(
        plugin._transfer_active and from_service["available"] and to_service["available"]
    )
    rename_history = _rename_history_stats(plugin, recent_limit=resolve_detail_limit(detail_limit))
    archive_stats = plugin.rename_archive_stats()
    module_details = _module_details(plugin, rename_history, archive_stats, detail_limit=detail_limit)

    checks = [
        _check(
            "源下载器",
            "ok" if from_service["available"] else "warn",
            from_service["message"],
        ),
        _check(
            "目标下载器",
            "ok" if to_service["available"] else "warn",
            to_service["message"],
        ),
        _check(
            "种子文件目录",
            "ok" if source_path_exists else "warn",
            "路径可访问" if source_path_exists else "未配置或路径不可访问",
        ),
        _check(
            "转移做种",
            "ok" if transfer_ready else ("off" if not plugin._transfer_enabled else "warn"),
            "配置完整" if transfer_ready else "未启用或配置不完整",
        ),
        _check(
            "插件总开关",
            "ok" if getattr(plugin, "_enabled", False) else "off",
            _bool_text(getattr(plugin, "_enabled", False)),
        ),
        *_module_switch_checks(plugin),
        *_module_fault_checks(plugin),
        _check(
            "种子重命名",
            "warn" if to_service.get("type") == "transmission" else ("ok" if plugin._rename_enabled else "off"),
            "不支持 Transmission" if to_service.get("type") == "transmission" else _bool_text(plugin._rename_enabled),
        ),
        _check("站点标签", "ok" if plugin._tag_enabled else "off", _bool_text(plugin._tag_enabled)),
        _check(
            "补刀归档",
            "warn" if archive_stats.get("archived") else "ok",
            f"已归档 {archive_stats.get('archived', 0)}，阈值 {archive_stats.get('threshold', 3)} 次",
        ),
    ]

    return {
        "code": 0,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "plugin": {
            "name": plugin.plugin_name,
            "version": plugin.plugin_version,
            "state": bool(plugin.get_state()),
        },
        "downloaders": {
            "from": from_service,
            "to": to_service,
        },
        "config": {
            "enabled": bool(plugin._enabled),
            "transfer_enabled": bool(plugin._transfer_enabled),
            "transfer_active": bool(plugin._transfer_active),
            "transfer_fallback_enabled": bool(plugin._transfer_fallback_enabled),
            "rename_enabled": bool(plugin._rename_enabled),
            "tag_enabled": bool(plugin._tag_enabled),
            "seed_autostart": bool(plugin._seed_autostart),
            "seed_skipverify": bool(plugin._seed_skipverify),
        },
        "paths": {
            "frompath": plugin._frompath or "",
            "topath": plugin._topath or "",
            "fromtorrentpath": getattr(plugin, "_fromtorrentpath", "") or "",
            "fromtorrentpath_exists": source_path_exists,
        },
        "rename_history": rename_history,
        "rename_archive": archive_stats,
        "cleanup_data": _cleanup_stats(plugin, archive_stats),
        "module_faults": module_faults(plugin),
        "checks": checks,
        "module_observe_only": module_observe_flags(plugin),
        "observe_previews": observe_previews(plugin),
        "module_details": module_details,
    }


__all__ = ("build_diagnostics",)
