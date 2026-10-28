"""整理失败事件处理入口，供插件入口层注册 EventType.TransferFailed。"""

from __future__ import annotations

from typing import Any

from app.sdk.logging import logger

from .constants import FAILCLEAN_LOG_PREFIX
from .service import empty_transfer_failed_result


def handle_transfer_failed_event(plugin: Any, event: Any) -> dict[str, Any]:
    """把整理失败事件交给插件级 FailCleanService 执行即时清理。

    :param plugin: DownloadManagerLocal 插件实例，需持有 ``_failclean_service``。
    :param event: 宿主 TransferFailed 事件，event_data 含 fileitem/transferinfo/download_hash/downloader。
    :return: 清理结果，含 deleted/history_deleted/skipped/duplicate。
    """
    service = getattr(plugin, "_failclean_service", None)
    if service is None:
        logger.warning(f"{FAILCLEAN_LOG_PREFIX}服务未初始化，跳过整理失败清理")
        return empty_transfer_failed_result()
    return service.handle_transfer_failed(event)


__all__ = ("handle_transfer_failed_event",)
