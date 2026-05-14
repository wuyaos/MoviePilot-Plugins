# input: ServiceInfo 实例（来自 MediaServerHelper）
# output: 媒体服务器元数据查询（库/用户/项目/合集/视图）
# pos: core/ 服务器适配层，封装 Emby/Jellyfin 差异；图片 IO 见 image_io.py
"""媒体服务器元数据查询。消除原 12 处 library_id 抽取与 2 处 URL 回落重复。"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)
LOG_PREFIX = "【CoverGen】"


def get_library_id(service, library: dict) -> Optional[str]:
    """统一抽取库 ID（消除原 12 处 emby/jellyfin 分支）。"""
    return library.get("Id") if service.type == "emby" else (library.get("ItemId") or library.get("Id"))


def _try_endpoints(service, urls: List[str]) -> Optional[dict]:
    """依次尝试候选 URL，返回首个 200 的 JSON 响应。"""
    for url in urls:
        try:
            res = service.instance.get_data(url=url)
            if res and res.status_code == 200:
                return res.json()
            status = res.status_code if res else "无响应"
            logger.warning(f"{LOG_PREFIX} endpoint {url.split('?')[0]} → {status}")
        except Exception:
            continue
    return None


def _extract_item_ids(data: Optional[dict]) -> Set[str]:
    if not data:
        return set()
    return {str(it.get("Id") or it.get("ItemId")) for it in data.get("Items", [])
            if it.get("Id") or it.get("ItemId")}


def get_libraries(service) -> List[dict]:
    """获取服务器所有库。"""
    if not service:
        return []
    try:
        is_emby = service.type == "emby"
        url = ("[HOST]emby/Library/VirtualFolders/Query?api_key=[APIKEY]" if is_emby
               else "[HOST]emby/Library/VirtualFolders/?api_key=[APIKEY]")
        res = service.instance.get_data(url=url)
        if not res:
            return []
        data = res.json()
        return data.get("Items", []) if is_emby else (data if isinstance(data, list) else [])
    except Exception as err:
        logger.error(f"{LOG_PREFIX} 获取库列表失败：{err}")
        return []


def get_all_libraries_options(server: str, service) -> List[Dict[str, str]]:
    """格式化为 UI 选项。"""
    out = []
    for lib in get_libraries(service):
        lib_id = get_library_id(service, lib)
        if lib.get("Name") and lib_id:
            out.append({"name": f"{server}: {lib['Name']}", "value": f"{server}-{lib_id}"})
    return out


def get_users(service) -> List[Dict[str, str]]:
    """获取用户列表。"""
    if not service:
        return []
    try:
        res = service.instance.get_data(url="[HOST]emby/Users?api_key=[APIKEY]")
        if not res or res.status_code != 200:
            return []
        return [{"name": u["Name"], "id": u["Id"]} for u in res.json()
                if u.get("Name") and u.get("Id")]
    except Exception as err:
        logger.debug(f"{LOG_PREFIX} 获取用户失败：{err}")
        return []


def get_boxsets_by_users(service, user_ids: Set[str]) -> Set[str]:
    """黑名单用户可见合集 ID。"""
    ids: Set[str] = set()
    prefix = "emby/" if service.type == "emby" else ""
    for uid in user_ids:
        urls = [
            f"{prefix}Users/{uid}/Items?IncludeItemTypes=BoxSet&Recursive=true&Fields=Id",
            f"{prefix}Items?UserId={uid}&IncludeItemTypes=BoxSet&Recursive=true&Fields=Id",
        ]
        found = _extract_item_ids(_try_endpoints(service, urls))
        ids.update(found)
        logger.info(f"{LOG_PREFIX} [用户黑名单] 用户 {uid} 可见合集数: {len(found)}")
    return ids


def get_boxsets_by_libraries(service, library_ids: Set[str]) -> Set[str]:
    """指定来源库内合集 ID。"""
    ids: Set[str] = set()
    prefix = "emby/" if service.type == "emby" else ""
    for lib_id in library_ids:
        url = f"{prefix}Items?ParentId={lib_id}&IncludeItemTypes=BoxSet&Recursive=true&Fields=Id"
        try:
            res = service.instance.get_data(url=url)
            if res and res.status_code == 200:
                found = _extract_item_ids(res.json())
                ids.update(found)
                logger.info(f"{LOG_PREFIX} [来源库过滤] 库 {lib_id} 内合集数: {len(found)}")
        except Exception as err:
            logger.warning(f"{LOG_PREFIX} 查询库 {lib_id} 出错：{err}")
    return ids


def get_user_views(service, user_ids: Set[str]) -> Set[str]:
    """用户可见来源库 ID（排除合集库）。"""
    lib_ids: Set[str] = set()
    if not service or not user_ids:
        return lib_ids
    is_emby = service.type == "emby"
    for uid in user_ids:
        urls = ([f"[HOST]emby/Users/{uid}/Views?api_key=[APIKEY]",
                 f"[HOST]emby/UserViews?userId={uid}&api_key=[APIKEY]"] if is_emby
                else [f"[HOST]emby/UserViews?userId={uid}&api_key=[APIKEY]"])
        data = _try_endpoints(service, urls)
        if not data:
            continue
        for item in data.get("Items", []):
            if item.get("Type") == "BoxSet" or item.get("CollectionType") == "boxsets":
                continue
            iid = item.get("Id") if is_emby else (item.get("Id") or item.get("ItemId"))
            if iid:
                lib_ids.add(str(iid))
    return lib_ids


def get_items_batch(service, parent_id: str, *, offset: int = 0, limit: int = 20,
                    include_types: str = "Movie,Series", sort_by: str = "Random",
                    user_ids: Optional[List[str]] = None) -> List[dict]:
    """批量获取库内项目（带排序/类型/用户筛选）。"""
    if not service:
        return []
    try:
        url = (f"[HOST]emby/Items/?api_key=[APIKEY]"
               f"&ParentId={parent_id}&SortBy={sort_by}&Limit={limit}"
               f"&StartIndex={offset}&IncludeItemTypes={include_types}"
               f"&Recursive=True&SortOrder=Descending")
        if user_ids:
            for uid in user_ids:
                url += f"&UserId={uid}"
        res = service.instance.get_data(url=url)
        return res.json().get("Items", []) if res else []
    except Exception as err:
        logger.error(f"{LOG_PREFIX} 获取媒体项失败：{err}")
        return []


def get_item_by_id(service, item_id: str) -> Optional[dict]:
    """获取单项详情。"""
    if not service or not item_id:
        return None
    try:
        res = service.instance.get_data(url=f"[HOST]emby/Items/{item_id}?api_key=[APIKEY]")
        if res and res.status_code == 200:
            data = res.json()
            if isinstance(data, dict) and (data.get("Id") or data.get("ItemId")):
                return data
    except Exception as err:
        logger.warning(f"{LOG_PREFIX} get_item_by_id 失败: {err}")
    return None
