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


def _tr_rpc(service: Any, method: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """直连 Transmission RPC（含 409 session 握手），返回 arguments 字典。"""
    cred = _downloader_credentials(service)
    host = cred["host"]
    if not host:
        return {}
    if not host.startswith("http"):
        host = f"http://{host}"
    session = requests.Session()
    if cred["username"]:
        session.auth = (cred["username"], cred["password"])
    url = f"{host.rstrip('/')}/transmission/rpc"
    for _ in range(2):
        try:
            resp = session.post(
                url, json={"method": method, "arguments": arguments},
                timeout=_SOURCE_HTTP_TIMEOUT,
            )
        except Exception as err:
            logger.warning(f"【PT下载中心:转移做种】Transmission RPC 请求失败：{err}")
            return {}
        if resp.status_code == 409:
            session.headers["X-Transmission-Session-Id"] = resp.headers.get(
                "X-Transmission-Session-Id", "")
            continue
        if resp.status_code != 200:
            logger.warning(f"【PT下载中心:转移做种】Transmission RPC HTTP {resp.status_code}")
            return {}
        try:
            payload = resp.json()
        except ValueError as err:
            logger.warning(f"【PT下载中心:转移做种】Transmission RPC 响应解析失败：{err}")
            return {}
        if payload.get("result") != "success":
            logger.warning(f"【PT下载中心:转移做种】Transmission RPC 返回 {payload.get('result')}")
            return {}
        return payload.get("arguments") or {}
    return {}


def _tr_first_field(rows: Any, name: str) -> Any:
    """从 transmission_rpc 对象取字段值（兼容 fields 字典与属性两种形态）。"""
    fields = getattr(rows, "fields", None) or getattr(rows, "_fields", None)
    if isinstance(fields, dict):
        raw = fields.get(name)
        return getattr(raw, "value", raw)
    return getattr(rows, name, None)


def _read_bytes(path: str) -> Optional[bytes]:
    try:
        data = Path(path).read_bytes()
    except OSError:
        return None
    return data or None


def _tr_path_candidates(remote_path: str, ext: Dict[str, Any], info_hash: str,
                        fallback_dir: str) -> List[str]:
    """TR 元数据文件候选：容器内路径映射 → 原路径 → 扩展目录 → 全局源种子目录。"""
    ext = ext or {}
    candidates: List[str] = []
    remote = str(remote_path or "").strip()
    remote_dir = str(ext.get("torrent_dir") or "").strip().rstrip("/")
    local_dir = str(ext.get("local_torrent_dir") or "").strip().rstrip("/")
    if remote and remote_dir and local_dir and remote.startswith(remote_dir):
        candidates.append(f"{local_dir}{remote[len(remote_dir):]}")
    if remote:
        candidates.append(remote)
    for directory in (local_dir, str(fallback_dir or "").strip().rstrip("/")):
        if not directory:
            continue
        for name in (info_hash.lower(), info_hash.upper()):
            candidates.append(f"{directory}/{name}.torrent")
    return candidates


def _tr_export(instance: Any, info_hash: str, service: Any = None,
               ext: Optional[Dict[str, Any]] = None, fallback_dir: str = "") -> Optional[bytes]:
    """Transmission 元数据导出。

    TR 4 起 torrent-get 不再返回 `torrent`（base64 元数据）字段，只能拿到
    `torrentFile`（容器内 .torrent 路径），因此按三级回退：
    1. torrent-get `torrent` 字段（TR 3.x）
    2. torrent-get `torrentFile` 路径 → 扩展配置映射后的本机路径直接读
    3. 扩展配置 local_torrent_dir / 全局「源种子文件路径」下 {hash}.torrent
    """
    # TR 4 已移除 `torrent` 字段：只请求它会被判为「no fields specified」，
    # 因此连同 torrentFile 一次取回（TR 4 返回 null，TR 3 返回 base64 元数据）。
    arguments = {"ids": [info_hash], "fields": ["torrent", "torrentFile"]}
    rows: Any = None
    if service is not None and _downloader_credentials(service)["host"]:
        rows = (_tr_rpc(service, "torrent-get", arguments) or {}).get("torrents")
    else:
        trc = getattr(instance, "trc", None) or instance
        try:
            rows = trc.get_torrents(ids=[info_hash], arguments=["torrent", "torrentFile"])
        except Exception as err:
            logger.warning(f"【PT下载中心:转移做种】TR 获取种子元数据失败 {info_hash[:8]}：{err}")
            rows = None
    metainfo = None
    remote_path = ""
    if rows:
        metainfo = _tr_first_field(rows[0], "torrent")
        remote_path = str(_tr_first_field(rows[0], "torrentFile") or "")
    if metainfo:
        try:
            decoded = base64.b64decode(metainfo)
        except Exception as err:
            logger.warning(f"【PT下载中心:转移做种】TR 元数据解码失败 {info_hash[:8]}：{err}")
            decoded = None
        if decoded:
            return decoded

    if not remote_path and service is not None and _downloader_credentials(service)["host"]:
        file_rows = (_tr_rpc(service, "torrent-get",
                             {"ids": [info_hash], "fields": ["torrentFile"]}) or {}).get("torrents")
        if file_rows:
            remote_path = str(_tr_first_field(file_rows[0], "torrentFile") or "")
    for candidate in _tr_path_candidates(remote_path, ext or {}, info_hash, fallback_dir):
        data = _read_bytes(candidate)
        if data:
            logger.info(
                f"【PT下载中心:转移做种】TR 元数据改用本机种子文件 {candidate}：{info_hash[:8]}"
            )
            return data
    logger.warning(
        f"【PT下载中心:转移做种】TR 元数据获取失败 {info_hash[:8]}："
        "Transmission 4 已移除 torrent 元数据字段，且本机读不到 .torrent 文件。"
        "请在下载器扩展配置填 torrent_dir（下载器内路径，如 /config/torrents）"
        "+ local_torrent_dir（本机可读路径），或全局配置「源种子文件路径」"
    )
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
    # ruTorrent source 插件的导出入口是 POST action.php（get.php 是部分分支的 GET 变体）。
    for method, url, kwargs in (
        ("post", f"{webui}/{plugin_path}/action.php", {"data": {"hash": info_hash}}),
        ("get", f"{webui}/{plugin_path}/get.php", {"params": {"hash": info_hash}}),
    ):
        try:
            resp = getattr(requests, method)(
                url, auth=auth, timeout=_SOURCE_HTTP_TIMEOUT, **kwargs,
            )
        except Exception as err:
            logger.warning(f"【PT下载中心:转移做种】rt source 导出失败 {info_hash[:8]}：{err}")
            continue
        # 失败时插件回 HTML/JS 提示，bencode 起始字符是有效性判据。
        if resp.status_code == 200 and resp.content[:1] == b"d":
            return resp.content
    return None


def _rt_session_fallback(session_dir: str, info_hash: str) -> Optional[bytes]:
    """rtorrent：从会话目录读取 {hash}.torrent。"""
    if not session_dir:
        return None
    base = Path(session_dir)
    # rt 会话目录文件名 hash 为大写，调用方传入可能为小写，两种都尝试。
    for candidate in (info_hash.lower(), info_hash.upper()):
        try:
            return (base / f"{candidate}.torrent").read_bytes()
        except OSError:
            continue
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
        ext = get_downloader_ext(plugin, downloader_name)
        fallback_dir = str(getattr(plugin, "_fromtorrentpath", "") or "").strip()
        results = {}
        for info_hash in info_hashes:
            data = _tr_export(
                instance, info_hash, service=service, ext=ext, fallback_dir=fallback_dir,
            )
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


