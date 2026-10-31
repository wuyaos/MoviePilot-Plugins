"""下载管理插件 - API 路由实现"""

import json
import threading
import time
from datetime import datetime
from typing import TypeVar

from app import schemas
from app.sdk.logging import logger
from fastapi import HTTPException
from pydantic import BaseModel

from ..adapter.moviepilot import get_downloader_service, get_url_domain, list_builtin_sites
from ..modules.rename.locator import resolve_record_downloader
from ..modules.rename.record_keys import downloader_of_key, hash_of_key, lookup as lookup_record
from ..model.api import (
    ApiBusinessModel,
    CleanupModuleRequest,
    CleanupModuleResult,
    DiagnosticsResult,
    EmptyRequest,
    HashActionResult,
    HrActionResult,
    HrClearTaskRequest,
    HrPresetsResult,
    HrSkipStatsResult,
    HrTasksResult,
    ModuleActionResult,
    ModuleConfigSummaryResult,
    ModuleStatusResult,
    OverviewResult,
    RetryRenamesResult,
    SelectionItem,
    TagCleanupExecuteRequest,
    TagCleanupExecuteResult,
    TagCleanupScanRequest,
    TagCleanupScanResult,
    UploadLimitDisableResult,
    UploadLimitReallocateResult,
    UploadLimitRulesRequest,
    UploadLimitRulesResult,
    UploadLimitSiteTagsRequest,
    UploadLimitSiteTagsResult,
    UploadLimitStatusResult,
)
from ..model.state import (
    RENAME_RECORDS_KEY,
    RENAME_RETRY_STATE_KEY,
    TRANSFER_SKIP_STATS_KEY,
    TRANSFER_STATS_KEY,
    load_transfer_stats,
)
from ..modules.rename.archive import serialized_rename_state
from ..modules.hr.guard import HrGuard
from ..modules.hr.rules import load_preset_rules
from ..utils.config import observe_skip
from ..modules.sitetag.service import complement_history, execute_tag_cleanup
try:
    from ..modules.sitetag.service import scan_tag_candidates
except ImportError:  # 兼容旧测试夹具
    from ..modules.sitetag.service import scan_and_clean_tags as scan_tag_candidates
from ..modules.uploadlimit.worker import stop_upload_limit_worker
from ..modules.uploadlimit.service import (
    get_upload_limit_status,
    persist_upload_limit_site_rules,
    restore_upload_limits,
    run_upload_limit_cycle,
    scan_upload_limit_site_tags,
)

from .records import record_page, record_query
from .config_summary import build_module_config_summary
BusinessModelT = TypeVar("BusinessModelT", bound=ApiBusinessModel)


def _request_dict(payload: BaseModel | dict | None) -> dict:
    """把具体 Pydantic 请求模型转换为领域服务使用的普通字典。"""
    if isinstance(payload, BaseModel):
        return payload.model_dump()
    return dict(payload) if isinstance(payload, dict) else {}


def _operation_response(
    payload: dict,
    model_type: type[BusinessModelT],
) -> schemas.Response[BusinessModelT]:
    """把旧版 code 结果转换为单层 MoviePilot V3 业务响应。"""
    data = model_type.model_validate(payload)
    code = int(getattr(data, "code", 0) or 0)
    message = str(getattr(data, "msg", "") or "")
    return schemas.Response[model_type](
        success=code == 0,
        message=message,
        data=data,
    )


def _raise_query_error(summary: str, error: Exception) -> None:
    """把查询端点异常转换为明确的 HTTP 500。"""
    logger.error(f"【PT下载中心】{summary}: {error}")
    raise HTTPException(status_code=500, detail=str(error)) from error
def _require_module(plugin, module: str, label: str) -> None:
    """模块核心执行端点的统一门控：总开关与模块开关任一关闭即拒绝（utils/config.py 注册表口径）。"""
    from ..utils.config import MODULE_SWITCHES
    attr = MODULE_SWITCHES[module][1]
    if not getattr(plugin, attr, False):
        logger.warning(f"【PT下载中心】{label}端点被拒：模块开关未启用（{attr}=False）")
        raise HTTPException(status_code=400, detail=f"「{label}」未启用（检查插件总开关与模块开关）")



def api_retry_renames(plugin):
    """后台线程触发失败历史和脏名称种子的批量补刮，立即返回。"""
    _require_module(plugin, "rename", "命名补刀")
    with getattr(plugin, "_rename_batch_lock", threading.Lock()):
        if getattr(plugin, "_rename_batch_running", False):
            return _operation_response(
                {"code": 1, "msg": "补刀已在后台运行，请稍后查看重命名历史"},
                RetryRenamesResult,
            )
        plugin._rename_batch_running = True
    def _run_batch():
        try:
            result = plugin._retry_pending_renames()
            logger.info(f"【PT下载中心:重命名】后台批量补刀完成: {result}")
        except Exception as e:
            logger.error(f"【PT下载中心:重命名】后台批量补刀失败: {e}")
        finally:
            plugin._rename_batch_running = False

    threading.Thread(target=_run_batch, daemon=True, name="dml-rename-batch").start()
    return _operation_response(
        {"code": 0, "msg": "补刀已开始，正在后台逐条处理，结果见重命名历史", "running": True},
        RetryRenamesResult,
    )

def api_rename_scan(plugin):
    """后台线程触发一次完整重命名扫描（等价定时任务的一次执行），立即返回。"""
    _require_module(plugin, "rename", "命名补刀")
    from ..modules.rename.service import scan_renames

    with getattr(plugin, "_rename_scan_lock", threading.Lock()):
        if getattr(plugin, "_rename_scan_running", False):
            return _operation_response(
                {"code": 1, "msg": "扫描已在运行，请稍后查看重命名历史"},
                RetryRenamesResult,
            )
        plugin._rename_scan_running = True

    def _run_scan():
        try:
            result = scan_renames(plugin)
            logger.info(f"【PT下载中心:重命名】手动扫描完成: {result}")
        except Exception as e:
            logger.error(f"【PT下载中心:重命名】手动扫描失败: {e}")
        finally:
            plugin._rename_scan_running = False

    threading.Thread(target=_run_scan, daemon=True, name="dml-rename-scan").start()
    return _operation_response(
        {"code": 0, "msg": "扫描已开始，正在后台处理，结果见重命名历史", "running": True},
        RetryRenamesResult,
    )
def api_retry_rename(plugin, hash: str = "", downloader: str = ""):
    """对指定种子 hash（可带下载器身份）手动重试重命名和站点标签。"""
    _require_module(plugin, "rename", "命名补刀")
    try:
        return _operation_response(plugin._retry_rename(hash, downloader), HashActionResult)
    except Exception as e:
        logger.error(f"【PT下载中心】单条补刀失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"补刀失败: {e}", "hash": hash or ""},
            HashActionResult,
        )


def api_diagnostics(plugin, detail_limit: int = 20, run: bool = False):
    """默认读取最近快照；run=true 才执行新一轮只读诊断。"""
    from ..modules.diagnostics.service import MODULE_DETAIL_LIMIT_CHOICES

    if detail_limit not in MODULE_DETAIL_LIMIT_CHOICES:
        allowed = "/".join(str(item) for item in MODULE_DETAIL_LIMIT_CHOICES)
        raise HTTPException(status_code=400, detail=f"运行明细条数只支持 {allowed}")
    try:
        from ..modules.diagnostics.service import diagnostics_snapshot

        return DiagnosticsResult.model_validate(diagnostics_snapshot(plugin, detail_limit, run=run))
    except Exception as e:
        _raise_query_error("诊断信息生成失败", e)


def _transfer_skip_stats(plugin) -> dict:
    """读取转移源端删除的 H&R 保护跳过计数。"""
    stats = plugin.get_data(TRANSFER_SKIP_STATS_KEY)
    protected = stats.get("hr_protected") if isinstance(stats, dict) else 0
    return {"hr_protected": int(protected or 0)}


def api_overview(plugin):
    """返回详情页总览数据。"""
    try:
        diagnostics = plugin._diagnostics()
        archive = plugin.rename_archive_stats()
        upload_limit = get_upload_limit_status(plugin)
        transfer_stats = load_transfer_stats(plugin)
        transfer_skip_stats = _transfer_skip_stats(plugin)
        rename_history = diagnostics.get("rename_history", {}) if isinstance(diagnostics, dict) else {}
        return OverviewResult.model_validate({
            "code": 0,
            "plugin": diagnostics.get("plugin", {}) if isinstance(diagnostics, dict) else {},
            "config": diagnostics.get("config", {}) if isinstance(diagnostics, dict) else {},
            "downloaders": diagnostics.get("downloaders", {}) if isinstance(diagnostics, dict) else {},
            "rename_history": rename_history,
            "archive": archive,
            "upload_limit": upload_limit,
            "transfer_skip_stats": transfer_skip_stats,
            "cards": {
                "upload_limit": {
                    "enabled": bool(getattr(plugin, "_upload_limit_enabled", False)),
                    "active": bool(upload_limit.get("active")),
                    "managed": int(upload_limit.get("managed_torrents") or 0),
                    "grace": int(upload_limit.get("grace_torrents") or 0),
                },
                "transfer": {
                    "enabled": bool(getattr(plugin, "_transfer_enabled", False)),
                    "active": bool(getattr(plugin, "_transfer_active", False)),
                    "fallback_enabled": bool(getattr(plugin, "_transfer_fallback_enabled", False)),
                    "success_total": int(transfer_stats["success_total"]),
                    "fallback_success": int(transfer_stats["fallback_success"]),
                    "today_success": int(transfer_stats["today_success"]),
                    "today_fallback": int(transfer_stats["today_fallback"]),
                },
                "rename": {
                    "enabled": bool(getattr(plugin, "_rename_enabled", False)),
                    "failed": int(rename_history.get("failed", 0) or 0),
                    "dirty": int(rename_history.get("dirty", 0) or 0),
                    "archived": int(archive.get("archived", 0) or 0),
                },
                "seed": {
                    "autostart": bool(getattr(plugin, "_seed_autostart", False)),
                    "skipverify": bool(getattr(plugin, "_seed_skipverify", False)),
                },
            },
        })
    except Exception as e:
        _raise_query_error("总览信息生成失败", e)
def api_module_config_summary(plugin):

    """返回七个模块的只读配置摘要（已生效配置，不含表单临时态）。"""

    try:

        return ModuleConfigSummaryResult.model_validate(build_module_config_summary(plugin))

    except Exception as e:

        _raise_query_error("模块配置摘要生成失败", e)
def api_upload_limit_status(plugin):
    """返回上传限速配置页状态。"""
    try:
        return UploadLimitStatusResult.model_validate(
            {"code": 0, **get_upload_limit_status(plugin)}
        )
    except Exception as e:
        _raise_query_error("上传限速状态读取失败", e)


def api_upload_limit_reallocate(plugin, payload: EmptyRequest | None = None):
    """立即执行一轮上传额度重新分配。"""
    _require_module(plugin, "upload_limit", "上传限速")
    try:
        result = run_upload_limit_cycle(plugin, reason="manual")
        return _operation_response(
            {"code": 0 if not result.get("errors") else 2,
             "msg": "上传额度已重新分配" if not result.get("errors") else f"部分下载器限速写入失败（{len(result['errors'])}项）", **result},
            UploadLimitReallocateResult,
        )
    except Exception as e:
        logger.error(f"【PT下载中心】上传额度重新分配失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"重新分配失败: {e}"},
            UploadLimitReallocateResult,
        )


def api_upload_limit_site_tags(plugin, payload: UploadLimitSiteTagsRequest):
    """扫描指定下载器中的站点前缀标签。"""
    try:
        request = _request_dict(payload)
        result = scan_upload_limit_site_tags(
            plugin, request.get("downloaders")
        )
        # 请求体 rules 为空（前端未传或显式传空）时沿用已持久化站点策略：
        # 站点扫描只负责补充站点名，不得清空既有站点上限。
        rules = dict(
            request.get("rules")
            or (getattr(plugin, "_upload_limit_site_rules", {}) or {})
        )
        for item in result.get("items") or []:
            name = str(item.get("name") or "").strip()
            if name:
                rules.setdefault(name, {"limit_kib": 0})
        result["rules"] = persist_upload_limit_site_rules(plugin, rules)
        result["msg"] = "站点标签扫描完成，策略已立即生效" if result.get("code") == 0 else result.get("msg")
        return _operation_response(result, UploadLimitSiteTagsResult)
    except Exception as e:
        logger.error(f"【PT下载中心】上传限速站点标签扫描失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"扫描失败: {e}", "items": [], "errors": [], "rules": {}},
            UploadLimitSiteTagsResult,
        )


def api_upload_limit_site_rules_update(plugin, payload: UploadLimitRulesRequest):
    """立即保存上传限速站点策略，不触发重新分配。"""
    try:
        request = _request_dict(payload)
        rules = persist_upload_limit_site_rules(plugin, request.get("rules"))
        return _operation_response(
            {
                "code": 0,
                "msg": "站点策略已清空并立即生效" if not rules else "站点策略已立即生效",
                "rules": rules,
            },
            UploadLimitRulesResult,
        )
    except Exception as e:
        logger.error(f"【PT下载中心】上传限速站点策略保存失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"站点策略保存失败: {e}", "rules": {}},
            UploadLimitRulesResult,
        )


def api_upload_limit_disable_restore(plugin, payload: EmptyRequest | None = None):
    """停用上传限速、停止协调 worker 并恢复接管前设置。"""
    try:
        config = plugin.get_config()
        if not isinstance(config, dict):
            raise RuntimeError("读取插件配置失败，未停用上传限速")
        config = dict(config)
        config["upload_limit_enabled"] = False
        if plugin.update_config(config=config) is False:
            raise RuntimeError("保存停用配置失败，未停用上传限速")
        plugin._upload_limit_enabled = False
        stop_upload_limit_worker(plugin)
        result = restore_upload_limits(plugin)
        return _operation_response(result, UploadLimitDisableResult)
    except Exception as e:
        logger.error(f"【PT下载中心】停用并恢复上传限速失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"停用恢复失败: {e}", "errors": [str(e)]},
            UploadLimitDisableResult,
        )


def api_downloaders(plugin):
    """返回可用下载器列表"""
    try:
        services = plugin.downloader_helper.get_services()
        result = []
        if services:
            for name, info in services.items():
                result.append({
                    "title": name,
                    "value": name,
                    "type": info.type,
                })
        return [SelectionItem.model_validate(item) for item in result]
    except Exception as e:
        _raise_query_error("获取下载器列表失败", e)


def api_sites(plugin):
    """返回 V3 站点数据库中的可用站点列表。"""
    try:
        result = [{"title": site.name, "value": site.id,
                   "domain": get_url_domain(getattr(site, "domain", None) or getattr(site, "url", "") or "")}
                  for site in list_builtin_sites()]
        return [SelectionItem.model_validate(item) for item in result]
    except Exception as e:
        _raise_query_error("获取站点列表失败", e)


def api_tag_cleanup_scan(plugin, payload: TagCleanupScanRequest):
    """只读扫描站点标签候选，不做任何写入。"""
    _require_module(plugin, "tag", "站点标签")
    try:
        request = _request_dict(payload)
        result = scan_tag_candidates(plugin, request.get("downloaders") or [])
        return _operation_response(result, TagCleanupScanResult)
    except Exception as e:
        logger.error(f"【PT下载中心】标签清理扫描失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"扫描失败: {e}", "downloaders": [], "auto_removed": [], "errors": []},
            TagCleanupScanResult,
        )


def api_tag_cleanup_execute(plugin, payload: TagCleanupExecuteRequest):
    """按用户确认的扫描快照清理其余标签。"""
    _require_module(plugin, "tag", "站点标签")
    try:
        request = _request_dict(payload)
        result = execute_tag_cleanup(plugin, request.get("removals") or [], request.get("scan_id"))
        return _operation_response(result, TagCleanupExecuteResult)
    except Exception as e:
        logger.error(f"【PT下载中心】标签清理执行失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"清理失败: {e}", "removed": [], "failed": []},
            TagCleanupExecuteResult,
        )


def api_rename_history(plugin, page: int = 1, page_size: int = 20, result_filter: str = "all"):
    """返回未归档重命名历史；success/failed 沿用 success 布尔值。"""
    page, page_size, result_filter = record_query(
        page, page_size, result_filter, ("all", "success", "failed"))
    records = plugin.get_data(RENAME_RECORDS_KEY) or {}
    retry_state = plugin.get_data(RENAME_RETRY_STATE_KEY) or {}
    archived_keys = {
        state_key
        for state_key, state in retry_state.items()
        if isinstance(state, dict) and state.get("archived")
    } if isinstance(retry_state, dict) else set()
    archived_pairs = {
        (hash_of_key(state_key), downloader_of_key(state_key) or str(state.get("downloader") or "").strip())
        for state_key, state in retry_state.items()
        if state_key in archived_keys and isinstance(state, dict)
    }
    items = []
    for record_hash, record in records.items():
        if not isinstance(record, dict):
            continue
        record_hash_part = hash_of_key(record_hash)
        record_dl = str(record.get("downloader") or "").strip() or downloader_of_key(record_hash)
        # 归档按 (hash, 下载器) 隔离；任一侧下载器未知（旧数据）保持旧行为（按 hash 隐藏）
        archived_hit = any(
            archived_hash == record_hash_part and (not record_dl or not archived_dl or archived_dl == record_dl)
            for archived_hash, archived_dl in archived_pairs)
        if record.get("history_hidden") or archived_hit:
            continue
        item = dict(record)
        item["_record_key"] = record_hash
        item["hash"] = item.get("hash") or hash_of_key(record_hash)
        item["downloader"] = str(item.get("downloader") or "").strip()
        items.append(item)
    if result_filter != "all":
        items = [item for item in items if bool(item.get("success")) == (result_filter == "success")]
    items.sort(key=lambda item: str(item["_record_key"]))
    items.sort(key=lambda item: str(item.get("time") or ""), reverse=True)
    for item in items:
        item.pop("_record_key")
    return record_page(items, page, page_size, result_filter)


@serialized_rename_state
def api_delete_rename_history(plugin, hash: str = "", downloader: str = ""):
    """仅隐藏指定历史，保留补刀与恢复依据；同 hash 多下载器时须指明下载器。"""
    records = plugin.get_data(RENAME_RECORDS_KEY) or {}
    found = lookup_record(records, hash, downloader)
    if found["status"] == "ambiguous" or (downloader and found["status"] == "other_downloader"):
        candidates = ", ".join(found.get("candidates") or [])
        return _operation_response(
            {"code": 1, "msg": f"该种子存在多个下载器的记录（{candidates}），请指定下载器", "hash": hash},
            HashActionResult,
        )
    if found["key"] and isinstance(found["record"], dict):
        records[found["key"]]["history_hidden"] = True
        plugin.save_data(RENAME_RECORDS_KEY, records)
        return _operation_response(
            {"code": 0, "msg": "已删除", "hash": hash},
            HashActionResult,
        )
    return _operation_response(
        {"code": 1, "msg": "记录不存在", "hash": hash},
        HashActionResult,
    )


@serialized_rename_state
def api_rename_archive(plugin, page: int = 1, page_size: int = 20, result_filter: str = "all"):
    """返回失败归档；归档本身均为失败，不推导新的成功状态。"""
    if result_filter == "success":
        raise HTTPException(status_code=400, detail="归档记录仅表示失败归档状态，不能推导为成功；result_filter 只支持 all/failed")
    page, page_size, result_filter = record_query(
        page, page_size, result_filter, ("all", "failed"))
    state = plugin.get_data(RENAME_RETRY_STATE_KEY) or {}
    items = []
    for key, item in state.items():
        if isinstance(item, dict) and item.get("archived") and not item.get("display_hidden"):
            entry = dict(item)
            entry["hash"] = hash_of_key(key)
            entry["downloader"] = str(entry.get("downloader") or "").strip() or downloader_of_key(key)
            items.append(entry)
    items.sort(key=lambda item: str(item["hash"]))
    items.sort(key=lambda item: str(item.get("archived_at") or item.get("last_failed_at") or ""), reverse=True)
    return record_page(items, page, page_size, result_filter)
def api_restore_rename_archive(plugin, hash: str = "", downloader: str = ""):
    """恢复归档记录，使其继续参与补刀。"""
    return _operation_response(plugin.restore_rename_archive(hash, downloader), HashActionResult)


def api_delete_rename_archive(plugin, hash: str = "", downloader: str = ""):
    """仅隐藏归档展示，保留自动补刀排除状态。"""
    return _operation_response(plugin.delete_rename_archive(hash, downloader), HashActionResult)
def _cleanup_actions(plugin) -> dict:
    """数据页清理白名单：对象标识 → 清理动作。

    只清插件自身历史/统计/快照，不触碰下载器种子与文件、H&R 安全状态、
    活动队列（transfer_schedule）与上传限速恢复状态（upload_limit_state）。
    """
    from ..modules.autoremove.constants import REMOVER_STATE_DATA_KEY
    from ..modules.autoremove.history import cleared_status, history_removed_count
    from ..modules.failclean.constants import FAILCLEAN_STATUS_DATA_KEY
    from ..modules.failclean.history import cleared_status as failclean_cleared_status
    from ..modules.failclean.history import history_removed_count as failclean_history_removed_count
    from ..modules.rename.archive import clear_rename_archive

    def clear_rename_archive_data() -> int:
        return int(clear_rename_archive(plugin).get("removed", 0) or 0)

    def clear_rename_history() -> int:
        from ..modules.rename.archive import hide_rename_history
        return hide_rename_history(plugin)

    def clear_transfer_stats() -> int:
        removed = 0
        for key in (TRANSFER_STATS_KEY, TRANSFER_SKIP_STATS_KEY):
            data = plugin.get_data(key)
            if data:
                removed += len(data)
                plugin.save_data(key, {})
        return removed

    def clear_remover_state() -> int:
        """清理最近一轮执行状态；服务在用则走服务清理，保证内存与持久化一致。"""
        service = getattr(plugin, "_autoremove_service", None)
        if service is not None:
            outcome = service.clear_history()
            if outcome.get("busy"):
                raise HTTPException(status_code=409, detail="自动删种正在执行，暂不能清理记录")
            return int(outcome.get("removed", 0) or 0)
        raw = plugin.get_data(REMOVER_STATE_DATA_KEY)
        removed = history_removed_count(raw)
        if not removed:
            return 0
        plugin.save_data(REMOVER_STATE_DATA_KEY, cleared_status())
        return removed

    def clear_failclean_status() -> int:
        """清理最近巡检/即时清理结果并保留累计计数；服务在用则走服务清理。"""
        service = getattr(plugin, "_failclean_service", None)
        if service is not None:
            outcome = service.clear_history()
            if outcome.get("busy"):
                raise HTTPException(status_code=409, detail="失败清理巡检正在运行，暂不能清理记录")
            return int(outcome.get("removed", 0) or 0)
        raw = plugin.get_data(FAILCLEAN_STATUS_DATA_KEY)
        removed = failclean_history_removed_count(raw)
        if not removed:
            return 0
        plugin.save_data(FAILCLEAN_STATUS_DATA_KEY, failclean_cleared_status(raw))
        return removed

    return {
        "rename_archive": clear_rename_archive_data,
        "rename_history": clear_rename_history,
        "transfer_stats": clear_transfer_stats,
        "autoremove_state": clear_remover_state,
        "failclean_state": clear_failclean_status,
    }


def api_cleanup_module_data(plugin, payload: CleanupModuleRequest):
    """按白名单清理插件自身历史数据，返回真实清理条数。"""
    body = _request_dict(payload)
    try:
        request = CleanupModuleRequest.model_validate(body)
    except Exception as error:
        raise HTTPException(status_code=400, detail=f"清理请求不合法：{error}") from error
    action = _cleanup_actions(plugin).get(request.module)
    if action is None:
        raise HTTPException(status_code=400, detail=f"未知的数据清理对象：{request.module}")
    removed = action()
    logger.info(f"【PT下载中心】数据清理[{request.module}]：清理 {removed} 条")
    return _operation_response(
        {
            "code": 0,
            "msg": f"已清理 {removed} 条",
            "removed": removed,
            "module": request.module,
        },
        CleanupModuleResult,
    )


@serialized_rename_state
def api_recovery_torrent(plugin, hash: str = "", downloader: str = ""):
    """恢复种子原始名称"""
    _require_module(plugin, "rename", "命名补刀")
    if not hash:
        return _operation_response(
            {"code": 1, "msg": "缺少 hash 参数", "hash": ""},
            HashActionResult,
        )
    records = plugin.get_data(RENAME_RECORDS_KEY) or {}
    found = lookup_record(records, hash, downloader)
    if found["status"] == "ambiguous" or (downloader and found["status"] == "other_downloader"):
        candidates = ", ".join(found.get("candidates") or [])
        return _operation_response(
            {"code": 1, "msg": f"该种子存在多个下载器的记录（{candidates}），请指定下载器", "hash": hash},
            HashActionResult,
        )
    record_key_hit = found["key"]
    record = found["record"] if isinstance(found["record"], dict) else None
    if not record or not record.get("success"):
        return _operation_response(
            {"code": 1, "msg": "未找到成功的重命名记录", "hash": hash},
            HashActionResult,
        )
    original_name = record.get("original_name")
    if not original_name:
        return _operation_response(
            {"code": 1, "msg": "原始名称为空", "hash": hash},
            HashActionResult,
        )

    # 在目标下载器中查找并恢复（记录带 downloader 字段用记录值；旧记录按 hash 唯一定位）
    located = resolve_record_downloader(plugin, hash, record)
    if located["ambiguous"]:
        return _operation_response(
            {"code": 1, "msg": f"该种子在多个下载器中存在（{', '.join(located['candidates'])}），请先移除多余实例中的同名任务", "hash": hash},
            HashActionResult,
        )
    to_service = located["service"] or get_downloader_service(plugin._todownloader)
    if not to_service or not to_service.instance:
        return _operation_response(
            {"code": 1, "msg": "未能在任何已配置下载器中找到该种子", "hash": hash},
            HashActionResult,
        )
    try:
        dl = to_service.instance
        dl_type = to_service.type

        if observe_skip(plugin, "rename", "恢复原名", f"{hash} → {original_name}"):
            return _operation_response(
                {"code": 1, "msg": "观察模式：未执行恢复原名（仅预览）", "hash": hash, "observed": True},
                HashActionResult,
            )
        if dl_type == "qbittorrent":
            dl.qbc.torrents_rename(torrent_hash=hash, new_torrent_name=original_name)
        else:
            dl.rename_torrent(hash, original_name)

        # 更新记录
        record["after_name"] = original_name
        record["success"] = True
        record["downloader"] = getattr(to_service, "name", "") or record.get("downloader", "")
        record["time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if record_key_hit:
            records[record_key_hit] = record
            plugin.save_data(RENAME_RECORDS_KEY, records)
        logger.info(f"【PT下载中心】种子恢复成功: {hash} → {original_name}")
        return _operation_response(
            {"code": 0, "msg": f"已恢复为: {original_name}", "hash": hash},
            HashActionResult,
        )
    except Exception as e:
        logger.error(f"【PT下载中心】种子恢复失败: {e}")
        return _operation_response(
            {"code": 1, "msg": str(e), "hash": hash},
            HashActionResult,
        )


def api_hr_tasks(plugin):
    """返回 H&R 任务列表与汇总。

    模块初始化被隔离（服务为 None）时返回空列表而不是 500：前端会无条件轮询本端点，
    一个模块不可用不应让数据页整体报错（模块独立性）。
    """
    service = getattr(plugin, "_hr_service", None)
    if service is None:
        return HrTasksResult.model_validate({"tasks": [], "summary": {}})
    try:
        return HrTasksResult.model_validate(service.get_service_infos())
    except Exception as e:
        _raise_query_error("H&R 任务查询失败", e)


def _require_hr_service(plugin):
    """取 H&R 服务实例，被隔离时抛出与门控一致的可读错误。"""
    service = getattr(plugin, "_hr_service", None)
    if service is None:
        raise HTTPException(status_code=400, detail="「H&R 助手」未启用或初始化失败（查看插件日志）")
    return service


def api_hr_skip_stats(plugin):
    """返回 H&R 保护在四条破坏性路径上的跳过计数。"""
    try:
        return HrSkipStatsResult.model_validate({"skip_stats": HrGuard().get_skip_stats()})
    except Exception as e:
        _raise_query_error("H&R 跳过计数查询失败", e)


def api_hr_presets(plugin):
    """返回内置 H&R 站点验证预设（只读，未设置字段已剔除，供前端显示继承值）。"""
    try:
        presets = [
            {"site_name": name, "rule": json.loads(rule.model_dump_json(exclude_none=True))}
            for name, rule in load_preset_rules().items()
        ]
        return HrPresetsResult.model_validate({"presets": presets})
    except Exception as e:
        _raise_query_error("H&R 预设查询失败", e)

def api_hr_check(plugin):
    """立即执行一轮 H&R 状态检查。"""
    _require_module(plugin, "hr", "H&R 助手")
    service = _require_hr_service(plugin)
    try:
        result = service.check_tasks("手动")
    except Exception as e:
        logger.error(f"【PT下载中心】H&R 状态检查失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"H&R 状态检查失败: {e}"}, HrActionResult
        )
    return _operation_response(
        {"code": 0, "msg": "H&R 状态检查完成", "result": result}, HrActionResult
    )


def api_hr_scan(plugin):
    """立即执行一轮 H&R 自动发现与状态检查。"""
    _require_module(plugin, "hr", "H&R 助手")
    service = _require_hr_service(plugin)
    try:
        result = service.run_scan("手动")
    except Exception as e:
        logger.error(f"【PT下载中心】H&R 全量扫描失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"H&R 全量扫描失败: {e}"}, HrActionResult
        )
    return _operation_response(
        {"code": 0, "msg": "H&R 全量扫描完成", "result": result}, HrActionResult
    )


def api_hr_clear_task(plugin, payload: HrClearTaskRequest):
    """清除单条已结束的 H&R 记录。"""
    request = _request_dict(payload)
    service = _require_hr_service(plugin)
    try:
        cleared = service.clear_task(
            request.get("downloader_id") or "",
            request.get("torrent_hash") or "",
        )
    except Exception as e:
        logger.error(f"【PT下载中心】H&R 记录清除失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"H&R 记录清除失败: {e}"}, HrActionResult
        )
    if not cleared:
        return _operation_response(
            {"code": 1, "msg": "未找到可清除的 H&R 记录"}, HrActionResult
        )
    return _operation_response({"code": 0, "msg": "已清除 H&R 记录"}, HrActionResult)


def api_hr_clear_compliant(plugin, payload: EmptyRequest | None = None):
    """批量清除已满足的 H&R 记录。"""
    service = _require_hr_service(plugin)
    try:
        cleared = service.clear_compliant()
    except Exception as e:
        logger.error(f"【PT下载中心】H&R 已满足记录清除失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"H&R 已满足记录清除失败: {e}"}, HrActionResult
        )
    return _operation_response(
        {"code": 0, "msg": f"已清除 {cleared} 条已满足记录", "cleared": cleared},
        HrActionResult,
    )


def api_hr_clear_missing(plugin, payload: EmptyRequest | None = None):
    """批量清除种子已不在下载器的 H&R 记录。"""
    service = _require_hr_service(plugin)
    try:
        cleared = service.clear_missing()
    except Exception as e:
        logger.error(f"【PT下载中心】H&R 需做种记录清除失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"H&R 需做种记录清除失败: {e}"}, HrActionResult
        )
    return _operation_response(
        {"code": 0, "msg": f"已清除 {cleared} 条需做种记录", "cleared": cleared},
        HrActionResult,
    )


def api_autoremove_status(plugin):
    """返回自动删种模块运行状态。"""
    service = getattr(plugin, "_autoremove_service", None)
    status = service.get_module_status() if service is not None else {}
    return ModuleStatusResult(code=0, status=status)


def api_autoremove_run(plugin, payload: EmptyRequest | None = None):
    """手动执行一轮自动删种。"""
    _require_module(plugin, "autoremove", "自动删种")
    service = getattr(plugin, "_autoremove_service", None)
    if service is None:
        raise HTTPException(status_code=500, detail="自动删种服务未初始化")
    result = service.run_cycle(trigger_source="手动")
    return _operation_response({"code": 0, "msg": "执行完成", "result": result}, ModuleActionResult)


def api_autoremove_preview(plugin, payload: EmptyRequest | None = None):
    """只列自动删种候选，不执行下载器写操作。"""
    service = getattr(plugin, "_autoremove_service", None)
    if service is None:
        raise HTTPException(status_code=500, detail="自动删种服务未初始化")
    result = service.collect_candidates(trigger_source="候选预览")
    return _operation_response({"code": 0, "msg": "候选已生成", "result": result}, ModuleActionResult)


def api_failclean_status(plugin):
    """返回整理失败清理模块运行状态。"""
    service = getattr(plugin, "_failclean_service", None)
    status = service.get_module_status() if service is not None else {}
    return ModuleStatusResult(code=0, status=status)


def api_failclean_scan(plugin, payload: EmptyRequest | None = None):
    """手动执行一轮重复下载残留巡检清理。"""
    _require_module(plugin, "failclean", "失败清理")
    service = getattr(plugin, "_failclean_service", None)
    if service is None:
        raise HTTPException(status_code=500, detail="整理失败清理服务未初始化")
    result = service.cleanup_repeat_sources(trigger_source="手动")
    return _operation_response({"code": 0, "msg": "巡检完成", "result": result}, ModuleActionResult)


def api_transfer_run(plugin, payload: EmptyRequest | None = None):
    """后台线程触发一轮转移做种，立即返回。

    整轮转移在种子多时会长达数分钟（120 个种子的实测超过 180s），同步执行会让调用方
    读超时——前端表现为「点了没反应」，实际服务端还在跑。与 /retry_renames、/rename_scan
    保持一致：后台执行 + 防重入，进度看数据页与插件日志。
    """
    logger.info("【PT下载中心】收到手动转移做种请求")
    _require_module(plugin, "transfer", "转移做种")
    if not plugin._transfer_active:
        logger.warning("【PT下载中心】手动转移被拒：转移做种未就绪（检查插件总开关、转移做种开关、源/目标下载器与种子文件路径）")
        return _operation_response(
            {"code": 1, "msg": "转移做种未就绪：请检查源/目标下载器与种子文件路径"},
            ModuleActionResult,
        )

    def _run_transfer():
        try:
            plugin.transfer(trigger_source="手动")
            logger.info("【PT下载中心】手动转移完成")
        except Exception as e:
            logger.error(f"【PT下载中心】转移做种执行失败: {e}")
        finally:
            plugin._transfer_manual_running = False

    with plugin._transfer_manual_lock:
        if plugin._transfer_manual_running:
            return _operation_response(
                {"code": 1, "msg": "转移做种已在后台运行，请稍后查看数据页"},
                ModuleActionResult,
            )
        plugin._transfer_manual_running = True

    threading.Thread(target=_run_transfer, daemon=True, name="dml-transfer-manual").start()
    return _operation_response(
        {"code": 0, "msg": "转移做种已开始，正在后台处理，进度见数据页与日志", "running": True},
        ModuleActionResult,
    )


def _transfer_record_key(value: dict) -> bool:
    """识别转移事务写下的来源-目标记录（基础插件字段）。"""
    return bool(value.get("source_hash") and value.get("transfer_state"))


def _iter_transfer_records(plugin):
    """遍历插件持久化的转移事务记录。

    记录以 `f"{源下载器}-{源种子哈希}"` 为 key 分散保存（见
    ``modules/transfer/pipeline.py 的 save_source_record``），没有聚合索引，
    因此需要枚举插件全部数据后按字段筛选。`get_data()` 无参调用在不同
    MoviePilot 版本返回 dict 或 ORM 行列表，这里两种形态都兼容。
    """
    try:
        raw = plugin.get_data()
    except Exception as e:
        logger.warning(f"【PT下载中心:转移做种】读取插件数据失败：{e}")
        return
    if isinstance(raw, dict):
        items = list(raw.items())
    else:
        items = []
        for row in raw or []:
            try:
                items.append((row.key, row.value))
            except Exception:
                continue
    for key, value in items:
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        if _transfer_record_key(value):
            yield key, value


def api_transfer_status(plugin, page: int = 1, page_size: int = 20, result_filter: str = "all"):
    """返回转移任务、在途事务与记录；统计保持全量口径。

    互斥结果分类：success 为 completed 且不属于删源未完成；failed 仅 failed
    终态；rollback = 回滚中或已回滚（rollback/rolled_back）；source_pending 为已请求删源
    但尚未删除、阶段 target_ready/completed（含 H&R 保护）。筛选不改真实阶段，
    不把 rolled_back/verifying 等阶段当作终态失败，all 仍返回全部。
    """
    from ..model.state import TRANSFER_SKIP_STATS_KEY, load_transfer_stats
    from ..modules.transfer.recheck import load_seed_recheck_queue
    from ..modules.transfer.tasks import load_transfer_tasks

    page, page_size, result_filter = record_query(
        page, page_size, result_filter, ("all", "success", "failed", "source_pending", "rollback"))
    now = time.time()

    def flag_projection(task):
        from ..modules.transfer.tasks import resolve_task_flag

        projection = {}
        for field in ("delete_source", "delete_duplicate"):
            effective, origin = resolve_task_flag(
                task, field, getattr(plugin, f"_transfer_{field}_default", False),
            )
            projection[f"{field}_effective"] = effective
            projection[f"{field}_origin"] = origin
        return projection

    task_rows = [
        {
            "name": task["name"],
            "enabled": bool(task["enabled"]),
            "from_downloader": task["from_downloader"],
            "to_downloader": task["to_downloader"],
            "include_category": task["include_category"],
            "include_labels": task["include_labels"],
            "exclude_labels": task["exclude_labels"],
            "from_path": task["from_path"],
            "to_path": task["to_path"],
            "delete_source": task.get("delete_source"),
            **flag_projection(task),
            "delete_duplicate": task.get("delete_duplicate"),
            "keep_category": bool(task["keep_category"]),
            "keep_tag": bool(task["keep_tag"]),
            "empty_label_ok": bool(task["empty_label_ok"]),
            "no_paths": task["no_paths"],
            "transfer_tag": task["transfer_tag"],
        }
        for task in load_transfer_tasks(plugin)
    ]

    pending = []
    for key, item in (load_seed_recheck_queue(plugin) or {}).items():
        if not isinstance(item, dict):
            continue
        created_at = float(item.get("created_at") or now)
        pending.append({
            "key": key,
            "task": item.get("task") or "",
            "source_downloader": item.get("source_downloader") or "",
            "downloader": item.get("downloader") or "",
            "source_hash": item.get("source_hash") or "",
            "source_name": str(item.get("source_name") or ""),
            "hash": item.get("hash") or "",
            "phase": item.get("phase") or "",
            "fallback": bool(item.get("fallback")),
            "skipverify": bool(item.get("skipverify")),
            "autostart": bool(item.get("autostart")),
            "delete_source": bool(item.get("delete_source_requested")),
            "waited_minutes": round(max(0.0, (now - created_at) / 60), 1),
        })
    pending.sort(key=lambda row: row["waited_minutes"], reverse=True)

    records = []
    for key, value in _iter_transfer_records(plugin):
        records.append({
            "_record_key": key,
            "_history_hidden": bool(value.get("history_hidden")),
            "_source_pending": bool(
                value.get("delete_source_requested") and not value.get("delete_source")
                and value.get("transfer_state") in ("target_ready", "completed")
            ),
            "task": value.get("task") or "",
            "source_downloader": value.get("source_downloader") or key.split("-", 1)[0],
            "source_hash": value.get("source_hash") or "",
            "source_name": str(value.get("source_name") or ""),
            "downloader": value.get("to_download") or value.get("downloader") or "",
            "hash": value.get("to_download_id") or value.get("hash") or "",
            "phase": value.get("transfer_state") or "",
            "delete_source": bool(value.get("delete_source")),
            "hr_protected": bool(value.get("hr_protected")),
            "fallback": bool(value.get("fallback")),
            "updated_at": float(value.get("updated_at") or 0),
            "error": value.get("error") or "",
            "attempts": value.get("attempts") or 0,
            "created_at": value.get("created_at") or 0,
            "delete_source_pending": bool(value.get("delete_source_requested") and not value.get("delete_source")),
        })
    records.sort(key=lambda row: row["_record_key"])
    records.sort(key=lambda row: row["updated_at"], reverse=True)
    filtered = [row for row in records if not row["_history_hidden"] and (
        result_filter == "all"
        or (result_filter == "success" and row["phase"] == "completed" and not row["_source_pending"])
        or (result_filter == "failed" and row["phase"] == "failed")
        or (result_filter == "rollback" and row["phase"] in ("rollback", "rolled_back"))
        or (result_filter == "source_pending" and row["_source_pending"])
    )]
    for row in records:
        row.pop("_history_hidden")
        row.pop("_record_key")
        row.pop("_source_pending")
    pagination = record_page(filtered, page, page_size, result_filter)
    stats = load_transfer_stats(plugin)
    skip_stats = plugin.get_data(TRANSFER_SKIP_STATS_KEY)
    skip_stats = skip_stats if isinstance(skip_stats, dict) else {}

    status = {
        "tasks": task_rows,
        "pending": pending,
        "records": pagination["items"],
        **pagination,
        "summary": {
            "pending": len(pending),
            "rollback": sum(1 for row in records if row["phase"] in ("rollback", "rolled_back")),
            "completed": sum(1 for row in records if row["phase"] == "completed"),
            "today_failed": stats.get("failure_today_count", 0),
            "today_success": stats.get("today_success", 0),
            "success_total": stats.get("success_total", 0),
            "today_fallback": stats.get("today_fallback", 0),
            "fallback_success": stats.get("fallback_success", 0),
            "hr_protected": int(skip_stats.get("hr_protected", 0) or 0),
        },
    }
    return {"code": 0, "status": status, **pagination}


def api_tag_complement(plugin, payload: EmptyRequest | None = None):
    """手动执行一轮站点标签历史补全（与 tag_interval_cron 定时任务同一服务入口）。"""
    _require_module(plugin, "tag", "站点标签")
    try:
        result = complement_history(plugin)
    except Exception as e:
        logger.error(f"【PT下载中心】站点标签历史补全失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"站点标签历史补全失败: {e}"}, ModuleActionResult
        )
    return _operation_response(
        {"code": 0, "msg": "站点标签历史补全完成", "result": result},
        ModuleActionResult,
    )


def api_tag_status(plugin):
    """返回站点标签增强模块运行状态。"""
    from ..modules.sitetag.service import get_module_status as site_tag_module_status

    return ModuleStatusResult(code=0, status=site_tag_module_status(plugin))


def api_rename_status(plugin):
    """返回命名补刀模块运行状态。"""
    from ..modules.rename.service import get_module_status as rename_module_status

    status = rename_module_status(plugin)
    status["batch_running"] = bool(getattr(plugin, "_rename_batch_running", False))
    return ModuleStatusResult(code=0, status=status)
def api_execution_history(plugin, module: str = "", page: int = 1, page_size: int = 20, result_filter: str = "all"):

    """分页返回指定模块的展示历史；未初始化（尚无新记录）与空结果可区分。"""

    from ..model import execution_history

    page, page_size, result_filter = record_query(

        page, page_size, result_filter, execution_history.HISTORY_FILTERS)

    try:

        snapshot = execution_history.query(plugin, module, result_filter)

    except execution_history.HistoryRecordError as error:

        raise HTTPException(status_code=400, detail=str(error)) from error

    except Exception as error:

        _raise_query_error("展示历史查询失败", error)

    result = record_page(snapshot["items"], page, page_size, result_filter)

    result["stream"] = module

    result["initialized"] = snapshot["initialized"]

    result["note"] = "" if snapshot["initialized"] else "尚无新记录"

    return result


def api_execution_history_clear(plugin, payload: CleanupModuleRequest):

    """清空指定模块的展示历史（不影响业务/保护/恢复数据）。"""

    from ..model import execution_history

    body = _request_dict(payload)

    try:

        request = CleanupModuleRequest.model_validate(body)

    except Exception as error:

        raise HTTPException(status_code=400, detail=f"清理请求不合法：{error}") from error

    try:

        removed = execution_history.clear(plugin, request.module)

    except execution_history.HistoryRecordError as error:

        raise HTTPException(status_code=400, detail=str(error)) from error

    logger.info(f"【PT下载中心】展示历史清理[{request.module}]：清理 {removed} 条")

    return _operation_response(

        {"code": 0, "msg": f"已清理 {removed} 条", "removed": removed, "module": request.module},

        CleanupModuleResult,

    )
