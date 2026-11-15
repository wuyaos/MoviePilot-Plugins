"""媒体服务器增强 - 宿主事件入口。

事件只做「取数据 → 判定开关 → 交给 service」，不含业务逻辑。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.sdk.logging import logger

from ..modules import capabilities
from ..modules.audit import service as audit_service
from ..modules.covers import service as cover_service
from ..modules.refresh import service as refresh_service
from ..utils.config import as_bool

# 插件远程命令 → 处理动作
COMMAND_ACTIONS: Dict[str, str] = {
    "refresh_now": "立即整库刷新",
    "refresh_recent": "刷新最近媒体",
    "audit_run": "立即媒体库体检",
    "cover_run": "立即生成封面",
    "capabilities_probe": "立即探测服务端能力",
}


def _event_data(event: Any) -> Dict[str, Any]:
    """兼容字典与事件对象两种形态取出 event_data。

    :param event: 宿主事件对象
    :return: 事件数据字典，取不到时返回空字典
    """
    if isinstance(event, dict):
        data = event.get("event_data")
        return data if isinstance(data, dict) else event
    data = getattr(event, "event_data", None)
    return data if isinstance(data, dict) else {}


def handle_transfer_complete_event(plugin, event: Any) -> None:
    """整理完成事件：并入防抖缓冲，窗口结束后批量刷新媒体库。

    :param plugin: 插件实例
    :param event: ``TransferComplete`` 事件
    """
    if not as_bool(getattr(plugin, "_refresh_enabled", False)):
        return
    try:
        refresh_service.enqueue_transfer(plugin, _event_data(event))
    except Exception as error:  # noqa: BLE001 - 事件线程不得向宿主抛错
        logger.error(f"【媒体服务器增强】处理入库事件失败：{error}")


def handle_plugin_action_event(plugin, event: Any) -> Optional[Dict[str, Any]]:
    """插件动作事件：按 action 触发对应模块。

    :param plugin: 插件实例
    :param event: ``PluginAction`` 事件
    :return: ``{success, message}`` 结果，非本插件动作返回 None
    """
    data = _event_data(event)
    action = str(data.get("action") or "").strip()
    if action not in COMMAND_ACTIONS:
        return None
    if not as_bool(getattr(plugin, "_enabled", False)):
        return {"success": False, "message": "插件未启用"}
    try:
        if action == "refresh_now":
            job = refresh_service.run_refresh(plugin, [], trigger="远程命令", root_refresh=True)
        elif action == "refresh_recent":
            job = refresh_service.run_recent_refresh(plugin, trigger="远程命令")
        elif action == "audit_run":
            report = audit_service.run_audit(plugin, trigger="远程命令")
            return {
                "success": True,
                "message": f"体检完成，发现 {len(report.get('issues') or [])} 个问题",
            }
        elif action == "cover_run":
            result = cover_service.run_cover(plugin, trigger="远程命令")
            return {"success": True, "message": str(result.get("message") or "封面任务已执行")}
        else:
            snapshot = capabilities.probe(plugin, trigger="远程命令")
            return {
                "success": True,
                "message": f"能力探测完成，共 {len(snapshot.get('servers') or [])} 台服务器",
            }
        return {"success": job.get("status") != "failed", "message": str(job.get("message") or "")}
    except Exception as error:  # noqa: BLE001 - 远程命令失败需回执而非抛出
        logger.error(f"【媒体服务器增强】远程命令 {action} 执行失败：{error}")
        return {"success": False, "message": f"执行失败：{error}"}
