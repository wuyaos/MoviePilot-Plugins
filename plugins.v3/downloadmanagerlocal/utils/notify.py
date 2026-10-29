"""统一通知出口（阶段四 P4-1）。

只负责统一标题与数量口径文本、安全发送（异常不中断业务）；
通知开关判断与消息类型留在各模块调用点，不引入队列、模板或调度。
标题格式：`下载中心 · 模块名` 或 `下载中心 · 模块名（后缀）`；
数量口径：普通轮次「结果：成功 X，跳过 Y，失败 Z」，观察期「预览：N 个候选，未执行」。
"""

from __future__ import annotations

from typing import Any

from app.sdk.logging import logger
from app.schemas.types import MessageType

NOTIFY_TITLE_PREFIX = "下载中心"

MODULE_TITLES = {
    "transfer": "转移做种",
    "rename": "种子重命名",
    "tag": "站点标签",
    "hr": "H&R 管理",
    "autoremove": "自动删种",
    "failclean": "失败清理",
    "upload_limit": "上传限速",
}


def module_title(module: str, suffix: str = "") -> str:
    """统一标题：「下载中心 · 模块名」或「下载中心 · 模块名（后缀）」。"""
    base = f"{NOTIFY_TITLE_PREFIX} · {MODULE_TITLES.get(module, module)}"
    return f"{base}（{suffix}）" if suffix else base


def result_text(
    *,
    success: int = 0,
    skipped: int = 0,
    failed: int = 0,
    preview_count: int = 0,
    observe: bool = False,
    downloader: str = "",
    extra: str = "",
) -> str:
    """统一数量口径文本；观察模式固定输出「预览：N 个候选，未执行」。"""
    if observe:
        lines = [f"预览：{preview_count} 个候选，未执行"]
    else:
        lines = [f"结果：成功 {success}，跳过 {skipped}，失败 {failed}"]
    if downloader:
        lines.append(f"下载器：{downloader}")
    if extra:
        lines.append(extra)
    return "\n".join(lines)


def notify_module_result(
    plugin: Any,
    module: str,
    *,
    text: str,
    suffix: str = "",
    mtype=None,
) -> bool:
    """统一发送入口：开关与消息类型由调用点决定；任何异常只告警，不中断业务。"""
    try:
        if plugin is None or not callable(getattr(plugin, "post_message", None)):
            return False
        plugin.post_message(
            mtype=mtype or MessageType.Manual,
            title=module_title(module, suffix),
            text=text,
            parse_mode="plain",
        )
        return True
    except Exception as exc:  # noqa: BLE001 通知失败不影响业务主流程
        logger.warning(
            f"【PT下载中心】通知发送失败（{MODULE_TITLES.get(module, module)}）：{exc}"
        )
        return False


__all__ = ("MODULE_TITLES", "module_title", "notify_module_result", "result_text")
