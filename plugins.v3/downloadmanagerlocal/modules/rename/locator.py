"""重命名历史的下载器定位（P1-4 修复）。

历史记录只存 hash，不存下载器身份；旧单链路键 `_todownloader` 可能为空或指向
另一实例。这里提供统一的「按 hash 在全部配置下载器里定位」逻辑：

- 新记录写入时附带 ``downloader`` 字段（写入点在 save_rename_record）；
- 旧记录无该字段时，在已配置下载器中查找**唯一**包含该 hash 的实例；
- 多个实例都含同一 hash 时返回歧义（candidates 列表），调用方要求用户选择，
  绝不任取一个（避免操作错误实例）。
"""

from __future__ import annotations

from typing import Any

from app.sdk.logging import logger

from ...adapter.moviepilot import get_downloader_services
from ...utils.torrent_adapter import get_hash
from ..transfer.tasks import load_transfer_tasks

RETRY_LOG_PREFIX = "【PT下载中心:重命名】"


def configured_downloader_names(plugin) -> list[str]:
    """收集插件配置涉及的下载器名（rename_downloaders 优先，回退转移任务与旧键）。"""
    names: list[str] = []

    def _add(value) -> None:
        text = str(value or "").strip()
        if text and text not in names:
            names.append(text)

    rename_cfg = getattr(plugin, "_rename_config", None)
    for name in (rename_cfg or {}).get("downloader") or []:
        _add(name)
    for raw in getattr(plugin, "_rename_downloaders", None) or []:
        _add(raw)
    try:
        for task in load_transfer_tasks(plugin):
            _add(task.get("from_downloader"))
            _add(task.get("to_downloader"))
    except Exception:
        pass
    _add(getattr(plugin, "_todownloader", None))
    _add(getattr(plugin, "_fromdownloader", None))
    return names


def resolve_record_downloader(plugin, torrent_hash: str, record: dict | None = None) -> dict:
    """定位一条重命名记录所属的下载器。

    返回 ``{"service": ServiceInfo|None, "candidates": [name, ...], "ambiguous": bool,
    "reason": str}``。
    """
    hash_text = str(torrent_hash or "").strip()
    recorded = str((record or {}).get("downloader") or "").strip()

    if recorded:
        service = get_downloader_services(name_filters=[recorded]).get(recorded)
        if service is not None:
            return {"service": service, "candidates": [recorded], "ambiguous": False, "reason": "record"}
        # 记录的下载器不可用，继续按 hash 搜索兜底。

    candidates: list[str] = []
    for name in configured_downloader_names(plugin):
        try:
            service = get_downloader_services(name_filters=[name]).get(name)
        except Exception as err:
            logger.warning(f"{RETRY_LOG_PREFIX}查询下载器 {name} 失败：{err}")
            continue
        instance = getattr(service, "instance", None)
        if instance is None or instance.is_inactive():
            continue
        try:
            torrents, _ = instance.get_torrents(ids=[hash_text])
        except Exception as err:
            logger.warning(f"{RETRY_LOG_PREFIX}在 {name} 查询 {hash_text} 失败：{err}")
            continue
        dl_type = getattr(service, "type", "")
        for torrent in torrents or []:
            if get_hash(torrent, dl_type) == hash_text:
                candidates.append(name)
                break

    if not candidates:
        return {"service": None, "candidates": [], "ambiguous": False, "reason": "not_found"}
    if len(candidates) > 1:
        return {"service": None, "candidates": candidates, "ambiguous": True, "reason": "ambiguous"}
    service = get_downloader_services(name_filters=[candidates[0]]).get(candidates[0])
    return {"service": service, "candidates": candidates, "ambiguous": False, "reason": "searched"}
