"""下载器种子字段适配工具（qBittorrent / Transmission / rtorrent 兼容）。"""

from dataclasses import dataclass
from typing import Any, List

from app.sdk.logging import logger


TORRENT_ACTIVE = "active"
TORRENT_PAUSED = "paused"
TORRENT_QUEUED = "queued"
TORRENT_CHECKING = "checking"
TORRENT_COMPLETED = "completed"
TORRENT_ERROR = "error"


@dataclass(frozen=True)
class TorrentSnapshot:
    """下载器无关的种子采样快照。"""

    downloader_id: str
    downloader_type: str
    torrent_hash: str
    name: str
    total_bytes: int
    downloaded_bytes: int
    added_at: float
    state: str
    state_category: str
    save_path: str
    download_speed_bps: float
    category: str = ""


@dataclass(frozen=True)
class DownloaderPollResult:
    """区分成功结果、成功空列表与下载器错误的轮询结果。"""

    success: bool
    items: tuple[TorrentSnapshot, ...] = ()
    error: str = ""


def poll_error(cause: Any) -> DownloaderPollResult:
    """构造下载器轮询失败结果。"""
    return DownloaderPollResult(success=False, items=(), error=str(cause or "unknown error"))


def _read(torrent: Any, *names: str, default: Any = None) -> Any:
    """兼容字典、snake_case 对象与 camelCase 对象读取字段。"""
    for name in names:
        if isinstance(torrent, dict) and name in torrent:
            return torrent.get(name)
        if hasattr(torrent, name):
            return getattr(torrent, name)
    return default


def _number(value: Any, default: float = 0) -> float:
    """将下载器数值字段安全转换为非负浮点数。"""
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return float(default)


def _timestamp(value: Any) -> float:
    """将时间戳或 datetime 风格对象转换为 Unix 秒。"""
    if hasattr(value, "timestamp"):
        try:
            return _number(value.timestamp())
        except (TypeError, ValueError, OSError):
            return 0.0
    return _number(value)

# Transmission 的「暂停」状态文本：transmission-rpc 归一回 "stopped"，
# qB 形态的 stoppedUP/stoppedDL 一并接受，便于跨客户端复用同一判定。
_STOPPED_STATES = frozenset({"stopped", "stoppedup", "stoppeddl", "paused", "pausedup", "pauseddl"})


def _state_value(value: Any) -> Any:
    """取状态字段的真实值：Enum 成员（transmission-rpc 的 Status 是 str 枚举）取 value。

    直接对 str 枚举取 `.name` 会得到 "STOPPED"，与 "stopped" 不相等；
    先取 `.value` 再比较文本才是可靠做法。
    """
    if value is None:
        return None
    inner = getattr(value, "value", None)
    return inner if inner is not None else value


def classify_torrent_state(state: Any, downloaded_bytes: int, total_bytes: int) -> str:
    """把 qBittorrent/Transmission 状态归一为监控状态类别。"""
    raw_state = _state_value(state) or ""
    normalized = str(raw_state).replace("_", "").replace(" ", "").lower()

    if total_bytes > 0 and downloaded_bytes >= total_bytes:
        return TORRENT_COMPLETED
    if normalized in {
        "uploading", "forcedup", "stalledup", "seeding", "completed",
    }:
        return TORRENT_COMPLETED
    if normalized in {
        "pauseddl", "pausedup", "stoppeddl", "stoppedup", "stopped", "paused",
    }:
        return TORRENT_PAUSED
    if normalized in {
        "queueddl", "queuedup", "downloadpending", "seedpending", "queued",
    }:
        return TORRENT_QUEUED
    if normalized in {
        "checkingdl", "checkingup", "checkingresumedata", "checkpending", "checking",
    }:
        return TORRENT_CHECKING
    if normalized in {"error", "missingfiles", "unknown", "isolated"}:
        return TORRENT_ERROR
    return TORRENT_ACTIVE


def delete_torrent_with_files(
    instance: Any,
    torrent_hash: str,
    *,
    delete_file: bool,
) -> Any:
    """仅在调用方显式确认时删除种子及该种子的全部数据。"""
    if delete_file is not True:
        raise ValueError("删除种子及全部数据必须显式传入 delete_file=True")
    if not torrent_hash:
        raise ValueError("删除种子及全部数据需要有效 hash")
    result = instance.delete_torrents(ids=[torrent_hash], delete_file=True)
    if result is False:
        raise RuntimeError("下载器未确认删除成功")
    return result


def normalize_hash(value: Any) -> str:
    """统一哈希大小写：qB/TR 一律小写，rTorrent（ruTorrent）回报大写。

    跨客户端比较与查询前必须归一，否则把 rt 的大写哈希丢给 Transmission 会得到
    `torrent ids XXXXXXXX is not valid`（transmission-rpc 只接受小写 40 位十六进制）。
    """
    return str(value or "").strip().lower()


def get_hash(torrent: Any, dl_type: str) -> str:
    """获取种子 hash（统一小写）。"""
    if dl_type == "qbittorrent":
        return normalize_hash(torrent.get("hash", ""))
    if dl_type == "rtorrent":
        return normalize_hash(_read(torrent, "hash", "hashString", "hash_string", default=""))
    return normalize_hash(_read(torrent, "hashString", "hash_string", default=""))


def _split_labels(labels: Any) -> List[str]:
    """将下载器返回的标签字段统一拆分为字符串列表。"""
    if not labels:
        return []
    if isinstance(labels, str):
        return [str(label).strip() for label in labels.split(",") if str(label).strip()]
    if isinstance(labels, (list, tuple, set)):
        return [str(label).strip() for label in labels if str(label).strip()]
    return []


def get_torrent_name(torrent: Any) -> str:
    """获取种子名称：兼容 qB/TR 返回 dict、部分版本返回对象两种形态。"""
    return str(_read(torrent, "name", "torrentName", default="") or "")


def get_label(torrent: Any, dl_type: str) -> List[str]:
    """获取种子标签/分类。"""
    if dl_type == "qbittorrent":
        return _split_labels(torrent.get("tags"))
    if dl_type == "rtorrent":
        return _split_labels(_read(torrent, "tags", "labels", default=[]))
    return _split_labels(_read(torrent, "labels", default=[]))


def get_category(torrent: Any, dl_type: str) -> str:
    """获取种子分类（qB category / TR group）。"""
    if dl_type == "qbittorrent":
        return _read(torrent, "category", default="") or ""
    return _read(torrent, "group", default="") or ""


def get_save_path(torrent: Any, dl_type: str) -> str:
    """获取种子保存路径。"""
    if dl_type == "qbittorrent":
        return torrent.get("save_path", "")
    if dl_type == "rtorrent":
        return _read(torrent, "save_path", "download_dir", "downloadDir", default="")
    return _read(torrent, "download_dir", "downloadDir", default="")


def get_torrent_size(torrent: Any, dl_type: str) -> int:
    """获取种子总大小（字节）。"""
    if dl_type == "qbittorrent":
        return torrent.get("size", 0) or torrent.get("total_size", 0) or 0
    return int(_number(_read(torrent, "total_size", "totalSize", default=0)))


def get_torrent_state(torrent: Any, dl_type: str) -> Any:
    """读取统一种子状态：qB 字符串、TR 状态对象、rt 为 d.state 数字。"""
    if dl_type == "qbittorrent":
        return torrent.get("state")
    return _read(torrent, "status", "state", default=None)


def torrent_percent_done(torrent: Any, dl_type: str) -> float:
    """归一化完成度到 0..1，兼容 TR percentDone 与 rt progress（百分数）。"""
    if torrent is None:
        return 0.0
    if dl_type == "rtorrent":
        if isinstance(torrent, dict) and "progress" in torrent:
            return min(1.0, max(0.0, _number(torrent.get("progress")) / 100.0))
        total = _number(_read(torrent, "total_size", "totalSize", default=0))
        done = _number(_read(torrent, "completed", "downloaded", default=0))
        return min(1.0, done / total) if total > 0 else 0.0
    percent = _read(torrent, "percent_done", "percentDone", default=None)
    if percent is not None:
        return min(1.0, max(0.0, _number(percent)))
    total = _number(_read(torrent, "total_size", "totalSize", default=0))
    done = _number(_read(torrent, "downloaded", "downloaded_ever", default=0))
    return min(1.0, done / total) if total > 0 else 0.0


def torrent_is_complete(torrent: Any, dl_type: str) -> bool:
    """判断种子是否已完成，优先使用下载器自带的完成标志。"""
    if torrent is None:
        return False
    if dl_type == "rtorrent":
        flag = _read(torrent, "complete", default=None)
        if flag is not None:
            return int(_number(flag)) != 0
    return torrent_percent_done(torrent, dl_type) >= 1.0


def is_torrent_active(torrent: Any, dl_type: str) -> bool:
    """判断种子是否活动（非停止/暂停），兼容字典与对象两种返回值。"""
    if torrent is None:
        return False
    if dl_type == "rtorrent":
        # rt：d.state 1=started 0=stopped；d.is_active 为活动标志。
        if int(_number(_read(torrent, "is_active", default=0))) != 0:
            return True
        return int(_number(_read(torrent, "state", default=0))) != 0
    if dl_type == "qbittorrent":
        return torrent.get("state") not in ("pausedUP", "pausedDL", "stoppedUP", "stoppedDL")
    state = _state_value(_read(torrent, "status", "state", default=None))
    if state is None or state == "":
        # 读不到状态时按「仍活动」处理，避免在未确认暂停的情况下继续转移。
        return True
    if isinstance(state, bool):
        return state
    if isinstance(state, (int, float)):
        # transmission-rpc 归一后是字符串，但部分形态仍是原始状态码（0=stopped）。
        return int(state) != 0
    return str(state).strip().lower() not in _STOPPED_STATES


def skipverify_applies(dl_type: str) -> bool:
    """跳过校验开关的作用范围：qB 走添加时 skip_checking，rt 走「不触发也不等待」；TR 始终显式校验。"""
    return str(dl_type or "").lower() in ("qbittorrent", "rtorrent")



def supports_recheck(dl_type: str) -> bool:
    """rt 宿主客户端没有 recheck_torrents，rt 目的端必须跳过显式校验。"""
    return str(dl_type or "").lower() != "rtorrent"


def get_tracker_urls(torrent: Any, dl_type: str) -> List[str]:
    """获取有效 tracker URL，兼容 qB 字段、对象属性和缺失字段。"""
    if dl_type == "qbittorrent":
        trackers = torrent.get("trackers") if isinstance(torrent, dict) else None
        if trackers is None:
            try:
                trackers = getattr(torrent, "trackers", None)
            except Exception:
                trackers = []
        urls = []
        for tracker in trackers or []:
            url = _read(tracker, "url", default="")
            tier = _read(tracker, "tier", default=-1)
            if url and tier >= 0:
                urls.append(str(url))
        return urls

    trackers = _read(torrent, "trackers", default=[]) or []
    urls = []
    for tracker in trackers:
        tier = _read(tracker, "tier", default=-1)
        announce = _read(tracker, "announce", default="")
        if announce and tier >= 0:
            urls.append(str(announce))
    return urls
