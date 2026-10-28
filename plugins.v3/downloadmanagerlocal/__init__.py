"""
DownloadManagerLocal v3.5.1 - MoviePilot V3 本地插件
下载中心插件，支持转移做种、命名补刀、站点标签、H&R、自动删种、失败清理与上传限速
"""
from threading import Event as ThreadEvent
import threading
from typing import Any, List, Dict, Tuple, Optional

from app.plugins import _PluginBase
from app.schemas import ServiceInfo
from app.schemas.types import EventType
from app.sdk.events import eventmanager, Event
from app.sdk.logging import logger
from app.sdk.media import MetaBase

from .adapter.moviepilot import get_downloader_service
from .model.state import SEED_RECHECK_QUEUE_KEY
from .utils.config import build_plugin_config_defaults, is_plugin_active, is_transfer_active
from .utils.path import convert_save_path
from .utils.torrent_adapter import get_hash, get_label, get_category, get_save_path, get_torrent_size
from .controller.handlers import api_downloaders as _api_downloaders, api_sites as _api_sites, api_rename_history as _api_rename_history, api_delete_rename_history as _api_delete_rename_history, api_recovery_torrent as _api_recovery_torrent, api_retry_renames as _api_retry_renames, api_retry_rename as _api_retry_rename, api_diagnostics as _api_diagnostics, api_overview as _api_overview, api_rename_archive as _api_rename_archive, api_restore_rename_archive as _api_restore_rename_archive, api_delete_rename_archive as _api_delete_rename_archive, api_hr_tasks as _api_hr_tasks, api_hr_skip_stats as _api_hr_skip_stats
from .modules.rename.service import rename_torrent as _rename_torrent_impl, format_torrent_name as _format_torrent_name_impl, save_rename_record as _save_rename_record_impl, get_failed_rename_hashes as _get_failed_rename_hashes_impl, retry_failed_renames as _retry_failed_renames_impl, retry_rename_by_hash as _retry_rename_by_hash_impl
from .modules.rename.archive import record_rename_failure as _record_rename_failure_impl, clear_rename_retry_state as _clear_rename_retry_state_impl, is_rename_archived as _is_rename_archived_impl, list_rename_archive as _list_rename_archive_impl, restore_rename_archive as _restore_rename_archive_impl, delete_rename_archive as _delete_rename_archive_impl, rename_archive_stats as _rename_archive_stats_impl
from .modules.diagnostics.service import build_diagnostics as _build_diagnostics_impl
from .modules.sitetag.service import tag_torrent as _tag_torrent_impl, find_site_by_domain as _find_site_by_domain_impl
from .modules.transfer.recheck import load_seed_recheck_queue as _load_seed_recheck_queue_impl, save_seed_recheck_queue as _save_seed_recheck_queue_impl, ensure_seed_recheck_worker as _ensure_seed_recheck_worker_impl, stop_seed_recheck_worker as _stop_seed_recheck_worker_impl, seed_recheck_loop as _seed_recheck_loop_impl, process_seed_recheck_once as _process_seed_recheck_once_impl, seed_should_remove_missing as _seed_should_remove_missing_impl, seed_is_checking as _seed_is_checking_impl, seed_is_ready as _seed_is_ready_impl, seed_is_error as _seed_is_error_impl, seed_is_timeout as _seed_is_timeout_impl, run_recheck_cycle as _check_recheck_impl, sweep_paused_seed_tasks as _sweep_paused_seed_tasks_impl, can_seed_paused_torrent as _can_seeding_impl
from .modules.transfer.service import validate_config as _validate_config_impl, download_torrent as _download_impl, post_transfer_process as _post_transfer_process_impl, transfer as _transfer_impl, fallback_transfer as _fallback_transfer_impl, delayed_transfer as _delayed_transfer_impl, retry_pending_renames as _retry_pending_renames_impl
from .controller import handlers as _controller_handlers
from .controller.api import build_api_routes as _build_api_routes_impl
from .modules.transfer.events import handle_download_added_event as _handle_download_added_event_impl, handle_transfer_complete_event as _handle_transfer_complete_event_impl, handle_plugin_triggered_event as _handle_plugin_triggered_event_impl
from .modules.failclean.events import handle_transfer_failed_event as _handle_transfer_failed_event_impl
from .core.lifecycle import initialize_plugin as _initialize_plugin_impl, stop_plugin_service as _stop_plugin_service_impl
from .core.scheduler import build_plugin_services as _build_plugin_services_impl
from .modules.cleanup.service import handle_sync_delete_by_hash_event as _handle_sync_delete_by_hash_event_impl, handle_webhook_message_event as _handle_webhook_message_event_impl, handle_plugin_action_event as _handle_plugin_action_event_impl
from .modules.uploadlimit.service import run_upload_limit_cycle as _run_upload_limit_cycle_impl

class DownloadManagerLocal(_PluginBase):
    """下载中心插件入口，负责声明 MoviePilot 契约并委托 service 层执行。"""
    # 插件名称
    plugin_name = "下载中心"
    # 插件描述
    plugin_desc = "转移做种、命名补刀、站点标签、H&R 保护、自动删种、失败清理与上传限速，一站式下载管理。"
    # 插件图标
    plugin_icon = "downloadmanagerlocal.png"
    # 插件颜色
    plugin_color = "#4CAF50"
    # 插件版本
    plugin_version = "3.9.8"
    # 插件作者
    plugin_author = "Kurisu, wuyaos"
    # 作者主页
    author_url = "https://github.com/z2561221"
    # 插件配置项ID前缀
    plugin_config_prefix = "downloadmanagerlocal_"
    # 加载顺序
    plugin_order = 18
    # 可使用的用户级别
    auth_level = 2

    # 私有属性
    _scheduler = None
    _hr_service = None
    _upload_limit_thread = None
    _upload_limit_stop_event = None
    _upload_limit_wake_event = None
    _upload_limit_worker_lock = None
    _upload_limit_restart_pending = False
    _upload_limit_cycle_lock = None
    _upload_limit_state = None
    _upload_limit_state_error = ""

    # ── 转移做种配置 ──
    _enabled = False
    _transfer_enabled = False
    _delay_minutes = 25
    _transfer_fallback_enabled = True
    _transfer_fallback_interval_minutes = 60
    _fromdownloader = None
    _todownloader = None
    _frompath = None
    _topath = None
    _notify = False
    _nolabels = None
    _includelabels = None
    _includecategory = None
    _nopaths = None
    _deletesource = False
    _deleteduplicate = False
    _fromtorrentpath = None
    _transferemptylabel = False
    _add_torrent_tags = None
    _remainoldcat = False
    _remainoldtag = False
    _seed_autostart: bool = True
    _seed_skipverify: bool = False
    _seed_check_interval: int = 60
    _seed_max_wait_minutes: int = 120

    # ── 重命名配置 ──
    _rename_enabled: bool = True
    _rename_movie_format: str = "[ {{ title }}{% if year %} ({{ year }}){% endif %} ] - {{original_name}}"
    _rename_tv_format: str = "[ {{ title }}{% if year %} ({{ year }}){% endif %}{% if season_episode %} - {{season_episode}}{% endif %} ] - {{original_name}}"
    _rename_exclude_dirs: str = ""

    # ── 站点标签配置 ──
    _tag_enabled: bool = True
    _tag_siteprefix: str = "🏠"
    _tag_tracker_mappings_str: str = ""

    # ── 上传限速配置 ──
    _upload_limit_enabled: bool = False
    _upload_limit_downloaders: Optional[list] = None
    _upload_limit_downloader_limits_kib: Optional[dict] = None
    _upload_limit_site_rules: Optional[dict] = None
    _upload_limit_grace_minutes: int = 30

    # 退出事件
    _event = None
    # 待检查种子清单：{下载器名: {hash: 来源}}
    _recheck_torrents: Optional[dict] = None
    _is_recheck_running = False
    _seed_recheck_running = False
    _seed_recheck_lock = None
    _seed_recheck_queue_key = SEED_RECHECK_QUEUE_KEY

    # 任务标签
    _torrent_tags: Optional[list] = None
    # tracker 映射
    _tracker_mappings: Optional[Dict[str, str]] = None
    _custom_site_labels: Optional[Dict[str, str]] = None

    # 辅助
    downloader_helper = None

    def __init__(self):
        """初始化实例级运行态，避免多实例共享配置、队列、缓存或退出信号。"""
        super().__init__()
        self._scheduler = None
        self._hr_service = None
        self._transfer_schedule_lock = threading.RLock()
        self._transfer_pending_runs = {}
        self._transfer_scheduled_run = None
        self._transfer_running_generation = None
        self._upload_limit_thread = None
        self._upload_limit_stop_event = None
        self._upload_limit_wake_event = None
        self._upload_limit_worker_lock = None
        self._upload_limit_restart_pending = False
        self._upload_limit_cycle_lock = None
        self._upload_limit_state = None
        self._upload_limit_state_error = ""
        self._upload_limit_downloaders = []
        self._upload_limit_downloader_limits_kib = {}
        self._upload_limit_site_rules = {}
        self._event = ThreadEvent()
        self._recheck_torrents = {}
        self._is_recheck_running = False
        self._seed_recheck_running = False
        self._seed_recheck_lock = threading.RLock()
        self._seed_recheck_queue_lock = self._seed_recheck_lock
        self._seed_recheck_thread = None
        self._seed_recheck_thread = None
        self._seed_recheck_stop_event = None
        self._rename_batch_running = False
        self._rename_batch_lock = threading.Lock()
        self._rename_scan_running = False
        self._rename_scan_lock = threading.Lock()
        self._transfer_manual_running = False
        self._transfer_manual_lock = threading.Lock()
        self._torrent_tags = []
        self._tracker_mappings = {}
        self._custom_site_labels = {}
        self.downloader_helper = None

    def init_plugin(self, config: dict = None):
        """根据配置初始化插件运行状态和后台服务。"""; return _initialize_plugin_impl(self, config)

    @staticmethod
    def get_hash(torrent, dl_type: str):
        """从指定下载器种子对象中提取唯一 hash。"""; return get_hash(torrent, dl_type)

    @staticmethod
    def get_label(torrent, dl_type: str):
        """从指定下载器种子对象中读取标签列表。"""; return get_label(torrent, dl_type)

    @staticmethod
    def get_category(torrent, dl_type: str):
        """从指定下载器种子对象中读取分类。"""; return get_category(torrent, dl_type)

    @staticmethod
    def get_save_path(torrent, dl_type: str):
        """从指定下载器种子对象中读取保存路径。"""; return get_save_path(torrent, dl_type)

    @staticmethod
    def get_torrent_size(torrent, dl_type: str):
        """从指定下载器种子对象中读取任务体积。"""; return get_torrent_size(torrent, dl_type)

    @staticmethod
    def convert_save_path(save_path: str, from_root: str, to_root: str):
        """按源目录和目标目录转换种子保存路径。"""; return convert_save_path(save_path, from_root, to_root)

    @staticmethod
    def service_info(name: str) -> Optional[ServiceInfo]:
        """
        服务信息
        """
        if not name:
            logger.warning("【PT下载中心】尚未配置下载器，请检查配置")
            return None

        service = get_downloader_service(name)
        if not service or not service.instance:
            logger.warning(f"【PT下载中心】获取下载器 {name} 实例失败，请检查配置")
            return None

        if service.instance.is_inactive():
            logger.warning(f"【PT下载中心】下载器 {name} 未连接，请检查配置")
            return None

        return service

    def get_state(self):
        """返回插件当前是否具备可运行能力。"""; return is_plugin_active(self)

    @property
    def _transfer_active(self) -> bool:
        """转移做种功能是否激活（总开关 + 转移开关 + 配置完整）"""
        return is_transfer_active(self)

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """返回插件远程命令声明列表。"""; return []

    def get_api(self) -> List[Dict[str, Any]]:
        """返回插件 API 路由声明。"""; return _build_api_routes_impl(self)

    def api_downloaders(self):
        """返回前端配置可选的下载器列表。"""; return _api_downloaders(self)

    def api_sites(self):
        """返回前端配置可选的站点列表。"""; return _api_sites(self)

    def api_rename_history(self, page: int = 1, page_size: int = 15):
        """分页返回重命名历史记录。"""; return _api_rename_history(self, page, page_size)

    def api_overview(self):
        """返回插件详情页总览数据。"""; return _api_overview(self)

    def api_delete_rename_history(self, hash: str = ""):
        """删除指定 hash 的重命名历史记录。"""; return _api_delete_rename_history(self, hash)

    def api_rename_archive(self, page: int = 1, page_size: int = 15):
        """分页返回重命名失败归档记录。"""; return _api_rename_archive(self, page, page_size)

    def api_restore_rename_archive(self, hash: str = ""):
        """恢复指定 hash 的重命名归档状态。"""; return _api_restore_rename_archive(self, hash)

    def api_delete_rename_archive(self, hash: str = ""):
        """删除指定 hash 的重命名归档状态。"""; return _api_delete_rename_archive(self, hash)

    def api_recovery_torrent(self, hash: str = ""):
        """按历史记录恢复指定种子的原始名称。"""; return _api_recovery_torrent(self, hash)

    def api_retry_renames(self):
        """触发失败和脏名称任务的一键补刮。"""; return _api_retry_renames(self)

    def api_retry_rename(self, hash: str = ""):
        """对指定 hash 的种子执行单条补刮。"""; return _api_retry_rename(self, hash)

    def api_diagnostics(self):
        """返回插件只读诊断信息。"""; return _api_diagnostics(self)

    def api_hr_tasks(self):
        """返回 H&R 任务列表与汇总。"""; return _api_hr_tasks(self)

    def api_hr_skip_stats(self):
        """返回 H&R 保护在四条破坏性路径上的跳过计数。"""; return _api_hr_skip_stats(self)

    def api_hr_presets(self):
        """返回内置 H&R 站点验证预设。"""
        return _controller_handlers.api_hr_presets(self)

    def api_autoremove_status(self):
        """返回自动删种模块状态。"""
        return _controller_handlers.api_autoremove_status(self)

    def api_autoremove_run(self, payload=None):
        """手动执行一轮自动删种。"""
        return _controller_handlers.api_autoremove_run(self, payload)

    def api_autoremove_preview(self, payload=None):
        """预览自动删种候选。"""
        return _controller_handlers.api_autoremove_preview(self, payload)

    def api_failclean_status(self):
        """返回整理失败清理模块状态。"""
        return _controller_handlers.api_failclean_status(self)

    def api_failclean_scan(self, payload=None):
        """手动执行重复下载残留巡检。"""
        return _controller_handlers.api_failclean_scan(self, payload)

    def api_transfer_run(self, payload=None):
        """手动执行一轮转移做种。"""
        return _controller_handlers.api_transfer_run(self, payload)

    def api_transfer_status(self, page: int = 1, page_size: int = 15):
        """返回转移做种数据页（任务配置、在途事务、最近记录、汇总）。"""
        return _controller_handlers.api_transfer_status(self, page=page, page_size=page_size)

    def api_tag_status(self):
        """返回站点标签增强模块状态。"""
        return _controller_handlers.api_tag_status(self)

    def api_tag_complement(self, payload=None):
        """手动执行一轮站点标签历史补全。"""
        return _controller_handlers.api_tag_complement(self, payload)

    def api_rename_status(self):
        """返回命名补刀模块状态。"""
        return _controller_handlers.api_rename_status(self)
    def get_service(self) -> List[Dict[str, Any]]:
        """
        注册插件公共服务
        """
        return _build_plugin_services_impl(self)

    def _fallback_transfer(self):
        """执行转移兜底定时任务的兼容入口。"""; return _fallback_transfer_impl(self)

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        """返回渲染模式：vue 联邦组件模式"""
        return "vue", "dist/assets"

    def get_form(self) -> Tuple[Optional[List[dict]], Dict[str, Any]]:
        """Vue 模式下返回前端配置组件使用的默认配置。"""
        return None, build_plugin_config_defaults()

    def get_page(self) -> Optional[List[dict]]:
        """Vue 模式下无详情页"""
        return None

    def __validate_config(self) -> bool:
        """校验转移做种所需的下载器和路径配置。"""; return _validate_config_impl(self)

    def __download(self, service: ServiceInfo, content: bytes,
                   save_path: str, torrent) -> Optional[str]:
        """向目标下载器添加转移后的种子内容。"""; return _download_impl(self, service, content, save_path, torrent)

    def transfer(self, trigger_source: str = "手动/定时"):
        """按当前配置执行一次转移做种流程。"""; return _transfer_impl(self, trigger_source)

    def __add_recheck_torrents(self, service: ServiceInfo, download_id: str, source: str = "未知来源"):
        """追加做种校验任务，记录来源用于日志区分。"""
        if not service or not download_id:
            return
        logger.info(f"【PT下载中心】做种校验服务：添加校验任务 [{source}] {service.name} / {download_id} ...")
        if not isinstance(self._recheck_torrents.get(service.name), dict):
            self._recheck_torrents[service.name] = {}
        self._recheck_torrents[service.name][download_id] = source or "未知来源"

    def check_recheck(self):
        """
        定时检查下载器中种子是否校验完成，校验完成且完整的自动开始辅种。
        同时执行队列外兜底扫描，处理插件重载后丢失队列的历史暂停任务。
        """
        return _check_recheck_impl(self)

    def _sweep_paused_seed_tasks(self, check_services: List[ServiceInfo]):
        """兜底扫描已完成但暂停的转移/铺种任务，并自动开始做种。"""
        return _sweep_paused_seed_tasks_impl(self, check_services)

    @staticmethod
    def __can_seeding(torrent: Any, dl_type: str):
        """
        判断种子是否可以做种并处于暂停状态
        """
        return _can_seeding_impl(torrent, dl_type)

    # ════════════════════════════════════════════════════════════
    # v2.0.0: 转移后自动重命名 + 站点标签
    # ════════════════════════════════════════════════════════════

    def _post_transfer_process(self, to_service: ServiceInfo, torrent_hash: str):
        """执行转移完成后的重命名、标签和复查登记。"""; return _post_transfer_process_impl(self, to_service, torrent_hash)

    def _rename_torrent(self, dl, dl_type: str, torrent_hash: str, torrent_name: str, save_path: str):
        """委托重命名服务处理单个种子名称。"""; return _rename_torrent_impl(self, dl, dl_type, torrent_hash, torrent_name, save_path)

    def _tag_torrent(self, dl, dl_type: str, torrent_hash: str, torrent_tags: list, trackers: list):
        """委托站点标签服务更新单个种子标签。"""; return _tag_torrent_impl(self, dl, dl_type, torrent_hash, torrent_tags, trackers)

    @staticmethod
    def _find_site_by_domain(domain: str) -> Optional[str]:
        """根据 tracker 域名查找对应站点名称。"""; return _find_site_by_domain_impl(domain)

    @staticmethod
    def _format_torrent_name(template_string: str, meta: MetaBase, mediainfo) -> Optional[str]:
        """根据模板和媒体信息格式化种子名称。"""; return _format_torrent_name_impl(template_string, meta, mediainfo)

    # ════════════════════════════════════════════════════════════
    # 重命名记录持久化
    # ════════════════════════════════════════════════════════════

    def _save_rename_record(self, torrent_hash: str, original_name: str, after_name: str,
                            success: bool, reason: str = ""):
        """保存单个种子的重命名结果记录。"""; return _save_rename_record_impl(self, torrent_hash, original_name, after_name, success, reason)

    def _get_failed_rename_hashes(self) -> set:
        """返回需要补刮的失败或脏名称种子 hash。"""; return _get_failed_rename_hashes_impl(self)

    def _retry_failed_renames(self, to_service: ServiceInfo):
        """对目标下载器中的失败重命名任务执行批量补刮。"""; return _retry_failed_renames_impl(self, to_service)

    def _retry_pending_renames(self):
        """重试历史失败和当前脏名称的待补刮任务。"""; return _retry_pending_renames_impl(self)

    def _retry_rename(self, hash: str = ""):
        """对指定 hash 执行单条补刮兼容入口。"""
        to_service = self.service_info(self._todownloader)
        return _retry_rename_by_hash_impl(self, to_service, hash)

    def _diagnostics(self):
        """生成插件详情页只读诊断数据。"""; return _build_diagnostics_impl(self)

    def record_rename_failure(self, torrent_hash: str, torrent_name: str,
                              category: str = "", reason: str = ""):
        """记录指定种子的重命名失败归档状态。"""; return _record_rename_failure_impl(self, torrent_hash, torrent_name, category, reason)

    def clear_rename_retry_state(self, torrent_hash: str):
        """清除指定种子的重命名重试状态。"""; return _clear_rename_retry_state_impl(self, torrent_hash)

    def is_rename_archived(self, torrent_hash: str):
        """判断指定种子是否已进入重命名归档。"""; return _is_rename_archived_impl(self, torrent_hash)

    def list_rename_archive(self, page: int = 1, page_size: int = 15):
        """分页列出重命名归档记录。"""; return _list_rename_archive_impl(self, page, page_size)

    def restore_rename_archive(self, torrent_hash: str):
        """恢复指定种子的重命名归档状态。"""; return _restore_rename_archive_impl(self, torrent_hash)

    def delete_rename_archive(self, torrent_hash: str):
        """删除指定种子的重命名归档状态。"""; return _delete_rename_archive_impl(self, torrent_hash)

    def rename_archive_stats(self):
        """统计当前重命名归档数量和状态。"""; return _rename_archive_stats_impl(self)

    @eventmanager.register(EventType.TransferComplete)
    def on_transfer_complete(self, event: Event):
        """监听 TransferComplete 事件，延迟 N 分钟后自动转移做种。"""; return _handle_transfer_complete_event_impl(self, event)
    @eventmanager.register(EventType.DownloadAdded)
    def on_download_added(self, event: Event):
        """监听下载新增事件，纳入 H&R/站点标签/命名补刀管理并唤醒上传限速协调。"""; return _handle_download_added_event_impl(self, event)
    @eventmanager.register(EventType.TransferFailed)
    def on_transfer_failed(self, event: Event):
        """监听整理失败事件，按配置删除源文件与下载记录。"""; return _handle_transfer_failed_event_impl(self, event)
    @eventmanager.register([EventType.DownloadFileDeleted, EventType.DownloadDeleted])
    def on_download_sync_delete(self, event: Event):
        """监听下载删除事件，同步删除转种和辅种任务。"""; return _handle_sync_delete_by_hash_event_impl(self, event, trigger=getattr(getattr(event, "event_type", None), "value", "DownloadDeleted"))
    @eventmanager.register(EventType.WebhookMessage)
    def on_webhook_message(self, event: Event):
        """监听媒体服务器删除 Webhook，同步删除转种和辅种任务。"""; return _handle_webhook_message_event_impl(self, event)

    @eventmanager.register(EventType.PluginAction)
    def on_plugin_action(self, event: Event):
        """监听插件动作事件：网盘同步删除与 H&R 命令。"""; return _handle_plugin_action_event_impl(self, event)

    @eventmanager.register(EventType.PluginTriggered)
    def on_plugin_triggered(self, event: Event):
        """监听刷流插件的下载新增动作，按刷流来源纳入 H&R 管理。"""; return _handle_plugin_triggered_event_impl(self, event)

    def _coordinate_upload_limits(self):
        """执行一轮上传限速扫描与动态额度分配。"""; return _run_upload_limit_cycle_impl(self)

    def _delayed_transfer(self):
        """执行 TransferComplete 延迟触发后的转移任务。"""; return _delayed_transfer_impl(self)
    # ════════════════════════════════════════════════════════════
    # v3.0.14: 按需做种校验
    # ════════════════════════════════════════════════════════════

    def _load_seed_recheck_queue(self):
        """读取按需做种校验队列。"""; return _load_seed_recheck_queue_impl(self)

    def _save_seed_recheck_queue(self, queue):
        """保存按需做种校验队列。"""; return _save_seed_recheck_queue_impl(self, queue)

    def _ensure_seed_recheck_worker(self):
        """确保按需做种复查后台线程已启动。"""; return _ensure_seed_recheck_worker_impl(self)

    def _stop_seed_recheck_worker(self):
        """停止按需做种复查后台线程并等待其退出。"""; return _stop_seed_recheck_worker_impl(self)

    def _seed_recheck_loop(self):
        """运行按需做种复查后台循环。"""; return _seed_recheck_loop_impl(self)

    def _process_seed_recheck_once(self, queue):
        """处理一轮按需做种复查队列。"""; return _process_seed_recheck_once_impl(self, queue)

    @staticmethod
    def _seed_should_remove_missing(item):
        """判断缺失种子队列项是否应移除。"""; return _seed_should_remove_missing_impl(item)

    @staticmethod
    def _seed_is_checking(state, dl_type):
        """判断下载器状态是否仍在校验中。"""; return _seed_is_checking_impl(state, dl_type)

    @staticmethod
    def _seed_is_ready(state, dl_type):
        """判断下载器状态是否可开始做种。"""; return _seed_is_ready_impl(state, dl_type)

    @staticmethod
    def _seed_is_error(state, dl_type):
        """判断下载器状态是否表示校验错误。"""; return _seed_is_error_impl(state, dl_type)

    def _seed_is_timeout(self, item):
        """判断复查队列项是否超过最大等待时间。"""; return _seed_is_timeout_impl(item, self._seed_max_wait_minutes)


    def stop_service(self):
        """停止插件后台调度器并释放运行资源。"""; return _stop_plugin_service_impl(self)
