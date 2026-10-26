"""下载中心配置初始化服务。"""

from app.sdk.logging import logger

from ..adapter.moviepilot import create_downloader_helper
from ..utils.config import (
    PLUGIN_CONFIG_DEFAULTS,
    build_module_switches,
    module_active,
    normalize_upload_limit_config,
    safe_int,
)
from ..service.rename import build_rename_config
from ..service.site_tag import build_tag_config
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
    plugin._rename_config = build_rename_config(config)
    plugin._site_tag_config = build_tag_config(_flat_tag_module_config(config))

    # 空配置也按发布默认值继续初始化运行时字段，避免类属性兜底值与配置页默认值不一致；
    # 此时返回的 config 不叠加清洗结果，保持全新安装的空配置语义。
    if config:
        config.update(upload_limit_config)
    defaults = PLUGIN_CONFIG_DEFAULTS

    plugin._enabled = config.get("enabled", defaults["enabled"])
    plugin._transfer_enabled = module_active(config, "transfer")
    plugin._onlyonce = config.get("onlyonce", defaults["onlyonce"])
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
    plugin._transfer_cron = config.get("transfer_cron", defaults["transfer_cron"]) or ""
    plugin._transfer_event_enabled = config.get(
        "transfer_event_enabled", defaults["transfer_event_enabled"]
    )
    plugin._seed_autostart = config.get("seed_autostart", defaults["seed_autostart"])
    plugin._seed_skipverify = config.get("seed_skipverify", defaults["seed_skipverify"])
    plugin._seed_check_interval = safe_int(config.get("seed_check_interval"), 60, 10, 3600)
    plugin._seed_max_wait_minutes = safe_int(config.get("seed_max_wait_minutes"), 120, 10, 1440)

    plugin._rename_enabled = config.get("rename_enabled", defaults["rename_enabled"])
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
    plugin._rename_movie_format = config.get(
        "rename_movie_format",
        defaults["rename_movie_format"],
    )
    plugin._rename_tv_format = config.get(
        "rename_tv_format",
        defaults["rename_tv_format"],
    )
    plugin._rename_exclude_dirs = config.get("rename_exclude_dirs", defaults["rename_exclude_dirs"])
    # 嵌套视图与门控属性对齐：调度注册、状态展示读嵌套键时口径一致。
    plugin._rename_config["enabled"] = plugin._rename_enabled

    plugin._tag_enabled = module_active(config, "tag")
    plugin._tag_siteprefix = config.get("tag_siteprefix", defaults["tag_siteprefix"])
    plugin._tag_tracker_mappings_str = config.get("tag_tracker_mappings_str", defaults["tag_tracker_mappings_str"])
    if plugin._tag_tracker_mappings_str:
        plugin._tracker_mappings.update(parse_tracker_mappings(plugin._tag_tracker_mappings_str))
    plugin._site_tag_config["enable"] = plugin._tag_enabled

    # hr/autoremove/failclean/upload_limit 的门控属性（transfer/rename/tag 已在上方按注册表口径赋值）；
    # upload_limit 此前由 normalize 循环写入裸值，此处统一覆盖为门控值。
    plugin._hr_enabled = module_active(config, "hr")
    plugin._remover_enabled = module_active(config, "autoremove")
    plugin._failcleanup_enabled = module_active(config, "failclean")
    plugin._upload_limit_enabled = module_active(config, "upload_limit")
    # 裸开关快照：展示层区分「插件停用」与「模块停用」。
    plugin._module_switches = build_module_switches(config)

    return config


_TAG_FLAT_PREFIX_MAP = {
    "tag_interval_cron": "interval_cron",
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
}


def _flat_tag_module_config(config: dict) -> dict:
    """把插件扁平配置映射为站点标签增强模块的嵌套配置键。"""
    return {
        module_key: config[flat_key]
        for flat_key, module_key in _TAG_FLAT_PREFIX_MAP.items()
        if flat_key in config
    }
