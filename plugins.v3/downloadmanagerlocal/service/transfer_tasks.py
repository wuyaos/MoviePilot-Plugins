"""转移任务模型与存储层。

transfer_tasks 为 JSON 数组字符串，每条任务字段：
- name/enabled/from_downloader/to_downloader
- include_category/include_labels/exclude_labels/empty_label_ok/no_paths
- from_path/to_path（数据可见性映射）
- delete_source/delete_duplicate/keep_category/keep_tag/transfer_tag
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.sdk.logging import logger

_TRANSFER_TASKS_KEY = "transfer_tasks"
_DEPRECATION_NOTIFIED_FLAG = "_fromtorrentpath_deprecation_notified"

_TASK_FIELDS = (
    "name", "enabled", "from_downloader", "to_downloader",
    "include_category", "include_labels", "exclude_labels", "empty_label_ok",
    "no_paths", "from_path", "to_path",
    "delete_source", "delete_duplicate", "keep_category", "keep_tag",
    "transfer_tag",
)

_TASK_DEFAULTS: Dict[str, Any] = {
    "name": "",
    "enabled": True,
    "from_downloader": "",
    "to_downloader": "",
    "include_category": "",
    "include_labels": "",
    "exclude_labels": "",
    "empty_label_ok": True,
    "no_paths": "",
    "from_path": "",
    "to_path": "",
    "delete_source": False,
    "delete_duplicate": True,
    "keep_category": True,
    "keep_tag": True,
    "transfer_tag": "已转移",
}


def _normalize_task(raw: Any, index: int) -> Optional[Dict[str, Any]]:
    """规范化单条任务；非法条目返回 None 并记录。"""
    if not isinstance(raw, dict):
        logger.warning(f"【PT下载中心:转移做种】任务 #{index + 1} 不是对象，已忽略")
        return None
    task = {**_TASK_DEFAULTS}
    for key in _TASK_FIELDS:
        if key in raw:
            task[key] = raw[key]
    task["name"] = str(task["name"] or "").strip() or f"任务{index + 1}"
    task["enabled"] = bool(task["enabled"])
    task["from_downloader"] = str(task["from_downloader"] or "").strip()
    task["to_downloader"] = str(task["to_downloader"] or "").strip()
    task["from_path"] = str(task["from_path"] or "").strip()
    task["to_path"] = str(task["to_path"] or "").strip()
    if not task["from_downloader"] or not task["to_downloader"]:
        logger.warning(f"【PT下载中心:转移做种】任务「{task['name']}」缺少源/目的下载器，已忽略")
        return None
    if task["from_downloader"] == task["to_downloader"]:
        logger.warning(f"【PT下载中心:转移做种】任务「{task['name']}」源与目的下载器相同，已忽略")
        return None
    if not task["from_path"] or not task["to_path"]:
        logger.warning(f"【PT下载中心:转移做种】任务「{task['name']}」缺少数据映射路径，已忽略")
        return None
    return task


def load_transfer_tasks(plugin) -> List[Dict[str, Any]]:
    """读取 transfer_tasks；为空时从旧单链路键构建迁移任务（不回写）。"""
    raw = getattr(plugin, "_transfer_tasks", "") or "[]"
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError) as err:
        logger.error(f"【PT下载中心:转移做种】transfer_tasks 解析失败：{err}，回退旧单链路配置")
        parsed = None
    tasks: List[Dict[str, Any]] = []
    if isinstance(parsed, list) and parsed:
        for index, item in enumerate(parsed):
            normalized = _normalize_task(item, index)
            if normalized:
                tasks.append(normalized)
    if tasks:
        return [task for task in tasks if task["enabled"]]

    # 旧单链路迁移视图（只读，不回写；前端保存后落为显式任务）
    legacy_from = str(getattr(plugin, "_fromdownloader", "") or "").strip()
    legacy_to = str(getattr(plugin, "_todownloader", "") or "").strip()
    if legacy_from and legacy_to and legacy_from != legacy_to:
        legacy_task = {
            **_TASK_DEFAULTS,
            "name": "默认任务（旧配置迁移）",
            "from_downloader": legacy_from,
            "to_downloader": legacy_to,
            "include_category": str(getattr(plugin, "_includecategory", "") or ""),
            "include_labels": str(getattr(plugin, "_includelabels", "") or ""),
            "exclude_labels": str(getattr(plugin, "_nolabels", "") or ""),
            "empty_label_ok": bool(getattr(plugin, "_transferemptylabel", True)),
            "no_paths": str(getattr(plugin, "_nopaths", "") or ""),
            "from_path": str(getattr(plugin, "_frompath", "") or ""),
            "to_path": str(getattr(plugin, "_topath", "") or ""),
            "delete_source": bool(getattr(plugin, "_deletesource", False)),
            "delete_duplicate": bool(getattr(plugin, "_deleteduplicate", True)),
            "keep_category": bool(getattr(plugin, "_remainoldcat", True)),
            "keep_tag": bool(getattr(plugin, "_remainoldtag", True)),
        }
        normalized = _normalize_task(legacy_task, 0)
        if normalized:
            tasks.append(normalized)
    return tasks


def iter_enabled_tasks(plugin) -> List[Dict[str, Any]]:
    """全部启用任务；全部停用/无任务时返回空列表。"""
    return load_transfer_tasks(plugin)


def notify_fromtorrentpath_deprecated(plugin) -> None:
    """源种子文件路径已废弃（改网络导出）；首次读取时提示一次。"""
    if getattr(plugin, _DEPRECATION_NOTIFIED_FLAG, False):
        return
    legacy = str(getattr(plugin, "_fromtorrentpath", "") or "").strip()
    if legacy:
        logger.info(
            "【PT下载中心:转移做种】配置项「源种子文件路径」已废弃（改为下载器网络导出），"
            f"忽略旧值：{legacy}"
        )
    setattr(plugin, _DEPRECATION_NOTIFIED_FLAG, True)
