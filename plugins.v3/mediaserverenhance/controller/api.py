"""媒体服务器增强 - API 路由声明。

路由只声明路径、方法与响应模型，业务由 ``handlers`` 承担。
"""

from __future__ import annotations

from functools import partial
from typing import Any, Dict, List

from app import schemas

from ..model.api import (
    ActionSummary,
    AuditReport,
    AuditRequest,
    CapabilityRequest,
    CapabilityResult,
    CoverRequest,
    CoverResult,
    DiagnosticsResult,
    HistoryClearRequest,
    JobPageResult,
    LibraryRow,
    OverviewResult,
    RefreshRequest,
    ServerRow,
)
from .handlers import MediaServerEnhanceApiHandlers as Handlers

Api = Handlers

def build_api_routes(plugin) -> List[Dict[str, Any]]:
    """构造插件 API 路由声明。

    :param plugin: 插件实例
    :return: 路由声明列表
    """
    return [
        {
            "path": "/overview",
            "endpoint": partial(Handlers.overview, plugin),
            "auth": "bear",
            "methods": ["GET"],
            "summary": "获取媒体服务器增强总览",
            "response_model": OverviewResult,
        },
        {
            "path": "/servers",
            "endpoint": partial(Handlers.servers, plugin),
            "auth": "bear",
            "methods": ["GET"],
            "summary": "获取媒体服务器列表",
            "response_model": List[ServerRow],
        },
        {
            "path": "/libraries/{server}",
            "endpoint": partial(Handlers.libraries, plugin),
            "auth": "bear",
            "methods": ["GET"],
            "summary": "获取媒体库列表",
            "response_model": List[LibraryRow],
        },
        {
            "path": "/jobs/{page}/{count}",
            "endpoint": partial(Handlers.jobs, plugin),
            "auth": "bear",
            "methods": ["GET"],
            "summary": "获取任务记录",
            "response_model": JobPageResult,
        },
        {
            "path": "/refresh",
            "endpoint": partial(Handlers.refresh_library, plugin),
            "auth": "bear",
            "methods": ["POST"],
            "summary": "触发媒体库刷新",
            "response_model": ActionSummary,
        },
        {
            "path": "/refresh_pending",
            "endpoint": partial(Handlers.refresh_pending, plugin),
            "auth": "bear",
            "methods": ["POST"],
            "summary": "立即提交待刷新条目",
            "response_model": ActionSummary,
        },
        {
            "path": "/audit",
            "endpoint": partial(Handlers.audit_report, plugin),
            "auth": "bear",
            "methods": ["GET"],
            "summary": "获取最近一次体检报告",
            "response_model": AuditReport,
        },
        {
            "path": "/audit_run",
            "endpoint": partial(Handlers.audit_run, plugin),
            "auth": "bear",
            "methods": ["POST"],
            "summary": "执行媒体库体检",
            "response_model": ActionSummary,
        },
        {
            "path": "/cover_preview",
            "endpoint": partial(Handlers.cover_preview, plugin),
            "auth": "bear",
            "methods": ["POST"],
            "summary": "预览封面效果",
            "response_model": CoverResult,
        },
        {
            "path": "/cover_run",
            "endpoint": partial(Handlers.cover_run, plugin),
            "auth": "bear",
            "methods": ["POST"],
            "summary": "生成并上传封面",
            "response_model": ActionSummary,
        },
        {
            "path": "/capabilities",
            "endpoint": partial(Handlers.capabilities_snapshot, plugin),
            "auth": "bear",
            "methods": ["GET"],
            "summary": "获取服务端能力快照",
            "response_model": CapabilityResult,
        },
        {
            "path": "/capabilities_probe",
            "endpoint": partial(Handlers.capabilities_probe, plugin),
            "auth": "bear",
            "methods": ["POST"],
            "summary": "探测服务端插件能力",
            "response_model": CapabilityResult,
        },
        {
            "path": "/diagnostics",
            "endpoint": partial(Handlers.diagnostics, plugin),
            "auth": "bear",
            "methods": ["GET"],
            "summary": "获取运行诊断",
            "response_model": DiagnosticsResult,
        },
        {
            "path": "/history_clear",
            "endpoint": partial(Handlers.clear_history, plugin),
            "auth": "bear",
            "methods": ["POST"],
            "summary": "清理历史记录",
            "response_model": ActionSummary,
        },
    ]


# 供类型检查与外部引用使用的请求模型别名
REQUEST_MODELS = {
    "refresh": RefreshRequest,
    "audit_run": AuditRequest,
    "cover_preview": CoverRequest,
    "cover_run": CoverRequest,
    "capabilities_probe": CapabilityRequest,
    "history_clear": HistoryClearRequest,
}
