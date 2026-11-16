"""
MediaServerEnhance v1.1.0 - MoviePilot V3 插件
媒体服务器增强：服务器与刷新、媒体库体检、封面工坊、服务端能力四模块聚合。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.plugins import _PluginBase
from app.schemas.types import EventType
from app.sdk.events import Event, eventmanager
from app.sdk.logging import logger

from .controller import events as _events
from .controller.api import build_api_routes as _build_api_routes_impl
from .controller.handlers import MediaServerEnhanceApiHandlers as _Handlers
from .core import lifecycle as _lifecycle
from .core.lifecycle import initialize_plugin as _initialize_plugin_impl
from .core.lifecycle import stop_plugin as _stop_plugin_impl
from .core.scheduler import build_plugin_services as _build_plugin_services_impl
from .utils import runtime as _runtime
from .model.api import (
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
from .utils.config import build_plugin_config_defaults


class MediaServerEnhance(_PluginBase):
    """媒体服务器增强插件入口，只声明 MoviePilot 契约并委托各层实现。"""

    # 插件名称
    plugin_name = "媒体服务器增强"
    # 插件描述
    plugin_desc = "Emby/Jellyfin 入库自动刷新、媒体库体检、风格化封面与能力探测，一个页面看住整台媒体服务器。"
    # 插件图标
    plugin_icon = "mediaserverenhance.png"
    # 插件颜色
    plugin_color = "#3F8CFF"
    # 插件版本
    plugin_version = "1.1.2"
    # 插件作者
    plugin_author = "wuyaos"
    # 作者主页
    author_url = "https://github.com/wuyaos"
    # 插件配置项ID前缀
    plugin_config_prefix = "mediaserverenhance_"
    # 加载顺序
    plugin_order = 30
    # 可使用的用户级别
    auth_level = 1

    # ── 通用 ──
    _enabled: bool = False
    _notify: bool = False
    _history_limit: int = 300
    _request_timeout: int = 30
    _config: Optional[Dict[str, Any]] = None

    # ── 服务器与刷新 ──
    _refresh_enabled: bool = False
    _refresh_servers: Optional[list] = None
    _refresh_libraries: Optional[list] = None
    _refresh_on_transfer: bool = True
    _refresh_debounce_seconds: int = 30
    _refresh_delay_seconds: int = 0
    _refresh_recent_enabled: bool = False
    _refresh_recent_count: int = 20
    _refresh_cron: str = ""

    # ── 媒体库体检 ──
    _audit_enabled: bool = False
    _audit_servers: Optional[list] = None
    _audit_libraries: Optional[list] = None
    _audit_checks: Optional[list] = None
    _audit_max_items: int = 20000
    _audit_cron: str = ""

    # ── 封面工坊 ──
    _covers_enabled: bool = False
    _cover_servers: Optional[list] = None
    _cover_libraries: Optional[list] = None
    _cover_style: str = "poster"
    _cover_limit: int = 20
    _cover_upload: bool = False
    _cover_font: str = ""
    _cover_output_dir: str = ""
    _covers_cron: str = ""

    # ── 服务端能力 ──
    _capabilities_enabled: bool = False
    _capability_servers: Optional[list] = None
    _capability_watched: Optional[list] = None
    _capabilities_cron: str = ""

    def __init__(self):
        """初始化实例级运行态，避免多实例共享待刷新缓冲。"""
        super().__init__()
        self._config = None
        self._refresh_pending: Dict[str, Dict[str, Any]] = {}
        self._refresh_timer = None

    def init_plugin(self, config: dict = None):
        """根据配置初始化插件运行状态。

        :param config: 宿主保存的插件配置
        """
        return _initialize_plugin_impl(self, config)

    def get_state(self) -> bool:
        """返回插件是否处于启用状态。"""
        return bool(self._enabled)

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """返回插件远程命令声明列表。"""
        return [
            {
                "cmd": "/mse_refresh_now",
                "event": EventType.PluginAction,
                "desc": "对全部启用实例执行整库刷新",
                "category": "",
                "data": {"action": "refresh_now"},
            },
            {
                "cmd": "/mse_refresh_recent",
                "event": EventType.PluginAction,
                "desc": "只刷新各实例最近入库的条目",
                "category": "",
                "data": {"action": "refresh_recent"},
            },
            {
                "cmd": "/mse_audit_run",
                "event": EventType.PluginAction,
                "desc": "执行一次只读体检并保存报告",
                "category": "",
                "data": {"action": "audit_run"},
            },
            {
                "cmd": "/mse_cover_run",
                "event": EventType.PluginAction,
                "desc": "按当前风格生成一批封面",
                "category": "",
                "data": {"action": "cover_run"},
            },
            {
                "cmd": "/mse_probe",
                "event": EventType.PluginAction,
                "desc": "探测服务端插件与能力",
                "category": "",
                "data": {"action": "capabilities_probe"},
            },
        ]

    def get_api(self) -> List[Dict[str, Any]]:
        """返回插件 API 路由声明。"""
        return _build_api_routes_impl(self)

    def get_service(self) -> List[Dict[str, Any]]:
        """注册插件定时服务。"""
        return _build_plugin_services_impl(self)

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        """返回渲染模式：Vue 联邦组件。"""
        return "vue", "dist/assets"

    def get_form(self) -> Tuple[Optional[List[dict]], Dict[str, Any]]:
        """Vue 模式下返回前端配置组件使用的默认配置。"""
        return None, build_plugin_config_defaults()

    def get_page(self) -> Optional[List[dict]]:
        """Vue 模式下无 Vuetify 详情页。"""
        return None

    def update_config(self, config: Dict[str, Any], plugin_id: Optional[str] = None) -> Optional[bool]:
        """保存配置并同步运行时属性。

        宿主默认实现只落盘、不触发 ``init_plugin``，保存后运行态仍是旧值；
        这里保存后立即把配置写入实例属性，免去一次 reload。
        """
        result = super().update_config(config, plugin_id)
        try:
            normalized = _runtime.apply_runtime_config(self, config)
            _lifecycle.reject_cover_conflict(self, normalized)
        except Exception as error:  # noqa: BLE001 - 同步失败不阻断保存
            logger.error(f"【媒体服务器增强】保存后同步运行态失败：{error}")
        return result

    def stop_service(self):
        """停止插件后台任务并释放运行资源。"""
        return _stop_plugin_impl(self)

    # ── 事件 ──

    @eventmanager.register(EventType.TransferComplete)
    def on_transfer_complete(self, event: Event):
        """监听整理完成事件，防抖后批量刷新媒体库。"""
        return _events.handle_transfer_complete_event(self, event)

    @eventmanager.register(EventType.PluginAction)
    def on_plugin_action(self, event: Event):
        """监听插件动作事件，执行远程命令。"""
        return _events.handle_plugin_action_event(self, event)

    @eventmanager.register(EventType.WebhookMessage)
    def on_webhook_message(self, event: Event):
        """监听媒体服务器 webhook 事件，只记录不动作。"""
        return _events.handle_webhook_event(self, event)

    # ── API 实现（同时供路由 partial 与直接调用使用）──

    def api_overview(self) -> OverviewResult:
        """返回总览数据。"""
        return _Handlers.overview(self)

    def api_servers(self) -> List[ServerRow]:
        """返回媒体服务器列表。"""
        return _Handlers.servers(self)

    def api_libraries(self, server: str = "") -> List[LibraryRow]:
        """返回指定服务器的媒体库列表。"""
        return _Handlers.libraries(self, server)

    def api_jobs(self, page: int = 1, count: int = 20, module: str = "",
                 status: str = "") -> JobPageResult:
        """分页返回任务历史。"""
        return _Handlers.jobs(self, page=page, count=count, module=module, status=status)

    def api_history_clear(self, payload: HistoryClearRequest) -> ActionSummary:
        """清理任务历史。"""
        return _Handlers.clear_history(self, payload)

    def api_refresh(self, payload: Optional[RefreshRequest] = None) -> ActionSummary:
        """手动刷新媒体库。"""
        return _Handlers.refresh_library(self, payload)

    def api_refresh_pending(self) -> ActionSummary:
        """立即提交待刷新队列。"""
        return _Handlers.refresh_pending(self)

    def api_audit_report(self) -> AuditReport:
        """返回最近一次体检报告。"""
        return _Handlers.audit_report(self)

    def api_audit_run(self, payload: Optional[AuditRequest] = None) -> ActionSummary:
        """执行一次体检。"""
        return _Handlers.audit_run(self, payload)

    def api_cover_run(self, payload: Optional[CoverRequest] = None) -> ActionSummary:
        """执行一次封面生成。"""
        return _Handlers.cover_run(self, payload)

    def api_cover_preview(self, payload: Optional[CoverRequest] = None) -> CoverResult:
        """生成一张封面预览。"""
        return _Handlers.cover_preview(self, payload)

    def api_capabilities(self) -> CapabilityResult:
        """返回服务端能力快照。"""
        return _Handlers.capabilities_snapshot(self)

    def api_capabilities_probe(self, payload: Optional[CapabilityRequest] = None) -> CapabilityResult:
        """探测服务端能力。"""
        return _Handlers.capabilities_probe(self, payload)

    def api_diagnostics(self) -> DiagnosticsResult:
        """返回运行诊断信息。"""
        return _Handlers.diagnostics(self)
