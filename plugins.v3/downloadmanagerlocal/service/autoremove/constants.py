"""自动删种模块配置键、默认值、持久化键与调度注册常量。"""

from __future__ import annotations

REMOVER_LOG_PREFIX = "[PT下载中心:自动删种]"

REMOVER_NOTIFY_TITLE = "【自动删种任务完成】"

REMOVER_SERVICE_ID = "AutoRemoveTorrents"
REMOVER_SERVICE_NAME = "自动删种"

REMOVER_STATE_DATA_KEY = "remover_state"
"""最近一轮执行状态（候选/执行/跳过统计与候选明细）的持久化 key。"""

MIGRATION_OBSERVE_ONLY_KEY = "migration_observe_only"
"""公共迁移观察闸门键；为 True 时只列候选，不执行任何下载器写操作。"""

REMOVER_ACTIONS = ("pause", "delete", "deletefile")
"""动作：暂停 / 删除任务 / 删除任务及文件，与来源插件一致。"""

REMOVER_CANDIDATE_VIEW_LIMIT = 50
"""运行状态中保留的候选明细条数上限。"""

REMOVER_NOTIFY_ITEM_LIMIT = 20
"""单条通知中列出的处理条目上限，超出只汇总数量。"""

REMOVER_FORM_DEFAULTS = {
    "remover_enabled": False,
    "remover_notify": False,
    "remover_action": "pause",
    "remover_downloaders": [],
    "remover_cron": "0 */12 * * *",
    "remover_samedata": False,
    "remover_mponly": False,
    "remover_size": "",
    "remover_ratio": "",
    "remover_time": "",
    "remover_upspeed": "",
    "remover_labels": "",
    "remover_pathkeywords": "",
    "remover_trackerkeywords": "",
    "remover_errorkeywords": "",
    "remover_torrentstates": "",
    "remover_torrentcategorys": "",
}
"""TorrentRemover 源码 get_form 的表单默认值（配置键加 remover_ 前缀）。"""



REMOVER_CONFIG_DEFAULTS = {**REMOVER_FORM_DEFAULTS}
"""插件发布默认值：来源 TorrentRemover get_form 表单默认值（remover_ 前缀）。"""


def build_remover_config_defaults() -> dict:
    """返回自动删种配置默认值的独立副本，供插件配置默认值合并使用。"""
    defaults = {}
    for key, value in REMOVER_CONFIG_DEFAULTS.items():
        defaults[key] = list(value) if isinstance(value, (list, dict)) else value
    return defaults


__all__ = (
    "MIGRATION_OBSERVE_ONLY_KEY",
    "REMOVER_ACTIONS",
    "REMOVER_CANDIDATE_VIEW_LIMIT",
    "REMOVER_CONFIG_DEFAULTS",
    "REMOVER_FORM_DEFAULTS",
    "REMOVER_LOG_PREFIX",
    "REMOVER_NOTIFY_ITEM_LIMIT",
    "REMOVER_NOTIFY_TITLE",
    "REMOVER_SERVICE_ID",
    "REMOVER_SERVICE_NAME",
    "REMOVER_STATE_DATA_KEY",
    "build_remover_config_defaults",
)
