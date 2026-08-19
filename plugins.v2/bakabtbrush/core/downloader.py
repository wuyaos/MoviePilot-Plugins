"""通过 MoviePilot 已配置 qBittorrent 下载器查询、限流和添加任务。"""

from __future__ import annotations

import time
from typing import Any

from .models import QBTorrentSnapshot


DOWNLOADING_STATES = frozenset({
    "metadl", "downloading", "stalleddl", "checkingdl", "allocating", "queueddl", "forceddl",
})
COMPLETE_STATES = frozenset({"uploading", "stalledup", "pausedup", "forcedup", "checkingup"})


class DownloaderError(RuntimeError):
    """下载器异常；错误信息不包含 qB 凭据。"""


def get_qb_instance(downloader_name: str) -> Any:
    """从 MoviePilot 获取已配置且已连接的 qBittorrent 实例。"""
    if not downloader_name:
        raise DownloaderError("未选择 MoviePilot qBittorrent 下载器")
    try:
        from app.helper.downloader import DownloaderHelper

        helper = DownloaderHelper()
        service = helper.get_service(name=downloader_name)
        if not service or not getattr(service, "instance", None):
            raise DownloaderError("选择的下载器不可用")
        instance = service.instance
        if hasattr(instance, "is_inactive") and instance.is_inactive():
            raise DownloaderError("选择的下载器未连接")
        if not helper.is_downloader("qbittorrent", service=service):
            raise DownloaderError("选择的下载器不是 qBittorrent")
        _get_qbc(instance)
        return instance
    except DownloaderError:
        raise
    except Exception as err:
        raise DownloaderError("读取 MoviePilot 下载器失败") from err


def list_bakabt_torrents(instance: Any, category: str, required_tag: str = "bakabt") -> list[QBTorrentSnapshot]:
    """先按分类从 qB 查询，再本地精确过滤标签，避免标签查询编码差异。"""
    qbc = _get_qbc(instance)
    try:
        raw_torrents = qbc.torrents_info(category=category) or []
    except Exception as err:
        raise DownloaderError("查询 qBittorrent 任务失败") from err

    torrents: list[QBTorrentSnapshot] = []
    for raw in raw_torrents:
        tags = _parse_tags(_value(raw, "tags", ""))
        if required_tag not in tags:
            continue
        infohash = str(_value(raw, "hash", "") or "").lower()
        if not infohash:
            continue
        torrents.append(QBTorrentSnapshot(
            infohash=infohash,
            name=str(_value(raw, "name", "") or ""),
            category=str(_value(raw, "category", "") or ""),
            tags=tags,
            state=str(_value(raw, "state", "") or ""),
            progress=_number(_value(raw, "progress", 0)),
            uploaded=_integer(_value(raw, "uploaded", 0)),
            downloaded=_integer(_value(raw, "downloaded", 0)),
        ))
    return torrents


def downloading_count(torrents: list[QBTorrentSnapshot]) -> int:
    return sum(1 for item in torrents if item.state.lower() in DOWNLOADING_STATES)


def available_slots(limit: int, current: int) -> int | None:
    """0 表示不限制；None 表示调用方不应截断候选数量。"""
    if limit == 0:
        return None
    return max(0, limit - current)


def transfer_totals_mb(torrents: list[QBTorrentSnapshot]) -> tuple[float, float]:
    uploaded = sum(item.uploaded for item in torrents) / (1024 * 1024)
    downloaded = sum(item.downloaded for item in torrents) / (1024 * 1024)
    return round(uploaded, 2), round(downloaded, 2)


def completed_infohashes(torrents: list[QBTorrentSnapshot]) -> set[str]:
    return {
        item.infohash for item in torrents
        if item.progress >= 0.999999 or item.state.lower() in COMPLETE_STATES
    }


def has_infohash(instance: Any, infohash: str) -> bool:
    qbc = _get_qbc(instance)
    try:
        return bool(qbc.torrents_info(torrent_hashes=infohash))
    except Exception as err:
        raise DownloaderError("查询 qBittorrent 重复任务失败") from err


def add_and_verify(
    instance: Any,
    content: bytes,
    expected_infohash: str,
    category: str,
    tags: tuple[str, ...],
    save_path: str = "",
) -> str:
    """经 MoviePilot 下载器封装添加种子，并以 infohash 确认 qB 已存在任务。"""
    if not expected_infohash:
        raise DownloaderError("BakaBT 详情页未提供 infohash，跳过添加")
    expected_infohash = expected_infohash.lower()
    if has_infohash(instance, expected_infohash):
        return expected_infohash

    kwargs: dict[str, Any] = {
        "content": content,
        "is_paused": False,
        "tag": list(tags),
        "category": category,
        "is_skip_checking": False,
    }
    if save_path:
        kwargs["download_dir"] = save_path

    try:
        result = instance.add_torrent(**kwargs)
    except Exception as err:
        raise DownloaderError("向 qBittorrent 添加种子失败") from err

    accepted, ids = _parse_add_result(result)
    if not accepted:
        raise DownloaderError("qBittorrent 未接受种子任务")
    actual_infohash = str(ids[0]).lower() if ids else expected_infohash
    if actual_infohash != expected_infohash:
        raise DownloaderError("qBittorrent 返回的种子 hash 与 BakaBT 信息不一致")

    # qB 添加接口可能先应答、后可见；有限轮询确保只在任务真实存在时记录成功。
    for attempt in range(3):
        if has_infohash(instance, actual_infohash):
            return actual_infohash
        if attempt < 2:
            time.sleep(0.3 * (attempt + 1))
    raise DownloaderError("qBittorrent 未确认新增任务")


def _parse_add_result(result: Any) -> tuple[bool, list[str]]:
    if isinstance(result, tuple):
        accepted = bool(result[0]) if result else False
        ids = result[1] if len(result) > 1 else []
        if isinstance(ids, str):
            ids = [ids]
        return accepted, [str(value) for value in ids or [] if value]
    return bool(result), []


def _get_qbc(instance: Any) -> Any:
    qbc = getattr(instance, "qbc", None)
    if not qbc:
        raise DownloaderError("MoviePilot 下载器未提供 qBittorrent 客户端")
    return qbc


def _value(source: Any, key: str, default: Any = None) -> Any:
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _parse_tags(value: Any) -> tuple[str, ...]:
    return tuple(dict.fromkeys(
        tag.strip() for tag in str(value or "").split(",") if tag.strip()
    ))


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _integer(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0
