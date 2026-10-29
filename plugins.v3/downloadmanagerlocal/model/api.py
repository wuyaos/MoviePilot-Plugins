"""下载中心 MoviePilot V3 API 请求与业务响应模型。"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import JsonData


class ApiBusinessModel(BaseModel):
    """允许领域服务在稳定字段之外附加兼容数据的业务模型。"""

    model_config = ConfigDict(extra="allow")


class ApiRequestModel(BaseModel):
    """拒绝未知字段的插件 API 请求基类。"""

    model_config = ConfigDict(extra="forbid")


class SelectionItem(ApiBusinessModel):
    """下载器或站点选择项。"""

    title: str
    value: str | int
    type: Optional[str] = None
    domain: Optional[str] = None


class RenameRecord(ApiBusinessModel):
    """种子重命名或归档记录。"""

    hash: str = ""
    original_name: str = ""
    after_name: str = ""
    success: bool = False
    reason: str = ""
    time: str = ""


class RenamePageResult(ApiBusinessModel):
    """重命名记录分页结果。"""

    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 1
    items: list[RenameRecord] = Field(default_factory=list)


class DiagnosticsResult(ApiBusinessModel):
    """插件诊断摘要。"""

    code: int = 0
    time: str = ""
    plugin: dict[str, JsonData] = Field(default_factory=dict)
    downloaders: dict[str, JsonData] = Field(default_factory=dict)
    config: dict[str, JsonData] = Field(default_factory=dict)
    paths: dict[str, JsonData] = Field(default_factory=dict)
    rename_history: dict[str, JsonData] = Field(default_factory=dict)
    rename_archive: dict[str, JsonData] = Field(default_factory=dict)
    checks: list[dict[str, JsonData]] = Field(default_factory=list)


class OverviewResult(ApiBusinessModel):
    """下载中心总览数据。"""

    code: int = 0
    plugin: dict[str, JsonData] = Field(default_factory=dict)
    config: dict[str, JsonData] = Field(default_factory=dict)
    downloaders: dict[str, JsonData] = Field(default_factory=dict)
    rename_history: dict[str, JsonData] = Field(default_factory=dict)
    archive: dict[str, JsonData] = Field(default_factory=dict)
    upload_limit: dict[str, JsonData] = Field(default_factory=dict)
    cards: dict[str, JsonData] = Field(default_factory=dict)


class ActionResult(ApiBusinessModel):
    """带旧版 code 的操作业务数据。"""

    code: int = 0
    msg: str = ""


class RetryRenamesResult(ActionResult):
    """批量补刀统计。"""

    history: int = 0
    dirty: int = 0
    total: int = 0
    attempted: int = 0
    failed: int = 0
    skipped: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    running: bool = False


class HashActionResult(ActionResult):
    """针对单个种子 hash 的操作结果。"""

    hash: str = ""


class UploadLimitStatusResult(ActionResult):
    """上传限速运行状态。"""

    service_status: str = ""
    active: bool = False
    managed_torrents: int = 0
    grace_torrents: int = 0
    errors: list[str] = Field(default_factory=list)


class UploadLimitReallocateResult(UploadLimitStatusResult):
    """上传额度重新分配结果。"""


class UploadLimitSiteTagsResult(ActionResult):
    """站点标签扫描结果。"""

    items: list[dict[str, JsonData]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    rules: dict[str, JsonData] = Field(default_factory=dict)


class UploadLimitRulesResult(ActionResult):
    """上传限速站点策略保存结果。"""

    rules: dict[str, JsonData] = Field(default_factory=dict)


class UploadLimitDisableResult(ActionResult):
    """停用上传限速并恢复原值的结果。"""

    errors: list[str] = Field(default_factory=list)


class TagCleanupScanResult(ActionResult):
    """下载器标签扫描结果。"""

    downloaders: list[dict[str, JsonData]] = Field(default_factory=list)
    auto_removed: list[dict[str, JsonData]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class TagCleanupExecuteResult(ActionResult):
    """下载器标签清理执行结果。"""

    removed: list[dict[str, JsonData]] = Field(default_factory=list)
    failed: list[dict[str, JsonData]] = Field(default_factory=list)


class EmptyRequest(ApiRequestModel):
    """没有业务字段的显式 JSON 请求体。"""


class UploadLimitSiteRule(ApiRequestModel):
    """单站点上传限速策略。"""

    limit_kib: int = Field(default=0, ge=0)


class UploadLimitSiteTagsRequest(ApiRequestModel):
    """上传限速站点标签扫描请求。"""

    downloaders: list[str] = Field(default_factory=list)
    rules: dict[str, UploadLimitSiteRule] = Field(default_factory=dict)


class UploadLimitRulesRequest(ApiRequestModel):
    """上传限速站点策略保存请求。"""

    rules: dict[str, UploadLimitSiteRule] = Field(default_factory=dict)


class TagCleanupScanRequest(ApiRequestModel):
    """下载器标签扫描请求。"""

    downloaders: list[str] = Field(default_factory=list)


class TagCleanupRemoval(ApiRequestModel):
    """待清理标签快照。"""

    downloader: str = Field(min_length=1, max_length=128)
    tag: str = Field(min_length=1, max_length=256)
    hashes: list[str] = Field(default_factory=list)


class TagCleanupExecuteRequest(ApiRequestModel):
    """按扫描快照执行标签清理的请求。"""

    removals: list[TagCleanupRemoval] = Field(default_factory=list)


class HrTasksResult(ApiBusinessModel):
    """H&R 任务列表与汇总。"""

    code: int = 0
    tasks: list[dict[str, JsonData]] = Field(default_factory=list)
    summary: dict[str, JsonData] = Field(default_factory=dict)


class HrSkipStatsResult(ApiBusinessModel):
    """H&R 保护在各破坏性路径上的跳过计数。"""

    code: int = 0
    skip_stats: dict[str, int] = Field(default_factory=dict)


class HrPresetsResult(ApiBusinessModel):
    """内置 H&R 站点验证预设（只读，随代码发布）。"""

    code: int = 0
    presets: list[dict[str, JsonData]] = Field(default_factory=list)


class HrActionResult(ActionResult):
    """H&R 操作执行结果。"""

    cleared: int = 0
    result: dict[str, JsonData] = Field(default_factory=dict)


class HrClearTaskRequest(ApiRequestModel):
    """清除单条 H&R 记录的请求。"""

    downloader_id: str = Field(min_length=1, max_length=128)
    torrent_hash: str = Field(min_length=1, max_length=128)


class CleanupModuleRequest(ApiRequestModel):
    """数据页模块数据清理请求：module 为白名单对象标识。"""

    module: str = Field(min_length=1, max_length=64)


class CleanupModuleResult(ActionResult):
    """数据清理结果：removed 为真实清理条数。"""

    removed: int = 0
    module: str = ""


class ModuleStatusResult(ApiBusinessModel):
    """模块运行状态（自动删种/失败清理/站点标签/命名补刀通用）。"""

    code: int = 0
    status: dict[str, JsonData] = Field(default_factory=dict)


class ModuleActionResult(ApiBusinessModel):
    """模块手动执行结果。"""

    code: int = 0
    msg: str = ""
    result: dict[str, JsonData] = Field(default_factory=dict)
