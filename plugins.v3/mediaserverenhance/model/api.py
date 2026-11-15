"""媒体服务器增强 - 请求与响应模型。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import JsonData


class ApiBusinessModel(BaseModel):
    """允许领域层在稳定字段之外附加兼容数据的业务模型。"""

    model_config = ConfigDict(extra="allow")


class ApiRequestModel(BaseModel):
    """拒绝未知字段的插件请求基类。"""

    model_config = ConfigDict(extra="forbid")


class SelectionItem(ApiBusinessModel):
    """服务器或媒体库选择项。"""

    title: str
    value: str
    type: Optional[str] = None
    server: Optional[str] = None


class ServerRow(ApiBusinessModel):
    """媒体服务器连接与能力摘要。"""

    name: str
    type: str = ""
    enabled: bool = False
    online: bool = False
    error: str = ""
    library_count: int = 0
    item_count: int = 0
    plugins_supported: bool = False
    plugin_count: int = 0
    watched_plugins: List[str] = Field(default_factory=list)


class LibraryRow(ApiBusinessModel):
    """媒体库摘要。"""

    server: str
    id: str
    name: str = ""
    type: str = ""
    item_count: int = 0
    path: str = ""


class JobRecord(ApiBusinessModel):
    """一次插件任务的执行记录。"""

    job_id: str = ""
    module: str = ""
    action: str = ""
    trigger: str = ""
    status: str = "unknown"
    message: str = ""
    server: str = ""
    library: str = ""
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    started_at: str = ""
    finished_at: str = ""
    detail: Dict[str, JsonData] = Field(default_factory=dict)


class JobPageResult(ApiBusinessModel):
    """任务记录分页结果。"""

    total: int = 0
    items: List[JobRecord] = Field(default_factory=list)


class OverviewResult(ApiBusinessModel):
    """运行总览数据。"""

    enabled: bool = False
    module_states: Dict[str, bool] = Field(default_factory=dict)
    server_count: int = 0
    online_count: int = 0
    library_count: int = 0
    audit_issue_count: int = 0
    audit_time: str = ""
    today_jobs: int = 0
    failed_jobs: int = 0
    last_refresh: str = ""
    cover_total: int = 0
    watched_hits: List[Dict[str, JsonData]] = Field(default_factory=list)
    servers: List[ServerRow] = Field(default_factory=list)


class RefreshRequest(ApiRequestModel):
    """手动刷新请求。"""

    servers: List[str] = Field(default_factory=list)
    libraries: List[str] = Field(default_factory=list)
    mode: str = Field(default="library", max_length=32)
    recent_count: int = Field(default=20, ge=1, le=500)


class ActionSummary(ApiBusinessModel):
    """一次动作的聚合结果。"""

    ok: bool = False
    message: str = ""
    job: JobRecord = Field(default_factory=JobRecord)


class AuditIssue(ApiBusinessModel):
    """单条体检问题。"""

    issue_type: str = ""
    server: str = ""
    library: str = ""
    library_name: str = ""
    item_id: str = ""
    title: str = ""
    year: str = ""
    detail: str = ""
    path: str = ""


class AuditReport(ApiBusinessModel):
    """体检报告。"""

    time: str = ""
    duration_ms: int = 0
    scanned_libraries: int = 0
    scanned_items: int = 0
    truncated: bool = False
    counts: Dict[str, int] = Field(default_factory=dict)
    issues: List[AuditIssue] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class AuditRequest(ApiRequestModel):
    """体检请求。"""

    servers: List[str] = Field(default_factory=list)
    libraries: List[str] = Field(default_factory=list)
    checks: List[str] = Field(default_factory=list)
    max_items: int = Field(default=20000, ge=100, le=200000)


class CoverRequest(ApiRequestModel):
    """封面生成或预览请求。"""

    servers: List[str] = Field(default_factory=list)
    libraries: List[str] = Field(default_factory=list)
    style: str = Field(default="", max_length=32)
    limit: int = Field(default=20, ge=1, le=500)
    upload: bool = False


class CoverResult(ApiBusinessModel):
    """封面任务结果。"""

    generated: int = 0
    uploaded: int = 0
    skipped: int = 0
    failed: int = 0
    items: List[Dict[str, JsonData]] = Field(default_factory=list)
    message: str = ""


class CapabilityPlugin(ApiBusinessModel):
    """服务端插件条目。"""

    name: str = ""
    version: str = ""
    status: str = ""


class CapabilityServer(ApiBusinessModel):
    """单台服务器的服务端能力探测结果。"""

    server: str
    type: str = ""
    supported: bool = False
    error: str = ""
    checked_at: str = ""
    plugins: List[CapabilityPlugin] = Field(default_factory=list)
    watched: List[Dict[str, JsonData]] = Field(default_factory=list)


class CapabilityResult(ApiBusinessModel):
    """服务端能力探测汇总。"""

    time: str = ""
    servers: List[CapabilityServer] = Field(default_factory=list)


class CapabilityRequest(ApiRequestModel):
    """服务端能力探测请求。"""

    servers: List[str] = Field(default_factory=list)


class DiagnosticsResult(ApiBusinessModel):
    """运行诊断摘要。"""

    checked: bool = True
    time: str = ""
    plugin: Dict[str, JsonData] = Field(default_factory=dict)
    servers: List[Dict[str, JsonData]] = Field(default_factory=list)
    config: Dict[str, JsonData] = Field(default_factory=dict)
    history: Dict[str, JsonData] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)


class HistoryClearRequest(ApiRequestModel):
    """清空历史记录请求。"""

    module: str = Field(default="", max_length=32)
    target: str = Field(default="jobs", max_length=32)
