"""配置清洗工具"""

from copy import deepcopy

from ..service.autoremove.constants import build_remover_config_defaults
from ..service.failclean.constants import build_failclean_config_defaults
from ..service.hr.constants import build_hr_config_defaults
from ..service.rename import build_rename_flat_defaults
from ..service.site_tag import DEFAULT_TAG_CONFIG

TRANSFER_DEFAULTS = {
    "transfer_enabled": False,
    "notify": False,
    "transfer_cron": "",
    "nolabels": "",
    "includelabels": "",
    "includecategory": "",
    "frompath": "",
    "topath": "",
    "fromdownloader": "",
    "todownloader": "",
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
    "transfer_event_enabled": False,
    **TRANSFER_DEFAULTS,
    "transfer_event_enabled": False,
    "transfer_tasks": "[]",
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
}


def build_plugin_config_defaults() -> dict:
    """返回插件配置页使用的独立默认配置副本。"""
    return deepcopy(PLUGIN_CONFIG_DEFAULTS)


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


def safe_float(value, default, min_exclusive=None):
    """安全转换浮点数，并在不满足下界时回退默认值。"""
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return default
    if min_exclusive is not None and converted <= min_exclusive:
        return default
    return converted


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


def is_transfer_active(plugin) -> bool:
    """判断转移做种能力是否处于可运行状态（开关已由门控属性承载）。

    v3.9.0 多任务引擎：以启用任务列表为准（transfer_tasks 优先，
    空则回退旧单链路迁移视图）；不再要求已废弃的 _fromtorrentpath。
    """
    if not getattr(plugin, "_transfer_enabled", False):
        return False
    from ..service.transfer_tasks import iter_enabled_tasks

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
