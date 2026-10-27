"""整理失败清理的配置键、默认值、持久化键与调度注册常量。"""

from __future__ import annotations

FAILCLEAN_LOG_PREFIX = "【PT下载中心:失败清理】"

FAILCLEAN_STATUS_DATA_KEY = "failclean_status"
"""最近巡检与累计清理计数的持久化 key。"""

FAILCLEAN_REPEAT_SERVICE_ID = "DownloadCenterRepeatCleanup"
""""重复下载残留清理"调度服务 ID。"""
FAILCLEAN_REPEAT_SERVICE_NAME = "重复下载残留清理"

FAILCLEAN_TRANSFER_FAILED_TRIGGER = "TransferFailed"
"""整理失败即时清理的触发来源名。"""
FAILCLEAN_SCAN_TRIGGER = "定时"
"""巡检清理的默认触发来源名。"""

FAILCLEAN_NOTIFY_PREVIEW_LIMIT = 10
"""巡检汇总通知中最多列出的文件数，与来源插件一致。"""

FAILCLEAN_RECENT_WINDOW_SECONDS = 30
"""同一 (hash, 路径) 在该窗口内的重复事件不再执行删除，避免事件风暴重复删。"""

FAILCLEAN_FORM_DEFAULTS = {
    "failcleanup_enabled": False,
    "failcleanup_notify": True,
    "failcleanup_cron": "0 */2 * * *",
    "failcleanup_clean_repeat": True,
    "failcleanup_retain_hours": 6,
}
"""transferfaildelete 源码 get_form 返回的表单默认值，键加 failcleanup_ 前缀。"""

FAILCLEAN_QNAP_CONFIG = {
    "failcleanup_enabled": True,
}
"""qnap 现役 TransferFailDelete 配置里与表单默认不同的键，仅作行为证据。"""

FAILCLEAN_CONFIG_DEFAULTS = dict(FAILCLEAN_FORM_DEFAULTS)
"""插件发布默认值：即 get_form 表单默认值；qnap 私有覆盖（FAILCLEAN_QNAP_CONFIG）已移出，仅留作行为证据。"""


def build_failclean_config_defaults() -> dict:
    """返回整理失败清理配置默认值的独立副本，供插件配置默认值合并使用。"""
    return dict(FAILCLEAN_CONFIG_DEFAULTS)


__all__ = (
    "FAILCLEAN_CONFIG_DEFAULTS",
    "FAILCLEAN_FORM_DEFAULTS",
    "FAILCLEAN_LOG_PREFIX",
    "FAILCLEAN_NOTIFY_PREVIEW_LIMIT",
    "FAILCLEAN_QNAP_CONFIG",
    "FAILCLEAN_RECENT_WINDOW_SECONDS",
    "FAILCLEAN_REPEAT_SERVICE_ID",
    "FAILCLEAN_REPEAT_SERVICE_NAME",
    "FAILCLEAN_SCAN_TRIGGER",
    "FAILCLEAN_STATUS_DATA_KEY",
    "FAILCLEAN_TRANSFER_FAILED_TRIGGER",
    "build_failclean_config_defaults",
)
