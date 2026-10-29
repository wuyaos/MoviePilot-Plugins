"""下载中心插件生命周期初始化服务。"""

from __future__ import annotations

from app.sdk.config import settings
from app.sdk.logging import logger
from apscheduler.schedulers.background import BackgroundScheduler

from ..utils.config import (
    clear_module_fault,
    is_upload_limit_active,
    record_module_fault,
)
from .config import initialize_runtime_config
from ..modules.autoremove.service import AutoRemoveService
from ..modules.transfer.events import clear_transfer_schedule, restore_transfer_schedule
from ..modules.failclean.service import FailCleanService
from ..modules.hr.guard import get_guard
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

    _init_upload_limit_isolated(plugin)

    scheduler_needed = False
    if plugin._transfer_active:
        if not validate_config(plugin):
            _mark_transfer_config_invalid(plugin)
        else:
            plugin._scheduler = BackgroundScheduler(timezone=settings.TZ)
            restore_transfer_schedule(plugin)
            scheduler_needed = True

    # 模块独立性（Goal: 单模块故障不得拖垮其它模块）：每个服务单独隔离初始化，
    # 任一模块抛异常只禁用该模块，其余模块与转移调度照常启动。
    plugin._hr_service = _init_service_isolated(plugin, "H&R", "hr", HrService, config)
    _sync_hr_guard_intent(plugin, config)
    plugin._autoremove_service = _init_service_isolated(
        plugin, "自动删种", "autoremove", AutoRemoveService, config
    )
    plugin._failclean_service = _init_service_isolated(
        plugin, "失败清理", "failclean", FailCleanService, config
    )
    if scheduler_needed:
        _start_scheduler_if_needed(plugin, print_jobs=True)

    if getattr(plugin, "_enabled", False) and load_seed_recheck_queue(plugin):
        try:
            ensure_seed_recheck_worker(plugin)
        except Exception as error:
            logger.error(f"【PT下载中心】做种校验 worker 启动失败（不影响其它模块）: {error}")


def _init_service_isolated(
    plugin, label: str, module: str, service_cls, config: dict
) -> object:
    """隔离初始化单个模块：失败时只标记该模块运行异常并返回 None，不中断其它模块。

    运行异常记录在 plugin._module_faults（页面据此显示「故障」），既不关闭插件总开关，
    也不落盘改写用户的模块开关——用户开关只能由用户或配置页改变，避免每轮 reload
    把失败状态固化进配置。
    """
    try:
        service = service_cls(plugin)
        service.init_module(config)
        clear_module_fault(plugin, module)
        return service
    except Exception as error:
        logger.error(f"【PT下载中心:{label}】模块初始化失败，已隔离该模块（其它模块不受影响）: {error}")
        record_module_fault(plugin, module, str(error))
        return None


def _mark_transfer_config_invalid(plugin) -> None:
    """转移配置无效：只标记该模块运行异常，不改插件总开关、不落盘改写用户开关。"""
    reason = "转移配置不完整（源/目的下载器、保存路径或任务缺少必要项）"
    logger.error(
        f"【PT下载中心】转移配置无效，已停止转移调度并标记运行异常（其余模块照常运行）：{reason}"
    )
    record_module_fault(plugin, "transfer", reason)


def _hr_protection_expected(config: dict) -> bool:
    """读取 H&R 保护开关意图（缺省与 modules/hr/constants.py 的默认值一致）。"""
    raw = (config or {}).get("hr_protection_enabled")
    return True if raw is None else bool(raw)


def _sync_hr_guard_intent(plugin, config: dict) -> None:
    """登记 H&R 保护的联动预期（阶段二 D 联动规则）。

    - 模块未生效（模块关闭/总开关关闭/已降级为故障）：撤销进程内保护快照，
      关闭的模块不得继续拦截其它模块的删除动作。
    - 模块生效但服务不可用（初始化失败）：保护状态无法确认，相关删除保守跳过，
      只影响该次删除，不拖停其它模块。
    """
    guard = get_guard()
    if not getattr(plugin, "_hr_enabled", False):
        guard.expect(enabled=False)
        return
    if getattr(plugin, "_hr_service", None) is not None:
        return  # 服务已在 _refresh_guard 中登记预期与快照
    guard.expect(enabled=_hr_protection_expected(config))
    logger.warning(
        "【PT下载中心:H&R】H&R 模块生效但服务不可用，保护状态无法确认："
        "相关删除动作将保守跳过（其余模块照常运行）"
    )


def _init_upload_limit_isolated(plugin) -> None:
    """按上传限速模块边界初始化：失败只标记该模块异常，不影响其它模块。"""
    try:
        upload_state = load_upload_limit_state(plugin)
        if is_upload_limit_active(plugin):
            start_upload_limit_worker(plugin)
        elif upload_state.get("management_active") or upload_state.get("downloaders"):
            restore_upload_limits(plugin)
        clear_module_fault(plugin, "upload_limit")
    except Exception as error:
        logger.error(
            f"【PT下载中心:上传限速】模块初始化失败，已隔离该模块（其它模块不受影响）: {error}"
        )
        record_module_fault(plugin, "upload_limit", str(error))

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

def _stop_isolated(label: str, action) -> None:
    """隔离停止单个后台组件：任一组件停止失败只记录日志，不影响其它组件。"""
    try:
        action()
    except Exception as error:
        logger.error(f"【PT下载中心:{label}】停止失败（不影响其它模块）: {error}")


def _stop_background_services(plugin) -> None:
    """逐个隔离停止各模块后台组件（模块独立性：单个 stop 抛异常不阻断其余组件）。"""
    _stop_isolated("做种校验 worker", lambda: stop_seed_recheck_worker(plugin))
    _stop_isolated("H&R", lambda: _stop_hr_service(plugin))
    _stop_isolated("自动删种", lambda: _stop_autoremove_service(plugin))
    _stop_isolated("失败清理", lambda: _stop_failclean_service(plugin))
    _stop_isolated("上传限速", lambda: stop_upload_limit_worker(plugin))


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
        _stop_background_services(plugin)


__all__ = ("initialize_plugin", "stop_plugin_service")
