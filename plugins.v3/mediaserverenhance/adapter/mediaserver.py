"""媒体服务器访问适配层。

本模块把宿主 ``MediaServerHelper`` 的能力收敛成插件可直接使用的稳定函数，
所有 Emby / Jellyfin / Plex 差异都收在这里，业务模块只面向本层编程。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

from app.schemas.mediaserver import MediaServerItem, RefreshMediaItem
from app.schemas.types import MediaType
from app.sdk.logging import logger
from app.sdk.network import RequestUtils
from app.sdk.services import MediaServerHelper

# 媒体类型字符串到宿主枚举的映射，兼容宿主内部值与前端展示值。
_MEDIA_TYPE_ALIASES: Dict[str, MediaType] = {
    "movie": MediaType.MOVIE,
    "电影": MediaType.MOVIE,
    "tv": MediaType.TV,
    "series": MediaType.TV,
    "电视剧": MediaType.TV,
    "music": MediaType.MUSIC,
    "音乐": MediaType.MUSIC,
}

# 默认请求超时（秒），由调用方按配置覆盖。
DEFAULT_TIMEOUT = 30


def media_server_helper() -> MediaServerHelper:
    """返回宿主媒体服务器服务发现入口。"""
    return MediaServerHelper()


def normalize_server_type(value: Any) -> str:
    """把服务配置的类型字段规范为小写类型名。

    :param value: 宿主配置中的类型字段
    :return: ``emby`` / ``jellyfin`` / ``plex`` 等小写类型名，缺失时为空串
    """
    return str(value or "").strip().lower()


def to_media_type(value: Any) -> Optional[MediaType]:
    """把媒体类型入参解析为宿主 MediaType 枚举。

    :param value: 类型字符串或 MediaType 枚举
    :return: 解析成功时返回枚举，无法识别时返回 None
    """
    if isinstance(value, MediaType):
        return value
    if value is None:
        return None
    return _MEDIA_TYPE_ALIASES.get(str(value).strip().lower())


def list_server_configs(include_disabled: bool = False) -> List[Dict[str, Any]]:
    """列出宿主已配置的媒体服务器。

    :param include_disabled: 是否包含已停用的服务器
    :return: 每项包含 name / type / enabled / host 的字典列表
    """
    configs = media_server_helper().get_configs(include_disabled=include_disabled) or {}
    rows: List[Dict[str, Any]] = []
    for name, conf in configs.items():
        options = getattr(conf, "config", None)
        host = ""
        if isinstance(options, dict):
            host = str(options.get("host") or "")
        rows.append(
            {
                "name": str(name),
                "type": normalize_server_type(getattr(conf, "type", "")),
                "enabled": bool(getattr(conf, "enabled", True)),
                "host": host,
                "sync_libraries": list(getattr(conf, "sync_libraries", None) or []),
            }
        )
    rows.sort(key=lambda row: (row["type"], row["name"]))
    return rows


def get_service(name: str):
    """按名称返回宿主媒体服务器运行实例。

    :param name: 服务器配置名称
    :return: 可用的 ``ServiceInfo``；未配置、未启用或实例不可用时返回 None
    """
    if not name:
        return None
    return media_server_helper().get_service(name=name)


def get_service_options(service) -> Dict[str, Any]:
    """读取服务配置中的连接参数。

    :param service: ``ServiceInfo`` 对象
    :return: 含 host / apikey / play_host 的字典，缺失字段为空串
    """
    options = getattr(getattr(service, "config", None), "config", None)
    if not isinstance(options, dict):
        return {"host": "", "apikey": "", "play_host": ""}
    return {
        "host": str(options.get("host") or ""),
        "apikey": str(options.get("apikey") or ""),
        "play_host": str(options.get("play_host") or ""),
    }


def server_online(name: str) -> Tuple[bool, str]:
    """判断媒体服务器是否可正常访问。

    :param name: 服务器配置名称
    :return: ``(是否在线, 失败原因)``，在线时原因为空串
    """
    service = get_service(name)
    if not service:
        return False, "未配置或未启用"
    instance = getattr(service, "instance", None)
    if not instance:
        return False, "服务实例不可用"
    is_inactive = getattr(instance, "is_inactive", None)
    if callable(is_inactive):
        try:
            if is_inactive():
                # 服务器可能曾不可达导致宿主实例未完成登录：尝试一次重连再判定
                reconnect = getattr(instance, "reconnect", None)
                if callable(reconnect):
                    try:
                        reconnect()
                    except Exception as error:  # noqa: BLE001 - 重连失败保持原判定
                        logger.warning(f"【媒体服务器增强】{name} 重连失败：{error}")
                if is_inactive():
                    return False, "服务未连接"
        except Exception as error:  # noqa: BLE001 - 宿主实现差异，探测失败按不可用处理
            return False, str(error)
    return True, ""


def list_libraries(name: str) -> List[Dict[str, Any]]:
    """读取指定服务器的媒体库列表。

    :param name: 服务器配置名称
    :return: 每项包含 id / name / type / item_count 的字典列表；失败时返回空列表
    """
    service = get_service(name)
    instance = getattr(service, "instance", None) if service else None
    if not instance:
        return []
    loader = getattr(instance, "get_librarys", None)
    if not callable(loader):
        return []
    try:
        libraries = loader()
    except Exception as error:  # noqa: BLE001 - 宿主适配器异常不应中断聚合查询
        logger.error(f"【媒体服务器增强】读取 {name} 媒体库失败：{error}")
        return []
    rows: List[Dict[str, Any]] = []
    for library in libraries or []:
        rows.append(
            {
                "server": name,
                "id": str(getattr(library, "item_id", None) or getattr(library, "id", "") or ""),
                "name": str(getattr(library, "name", "") or ""),
                "type": str(getattr(library, "type", "") or ""),
                "item_count": int(getattr(library, "item_count", 0) or 0),
                "path": _as_path_text(getattr(library, "path", None)),
            }
        )
    return rows


def iter_library_items(name: str, library_id: str, limit: int = 0) -> Iterator[MediaServerItem]:
    """迭代指定媒体库的媒体条目。

    :param name: 服务器配置名称
    :param library_id: 媒体库标识
    :param limit: 最多返回条目数，0 表示不限制
    :return: 宿主统一媒体条目迭代器
    :raises Exception: 服务器读取失败时原样外抛，调用方负责区分
        「空库」与「读取失败」并写入报告，防止服务器故障被误判为媒体库清空
    """
    service = get_service(name)
    instance = getattr(service, "instance", None) if service else None
    loader = getattr(instance, "get_items", None) if instance else None
    if not callable(loader):
        return iter(())
    items = loader(library_id, 0, -1)

    def _bounded() -> Iterator[MediaServerItem]:
        count = 0
        for item in items or ():
            if item is None:
                continue
            yield item
            count += 1
            if limit and count >= limit:
                return

    return _bounded()


def fetch_season_episodes(name: str, item_id: str, title: str = "",
                          year: Any = None) -> Dict[int, List[int]]:
    """读取电视剧在服务器侧的季集信息。

    :param name: 服务器配置名称
    :param item_id: 剧集条目标识
    :param title: 条目标识失效时的回退搜索剧名
    :param year: 回退搜索年份
    :return: 季号到集号列表的映射；不支持或读取失败返回空映射
    """
    service = get_service(name)
    instance = getattr(service, "instance", None) if service else None
    loader = getattr(instance, "get_tv_episodes", None)
    if not callable(loader) or (not item_id and not title):
        return {}
    try:
        _, seasoninfo = loader(item_id=item_id or None, title=title or None, year=year or None)
    except Exception as error:  # noqa: BLE001 - 季集缺失属正常分支
        logger.debug(f"【媒体服务器增强】读取 {name}/{item_id or title} 季集失败：{error}")
        return {}
    if not seasoninfo:
        return {}
    result: Dict[int, List[int]] = {}
    for season, episodes in dict(seasoninfo).items():
        try:
            result[int(season)] = sorted({int(episode) for episode in episodes or []})
        except (TypeError, ValueError):
            continue
    return result


def build_refresh_items(payloads: Iterable[Dict[str, Any]]) -> List[RefreshMediaItem]:
    """把插件内部的刷新请求转换为宿主刷新模型。

    :param payloads: 含 title / year / type / category / path 的字典列表
    :return: 可直接交给服务器实例的 ``RefreshMediaItem`` 列表
    """
    items: List[RefreshMediaItem] = []
    for payload in payloads or []:
        if not isinstance(payload, dict):
            continue
        target = payload.get("path") or payload.get("target_path")
        items.append(
            RefreshMediaItem(
                title=_as_text(payload.get("title")),
                year=_as_text(payload.get("year")),
                type=to_media_type(payload.get("type")),
                category=_as_text(payload.get("category")),
                target_path=Path(str(target)) if target else None,
            )
        )
    return items


def refresh_server(name: str, payloads: Iterable[Dict[str, Any]]) -> Tuple[bool, str]:
    """对指定服务器发起一次媒体库刷新。

    优先按条目精确定位媒体库；实例不支持按条目刷新或未提供条目时退回整库刷新。

    :param name: 服务器配置名称
    :param payloads: 刷新请求列表
    :return: ``(是否成功, 说明)``
    """
    items = build_refresh_items(payloads)
    service = get_service(name)
    instance = getattr(service, "instance", None) if service else None
    if not instance:
        return False, "服务器未启用或实例不可用"
    if items:
        by_items = getattr(instance, "refresh_library_by_items", None)
        # 条目全部缺少目标路径时按条目刷新必然空转（服务器查不到对应媒体库），
        # 直接落整库刷新，避免虚假的「按条目刷新 N 项」成功记录
        if callable(by_items) and any(item.target_path for item in items):
            try:
                result = by_items(items)
                if result:
                    return True, f"按条目刷新 {len(items)} 项"
            except Exception as error:  # noqa: BLE001 - 精确定位失败后仍可退回整库刷新
                logger.warning(f"【媒体服务器增强】{name} 按条目刷新失败，回退整库刷新：{error}")
    root_refresh = getattr(instance, "refresh_root_library", None)
    if not callable(root_refresh):
        return False, "服务器实现不支持刷新"
    try:
        result = root_refresh()
        return bool(result), "整库刷新" if result else "整库刷新未确认成功"
    except Exception as error:  # noqa: BLE001 - 刷新失败由调用方记录任务结果
        logger.error(f"【媒体服务器增强】{name} 整库刷新失败：{error}")
        return False, str(error)


def probe_server_plugins(name: str, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """探测媒体服务器侧已安装的服务端插件。

    仅支持 Emby 与 Jellyfin（两者提供 ``/Plugins`` 接口）；Plex 无插件体系。

    :param name: 服务器配置名称
    :param timeout: 请求超时秒数
    :return: 含 supported / plugins / error 的字典
    """
    service = get_service(name)
    if not service:
        return {"supported": False, "plugins": [], "error": "服务器未启用或实例不可用"}
    server_type = normalize_server_type(getattr(service, "type", ""))
    options = get_service_options(service)
    host = options["host"].rstrip("/")
    apikey = options["apikey"]
    if not host or not apikey:
        return {"supported": False, "plugins": [], "error": "服务器地址或 API Key 缺失"}
    if server_type not in {"emby", "jellyfin"}:
        return {"supported": False, "plugins": [], "error": f"{server_type or '未知类型'} 不提供服务端插件接口"}
    prefix = "emby/" if server_type == "emby" else ""
    url = f"{host}/{prefix}Plugins"
    try:
        response = RequestUtils(timeout=timeout, content_type="application/json").get_res(
            url=url, params={"api_key": apikey}
        )
        if not response or response.status_code != 200:
            return {
                "supported": False,
                "plugins": [],
                "error": f"HTTP {getattr(response, 'status_code', 'unknown')}",
            }
        payload = response.json()
    except Exception as error:  # noqa: BLE001 - 探测失败由界面展示原因
        return {"supported": False, "plugins": [], "error": str(error)}
    plugins: List[Dict[str, Any]] = []
    for entry in payload or []:
        if not isinstance(entry, dict):
            continue
        plugins.append(
            {
                "name": str(entry.get("Name") or entry.get("name") or ""),
                "version": str(entry.get("Version") or entry.get("version") or ""),
                "status": str(entry.get("Status") or entry.get("status") or ""),
                "id": str(entry.get("Id") or entry.get("id") or ""),
            }
        )
    plugins.sort(key=lambda row: row["name"].lower())
    return {"supported": True, "plugins": plugins, "error": ""}


def fetch_primary_image(name: str, item_id: str, max_width: int = 0,
                        timeout: int = DEFAULT_TIMEOUT) -> Optional[bytes]:
    """下载条目在服务器侧的主图原始字节。

    :param name: 服务器配置名称
    :param item_id: 媒体条目标识
    :param max_width: 期望最大宽度，0 表示取原图
    :param timeout: 请求超时秒数
    :return: 图片字节；不可用或下载失败时返回 None
    """
    service = get_service(name)
    options = get_service_options(service) if service else {"host": "", "apikey": ""}
    host = options["host"].rstrip("/")
    if not host or not options["apikey"] or not item_id:
        return None
    prefix = "emby/" if normalize_server_type(getattr(service, "type", "")) == "emby" else ""
    params: Dict[str, Any] = {"api_key": options["apikey"]}
    if max_width > 0:
        params["maxWidth"] = max_width
    try:
        response = RequestUtils(timeout=timeout).get_res(
            url=f"{host}/{prefix}Items/{item_id}/Images/Primary", params=params
        )
        if not response or response.status_code != 200:
            return None
        return response.content
    except Exception as error:  # noqa: BLE001 - 缺图属正常分支，按无图处理
        logger.debug(f"【媒体服务器增强】{name}/{item_id} 主图下载失败：{error}")
        return None


def upload_primary_image(name: str, item_id: str, content: bytes,
                         timeout: int = DEFAULT_TIMEOUT) -> Tuple[bool, str]:
    """把封面图上传为条目的主图。

    :param name: 服务器配置名称
    :param item_id: 媒体条目标识
    :param content: 图片二进制内容
    :param timeout: 请求超时秒数
    :return: ``(是否成功, 说明)``
    """
    if not content:
        return False, "图片内容为空"
    service = get_service(name)
    if not service:
        return False, "服务器未启用或实例不可用"
    server_type = normalize_server_type(getattr(service, "type", ""))
    if server_type not in {"emby", "jellyfin"}:
        return False, f"{server_type or '未知类型'} 暂不支持上传主图"
    options = get_service_options(service)
    host = options["host"].rstrip("/")
    if not host or not options["apikey"]:
        return False, "服务器地址或 API Key 缺失"
    prefix = "emby/" if server_type == "emby" else ""
    url = f"{host}/{prefix}Items/{item_id}/Images/Primary"
    try:
        response = RequestUtils(timeout=timeout).post_res(
            url=url,
            params={"api_key": options["apikey"]},
            data=content,
            headers={"Content-Type": _image_mime(content)},
        )
    except Exception as error:  # noqa: BLE001 - 上传失败由任务结果记录
        return False, str(error)
    if response is None:
        return False, "上传请求异常"
    if response.status_code in (200, 204):
        return True, "上传成功"
    return False, f"HTTP {response.status_code}"


def _image_mime(content: bytes) -> str:
    """按文件头判断图片 MIME。

    :param content: 图片二进制内容
    :return: 用于上传的 Content-Type 文本
    """
    if content[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if content[:4] == b"RIFF":
        return "image/webp"
    if content[:3] == b"GIF":
        return "image/gif"
    return "image/png"


def _as_text(value: Any) -> Optional[str]:
    """把任意标量转换为去空字符串。

    :param value: 原始值
    :return: 非空时返回字符串，否则返回 None
    """
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_path_text(value: Any) -> str:
    """把媒体库路径字段归一为可展示文本。

    :param value: 字符串、列表或 None
    :return: 多路径以 `` ; `` 连接后的文本
    """
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return " ; ".join(str(item) for item in value if item)
    return str(value)
