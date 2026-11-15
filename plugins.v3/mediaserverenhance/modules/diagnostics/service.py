"""运行诊断模块。

汇总插件自身状态、媒体服务器连通性、配置规模与历史规模，给出可执行的告警。
"""

from __future__ import annotations

from typing import Any, Dict, List

from ...adapter import mediaserver
from ...utils import store
from ...utils.config import as_bool
from ...utils.pillow import pillow_available
from .. import capabilities, refresh
from ..audit.service import latest_report
from ..covers.service import cover_history

MODULE = "diagnostics"

# 已知与本插件功能重叠的市场插件，建议用户自行停用
OVERLAP_PLUGINS = (
    ("CoverGen", "封面生成"),
    ("StrmManage", "STRM 生成与旁车"),
    ("EmbyMetaRefresh", "元数据刷新"),
    ("MediaSyncDel", "删除联动"),
    ("MediaServerRefresh", "媒体库刷新"),
)


def build(plugin) -> Dict[str, Any]:
    """生成运行诊断快照。

    :param plugin: 插件实例
    :return: 诊断结果字典
    """
    warnings: List[str] = []
    servers: List[Dict[str, Any]] = []
    for row in mediaserver.list_server_configs(include_disabled=True):
        name = str(row.get("name") or "")
        online, message = mediaserver.server_online(name)
        libraries = mediaserver.list_libraries(name) if online else []
        servers.append(
            {
                "name": name,
                "type": str(row.get("type") or ""),
                "enabled": bool(row.get("enabled")),
                "online": online,
                "message": message,
                "libraries": len(libraries),
                "items": sum(int(item.get("item_count") or 0) for item in libraries),
            }
        )
        if row.get("enabled") and not online:
            warnings.append(f"媒体服务器 {name} 已启用但连接失败：{message}")

    enabled_servers = [item for item in servers if item["enabled"]]
    if not enabled_servers:
        warnings.append("没有启用的媒体服务器，刷新、体检与封面模块都无法运行")

    modules = {
        "refresh": as_bool(getattr(plugin, "_refresh_enabled", True)),
        "audit": as_bool(getattr(plugin, "_audit_enabled", True)),
        "covers": as_bool(getattr(plugin, "_covers_enabled", False)),
        "capabilities": as_bool(getattr(plugin, "_capabilities_enabled", True)),
    }
    if not any(modules.values()):
        warnings.append("所有业务模块都已关闭，插件不会执行任何操作")

    if modules["covers"] and not pillow_available():
        warnings.append("封面工坊已启用，但当前环境缺少 Pillow，无法生成封面")

    stats = store.today_job_stats(plugin)
    report = latest_report(plugin)
    covers = cover_history(plugin)
    history = {
        "jobs": len(store.load_jobs(plugin)),
        "today": stats["today"],
        "failed": stats["failed"],
        "audit_issues": len(report.get("issues") or []),
        "audit_time": report.get("time", ""),
        "cover_runs": len(covers),
        "keep": refresh.history_limit(plugin),
    }
    if history["failed"] > 0:
        warnings.append(f"存在 {history['failed']} 条失败任务，可在任务中心查看原因")

    snapshot = capabilities.latest(plugin)
    capability_servers = snapshot.get("servers") or []
    if modules["capabilities"] and not capability_servers:
        warnings.append("尚未执行过服务端能力探测，能力矩阵为空")

    config_info = {
        "enabled": as_bool(getattr(plugin, "_enabled", False)),
        "notify": as_bool(getattr(plugin, "_notify", False)),
        "refresh_on_transfer": as_bool(getattr(plugin, "_refresh_on_transfer", True)),
        "debounce": getattr(plugin, "_refresh_debounce_seconds", 30),
        "audit_checks": list(getattr(plugin, "_audit_checks", []) or []),
        "cover_style": getattr(plugin, "_cover_style", ""),
        "cover_limit": getattr(plugin, "_cover_limit", 0),
        "watched": list(capabilities.watched_keywords(plugin)),
    }

    return {
        "checked": True,
        "time": store.now_text(),
        "plugin": {
            "version": getattr(plugin, "plugin_version", ""),
            "enabled": as_bool(getattr(plugin, "_enabled", False)),
            "modules": modules,
            "pillow": pillow_available(),
        },
        "servers": servers,
        "config": config_info,
        "history": history,
        "warnings": warnings,
        "overlap": [
            {"plugin": name, "capability": label} for name, label in OVERLAP_PLUGINS
        ],
    }
