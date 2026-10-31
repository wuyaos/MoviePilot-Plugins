"""配置清洗工具"""

from copy import deepcopy

from app.sdk.logging import logger

from ..modules.autoremove.constants import (
    MIGRATION_OBSERVE_ONLY_KEY,
    build_remover_config_defaults,
)
from ..modules.failclean.constants import build_failclean_config_defaults
from ..modules.hr.constants import build_hr_config_defaults
from ..modules.rename.service import build_rename_flat_defaults
from ..modules.sitetag.service import DEFAULT_TAG_CONFIG

TRANSFER_DEFAULTS = {
    "transfer_enabled": False,
    "notify": False,
    "nolabels": "",
    "includelabels": "",
    "includecategory": "",
    "frompath": "",
    "topath": "",
    "fromdownloader": "",
    "todownloader": "",
    "transfer_delete_source_default": False,
    "transfer_delete_duplicate_default": False,
    "deletesource": False,
    "deleteduplicate": False,
    "fromtorrentpath": "",
    "transfer_tasks": "[]",
    "transfer_rename_enabled": False,
    "downloader_ext": "{}",
    "nopaths": "",
    "seed_autostart": True,
    "seed_skipverify": False,
    "transferemptylabel": False,
    "add_torrent_tags": "已整理,转移做种",
    "remainoldcat": False,
    "remainoldtag": False,
    "scan_limit": 500,
    "pause_source": True,
}

UPLOAD_LIMIT_CONFIG_DEFAULTS = {
    "upload_limit_enabled": False,
    "upload_limit_downloaders": [],
    "upload_limit_downloader_limits_kib": {},
    "upload_limit_site_rules": {},
    "upload_limit_grace_minutes": 30,
}


# ---- 模块观察模式注册表（阶段三：每模块独立「只预览不写入」）----
# module -> 配置页扁平观察键；观察模式下该模块只列候选/预览，不执行下载器写操作。
OBSERVE_ONLY_KEYS = {
    "transfer": "transfer_observe_only",
    "rename": "rename_observe_only",
    "tag": "tag_observe_only",
    "hr": "hr_observe_only",
    "autoremove": "remover_observe_only",
    "failclean": "failcleanup_observe_only",
    "upload_limit": "upload_limit_observe_only",
}

# 旧键兼容（决策 A）：自动删种的观察值原由 MIGRATION_OBSERVE_ONLY_KEY 承载，新键缺失时继承旧值。
LEGACY_OBSERVE_ONLY_KEYS = {
    "autoremove": MIGRATION_OBSERVE_ONLY_KEY,
}

# 全新安装默认值（决策 A）：有写操作的模块默认开启观察；升级来的老配置保持升级前行为，见 module_observe_only。
OBSERVE_ONLY_DEFAULTS = {
    "transfer_observe_only": True,
    "rename_observe_only": True,
    "tag_observe_only": True,
    "hr_observe_only": True,
    "remover_observe_only": True,
    "failcleanup_observe_only": True,
    "upload_limit_observe_only": True,
}
TAG_MODULE_FLAT_DEFAULTS = {
    "tag_interval_cron": DEFAULT_TAG_CONFIG["interval_cron"],
    "tag_enable_media_tag": DEFAULT_TAG_CONFIG["enable_media_tag"],
    "tag_enable_tag": DEFAULT_TAG_CONFIG["enable_tag"],
    "tag_enable_category": DEFAULT_TAG_CONFIG["enable_category"],
    "tag_enable_del_tags": DEFAULT_TAG_CONFIG["enable_del_tags"],
    "tag_downloaders": list(DEFAULT_TAG_CONFIG["downloaders"]),
    "tag_all_cat": list(DEFAULT_TAG_CONFIG["all_cat"]),
    "tag_all_cat_rename": list(DEFAULT_TAG_CONFIG["all_cat_rename"]),
    "tag_rename_type": DEFAULT_TAG_CONFIG["rename_type"],
    "tag_path_rename": DEFAULT_TAG_CONFIG["path_rename"],
    "tag_catprefix": DEFAULT_TAG_CONFIG["catprefix"],
}

"""站点标签增强模块的扁平默认值（DownloadSiteTagModNew get_form，键加 tag_ 前缀）。"""

PLUGIN_CONFIG_DEFAULTS = {
    "enabled": False,
    "delay_minutes": 25,
    "transfer_fallback_enabled": True,
    "transfer_fallback_interval_minutes": 60,
    "seed_check_interval": 60,
    "seed_max_wait_minutes": 120,
    **TRANSFER_DEFAULTS,
    "transfer_rename_enabled": False,
    "downloader_ext": "{}",
    **build_rename_flat_defaults(),
    "tag_enabled": True,
    "tag_siteprefix": "🏠",
    "tag_tracker_mappings_str": "",
    "tag_custom_sites_str": "",
    **TAG_MODULE_FLAT_DEFAULTS,
    **UPLOAD_LIMIT_CONFIG_DEFAULTS,
    **build_hr_config_defaults(),
    **build_remover_config_defaults(),
    **build_failclean_config_defaults(),
    **OBSERVE_ONLY_DEFAULTS,
}


def build_plugin_config_defaults() -> dict:
    """返回插件配置页使用的独立默认配置副本。"""
    return deepcopy(PLUGIN_CONFIG_DEFAULTS)


def transfer_delete_defaults(config: dict) -> dict[str, bool]:
    """新键显式优先；仅在新键缺失时迁移旧全局布尔值，不做真值转换。"""
    return {
        key: config.get(key, config.get(legacy, False)) is True
        for key, legacy in (
            ("transfer_delete_source_default", "deletesource"),
            ("transfer_delete_duplicate_default", "deleteduplicate"),
        )
    }


def safe_int(value, default, min_value=None, max_value=None):
    """安全整数转换，带范围限制"""
    try:
        v = int(value)
    except (TypeError, ValueError):
        return default
    if min_value is not None and v < min_value:
        return min_value
    if max_value is not None and v > max_value:
        return max_value
    return v


def _positive_integer_mapping(value) -> dict[str, int]:
    """清洗按下载器保存的正整数 KiB/s 映射。"""
    if not isinstance(value, dict):
        return {}
    result = {}
    for downloader, speed in value.items():
        if not isinstance(downloader, str) or not downloader.strip():
            continue
        try:
            normalized_speed = int(float(speed))
        except (TypeError, ValueError):
            continue
        if normalized_speed > 0:
            result[downloader.strip()] = normalized_speed
    return result


def _normalize_upload_site_rules(value) -> dict[str, dict]:
    """清洗站点合计上传上限，零值表示不设置站点限速。"""
    if not isinstance(value, dict):
        return {}
    result = {}
    for site_name, raw_rule in value.items():
        clean_name = str(site_name or "").strip()
        if not clean_name or not isinstance(raw_rule, dict):
            continue
        try:
            limit_kib = int(float(raw_rule.get("limit_kib") or 0))
        except (TypeError, ValueError):
            limit_kib = 0
        result[clean_name] = {
            "limit_kib": max(0, limit_kib),
        }
    return result


def normalize_upload_limit_config(config: dict | None) -> dict:
    """按上传限速契约清洗配置并补齐默认值。"""
    source = config if isinstance(config, dict) else {}
    downloaders = []
    for downloader in source.get("upload_limit_downloaders") or []:
        if (
            isinstance(downloader, str)
            and downloader.strip()
            and downloader.strip() not in downloaders
        ):
            downloaders.append(downloader.strip())
    return {
        "upload_limit_enabled": bool(source.get("upload_limit_enabled", False)),
        "upload_limit_downloaders": downloaders,
        "upload_limit_downloader_limits_kib": _positive_integer_mapping(
            source.get("upload_limit_downloader_limits_kib")
        ),
        "upload_limit_site_rules": _normalize_upload_site_rules(
            source.get("upload_limit_site_rules")
        ),
        "upload_limit_grace_minutes": safe_int(
            source.get("upload_limit_grace_minutes"), 30, 0, 1440
        ),
    }


# ---- 模块开关注册表（唯一真源）----
# module -> (配置页扁平开关键, plugin 运行时属性名)
# 运行时属性统一存「门控值」：enabled AND 模块开关；裸开关用 _module_switches 快照。
MODULE_SWITCHES = {
    "transfer": ("transfer_enabled", "_transfer_enabled"),
    "rename": ("rename_enabled", "_rename_enabled"),
    "tag": ("tag_enabled", "_tag_enabled"),
    "hr": ("hr_enabled", "_hr_enabled"),
    "autoremove": ("remover_enabled", "_remover_enabled"),
    "failclean": ("failcleanup_enabled", "_failcleanup_enabled"),
    "upload_limit": ("upload_limit_enabled", "_upload_limit_enabled"),
}


def module_switch_on(config: dict, module: str) -> bool:
    """读模块裸开关（不含总开关；展示层区分「插件停用」与「模块停用」时用）。"""
    flat_key = MODULE_SWITCHES[module][0]
    default = PLUGIN_CONFIG_DEFAULTS.get(flat_key, False)
    return bool(config.get(flat_key, default))


def module_active(config: dict, module: str) -> bool:
    """模块生效的唯一门控口径：插件总开关 AND 模块开关。"""
    if not config.get("enabled", False):
        return False
    return module_switch_on(config, module)


def build_module_switches(config: dict) -> dict:
    """返回 {module: 裸开关布尔} 快照，供展示层与诊断使用。"""
    return {module: module_switch_on(config, module) for module in MODULE_SWITCHES}



def module_observe_only(config: dict, module: str) -> bool:
    """解析模块观察模式（阶段三唯一口径）。

    - 已保存新键：以新值为准（保存开关后下一轮才切换）。
    - 只有旧键（自动删种 migration_observe_only）：继承旧值。
    - 升级来的老配置（新旧键都没有）：保持升级前行为，返回 False（允许执行）。
    - 全新安装（空配置）：默认开启观察（PLUGIN_CONFIG_DEFAULTS）。
    """
    key = OBSERVE_ONLY_KEYS.get(module)
    if key is None:
        return False
    source = config if isinstance(config, dict) else {}
    if key in source:
        return bool(source[key])
    legacy_key = LEGACY_OBSERVE_ONLY_KEYS.get(module)
    if legacy_key and legacy_key in source:
        return bool(source[legacy_key])
    if not source:
        return bool(PLUGIN_CONFIG_DEFAULTS.get(key, False))
    return False


def build_module_observe_flags(config: dict) -> dict:
    """返回 {module: 观察模式布尔} 快照；一轮运行内固定，保存开关后新一轮才切换。"""
    source = config if isinstance(config, dict) else {}
    return {module: module_observe_only(source, module) for module in OBSERVE_ONLY_KEYS}


def module_observe_flags(plugin) -> dict:
    """读取插件实例上的观察模式快照；快照缺失时按「不观察」处理。"""
    flags = getattr(plugin, "_module_observe_only", None)
    if not isinstance(flags, dict):
        return {module: False for module in OBSERVE_ONLY_KEYS}
    return {module: bool(flags.get(module, False)) for module in OBSERVE_ONLY_KEYS}


def observe_only(plugin, module: str) -> bool:
    """判断模块本轮是否处于观察模式（模块是否启用由模块门控负责，此处不重复判断）。"""
    return bool(module_observe_flags(plugin).get(module, False))


OBSERVE_PREVIEW_SAMPLE_LIMIT = 20

# 观察模式日志的模块中文名（与 utils/log_prefix.MODULES 一致，供【PT下载中心】日志正文标注）
OBSERVE_MODULE_LABELS = {
    "transfer": "转移做种",
    "rename": "重命名",
    "tag": "站点标签",
    "hr": "H&R",
    "autoremove": "自动删种",
    "failclean": "失败清理",
    "upload_limit": "上传限速",
}


def record_observe_preview(plugin, module: str, detail: str) -> None:
    """登记观察模式预览样本（内存滚动保留），不触发任何下载器写操作。"""
    previews = getattr(plugin, "_observe_previews", None)
    if not isinstance(previews, dict):
        previews = {}
        plugin._observe_previews = previews
    entry = previews.get(module)
    if not isinstance(entry, dict):
        entry = {"count": 0, "samples": []}
        previews[module] = entry
    entry["count"] = int(entry.get("count") or 0) + 1
    samples = entry.get("samples")
    if not isinstance(samples, list):
        samples = []
        entry["samples"] = samples
    line = str(detail or "").strip()
    if line and len(samples) < OBSERVE_PREVIEW_SAMPLE_LIMIT:
        samples.append(line)


def observe_skip(plugin, module: str, action: str, detail: str = "") -> bool:
    """观察模式统一写边界：返回 True 表示调用方必须跳过真实写操作（只登记预览）。"""
    if not observe_only(plugin, module):
        return False
    record_observe_preview(plugin, module, f"{action}：{detail}" if detail else action)
    suffix = f"：{detail}" if detail else ""
    label = OBSERVE_MODULE_LABELS.get(module, module)
    logger.info(f"【PT下载中心】观察模式[{label}]：跳过{action}{suffix}")
    return True


def observe_previews(plugin) -> dict:
    """返回观察模式预览快照 {module: {count, samples}}，供页面展示「本应执行」的条数。"""
    previews = getattr(plugin, "_observe_previews", None)
    if not isinstance(previews, dict):
        return {}
    snapshot = {}
    for module, entry in previews.items():
        if not isinstance(entry, dict):
            continue
        snapshot[str(module)] = {
            "count": int(entry.get("count") or 0),
            "samples": list(entry.get("samples") or []),
        }
    return snapshot

def record_module_fault(plugin, module: str, reason: str) -> None:
    """记录模块运行异常（只记内存、不改用户开关），供页面区分「关闭」与「故障」。"""
    faults = getattr(plugin, "_module_faults", None)
    if not isinstance(faults, dict):
        faults = {}
        plugin._module_faults = faults
    faults[module] = str(reason or "").strip() or "未知原因"


def clear_module_fault(plugin, module: str) -> None:
    """清除模块运行异常标记（该模块重新初始化成功时调用）。"""
    faults = getattr(plugin, "_module_faults", None)
    if isinstance(faults, dict):
        faults.pop(module, None)


def module_faults(plugin) -> dict:
    """返回模块运行异常快照 {module: 原因}。"""
    faults = getattr(plugin, "_module_faults", None)
    if not isinstance(faults, dict):
        return {}
    return {str(name): str(reason) for name, reason in faults.items() if reason}

def is_transfer_active(plugin) -> bool:
    """判断转移做种能力是否处于可运行状态（开关已由门控属性承载）。

    v3.9.0 多任务引擎：以启用任务列表为准（transfer_tasks 优先，
    空则回退旧单链路迁移视图）；不再要求已废弃的 _fromtorrentpath。
    """
    if not getattr(plugin, "_transfer_enabled", False):
        return False
    from ..modules.transfer.tasks import iter_enabled_tasks

    try:
        return bool(iter_enabled_tasks(plugin))
    except Exception:
        return False


def is_upload_limit_active(plugin) -> bool:
    """判断上传限速是否具备运行所需的完整下载器额度。"""
    selected = getattr(plugin, "_upload_limit_downloaders", [])
    selected_names = [
        name.strip()
        for name in selected
        if isinstance(name, str) and name.strip()
    ] if isinstance(selected, (list, tuple, set)) else []
    limits = getattr(plugin, "_upload_limit_downloader_limits_kib", {})
    if not isinstance(limits, dict):
        return False
    return bool(
        getattr(plugin, "_upload_limit_enabled", False)
        and selected_names
        and all(safe_int(limits.get(name), 0, 0) > 0 for name in selected_names)
    )


def is_plugin_active(plugin) -> bool:
    """判断插件是否至少有一个模块处于生效状态（门控属性已含总开关）。"""
    return any(
        bool(getattr(plugin, attr, False))
        for _, attr in MODULE_SWITCHES.values()
    )
