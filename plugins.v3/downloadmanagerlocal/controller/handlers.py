"""下载管理插件 - API 路由实现"""

from datetime import datetime
from typing import TypeVar

from app import schemas
from app.sdk.logging import logger
from fastapi import HTTPException
from pydantic import BaseModel

from ..adapter.moviepilot import get_downloader_service, list_builtin_sites
from ..model.api import (
    ApiBusinessModel,
    DiagnosticsResult,
    EmptyRequest,
    HashActionResult,
    HrActionResult,
    HrClearTaskRequest,
    HrSkipStatsResult,
    HrTasksResult,
    ModuleActionResult,
    ModuleStatusResult,
    OverviewResult,
    RenamePageResult,
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
    load_transfer_stats,
)
from ..service.archive import serialized_rename_state
from ..service.hr.guard import HrGuard
from ..service.site_tag import execute_tag_cleanup, scan_and_clean_tags
from ..service.upload_limit_worker import stop_upload_limit_worker
from ..service.upload_limiter import (
    get_upload_limit_status,
    persist_upload_limit_site_rules,
    restore_upload_limits,
    run_upload_limit_cycle,
    scan_upload_limit_site_tags,
)

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
        success=code != 1,
        message=message,
        data=data,
    )


def _raise_query_error(summary: str, error: Exception) -> None:
    """把查询端点异常转换为明确的 HTTP 500。"""
    logger.error(f"{summary}: {error}")
    raise HTTPException(status_code=500, detail=str(error)) from error
def _require_module(plugin, module: str, label: str) -> None:
    """模块核心执行端点的统一门控：总开关与模块开关任一关闭即拒绝（utils/config.py 注册表口径）。"""
    from ..utils.config import MODULE_SWITCHES
    attr = MODULE_SWITCHES[module][1]
    if not getattr(plugin, attr, False):
        raise HTTPException(status_code=400, detail=f"「{label}」未启用（检查插件总开关与模块开关）")



def api_retry_renames(plugin):
    """手动触发失败历史和脏名称种子的批量补刮。"""
    _require_module(plugin, "rename", "命名补刀")
    try:
        return _operation_response(plugin._retry_pending_renames(), RetryRenamesResult)
    except Exception as e:
        logger.error(f"一键补刀失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"补刀失败: {e}", "history": 0, "dirty": 0, "total": 0},
            RetryRenamesResult,
        )


def api_retry_rename(plugin, hash: str = ""):
    """对指定种子 hash 手动重试重命名和站点标签。"""
    _require_module(plugin, "rename", "命名补刀")
    try:
        return _operation_response(plugin._retry_rename(hash), HashActionResult)
    except Exception as e:
        logger.error(f"单条补刀失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"补刀失败: {e}", "hash": hash or ""},
            HashActionResult,
        )


def api_diagnostics(plugin):
    """返回详情页使用的只读诊断摘要。"""
    try:
        return DiagnosticsResult.model_validate(plugin._diagnostics())
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
            {"code": 0 if not result.get("errors") else 2, "msg": "上传额度已重新分配", **result},
            UploadLimitReallocateResult,
        )
    except Exception as e:
        logger.error(f"上传额度重新分配失败: {e}")
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
        request_rules = request.get("rules")
        rules = dict(
            request_rules
            if isinstance(request_rules, dict)
            else (getattr(plugin, "_upload_limit_site_rules", {}) or {})
        )
        for item in result.get("items") or []:
            name = str(item.get("name") or "").strip()
            if name:
                rules.setdefault(name, {"limit_kib": 0})
        result["rules"] = persist_upload_limit_site_rules(plugin, rules)
        result["msg"] = "站点标签扫描完成，策略已立即生效" if result.get("code") == 0 else result.get("msg")
        return _operation_response(result, UploadLimitSiteTagsResult)
    except Exception as e:
        logger.error(f"上传限速站点标签扫描失败: {e}")
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
        logger.error(f"上传限速站点策略保存失败: {e}")
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
        logger.error(f"停用并恢复上传限速失败: {e}")
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
        result = [{"title": site.name, "value": site.id}
                  for site in list_builtin_sites()]
        return [SelectionItem.model_validate(item) for item in result]
    except Exception as e:
        _raise_query_error("获取站点列表失败", e)


def api_tag_cleanup_scan(plugin, payload: TagCleanupScanRequest):
    """扫描所选 qBittorrent 下载器并自动清理明确的临时标签。"""
    try:
        request = _request_dict(payload)
        result = scan_and_clean_tags(plugin, request.get("downloaders") or [])
        return _operation_response(result, TagCleanupScanResult)
    except Exception as e:
        logger.error(f"标签清理扫描失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"扫描失败: {e}", "downloaders": [], "auto_removed": [], "errors": []},
            TagCleanupScanResult,
        )


def api_tag_cleanup_execute(plugin, payload: TagCleanupExecuteRequest):
    """按用户确认的扫描快照清理其余标签。"""
    _require_module(plugin, "tag", "站点标签")
    try:
        request = _request_dict(payload)
        result = execute_tag_cleanup(plugin, request.get("removals") or [])
        return _operation_response(result, TagCleanupExecuteResult)
    except Exception as e:
        logger.error(f"标签清理执行失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"清理失败: {e}", "removed": [], "failed": []},
            TagCleanupExecuteResult,
        )


def api_rename_history(plugin, page: int = 1, page_size: int = 15):
    """返回重命名历史记录（支持分页）"""
    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 15)))
    records = plugin.get_data(RENAME_RECORDS_KEY) or {}
    retry_state = plugin.get_data(RENAME_RETRY_STATE_KEY) or {}
    archived_hashes = {
        record_hash
        for record_hash, state in retry_state.items()
        if isinstance(state, dict) and state.get("archived")
    } if isinstance(retry_state, dict) else set()
    items = []
    for record_hash, record in records.items():
        if not isinstance(record, dict):
            continue
        if record_hash in archived_hashes:
            continue
        item = dict(record)
        item["hash"] = item.get("hash") or record_hash
        items.append(item)
    all_items = sorted(items, key=lambda x: x.get("time", ""), reverse=True)
    total = len(all_items)
    start = (page - 1) * page_size
    end = start + page_size
    return RenamePageResult.model_validate({
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
        "items": all_items[start:end]
    })


@serialized_rename_state
def api_delete_rename_history(plugin, hash: str = ""):
    """删除指定 hash 的重命名记录"""
    records = plugin.get_data(RENAME_RECORDS_KEY) or {}
    if hash in records:
        del records[hash]
        plugin.save_data(RENAME_RECORDS_KEY, records)
        return _operation_response(
            {"code": 0, "msg": "已删除", "hash": hash},
            HashActionResult,
        )
    return _operation_response(
        {"code": 1, "msg": "记录不存在", "hash": hash},
        HashActionResult,
    )


def api_rename_archive(plugin, page: int = 1, page_size: int = 15):
    """返回补刀归档记录（支持分页）。"""
    return RenamePageResult.model_validate(plugin.list_rename_archive(page, page_size))


def api_restore_rename_archive(plugin, hash: str = ""):
    """恢复归档记录，使其继续参与补刀。"""
    return _operation_response(plugin.restore_rename_archive(hash), HashActionResult)


def api_delete_rename_archive(plugin, hash: str = ""):
    """删除归档状态记录。"""
    return _operation_response(plugin.delete_rename_archive(hash), HashActionResult)


@serialized_rename_state
def api_recovery_torrent(plugin, hash: str = ""):
    """恢复种子原始名称"""
    _require_module(plugin, "rename", "命名补刀")
    if not hash:
        return _operation_response(
            {"code": 1, "msg": "缺少 hash 参数", "hash": ""},
            HashActionResult,
        )
    records = plugin.get_data(RENAME_RECORDS_KEY) or {}
    record = records.get(hash)
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

    # 在目标下载器中查找并恢复
    try:
        to_service = get_downloader_service(plugin._todownloader)
        if not to_service or not to_service.instance:
            return _operation_response(
                {"code": 1, "msg": f"下载器 {plugin._todownloader} 不存在", "hash": hash},
                HashActionResult,
            )
        dl = to_service.instance
        dl_type = to_service.type

        if dl_type == "qbittorrent":
            dl.qbc.torrents_rename(torrent_hash=hash, new_torrent_name=original_name)
        else:
            dl.rename_torrent(hash, original_name)

        # 更新记录
        record["after_name"] = original_name
        record["success"] = True
        record["time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        records[hash] = record
        plugin.save_data(RENAME_RECORDS_KEY, records)
        logger.info(f"种子恢复成功: {hash} → {original_name}")
        return _operation_response(
            {"code": 0, "msg": f"已恢复为: {original_name}", "hash": hash},
            HashActionResult,
        )
    except Exception as e:
        logger.error(f"种子恢复失败: {e}")
        return _operation_response(
            {"code": 1, "msg": str(e), "hash": hash},
            HashActionResult,
        )


def api_hr_tasks(plugin):
    """返回 H&R 任务列表与汇总。"""
    try:
        return HrTasksResult.model_validate(plugin._hr_service.get_service_infos())
    except Exception as e:
        _raise_query_error("H&R 任务查询失败", e)


def api_hr_skip_stats(plugin):
    """返回 H&R 保护在四条破坏性路径上的跳过计数。"""
    try:
        return HrSkipStatsResult.model_validate({"skip_stats": HrGuard().get_skip_stats()})
    except Exception as e:
        _raise_query_error("H&R 跳过计数查询失败", e)


def api_hr_check(plugin):
    """立即执行一轮 H&R 状态检查。"""
    _require_module(plugin, "hr", "H&R 助手")
    try:
        result = plugin._hr_service.check_tasks("手动")
    except Exception as e:
        logger.error(f"H&R 状态检查失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"H&R 状态检查失败: {e}"}, HrActionResult
        )
    return _operation_response(
        {"code": 0, "msg": "H&R 状态检查完成", "result": result}, HrActionResult
    )


def api_hr_scan(plugin):
    """立即执行一轮 H&R 自动发现与状态检查。"""
    _require_module(plugin, "hr", "H&R 助手")
    try:
        result = plugin._hr_service.run_scan("手动")
    except Exception as e:
        logger.error(f"H&R 全量扫描失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"H&R 全量扫描失败: {e}"}, HrActionResult
        )
    return _operation_response(
        {"code": 0, "msg": "H&R 全量扫描完成", "result": result}, HrActionResult
    )


def api_hr_clear_task(plugin, payload: HrClearTaskRequest):
    """清除单条已结束的 H&R 记录。"""
    request = _request_dict(payload)
    try:
        cleared = plugin._hr_service.clear_task(
            request.get("downloader_id") or "",
            request.get("torrent_hash") or "",
        )
    except Exception as e:
        logger.error(f"H&R 记录清除失败: {e}")
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
    try:
        cleared = plugin._hr_service.clear_compliant()
    except Exception as e:
        logger.error(f"H&R 已满足记录清除失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"H&R 已满足记录清除失败: {e}"}, HrActionResult
        )
    return _operation_response(
        {"code": 0, "msg": f"已清除 {cleared} 条已满足记录", "cleared": cleared},
        HrActionResult,
    )


def api_hr_clear_missing(plugin, payload: EmptyRequest | None = None):
    """批量清除种子已不在下载器的 H&R 记录。"""
    try:
        cleared = plugin._hr_service.clear_missing()
    except Exception as e:
        logger.error(f"H&R 需做种记录清除失败: {e}")
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


def api_tag_status(plugin):
    """返回站点标签增强模块运行状态。"""
    from ..service.site_tag import get_module_status as site_tag_module_status

    return ModuleStatusResult(code=0, status=site_tag_module_status(plugin))


def api_rename_status(plugin):
    """返回命名补刀模块运行状态。"""
    from ..service.rename import get_module_status as rename_module_status

    return ModuleStatusResult(code=0, status=rename_module_status(plugin))
