"""源端种子数据网络导出（统一 payload 接口）。

宿主下载器模块无统一导出方法（MP 3.8.x qB/TR 模块均无 export_torrent），
因此本模块直连下载器协议完成导出：

- qbittorrent：WebUI API /torrents/export（凭据取自下载器配置），
  模块若未来提供 export_torrent 则优先使用
- transmission：transmission_rpc torrent-get 'torrent' 字段（base64 元数据）
- rtorrent：ruTorrent WebUI source 插件逐个导出（需 downloader_ext 扩展配置：
  webui_url 必填，username/password/source_plugin 可选），连续失败达阈值即
  中止剩余请求；可选 session_dir 按会话目录 {hash}.torrent 回退
"""

import base64
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from app.sdk.logging import logger

_SOURCE_HTTP_TIMEOUT = (5, 30)
_SOURCE_SINGLE_FALLBACK_THRESHOLD = 5


def get_downloader_ext(plugin, downloader_name: str) -> Dict[str, Any]:
    """读取下载器扩展配置（downloader_ext JSON：名称→{webui_url, source_plugin, ...}）。"""
    raw = getattr(plugin, "_downloader_ext", "") or "{}"
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    entry = parsed.get(downloader_name)
    return entry if isinstance(entry, dict) else {}


def _downloader_credentials(service: Any) -> Dict[str, str]:
    """从 ServiceInfo.config（DownloaderConf.config）提取连接凭据。"""
    conf = getattr(service, "config", None)
    inner = getattr(conf, "config", None) or {}
    if not isinstance(inner, dict):
        inner = {}
    return {
        "host": (getattr(conf, "host", None) or inner.get("host") or "").rstrip("/"),
        "username": getattr(conf, "username", None) or inner.get("username") or "",
        "password": getattr(conf, "password", None) or inner.get("password") or "",
    }


def _qb_export(instance: Any, info_hash: str, service: Any = None) -> Optional[bytes]:
    """qBittorrent：模块方法优先，WebUI /torrents/export 兜底。"""
    export = getattr(instance, "export_torrent", None)
    if callable(export):
        try:
            data = export(info_hash)
        except Exception as err:
            logger.warning(f"【PT下载中心:转移做种】qB 模块导出异常 {info_hash[:8]}：{err}")
            data = None
        if data:
            return data
    if service is None:
        logger.warning("【PT下载中心:转移做种】qB 网络导出缺少下载器配置，无法兜底")
        return None
    cred = _downloader_credentials(service)
    if not cred["host"]:
        logger.warning("【PT下载中心:转移做种】qB 下载器缺少 host 配置，无法网络导出")
        return None
    try:
        resp = requests.post(
            f"{cred['host']}/api/v2/torrents/export",
            data={"hash": info_hash},
            auth=(cred["username"], cred["password"]) if cred["username"] else None,
            timeout=_SOURCE_HTTP_TIMEOUT,
        )
    except Exception as err:
        logger.warning(f"【PT下载中心:转移做种】qB WebUI 导出失败 {info_hash[:8]}：{err}")
        return None
    if resp.status_code != 200 or not resp.content:
        logger.warning(
            f"【PT下载中心:转移做种】qB WebUI 导出失败 {info_hash[:8]}：HTTP {resp.status_code}"
        )
        return None
    return resp.content


def _tr_export(instance: Any, info_hash: str) -> Optional[bytes]:
    """Transmission：torrent-get 'torrent' 字段（base64 元数据）。"""
    trc = getattr(instance, "trc", None) or instance
    try:
        torrents = trc.get_torrents(ids=[info_hash], arguments=["torrent"])
        raw = None
        if torrents:
            fields = getattr(torrents[0], "fields", None) or getattr(torrents[0], "_fields", {})
            raw = fields.get("torrent") if isinstance(fields, dict) else None
        metainfo = getattr(raw, "value", raw)
    except Exception as err:
        logger.warning(f"【PT下载中心:转移做种】TR 获取种子元数据失败 {info_hash[:8]}：{err}")
        return None
    if not metainfo:
        return None
    try:
        return base64.b64decode(metainfo)
    except Exception as err:
        logger.warning(f"【PT下载中心:转移做种】TR 元数据解码失败 {info_hash[:8]}：{err}")
        return None


def _rt_export_one(ext: Dict[str, Any], info_hash: str) -> Optional[bytes]:
    """rtorrent：ruTorrent source 插件单个导出。"""
    webui = str(ext.get("webui_url") or "").rstrip("/")
    if not webui:
        return None
    plugin_path = str(ext.get("source_plugin") or "plugins/source").strip("/")
    auth = None
    username = str(ext.get("username") or "")
    password = str(ext.get("password") or "")
    if username:
        auth = (username, password)
    try:
        resp = requests.get(
            f"{webui}/{plugin_path}/get.php",
            params={"hash": info_hash},
            auth=auth,
            timeout=_SOURCE_HTTP_TIMEOUT,
        )
    except Exception as err:
        logger.warning(f"【PT下载中心:转移做种】rt source 导出失败 {info_hash[:8]}：{err}")
        return None
    if resp.status_code != 200 or not resp.content:
        return None
    return resp.content


def _rt_session_fallback(session_dir: str, info_hash: str) -> Optional[bytes]:
    """rtorrent：从会话目录读取 {hash}.torrent。"""
    if not session_dir:
        return None
    path = Path(session_dir) / f"{info_hash}.torrent"
    try:
        return path.read_bytes()
    except OSError:
        return None


def _rt_source_export(ext: Dict[str, Any], info_hashes: List[str]) -> Dict[str, bytes]:
    """rtorrent 批量导出：连续失败达阈值即中止。"""
    results: Dict[str, bytes] = {}
    consecutive_fail = 0
    for info_hash in info_hashes:
        data = _rt_export_one(ext, info_hash)
        if data:
            results[info_hash] = data
            consecutive_fail = 0
        else:
            consecutive_fail += 1
            if consecutive_fail >= _SOURCE_SINGLE_FALLBACK_THRESHOLD:
                logger.warning(
                    f"【PT下载中心:转移做种】rt source 连续失败 {consecutive_fail} 次，中止剩余导出"
                )
                break
        time.sleep(0.2)
    return results


def get_torrent_payloads(
    plugin,
    dl_type: str,
    downloader_name: str,
    service: Any,
    info_hashes: List[str],
) -> Dict[str, bytes]:
    """统一入口：按下载器类型网络导出种子数据，{info_hash: bytes}。

    service 为 ServiceInfo（instance + config 凭据）。
    """
    if not info_hashes:
        return {}
    instance = getattr(service, "instance", None) if service is not None else None
    if dl_type == "qbittorrent":
        results: Dict[str, bytes] = {}
        for info_hash in info_hashes:
            data = _qb_export(instance, info_hash, service)
            if data:
                results[info_hash] = data
        return results
    if dl_type == "transmission":
        results = {}
        for info_hash in info_hashes:
            data = _tr_export(instance, info_hash)
            if data:
                results[info_hash] = data
        return results
    if dl_type == "rtorrent":
        ext = get_downloader_ext(plugin, downloader_name)
        if not ext.get("webui_url"):
            logger.error(
                f"【PT下载中心:转移做种】下载器 {downloader_name} 为 rtorrent，"
                "但未配置 WebUI 地址（下载器扩展配置），无法网络导出"
            )
            return {}
        results = _rt_source_export(ext, info_hashes)
        missing = [h for h in info_hashes if h not in results]
        session_dir = str(ext.get("session_dir") or "").strip()
        for info_hash in missing:
            data = _rt_session_fallback(session_dir, info_hash)
            if data:
                results[info_hash] = data
        return results
    logger.warning(f"【PT下载中心:转移做种】下载器类型 {dl_type} 不支持网络导出")
    return {}


def get_torrent_payload(plugin, dl_type: str, downloader_name: str, service: Any, info_hash: str) -> Optional[bytes]:
    """单种子便捷入口。"""
    mapping = get_torrent_payloads(plugin, dl_type, downloader_name, service, [info_hash])
    return mapping.get(info_hash)
