"""下载中心配置初始化服务。"""

from app.sdk.logging import logger

from ..adapter.moviepilot import create_downloader_helper
from ..utils.config import (
    MODULE_SWITCHES,
    PLUGIN_CONFIG_DEFAULTS,
    build_module_switches,
    build_module_observe_flags,
    module_active,
    module_faults,
    normalize_upload_limit_config,
    record_module_fault,
    safe_int,
)
from ..modules.rename.service import build_rename_config
from ..modules.sitetag.service import build_tag_config
from ..utils.tracker import parse_tracker_mappings


def initialize_runtime_config(plugin, config: dict = None) -> dict:
    """根据插件配置初始化运行时字段并返回可继续持久化的配置。"""
    config = config or {}
    plugin.downloader_helper = create_downloader_helper()

    default_mappings = (
        "chdbits.xyz -> ptchdbits.co\n"
        "agsvpt.trackers.work -> agsvpt.com\n"
        "tracker.cinefiles.info -> audiences.me"
    )
    plugin._tracker_mappings = parse_tracker_mappings(default_mappings)

    upload_limit_config = normalize_upload_limit_config(config)
    for key, value in upload_limit_config.items():
        setattr(plugin, f"_{key}", value)

    # 命名补刀与站点标签增强模块配置（来源 get_form 默认 + 扁平键覆盖）
    # 模块门控（Goal: 关闭模块不解析、坏配置不阻断其它模块；启用但解析失败只标记运行异常）：
    # 关闭的模块不解析其用户配置，运行时只留「未启用」占位，历史数据仍可读取。
    plugin._module_faults = {}
    # 观察模式快照（阶段三）：一轮运行内固定；保存开关后新一轮才切换。
    plugin._module_observe_only = build_module_observe_flags(config)
    plugin._rename_config = _module_config_guarded(
        plugin,
        "rename",
        module_active(config, "rename"),
        lambda: build_rename_config(config),
        {"enabled": False},
    )
    plugin._site_tag_config = _module_config_guarded(
        plugin,
        "tag",
        module_active(config, "tag"),
        lambda: build_tag_config(_flat_tag_module_config(config)),
        {"enable": False},
    )

    # 空配置也按发布默认值继续初始化运行时字段，避免类属性兜底值与配置页默认值不一致；
    # 此时返回的 config 不叠加清洗结果，保持全新安装的空配置语义。
    if config:
        config.update(upload_limit_config)
    defaults = PLUGIN_CONFIG_DEFAULTS

    plugin._enabled = config.get("enabled", defaults["enabled"])
    plugin._transfer_enabled = module_active(config, "transfer")
    plugin._delay_minutes = config.get("delay_minutes", defaults["delay_minutes"])
    plugin._transfer_fallback_enabled = config.get(
        "transfer_fallback_enabled", defaults["transfer_fallback_enabled"]
    )
    try:
        plugin._transfer_fallback_interval_minutes = max(1, int(
            config.get("transfer_fallback_interval_minutes")
            or defaults["transfer_fallback_interval_minutes"]
        ))
    except (TypeError, ValueError):
        plugin._transfer_fallback_interval_minutes = defaults["transfer_fallback_interval_minutes"]
    plugin._notify = config.get("notify", defaults["notify"])
    plugin._nolabels = config.get("nolabels", defaults["nolabels"])
    plugin._includelabels = config.get("includelabels", defaults["includelabels"])
    plugin._includecategory = config.get("includecategory", defaults["includecategory"])
    plugin._frompath = config.get("frompath", defaults["frompath"])
    plugin._topath = config.get("topath", defaults["topath"])
    plugin._fromdownloader = config.get("fromdownloader", defaults["fromdownloader"])
    plugin._todownloader = config.get("todownloader", defaults["todownloader"])
    plugin._deletesource = config.get("deletesource", defaults["deletesource"])
    plugin._deleteduplicate = config.get("deleteduplicate", defaults["deleteduplicate"])
    plugin._transfer_tasks = config.get("transfer_tasks", defaults["transfer_tasks"])
    plugin._transfer_rename_enabled = config.get("transfer_rename_enabled", defaults["transfer_rename_enabled"])
    plugin._downloader_ext = config.get("downloader_ext", defaults["downloader_ext"])
    plugin._fromtorrentpath = config.get("fromtorrentpath", defaults["fromtorrentpath"])
    plugin._nopaths = config.get("nopaths", defaults["nopaths"])
    plugin._transferemptylabel = config.get("transferemptylabel", defaults["transferemptylabel"])
    plugin._add_torrent_tags = config.get("add_torrent_tags") or ""
    plugin._torrent_tags = (
        plugin._add_torrent_tags.strip().split(",")
        if plugin._add_torrent_tags
        else []
    )
    plugin._remainoldcat = config.get("remainoldcat", defaults["remainoldcat"])
    plugin._remainoldtag = config.get("remainoldtag", defaults["remainoldtag"])
    plugin._scan_limit = safe_int(config.get("scan_limit"), defaults["scan_limit"], 1)
    plugin._pause_source = config.get("pause_source", defaults["pause_source"])
    # transfer_cron / transfer_event_enabled 已移除：全仓零读取（调度实际只有 fallback 间隔一条路径），
    # 且 transfer_event_enabled 在 defaults 里被重复声明两次。旧配置里若残留这两个键，
    # 读取时忽略即可，不影响其余键。
    plugin._seed_autostart = config.get("seed_autostart", defaults["seed_autostart"])
    plugin._seed_skipverify = config.get("seed_skipverify", defaults["seed_skipverify"])
    plugin._seed_check_interval = safe_int(config.get("seed_check_interval"), 60, 10, 3600)
    plugin._seed_max_wait_minutes = safe_int(config.get("seed_max_wait_minutes"), 120, 10, 1440)

    plugin._rename_movie_format = config.get(
        "rename_movie_format",
        defaults["rename_movie_format"],
    )
    plugin._rename_tv_format = config.get(
        "rename_tv_format",
        defaults["rename_tv_format"],
    )
    plugin._rename_exclude_dirs = config.get("rename_exclude_dirs", defaults["rename_exclude_dirs"])
    plugin._rename_enabled = module_active(config, "rename")
    # 嵌套视图与门控属性对齐：调度注册、状态展示读嵌套键时口径一致。
    plugin._rename_config["enabled"] = plugin._rename_enabled

    plugin._tag_enabled = module_active(config, "tag")
    plugin._tag_siteprefix = config.get("tag_siteprefix", defaults["tag_siteprefix"])
    plugin._tag_tracker_mappings_str = config.get("tag_tracker_mappings_str", defaults["tag_tracker_mappings_str"])
    if plugin._tag_tracker_mappings_str:
        plugin._tracker_mappings.update(parse_tracker_mappings(plugin._tag_tracker_mappings_str))
    plugin._site_tag_config["enable"] = plugin._tag_enabled
    # 自定义站点映射表的扁平键是 tag_custom_sites_str，别名到 custom_site_labels_str
    # 只发生在 _flat_tag_module_config 里；此处若直接读扁平 config 的 custom_site_labels
    # 永远为空，会让转移后打标路径静默忽略用户配置的自定义站点（只有补全历史路径生效）。
    plugin._custom_site_labels = dict(plugin._site_tag_config.get("custom_site_labels") or {})

    # hr/autoremove/failclean/upload_limit 的门控属性（transfer/rename/tag 已在上方按注册表口径赋值）；
    # upload_limit 此前由 normalize 循环写入裸值，此处统一覆盖为门控值。
    plugin._hr_enabled = module_active(config, "hr")
    plugin._remover_enabled = module_active(config, "autoremove")
    plugin._failcleanup_enabled = module_active(config, "failclean")
    plugin._upload_limit_enabled = module_active(config, "upload_limit")
    # 裸开关快照：展示层区分「插件停用」与「模块停用」。
    plugin._module_switches = build_module_switches(config)

    # 配置解析失败的模块不进入运行态：门控属性与嵌套视图归零，避免用默认值执行写操作。
    _downgrade_faulted_module_gates(plugin)

    return config


def _downgrade_faulted_module_gates(plugin) -> None:
    """把配置解析失败的模块门控属性归零（用户开关与落盘配置保持不变）。"""
    faults = module_faults(plugin)
    if not faults:
        return
    for module, (_, attr) in MODULE_SWITCHES.items():
        if module in faults:
            setattr(plugin, attr, False)
    rename_config = getattr(plugin, "_rename_config", None)
    if "rename" in faults and isinstance(rename_config, dict):
        rename_config["enabled"] = False
    tag_config = getattr(plugin, "_site_tag_config", None)
    if "tag" in faults and isinstance(tag_config, dict):
        tag_config["enable"] = False


def _module_config_guarded(plugin, module: str, active: bool, builder, fallback: dict) -> dict:
    """按模块门控解析模块配置：关闭不解析，解析失败只记运行异常并回退占位。"""
    if not active:
        return dict(fallback)
    try:
        return builder()
    except Exception as error:
        logger.error(
            f"【PT下载中心】{module} 模块配置解析失败，已隔离该模块"
            f"（不改插件总开关与其它模块）: {error}"
        )
        record_module_fault(plugin, module, f"配置解析失败：{error}")
        return dict(fallback)


_TAG_FLAT_PREFIX_MAP = {
    "tag_interval_cron": "interval_cron",
    "tag_enabled": "enable",
    "tag_enable_media_tag": "enable_media_tag",
    "tag_enable_tag": "enable_tag",
    "tag_enable_category": "enable_category",
    "tag_enable_del_tags": "enable_del_tags",
    "tag_downloaders": "downloaders",
    "tag_all_cat": "all_cat",
    "tag_all_cat_rename": "all_cat_rename",
    "tag_rename_type": "rename_type",
    "tag_path_rename": "path_rename",
    "tag_catprefix": "catprefix",
    "tag_siteprefix": "siteprefix",
    "tag_tracker_mappings_str": "tracker_mappings_str",
    "tag_custom_sites_str": "custom_site_labels_str",
}


def _flat_tag_module_config(config: dict) -> dict:
    """把插件扁平配置映射为站点标签增强模块的嵌套配置键。"""
    return {
        module_key: config[flat_key]
        for flat_key, module_key in _TAG_FLAT_PREFIX_MAP.items()
        if flat_key in config
    }
