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
    "delete_source": "inherit",
    "delete_duplicate": "inherit",
    "keep_category": True,
    "keep_tag": True,
    "transfer_tag": "已转移",
}


_LEGACY_FLAG_DEFAULTS = {"delete_source": False, "delete_duplicate": True}


def resolve_task_flag(task: dict, field: str, global_default: bool) -> tuple[bool, str]:
    """仅 inherit 跟随全局值；缺失及非法值保留升级前语义（无 IO）。"""
    value = task.get(field)
    if type(value) is bool:
        return value, "task"
    if value == "inherit":
        return global_default is True, "global"
    return _LEGACY_FLAG_DEFAULTS[field], "legacy-default"


def _normalize_task(raw: Any, index: int) -> Optional[Dict[str, Any]]:
    """规范化单条任务；非法条目返回 None 并记录。"""
    if not isinstance(raw, dict):
        logger.warning(f"【PT下载中心:转移做种】任务 #{index + 1} 不是对象，已忽略")
        return None
    # 旧任务缺失风险键必须保持缺失，不能由新任务模板补成继承。
    task = {key: value for key, value in _TASK_DEFAULTS.items() if key not in _LEGACY_FLAG_DEFAULTS}
    for key in _TASK_FIELDS:
        if key in raw:
            task[key] = raw[key]
    task["name"] = str(task["name"] or "").strip() or f"任务{index + 1}"
    for field in _LEGACY_FLAG_DEFAULTS:
        if field in raw and type(raw[field]) is not bool and raw[field] != "inherit":
            logger.warning(
                f"【PT下载中心:转移做种】任务「{task['name']}」{field} 非法值 {raw[field]!r}，按旧默认解释"
            )
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
    # 路径映射是「可选」能力：两者都为空的语义 = 不做映射（与 utils/path.py 的
    # convert_save_path 契约 C1 一致——任一入参为空则原样返回）。只有「只填了一个」
    # 才是真的配置错误：那会让映射方向不明，必须拒绝。
    if bool(task["from_path"]) != bool(task["to_path"]):
        logger.warning(
            f"【PT下载中心:转移做种】任务「{task['name']}」数据映射路径需同时填写或同时留空，已忽略"
        )
        return None
    return task


def load_transfer_tasks(plugin) -> List[Dict[str, Any]]:
    """读取 transfer_tasks；仅当「从未迁移过」时回退旧单链路键构建迁移任务（不回写）。

    迁移判定（P1-8）：配置里存在 ``transfer_tasks_migrated`` 标记，或 transfer_tasks
    本身是合法 JSON 数组（包括空数组 ``[]``）即视为已迁移——用户显式删光任务后
    ``"[]"`` 不得复活旧链路；只有解析失败/键不存在时才回退旧配置。
    """
    raw = getattr(plugin, "_transfer_tasks", None)
    migrated_flag = bool(getattr(plugin, "_transfer_tasks_migrated", False))
    parsed = None
    parse_failed = False
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError) as err:
            logger.error(f"【PT下载中心:转移做种】transfer_tasks 解析失败：{err}，回退旧单链路配置")
            parse_failed = True
    migrated = migrated_flag or (isinstance(parsed, list) and not parse_failed)
    tasks: List[Dict[str, Any]] = []
    if isinstance(parsed, list) and parsed:
        for index, item in enumerate(parsed):
            normalized = _normalize_task(item, index)
            if normalized:
                tasks.append(normalized)
    if tasks:
        return [task for task in tasks if task["enabled"]]
    if migrated:
        return []

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
            "delete_source": getattr(plugin, "_deletesource", False),
            "delete_duplicate": getattr(plugin, "_deleteduplicate", True),
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
    """源种子文件路径：不再作为主路径（改下载器网络导出），仅作 TR4 元数据兜底目录。"""
    if getattr(plugin, _DEPRECATION_NOTIFIED_FLAG, False):
        return
    legacy = str(getattr(plugin, "_fromtorrentpath", "") or "").strip()
    if legacy:
        logger.info(
            "【PT下载中心:转移做种】配置项「源种子文件路径」仅作 Transmission 4 元数据兜底目录"
            f"（主路径为下载器网络导出），当前值：{legacy}"
        )
    setattr(plugin, _DEPRECATION_NOTIFIED_FLAG, True)
