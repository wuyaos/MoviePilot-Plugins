"""下载器公共只读查询边界；返回原始客户端对象，不创建业务快照。"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Iterable, Optional


@dataclass(frozen=True)
class TorrentQueryResult:
    """区分成功空集合与查询失败，items 保留客户端对象身份。"""

    success: bool
    items: tuple
    error: str = ""


def downloader_type(service: Any) -> str:
    """沿用现有 scanner 的下载器类型归一口径。"""
    return str(getattr(service, "type", "") or "").strip().lower()


def _query_error(error: Exception) -> str:
    text = str(error)
    if any(marker in text.lower() for marker in (
        "http://", "https://", "password", "passwd", "token", "authorization",
        "cookie", "api_key", "apikey", "secret", "@",
    )):
        return "下载器查询失败（错误详情已脱敏）"
    return text


def read_torrents(service: Any, ids: Optional[Iterable[str]] = None) -> TorrentQueryResult:
    """只查指定任务或无参查全量；不重试，不回退扩大查询范围。"""
    try:
        instance = getattr(service, "instance", None)
        if instance is None:
            return TorrentQueryResult(False, (), "下载器实例缺失")
        if ids is None:
            response = instance.get_torrents()
        else:
            id_list = list(ids)
            # 客户端可能把 ids=[] 当作全量，公共层不允许扩大查询范围。
            if not id_list:
                return TorrentQueryResult(True, ())
            response = instance.get_torrents(ids=id_list)
        if isinstance(response, tuple) and len(response) == 2:
            items, failed = response
            if failed:
                return TorrentQueryResult(False, (), "下载器查询失败")
        elif (isinstance(response, Sequence) and not isinstance(response, (str, bytes, tuple))) or response is None:
            items = response
        else:
            return TorrentQueryResult(False, (), "无法识别的返回结构")
        if items is None:
            return TorrentQueryResult(False, (), "下载器返回空响应")
        if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
            return TorrentQueryResult(False, (), "无法识别的返回结构")
        return TorrentQueryResult(True, tuple(items))
    except Exception as error:
        return TorrentQueryResult(False, (), _query_error(error))
