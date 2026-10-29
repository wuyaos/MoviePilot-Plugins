"""整理失败清理通知：单文件删除结果与巡检汇总。"""

from __future__ import annotations

from typing import Any

from app.schemas.types import MessageType

from .constants import FAILCLEAN_NOTIFY_PREVIEW_LIMIT

DELETE_SUCCESS_TITLE = "源文件已删除"
DELETE_FAILURE_TITLE = "源文件删除失败"
SCAN_SUMMARY_TITLE = "重复下载残留清理完成"


def notify_delete_success(plugin: Any, path: str, reason: str) -> None:
    """通知源文件已删除，文案与来源插件立即删除路径一致。"""
    _send(plugin, DELETE_SUCCESS_TITLE, f"文件：{path}\n原因：{reason}")


def notify_delete_failure(plugin: Any, path: str, reason: str) -> None:
    """通知源文件删除失败并提示人工处理。"""
    _send(plugin, DELETE_FAILURE_TITLE, f"文件：{path}\n原因：{reason}\n请手动处理")


def notify_scan_result(plugin: Any, cleaned_paths: list[str]) -> None:
    """按来源语义汇总巡检结果：最多列出 10 个文件，其余只报数量。"""
    preview = "\n".join(cleaned_paths[:FAILCLEAN_NOTIFY_PREVIEW_LIMIT])
    more_text = ""
    if len(cleaned_paths) > FAILCLEAN_NOTIFY_PREVIEW_LIMIT:
        more_text = f"\n... 另有 {len(cleaned_paths) - FAILCLEAN_NOTIFY_PREVIEW_LIMIT} 个文件"
    _send(
        plugin,
        SCAN_SUMMARY_TITLE,
        f"共清理 {len(cleaned_paths)} 个文件：\n{preview}{more_text}",
    )


def _send(plugin: Any, title: str, text: str) -> None:
    """按来源语义以“手动处理”类型发送纯文本通知（统一标题前缀）。"""
    from ...utils.notify import module_title

    plugin.post_message(
        mtype=MessageType.Manual, title=module_title("failclean", title),
        text=text, parse_mode="plain",
    )


__all__ = (
    "DELETE_FAILURE_TITLE",
    "DELETE_SUCCESS_TITLE",
    "SCAN_SUMMARY_TITLE",
    "notify_delete_failure",
    "notify_delete_success",
    "notify_scan_result",
)
