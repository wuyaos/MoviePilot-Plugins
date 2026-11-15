"""媒体服务器增强 - API 处理层。

只做参数编排与结果整形，具体业务全部委托给 ``modules`` 下的服务。
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.sdk.logging import logger

from ..adapter import mediaserver
from ..modules import capabilities, diagnostics, refresh
from ..modules.audit import service as audit_service
from ..modules.covers import service as cover_service
from ..model.api import (
    ActionSummary,
    AuditReport,
    AuditRequest,
    CapabilityResult,
    CapabilityRequest,
    CoverRequest,
    CoverResult,
    DiagnosticsResult,
    HistoryClearRequest,
    JobPageResult,
    JobRecord,
    LibraryRow,
    OverviewResult,
    RefreshRequest,
    ServerRow,
)
from ..utils import store
from ..utils.config import as_bool

MODULE_LABELS = {
    "refresh": "服务器与刷新",
    "audit": "媒体库体检",
    "covers": "封面工坊",
    "capabilities": "服务端能力",
}


def _job_record(job: Optional[Dict[str, Any]]) -> JobRecord:
    """把任务字典转成 API 模型。

    :param job: 任务记录字典
    :return: 任务模型
    """
    if not job:
        return JobRecord()
    safe = {key: value for key, value in job.items() if key in JobRecord.model_fields}
    record = JobRecord(**safe)
    extra = {key: value for key, value in job.items() if key not in JobRecord.model_fields}
    if extra:
        record.detail.update(extra)
    return record


def _module_states(plugin) -> Dict[str, bool]:
    """收集各业务模块的启用状态。

    :param plugin: 插件实例
    :return: 模块键到启用状态的映射
    """
    return {
        key: as_bool(getattr(plugin, f"_{key}_enabled", False))
        for key in MODULE_LABELS
    }


def _with_preview(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """给封面条目补上可直接渲染的 data URL。

    :param items: 封面条目列表
    :return: 同一批条目（原地补充 preview 字段）
    """
    for entry in items:
        raw_path = str(entry.get("path") or "").strip()
        if not raw_path:
            continue
        try:
            raw = Path(raw_path).read_bytes()
        except OSError as err:
            logger.debug(f"【媒体服务器增强】封面预览读取失败 {raw_path}：{err}")
            continue
        if raw and len(raw) <= 4 * 1024 * 1024:
            entry["preview"] = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
    return items


class MediaServerEnhanceApiHandlers:
    """插件 REST 接口实现。"""

    # ---------- 总览 ----------

    @staticmethod
    def overview(plugin) -> OverviewResult:
        """返回运行总览数据。

        :param plugin: 插件实例
        :return: 总览模型
        """
        servers: List[ServerRow] = []
        online_count = 0
        library_count = 0
        for row in mediaserver.list_server_configs(include_disabled=True):
            name = str(row.get("name") or "")
            online, message = mediaserver.server_online(name) if row.get("enabled") else (False, "")
            libraries = mediaserver.list_libraries(name) if online else []
            libraries_count = len(libraries)
            if online:
                online_count += 1
            library_count += libraries_count
            servers.append(
                ServerRow(
                    name=name,
                    type=str(row.get("type") or ""),
                    enabled=bool(row.get("enabled")),
                    online=online,
                    error=message if row.get("enabled") and not online else "",
                    library_count=libraries_count,
                    item_count=sum(int(item.get("item_count") or 0) for item in libraries),
                )
            )

        stats = store.today_job_stats(plugin)
        report = audit_service.latest_report(plugin)
        refresh_state = store.read_snapshot(plugin, store.REFRESH_STATE_KEY)
        covers = cover_service.cover_history(plugin)
        capability_rows = capabilities.watched_summary(plugin)
        by_name = {row["server"]: row for row in capability_rows}
        for server in servers:
            capability = by_name.get(server.name)
            if capability:
                server.plugins_supported = capability["supported"]
                server.plugin_count = int(capability.get("plugin_count") or 0)
                server.watched_plugins = [
                    item.strip() for item in str(capability.get("installed") or "").split(",") if item.strip()
                ]

        return OverviewResult(
            enabled=as_bool(getattr(plugin, "_enabled", False)),
            module_states=_module_states(plugin),
            server_count=len(servers),
            online_count=online_count,
            library_count=library_count,
            audit_issue_count=len(report.get("issues") or []),
            audit_time=str(report.get("time") or ""),
            today_jobs=stats["today"],
            failed_jobs=stats["failed"],
            last_refresh=str(refresh_state.get("time") or ""),
            cover_total=sum(int(item.get("generated") or 0) for item in covers),
            watched_hits=capability_rows,
            servers=servers,
        )

    # ---------- 服务器与媒体库 ----------

    @staticmethod
    def servers(plugin) -> List[ServerRow]:
        """返回媒体服务器列表。

        :param plugin: 插件实例
        :return: 服务器模型列表
        """
        rows: List[ServerRow] = []
        for row in mediaserver.list_server_configs(include_disabled=True):
            name = str(row.get("name") or "")
            online, message = mediaserver.server_online(name) if row.get("enabled") else (False, "")
            libraries = mediaserver.list_libraries(name) if online else []
            rows.append(
                ServerRow(
                    name=name,
                    type=str(row.get("type") or ""),
                    enabled=bool(row.get("enabled")),
                    online=online,
                    error=message if row.get("enabled") and not online else "",
                    library_count=len(libraries),
                    item_count=sum(int(item.get("item_count") or 0) for item in libraries),
                )
            )
        return rows

    @staticmethod
    def libraries(plugin, server: str = "") -> List[LibraryRow]:
        """返回媒体库列表。

        :param plugin: 插件实例
        :param server: 限定服务器名称，空串表示全部
        :return: 媒体库模型列表
        """
        names = [server] if server else [
            row["name"] for row in mediaserver.list_server_configs() if row.get("enabled")
        ]
        rows: List[LibraryRow] = []
        for name in names:
            for library in mediaserver.list_libraries(name) or []:
                rows.append(
                    LibraryRow(
                        server=name,
                        id=str(library.get("id") or ""),
                        name=str(library.get("name") or ""),
                        type=str(library.get("type") or ""),
                        item_count=int(library.get("item_count") or 0),
                        path=str(library.get("path") or ""),
                    )
                )
        return rows

    # ---------- 任务 ----------

    @staticmethod
    def jobs(plugin, page: int = 1, count: int = 20, module: str = "",
             status: str = "") -> JobPageResult:
        """分页返回任务记录。

        :param plugin: 插件实例
        :param page: 页码，从 1 开始
        :param count: 每页条数
        :param module: 只返回指定模块
        :param status: 只返回指定状态
        :return: 分页结果
        """
        rows = store.load_jobs(plugin)
        if module:
            rows = [row for row in rows if row.get("module") == module]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        start = max(0, (max(1, page) - 1) * max(1, count))
        window = rows[start:start + max(1, count)]
        return JobPageResult(total=len(rows), items=[_job_record(row) for row in window])

    @staticmethod
    def clear_history(plugin, payload: HistoryClearRequest) -> ActionSummary:
        """清理历史记录。

        :param plugin: 插件实例
        :param payload: 清理请求
        :return: 动作结果
        """
        target = payload.target or "jobs"
        if target == "jobs":
            removed = store.clear_jobs(plugin, payload.module)
            return ActionSummary(ok=True, message=f"已清理 {removed} 条任务记录")
        if target == "audit":
            store.write_value(plugin, store.AUDIT_REPORT_KEY, {})
            return ActionSummary(ok=True, message="已清空体检报告")
        if target == "covers":
            store.write_value(plugin, store.COVER_HISTORY_KEY, [])
            return ActionSummary(ok=True, message="已清空封面历史")
        if target == "capabilities":
            store.write_value(plugin, store.CAPABILITIES_KEY, {})
            return ActionSummary(ok=True, message="已清空能力探测快照")
        return ActionSummary(ok=False, message=f"未知的清理目标：{target}")

    # ---------- 刷新 ----------

    @staticmethod
    def refresh_library(plugin, payload: Optional[RefreshRequest] = None) -> ActionSummary:
        """按媒体库或按条目触发刷新。

        :param plugin: 插件实例
        :param payload: 刷新请求
        :return: 动作结果
        """
        payload = payload or RefreshRequest()
        if payload.mode == "recent":
            job = refresh.run_recent_refresh(plugin, trigger="手动刷新最近媒体")
        else:
            job = refresh.run_refresh(
                plugin,
                [],
                trigger="手动整库刷新",
                servers=payload.servers or None,
                root_refresh=True,
            )
        return ActionSummary(
            ok=job.get("status") in {"success", "partial"},
            message=str(job.get("message") or ""),
            job=_job_record(job),
        )

    @staticmethod
    def refresh_pending(plugin) -> ActionSummary:
        """立即提交防抖缓冲中的刷新请求。

        :param plugin: 插件实例
        :return: 动作结果
        """
        job = refresh.flush_pending(plugin, trigger="手动提交待刷新")
        if not job:
            return ActionSummary(ok=True, message="当前没有待刷新条目")
        return ActionSummary(
            ok=job.get("status") in {"success", "partial"},
            message=str(job.get("message") or ""),
            job=_job_record(job),
        )

    # ---------- 体检 ----------

    @staticmethod
    def audit_report(plugin) -> AuditReport:
        """返回最近一次体检报告。

        :param plugin: 插件实例
        :return: 体检报告模型
        """
        report = audit_service.latest_report(plugin)
        issues = [
            {key: value for key, value in row.items() if key in {
                "issue_type", "server", "library", "library_name",
                "item_id", "title", "year", "detail", "path",
            }}
            for row in (report.get("issues") or [])
        ]
        return AuditReport(
            time=str(report.get("time") or ""),
            duration_ms=int(report.get("duration_ms") or 0),
            scanned_libraries=int(report.get("scanned_libraries") or 0),
            scanned_items=int(report.get("scanned_items") or 0),
            truncated=bool(report.get("truncated")),
            counts={str(key): int(value) for key, value in (report.get("counts") or {}).items()},
            issues=issues,
            errors=[str(item) for item in (report.get("errors") or [])],
        )

    @staticmethod
    def audit_run(plugin, payload: Optional[AuditRequest] = None) -> ActionSummary:
        """执行一次体检。

        :param plugin: 插件实例
        :param payload: 体检请求
        :return: 动作结果，``detail`` 中附带报告摘要
        """
        payload = payload or AuditRequest()
        report = audit_service.run_audit(
            plugin,
            servers=payload.servers or None,
            libraries=payload.libraries or None,
            checks=payload.checks or None,
            max_items=payload.max_items,
            trigger="手动体检",
        )
        jobs = store.load_jobs(plugin)
        job = jobs[0] if jobs else {}
        summary = ActionSummary(
            ok=True,
            message=f"扫描 {report.get('scanned_items', 0)} 条，发现 {len(report.get('issues') or [])} 个问题",
            job=_job_record(job),
        )
        summary.detail = {
            "counts": report.get("counts") or {},
            "errors": report.get("errors") or [],
            "truncated": bool(report.get("truncated")),
        }
        return summary

    # ---------- 封面 ----------

    @staticmethod
    def cover_run(plugin, payload: Optional[CoverRequest] = None) -> ActionSummary:
        """生成封面，按请求决定是否上传。

        :param plugin: 插件实例
        :param payload: 封面请求
        :return: 动作结果
        """
        payload = payload or CoverRequest()
        result = cover_service.run_cover(
            plugin,
            servers=payload.servers or None,
            libraries=payload.libraries or None,
            style=payload.style or None,
            limit=payload.limit,
            upload=payload.upload,
            trigger="手动生成",
        )
        jobs = store.load_jobs(plugin)
        summary = ActionSummary(
            ok=result.get("failed", 0) == 0,
            message=str(result.get("message") or ""),
            job=_job_record(jobs[0] if jobs else None),
        )
        summary.detail = {
            "generated": result.get("generated", 0),
            "uploaded": result.get("uploaded", 0),
            "skipped": result.get("skipped", 0),
            "failed": result.get("failed", 0),
            "items": result.get("items", [])[:20],
        }
        return summary

    @staticmethod
    def cover_preview(plugin, payload: Optional[CoverRequest] = None) -> CoverResult:
        """生成一小批不上传的封面用于预览。

        :param plugin: 插件实例
        :param payload: 封面请求，``upload`` 固定忽略
        :return: 封面结果模型
        """
        payload = payload or CoverRequest()
        result = cover_service.run_cover(
            plugin,
            servers=payload.servers or None,
            libraries=payload.libraries or None,
            style=payload.style or None,
            limit=min(payload.limit, 6),
            upload=False,
            trigger="预览",
        )
        return CoverResult(
            generated=int(result.get("generated") or 0),
            uploaded=0,
            skipped=int(result.get("skipped") or 0),
            failed=int(result.get("failed") or 0),
            items=_with_preview(result.get("items") or []),
            message=str(result.get("message") or ""),
        )

    # ---------- 服务端能力 ----------

    @staticmethod
    def capabilities_snapshot(plugin) -> CapabilityResult:
        """返回最近一次服务端能力探测结果。

        :param plugin: 插件实例
        :return: 能力模型
        """
        snapshot = capabilities.latest(plugin)
        rows = []
        for row in snapshot.get("servers") or []:
            rows.append(
                {
                    "server": str(row.get("server") or ""),
                    "type": str(row.get("type") or ""),
                    "supported": bool(row.get("supported")),
                    "error": str(row.get("error") or ""),
                    "checked_at": str(row.get("checked_at") or ""),
                    "plugins": row.get("plugins") or [],
                    "watched": row.get("watched") or [],
                }
            )
        return CapabilityResult(time=str(snapshot.get("time") or ""), servers=rows)

    @staticmethod
    def capabilities_probe(plugin, payload: Optional[CapabilityRequest] = None) -> CapabilityResult:
        """执行一次服务端能力探测。

        :param plugin: 插件实例
        :param payload: 探测请求
        :return: 能力模型
        """
        payload = payload or CapabilityRequest()
        snapshot = capabilities.probe(plugin, payload.servers or None, trigger="手动探测")
        rows = []
        for row in snapshot.get("servers") or []:
            rows.append(
                {
                    "server": str(row.get("server") or ""),
                    "type": str(row.get("type") or ""),
                    "supported": bool(row.get("supported")),
                    "error": str(row.get("error") or ""),
                    "checked_at": str(row.get("checked_at") or ""),
                    "plugins": row.get("plugins") or [],
                    "watched": row.get("watched") or [],
                }
            )
        return CapabilityResult(time=str(snapshot.get("time") or ""), servers=rows)

    # ---------- 诊断 ----------

    @staticmethod
    def diagnostics(plugin) -> DiagnosticsResult:
        """返回运行诊断结果。

        :param plugin: 插件实例
        :return: 诊断模型
        """
        try:
            return DiagnosticsResult(**diagnostics.build(plugin))
        except Exception as error:  # noqa: BLE001 - 诊断失败也要给出可读结果
            logger.error(f"【媒体服务器增强】运行诊断失败：{error}")
            return DiagnosticsResult(
                checked=False,
                time=store.now_text(),
                warnings=[f"诊断执行失败：{error}"],
            )
