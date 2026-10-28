"""下载中心插件生命周期初始化服务。"""

from __future__ import annotations

from app.sdk.config import settings
from app.sdk.logging import logger
from apscheduler.schedulers.background import BackgroundScheduler

from ..utils.config import is_upload_limit_active
from .config import initialize_runtime_config
from ..modules.autoremove.service import AutoRemoveService
from ..modules.transfer.events import clear_transfer_schedule, restore_transfer_schedule
from ..modules.failclean.service import FailCleanService
from ..modules.hr.service import HrService
from ..modules.transfer.recheck import (
    ensure_seed_recheck_worker,
    load_seed_recheck_queue,
    stop_seed_recheck_worker,
)
from ..modules.transfer.service import validate_config
from ..modules.uploadlimit.worker import (
    start_upload_limit_worker,
    stop_upload_limit_worker,
)
from ..modules.uploadlimit.service import load_upload_limit_state, restore_upload_limits


def initialize_plugin(plugin, config: dict = None) -> None:
    """初始化插件运行时配置，并按当前配置启动转移做种调度。"""
    plugin.stop_service()
    config = initialize_runtime_config(plugin, config)
    event = getattr(plugin, "_event", None)
    if event is not None:
        event.clear()

    upload_state = load_upload_limit_state(plugin)
    if is_upload_limit_active(plugin):
        start_upload_limit_worker(plugin)
    elif upload_state.get("management_active") or upload_state.get("downloaders"):
        restore_upload_limits(plugin)

    scheduler_needed = False
    if plugin._transfer_active:
        if not validate_config(plugin):
            _disable_invalid_transfer_config(plugin, config)
        else:
            plugin._scheduler = BackgroundScheduler(timezone=settings.TZ)
            restore_transfer_schedule(plugin)
            scheduler_needed = True

    plugin._hr_service = HrService(plugin)
    plugin._hr_service.init_module(config)

    plugin._autoremove_service = AutoRemoveService(plugin)
    plugin._autoremove_service.init_module(config)

    plugin._failclean_service = FailCleanService(plugin)
    plugin._failclean_service.init_module(config)
    if scheduler_needed:
        _start_scheduler_if_needed(plugin, print_jobs=True)

    if getattr(plugin, "_enabled", False) and load_seed_recheck_queue(plugin):
        ensure_seed_recheck_worker(plugin)


def _disable_invalid_transfer_config(plugin, config: dict) -> None:
    """在转移配置无效时按旧逻辑关闭转移开关并持久化。"""
    plugin._enabled = False
    config["enabled"] = plugin._enabled
    plugin.update_config(config=config)


def _start_scheduler_if_needed(plugin, print_jobs: bool = False) -> None:
    """在 scheduler 已有任务且尚未运行时启动后台调度器。"""
    if not plugin._scheduler.get_jobs():
        return
    if print_jobs:
        plugin._scheduler.print_jobs()
    if not plugin._scheduler.running:
        plugin._scheduler.start()


def _stop_hr_service(plugin) -> None:
    """停止 H&R 服务并撤销其保护快照。"""
    service = getattr(plugin, "_hr_service", None)
    if service is None:
        return
    service.stop()
    plugin._hr_service = None


def _stop_autoremove_service(plugin) -> None:
    """停止自动删种服务。"""
    service = getattr(plugin, "_autoremove_service", None)
    if service is None:
        return
    service.stop()
    plugin._autoremove_service = None


def _stop_failclean_service(plugin) -> None:
    """停止整理失败清理服务。"""
    service = getattr(plugin, "_failclean_service", None)
    if service is None:
        return
    service.stop()
    plugin._failclean_service = None

def stop_plugin_service(plugin) -> None:
    """发出退出信号并停止后台调度器，旧批次通过代次识别停止。"""
    plugin._transfer_stop_generation = int(getattr(plugin, "_transfer_stop_generation", 0) or 0) + 1
    event = getattr(plugin, "_event", None)
    if event is not None:
        event.set()
    clear_transfer_schedule(plugin)
    try:
        if not plugin._scheduler:
            return
        plugin._scheduler.remove_all_jobs()
        if plugin._scheduler.running:
            plugin._scheduler.shutdown()
        plugin._scheduler = None
    except Exception as error:
        logger.error(f"【PT下载中心】停止服务失败: {error}")
    finally:
        stop_seed_recheck_worker(plugin)
        _stop_hr_service(plugin)
        _stop_autoremove_service(plugin)
        _stop_failclean_service(plugin)
        stop_upload_limit_worker(plugin)


__all__ = ("initialize_plugin", "stop_plugin_service")
