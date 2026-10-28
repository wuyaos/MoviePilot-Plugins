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
from ..model.api import (
    ApiBusinessModel,
    DiagnosticsResult,
    EmptyRequest,
    HashActionResult,
    HrActionResult,
    HrClearTaskRequest,
    HrPresetsResult,
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
from ..service.hr.rules import load_preset_rules
from ..service.site_tag import complement_history, execute_tag_cleanup, scan_and_clean_tags
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
    logger.error(f"[PT下载中心]{summary}: {error}")
    raise HTTPException(status_code=500, detail=str(error)) from error
def _require_module(plugin, module: str, label: str) -> None:
    """模块核心执行端点的统一门控：总开关与模块开关任一关闭即拒绝（utils/config.py 注册表口径）。"""
    from ..utils.config import MODULE_SWITCHES
    attr = MODULE_SWITCHES[module][1]
    if not getattr(plugin, attr, False):
        logger.warning(f"[PT下载中心]{label}端点被拒：模块开关未启用（{attr}=False）")
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
            logger.info(f"【PT下载中心:命名补刀】后台批量补刀完成: {result}")
        except Exception as e:
            logger.error(f"【PT下载中心:命名补刀】后台批量补刀失败: {e}")
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
    from ..service.rename import scan_renames

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
            logger.info(f"【PT下载中心:命名补刀】手动扫描完成: {result}")
        except Exception as e:
            logger.error(f"【PT下载中心:命名补刀】手动扫描失败: {e}")
        finally:
            plugin._rename_scan_running = False

    threading.Thread(target=_run_scan, daemon=True, name="dml-rename-scan").start()
    return _operation_response(
        {"code": 0, "msg": "扫描已开始，正在后台处理，结果见重命名历史", "running": True},
        RetryRenamesResult,
    )


def api_retry_rename(plugin, hash: str = ""):
    """对指定种子 hash 手动重试重命名和站点标签。"""
    _require_module(plugin, "rename", "命名补刀")
    try:
        return _operation_response(plugin._retry_rename(hash), HashActionResult)
    except Exception as e:
        logger.error(f"[PT下载中心]单条补刀失败: {e}")
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
        logger.error(f"[PT下载中心]上传额度重新分配失败: {e}")
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
        logger.error(f"[PT下载中心]上传限速站点标签扫描失败: {e}")
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
        logger.error(f"[PT下载中心]上传限速站点策略保存失败: {e}")
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
        logger.error(f"[PT下载中心]停用并恢复上传限速失败: {e}")
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
    """扫描所选 qBittorrent 下载器并自动清理明确的临时标签。"""
    # 扫描兼有写操作（自动移除临时标签），与 execute 同按执行类端点门控。
    _require_module(plugin, "tag", "站点标签")
    try:
        request = _request_dict(payload)
        result = scan_and_clean_tags(plugin, request.get("downloaders") or [])
        return _operation_response(result, TagCleanupScanResult)
    except Exception as e:
        logger.error(f"[PT下载中心]标签清理扫描失败: {e}")
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
        logger.error(f"[PT下载中心]标签清理执行失败: {e}")
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
        logger.info(f"[PT下载中心]种子恢复成功: {hash} → {original_name}")
        return _operation_response(
            {"code": 0, "msg": f"已恢复为: {original_name}", "hash": hash},
            HashActionResult,
        )
    except Exception as e:
        logger.error(f"[PT下载中心]种子恢复失败: {e}")
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
    try:
        result = plugin._hr_service.check_tasks("手动")
    except Exception as e:
        logger.error(f"[PT下载中心]H&R 状态检查失败: {e}")
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
        logger.error(f"[PT下载中心]H&R 全量扫描失败: {e}")
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
        logger.error(f"[PT下载中心]H&R 记录清除失败: {e}")
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
        logger.error(f"[PT下载中心]H&R 已满足记录清除失败: {e}")
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
        logger.error(f"[PT下载中心]H&R 需做种记录清除失败: {e}")
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
    """手动执行一轮转移做种（替代已删除的 onlyonce 立即运行开关）。"""
    logger.info("[PT下载中心]收到手动转移做种请求")
    _require_module(plugin, "transfer", "转移做种")
    if not plugin._transfer_active:
        logger.warning("[PT下载中心]手动转移被拒：转移做种未就绪（检查插件总开关、转移做种开关、源/目标下载器与种子文件路径）")
        return _operation_response(
            {"code": 1, "msg": "转移做种未就绪：请检查源/目标下载器与种子文件路径"},
            ModuleActionResult,
        )
    try:
        plugin.transfer(trigger_source="手动")
    except Exception as e:
        logger.error(f"[PT下载中心]转移做种执行失败: {e}")
        return _operation_response({"code": 1, "msg": f"转移做种失败: {e}"}, ModuleActionResult)
    return _operation_response({"code": 0, "msg": "转移做种已执行"}, ModuleActionResult)


def _transfer_record_key(value: dict) -> bool:
    """识别转移事务写下的来源-目标记录（基础插件字段）。"""
    return bool(value.get("source_hash") and value.get("transfer_state"))


def _iter_transfer_records(plugin):
    """遍历插件持久化的转移事务记录。

    记录以 `f"{源下载器}-{源种子哈希}"` 为 key 分散保存（见
    ``service/transfer_pipeline.save_source_record``），没有聚合索引，
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


def api_transfer_status(plugin, page: int = 1, page_size: int = 15):
    """返回转移做种数据页：任务配置、在途事务、最近记录与汇总。"""
    from ..model.state import TRANSFER_SKIP_STATS_KEY, load_transfer_stats
    from ..service.recheck import load_seed_recheck_queue
    from ..service.transfer_tasks import load_transfer_tasks

    try:
        page = max(1, int(page or 1))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = min(100, max(1, int(page_size or 15)))
    except (TypeError, ValueError):
        page_size = 15
    now = time.time()

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
            "delete_source": bool(task["delete_source"]),
            "delete_duplicate": bool(task["delete_duplicate"]),
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
            "task": value.get("task") or "",
            "source_downloader": value.get("source_downloader") or key.split("-", 1)[0],
            "source_hash": value.get("source_hash") or "",
            "downloader": value.get("to_download") or value.get("downloader") or "",
            "hash": value.get("to_download_id") or value.get("hash") or "",
            "phase": value.get("transfer_state") or "",
            "delete_source": bool(value.get("delete_source")),
            "hr_protected": bool(value.get("hr_protected")),
            "fallback": bool(value.get("fallback")),
            "updated_at": float(value.get("updated_at") or 0),
        })
    records.sort(key=lambda row: row["updated_at"], reverse=True)
    total = len(records)
    start = (page - 1) * page_size
    stats = load_transfer_stats(plugin)
    skip_stats = plugin.get_data(TRANSFER_SKIP_STATS_KEY)
    skip_stats = skip_stats if isinstance(skip_stats, dict) else {}

    return ModuleStatusResult(code=0, status={
        "tasks": task_rows,
        "pending": pending,
        "records": records[start:start + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
        "summary": {
            "pending": len(pending),
            "rollback": sum(1 for row in pending if row["phase"] == "rollback"),
            "completed": sum(1 for row in records if row["phase"] == "completed"),
            "today_success": stats.get("today_success", 0),
            "success_total": stats.get("success_total", 0),
            "today_fallback": stats.get("today_fallback", 0),
            "fallback_success": stats.get("fallback_success", 0),
            "hr_protected": int(skip_stats.get("hr_protected", 0) or 0),
        },
    })


def api_tag_complement(plugin, payload: EmptyRequest | None = None):
    """手动执行一轮站点标签历史补全（与 tag_interval_cron 定时任务同一服务入口）。"""
    _require_module(plugin, "tag", "站点标签")
    try:
        result = complement_history(plugin)
    except Exception as e:
        logger.error(f"[PT下载中心]站点标签历史补全失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"站点标签历史补全失败: {e}"}, ModuleActionResult
        )
    return _operation_response(
        {"code": 0, "msg": "站点标签历史补全完成", "result": result},
        ModuleActionResult,
    )


def api_tag_status(plugin):
    """返回站点标签增强模块运行状态。"""
    from ..service.site_tag import get_module_status as site_tag_module_status

    return ModuleStatusResult(code=0, status=site_tag_module_status(plugin))


def api_rename_status(plugin):
    """返回命名补刀模块运行状态。"""
    from ..service.rename import get_module_status as rename_module_status

    status = rename_module_status(plugin)
    status["batch_running"] = bool(getattr(plugin, "_rename_batch_running", False))
    return ModuleStatusResult(code=0, status=status)
