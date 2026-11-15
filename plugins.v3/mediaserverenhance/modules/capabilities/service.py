"""服务端能力模块。

探测媒体服务器自身安装的服务端插件（如 Emby 的 StrmAssistant），
用于能力门控与诊断提示，不调用其私有接口。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from app.sdk.logging import logger

from ...adapter import mediaserver
from ...utils import store
from ...utils.config import as_list
from ..refresh.service import history_limit, plugin_active

MODULE = "capabilities"

# 默认关注的媒体服务器端插件关键词（子串匹配，忽略大小写）
DEFAULT_WATCHED = ("StrmAssistant", "神医")


def _servers(plugin, override: Optional[Sequence[str]] = None) -> List[str]:
    """解析本次探测涉及的服务器清单。"""
    explicit = as_list(override)
    if explicit:
        return explicit
    configured = as_list(getattr(plugin, "_capability_servers", None))
    if configured:
        return configured
    return [row["name"] for row in mediaserver.list_server_configs() if row.get("enabled")]


def watched_keywords(plugin) -> List[str]:
    """返回关注的服务端插件关键词。

    :param plugin: 插件实例
    :return: 关键词列表，配置为空时使用默认值
    """
    configured = as_list(getattr(plugin, "_capability_watched", None))
    return configured or list(DEFAULT_WATCHED)


def _match_watched(plugins: Sequence[Dict[str, Any]], keywords: Sequence[str]) -> List[Dict[str, Any]]:
    """在已安装插件中匹配关注项。

    :param plugins: 服务端插件列表
    :param keywords: 关注关键词
    :return: 命中的插件条目列表
    """
    hits: List[Dict[str, Any]] = []
    for keyword in keywords:
        needle = str(keyword or "").strip().lower()
        if not needle:
            continue
        matched = [
            {
                "keyword": keyword,
                "name": str(row.get("name") or ""),
                "version": str(row.get("version") or ""),
                "status": str(row.get("status") or ""),
            }
            for row in plugins
            if needle in str(row.get("name") or "").lower()
        ]
        hits.append(
            {
                "keyword": keyword,
                "installed": bool(matched),
                "matches": matched,
            }
        )
    return hits


def probe(plugin, servers: Optional[Sequence[str]] = None,
          trigger: str = "手动") -> Dict[str, Any]:
    """探测服务端插件能力并保存快照。

    :param plugin: 插件实例
    :param servers: 指定服务器
    :param trigger: 触发来源说明
    :return: 探测结果字典
    """
    server_names = _servers(plugin, servers)
    keywords = watched_keywords(plugin)
    checked_at = store.now_text()
    snapshot: Dict[str, Any] = {"time": checked_at, "servers": []}
    job = store.build_job(MODULE, "probe", trigger=trigger, total=len(server_names))
    if not server_names:
        store.finish_job(job, "skipped", "没有可用的媒体服务器")
        store.append_job(plugin, job, history_limit(plugin))
        store.write_value(plugin, store.CAPABILITIES_KEY, snapshot)
        return snapshot

    success = 0
    failed = 0
    for name in server_names:
        row = {"server": name, "type": "", "supported": False, "error": "",
               "checked_at": checked_at, "plugins": [], "watched": []}
        config_row = next(
            (item for item in mediaserver.list_server_configs(include_disabled=True)
             if item.get("name") == name),
            None,
        )
        if config_row:
            row["type"] = str(config_row.get("type") or "")
        try:
            result = mediaserver.probe_server_plugins(name)
        except Exception as error:  # noqa: BLE001 - 探测异常按不可用记录
            result = {"supported": False, "plugins": [], "error": str(error)}
        row["supported"] = bool(result.get("supported"))
        row["error"] = str(result.get("error") or "")
        row["plugins"] = list(result.get("plugins") or [])
        row["watched"] = _match_watched(row["plugins"], keywords)
        if row["error"]:
            failed += 1
        else:
            success += 1
        snapshot["servers"].append(row)

    store.write_value(plugin, store.CAPABILITIES_KEY, snapshot)
    store.finish_job(
        job,
        "success" if failed == 0 else ("failed" if success == 0 else "partial"),
        f"探测 {len(server_names)} 台服务器，异常 {failed} 台",
        success=success,
        failed=failed,
    )
    store.append_job(plugin, job, history_limit(plugin))
    return snapshot


def latest(plugin) -> Dict[str, Any]:
    """读取最近一次能力探测快照。"""
    snapshot = store.read_snapshot(plugin, store.CAPABILITIES_KEY)
    if not snapshot:
        return {"time": "", "servers": []}
    snapshot.setdefault("servers", [])
    return snapshot


def watched_summary(plugin) -> List[Dict[str, Any]]:
    """汇总各服务器上关注插件的命中情况，供总览页展示。

    :param plugin: 插件实例
    :return: 每台服务器的命中摘要
    """
    summary: List[Dict[str, Any]] = []
    for row in latest(plugin).get("servers") or []:
        watched = row.get("watched") or []
        installed = [item for item in watched if item.get("installed")]
        summary.append(
            {
                "server": row.get("server", ""),
                "type": row.get("type", ""),
                "supported": bool(row.get("supported")),
                "error": row.get("error", ""),
                "installed": ", ".join(item.get("keyword", "") for item in installed),
                "plugin_count": len(row.get("plugins") or []),
            }
        )
    return summary


def run_scheduled(plugin) -> None:
    """定时能力探测入口。"""
    if not plugin_active(plugin, MODULE):
        return
    try:
        probe(plugin, trigger="定时探测")
    except Exception as error:  # noqa: BLE001 - 定时任务异常只记录
        logger.error(f"【媒体服务器增强】定时能力探测失败：{error}")
