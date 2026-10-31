"""模块配置摘要投影（只读）。

把七个模块的「已生效配置」投影成前端配置摘要可消费的字段视图，同时给出每个模块的
scope（生效范围）、schedule（调度）、protection（保护状态）与每个字段的来源。

口径要点：
- 只读：只调用 ``plugin.get_config()`` 与运行时属性/服务状态，不写配置、不发通知、不触发业务动作。
- 已生效：读取保存后的配置（``get_config()``），表单里改动但未保存的临时值不会进入本投影。
- 白名单：只投影明确存在的配置键，不把实现常量（如上传限速 worker 的 30 秒周期）伪装成配置项。
- 门控：``enabled`` 用运行时门控属性（总开关 AND 模块开关）；``bare_switch`` 用裸开关快照；
  ``active`` 只在有「配置完整性」概念的模块（transfer/upload_limit）做完整性判定，其余等于门控 enabled。
"""
from __future__ import annotations

from typing import Any


def _list_display(value: Any) -> str:
    """列表展示文本：去重、去空、逗号连接；空列表为未配置。"""
    if isinstance(value, str):
        raw_items = [part.strip() for part in value.replace("，", ",").split(",")]
    elif isinstance(value, (list, tuple, set)):
        raw_items = [str(item or "").strip() for item in value]
    else:
        raw_items = []
    items = []
    for item in raw_items:
        if item and item not in items:
            items.append(item)
    return ", ".join(items) if items else "未配置"


def _bool_display(value: Any) -> str:
    """布尔展示文本。"""
    return "开启" if bool(value) else "关闭"


def _field(key: str, label: str, value: str, category: str, source: str,
           *, badge: bool = False, long: bool = False) -> dict:
    """构造单个摘要字段；value 已是展示就绪文本。"""
    result: dict[str, Any] = {
        "key": key,
        "label": label,
        "value": value,
        "category": category,
        "source": source,
    }
    if badge:
        result["badge"] = True
    if long:
        result["long"] = True
    return result


def _config(plugin: Any) -> dict:
    """读取已保存配置；get_config 不可用或非 dict 时返回空 dict。"""
    getter = getattr(plugin, "get_config", None)
    if not callable(getter):
        return {}
    try:
        raw = getter()
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _defaults() -> dict:
    """插件发布默认值（惰性导入，避免测试替身环境下顶层依赖）。"""
    from ..utils.config import PLUGIN_CONFIG_DEFAULTS
    return PLUGIN_CONFIG_DEFAULTS


def _bare_switches(plugin: Any, config: dict) -> dict:
    """读取裸开关快照；快照缺失时按已保存配置重新计算。"""
    snapshot = getattr(plugin, "_module_switches", None)
    if isinstance(snapshot, dict) and snapshot:
        return dict(snapshot)
    from ..utils.config import build_module_switches
    return build_module_switches(config)


def _observe_flags(plugin: Any) -> dict:
    """读取观察模式快照；缺失时按不观察处理。"""
    flags = getattr(plugin, "_module_observe_only", None)
    if isinstance(flags, dict):
        return flags
    from ..utils.config import module_observe_flags
    return module_observe_flags(plugin)


def _cfg(config: dict, defaults: dict, key: str, default=None):
    """读已保存配置键；缺失时回退插件发布默认值，再回退显式 default。"""
    if key in config:
        return config[key]
    if key in defaults:
        return defaults[key]
    return default


def _service_status(plugin: Any, attr: str) -> dict:
    """读取模块服务的 get_module_status()，不可用时返回空 dict。"""
    service = getattr(plugin, attr, None)
    getter = getattr(service, "get_module_status", None)
    if not callable(getter):
        return {}
    try:
        status = getter()
    except Exception:
        return {}
    return status if isinstance(status, dict) else {}


def _upload_limit_status(plugin: Any) -> dict:
    """上传限速持久化状态；服务不可用时返回空 dict。"""
    try:
        from ..modules.uploadlimit.service import get_upload_limit_status
        return get_upload_limit_status(plugin) or {}
    except Exception:
        return {}


def _upload_limit_active(plugin: Any, status: dict) -> bool:
    """上传限速配置完整性（额度与下载器齐全）。"""
    try:
        from ..utils.config import is_upload_limit_active
        return bool(is_upload_limit_active(plugin))
    except Exception:
        return bool(status.get("active"))


def _hr_runtime_config(hr_service) -> dict:
    """返回 H&R 运行时配置的少量投影字段；服务缺失时返回空 dict。"""
    config = getattr(hr_service, "config", None)
    if config is None:
        return {}
    return {
        "downloaders": list(getattr(config, "downloaders", []) or []),
        "sites": list(getattr(config, "sites", []) or []),
        "protection_enabled": bool(getattr(config, "protection_enabled", False)),
        "enabled": bool(getattr(config, "enabled", False)),
    }


def _hr_guard_effective(hr_runtime: dict) -> bool:
    """H&R 保护闸门是否生效（模块门控 AND 保护开关）。"""
    return bool(hr_runtime.get("enabled") and hr_runtime.get("protection_enabled"))


# ── 各模块字段投影 ────────────────────────────────────────────────────────

def _transfer_fields(config: dict, defaults: dict) -> list[dict]:
    seed_check_interval = _cfg(config, defaults, "seed_check_interval", 60)
    try:
        interval = f"{int(seed_check_interval)} 分钟"
    except (TypeError, ValueError):
        interval = "未配置"
    return [
        _field("event", "入列触发", "下载完成事件", "static",
               "固有行为（TransferComplete 事件）"),
        _field("fallback", "定时兜底",
               _bool_display(_cfg(config, defaults, "transfer_fallback_enabled", True)),
               "bare_switch", "配置键 transfer_fallback_enabled", badge=True),
        _field("start", "自动开始",
               _bool_display(_cfg(config, defaults, "seed_autostart", True)),
               "bare_switch", "配置键 seed_autostart", badge=True),
        _field("verify", "跳过校验",
               _bool_display(_cfg(config, defaults, "seed_skipverify", False)),
               "bare_switch", "配置键 seed_skipverify", badge=True),
        _field("interval", "检查间隔", interval, "config_value",
               "配置键 seed_check_interval"),
    ]


def _rename_fields(config: dict, defaults: dict) -> list[dict]:
    cron_enabled = _cfg(config, defaults, "rename_cron_enabled", False)
    cron = str(_cfg(config, defaults, "rename_cron", "") or "").strip()
    if not cron_enabled:
        cron_display = "关闭"
    elif cron:
        cron_display = cron
    else:
        cron_display = "开启（未设置周期）"
    return [
        _field("event", "入列触发",
               _bool_display(_cfg(config, defaults, "rename_on_download_added", True)),
               "bare_switch", "配置键 rename_on_download_added", badge=True),
        _field("cron", "定时补查及周期", cron_display, "bare_switch",
               "配置键 rename_cron_enabled + rename_cron"),
        _field("movie", "电影模板",
               str(_cfg(config, defaults, "rename_movie_format", "") or "").strip(),
               "config_value", "配置键 rename_movie_format", long=True),
        _field("tv", "剧集模板",
               str(_cfg(config, defaults, "rename_tv_format", "") or "").strip(),
               "config_value", "配置键 rename_tv_format", long=True),
    ]


def _hr_fields(config: dict, defaults: dict, hr_runtime: dict) -> list[dict]:
    downloaders = (hr_runtime.get("downloaders")
                   if hr_runtime.get("downloaders") is not None
                   else _cfg(config, defaults, "hr_downloader", []))
    sites = (hr_runtime.get("sites")
             if hr_runtime.get("sites") is not None
             else _cfg(config, defaults, "hr_sites", []))
    enable_site_config = _cfg(config, defaults, "hr_enable_site_config", False)
    rule_value = "站点规则（内置预设 + 自定义）" if enable_site_config else "全局默认"
    check_period = _cfg(config, defaults, "hr_check_period", 10)
    try:
        hr_interval = f"{int(check_period)} 分钟"
    except (TypeError, ValueError):
        hr_interval = "未配置"
    return [
        _field("downloaders", "下载器范围", _list_display(downloaders), "config_value",
               "配置键 hr_downloader"),
        _field("sites", "站点范围", _list_display(sites), "config_value",
               "配置键 hr_sites"),
        _field("rules", "规则来源", rule_value, "config_value",
               "配置键 hr_enable_site_config + hr_site_config_str"),
        _field("interval", "检查周期", hr_interval, "config_value",
               "配置键 hr_check_period"),
        _field("guard", "删除保护",
               _bool_display(_hr_guard_effective(hr_runtime)),
               "bare_switch", "配置键 hr_protection_enabled（受模块门控）", badge=True),
    ]


def _autoremove_fields(config: dict, defaults: dict, status: dict,
                       enabled: bool, observe_only: bool) -> list[dict]:
    action = _cfg(config, defaults, "remover_action", "pause")
    action_text = {
        "pause": "暂停任务",
        "delete": "删除任务",
        "deletefile": "删除任务及文件",
    }.get(action, action or "暂停任务")
    if observe_only:
        mode = "观察模式"
    else:
        mode = _bool_display(enabled)
    return [
        _field("mode", "运行模式", mode, "gated_enabled",
               "运行时门控 remover_enabled（总开关 AND 模块开关）", badge=True),
        _field("action", "执行动作", action_text, "config_value",
               "配置键 remover_action"),
        _field("downloaders", "下载器范围",
               _list_display(_cfg(config, defaults, "remover_downloaders", [])),
               "config_value", "配置键 remover_downloaders"),
        _field("rules", "命中规则",
               "已启用" if _remover_rule_active(config, defaults) else "未启用",
               "config_value", "配置键 remover_*（大小/分享率/做种时间等命中条件）"),
        _field("cron", "执行周期", str(_cfg(config, defaults, "remover_cron", "") or "").strip(),
               "config_value", "配置键 remover_cron"),
        _field("guard", "H&R保护", _bool_display(status.get("guard_enabled")),
               "bare_switch", "H&R 保护闸门（自动删种路径）", badge=True),
    ]


def _remover_rule_active(config: dict, defaults: dict) -> bool:
    """自动删种是否配置了任一命中规则（任一非空即视为启用）。"""
    keys = (
        "remover_size", "remover_ratio", "remover_time", "remover_upspeed",
        "remover_labels", "remover_pathkeywords", "remover_trackerkeywords",
        "remover_errorkeywords", "remover_torrentstates", "remover_torrentcategorys",
    )
    for key in keys:
        value = _cfg(config, defaults, key, "")
        if isinstance(value, (list, tuple, set)) and len(value):
            return True
        if str(value or "").strip():
            return True
    return False


def _failclean_fields(config: dict, defaults: dict) -> list[dict]:
    return [
        _field("scope", "清理范围", "本地下载目录", "static",
               "固有行为（按下载目录巡检）"),
        _field("event", "事件触发", "整理失败事件（固有行为）", "static",
               "固有行为（TransferFailed 事件）"),
        _field("cron", "定时巡检及周期",
               str(_cfg(config, defaults, "failcleanup_cron", "") or "").strip(),
               "config_value", "配置键 failcleanup_cron"),
        _field("action", "清理动作",
               "删除重复下载残留" if _cfg(config, defaults, "failcleanup_clean_repeat", True)
               else "关闭", "bare_switch", "配置键 failcleanup_clean_repeat"),
    ]


def _tag_fields(config: dict, defaults: dict, tag_config: dict,
                enabled: bool) -> list[dict]:
    nested = tag_config if isinstance(tag_config, dict) else {}
    return [
        _field("mode", "运行模式", _bool_display(enabled), "gated_enabled",
               "运行时门控 tag_enabled（总开关 AND 模块开关）", badge=True),
        _field("downloaders", "下载器范围",
               _list_display(nested.get("downloaders", [])),
               "config_value", "配置键 tag_downloaders"),
        _field("site", "站点标签", _bool_display(nested.get("enable_tag")),
               "bare_switch", "配置键 tag_enable_tag", badge=True),
        _field("media", "媒体标签", _bool_display(nested.get("enable_media_tag")),
               "bare_switch", "配置键 tag_enable_media_tag", badge=True),
        _field("category", "下载分类", _bool_display(nested.get("enable_category")),
               "bare_switch", "配置键 tag_enable_category", badge=True),
        _field("cron", "执行周期", str(nested.get("interval_cron") or "").strip(),
               "config_value", "配置键 tag_interval_cron"),
    ]


def _upload_limit_fields(config: dict, defaults: dict, status: dict) -> list[dict]:
    mode_label = {
        "disabled": "未启用",
        "starting": "启动中",
        "running": "分配中",
        "degraded": "部分异常",
        "error": "状态异常",
        "observe_only": "观察模式",
    }.get(status.get("service_status"), "未启用")
    global_limits = _cfg(config, defaults, "upload_limit_downloader_limits_kib", {})
    site_rules = _cfg(config, defaults, "upload_limit_site_rules", {})
    global_display = "未配置"
    if isinstance(global_limits, dict):
        active = {}
        for name, value in global_limits.items():
            try:
                speed = int(float(value))
            except (TypeError, ValueError):
                continue
            if speed > 0:
                active[str(name)] = speed
        if active:
            global_display = ", ".join(
                f"{name} {speed} KiB/s" for name, speed in sorted(active.items()))
    sites_display = "未配置"
    if isinstance(site_rules, dict):
        active_sites = []
        for name, rule in site_rules.items():
            if not isinstance(rule, dict):
                continue
            try:
                limit = int(rule.get("limit_kib") or 0)
            except (TypeError, ValueError):
                limit = 0
            if limit > 0:
                active_sites.append(name)
        sites_display = ", ".join(sorted(active_sites)) if active_sites else "未配置"
    return [
        _field("mode", "运行模式", mode_label, "gated_enabled",
               "运行时门控 upload_limit_enabled + 配置完整性", badge=True),
        _field("downloaders", "下载器范围",
               _list_display(_cfg(config, defaults, "upload_limit_downloaders", [])),
               "config_value", "配置键 upload_limit_downloaders"),
        _field("global", "全局限速", global_display, "config_value",
               "配置键 upload_limit_downloader_limits_kib"),
        _field("sites", "站点限速", sites_display, "config_value",
               "配置键 upload_limit_site_rules"),
        _field("dynamic", "动态调速", "按站点池自动分配（固有）", "static",
               "固有行为（动态额度分配）"),
        _field("interval", "调整周期", "后台自动协调（固有）", "static",
               "固有行为（后台 worker 协调，非配置项）"),
    ]


# ── 模块级 scope/schedule/protection ──────────────────────────────────────

def _scope_view(value: str, source: str) -> dict:
    return {"value": value, "source": source}


def _schedule_view(value: str, source: str) -> dict:
    return {"value": value, "source": source}


def _protection_view(enabled, value: str, source: str) -> dict:
    return {"enabled": enabled, "value": value, "source": source}


def build_module_config_summary(plugin: Any) -> dict:
    """构造七个模块的只读配置摘要。"""
    config = _config(plugin)
    defaults = _defaults()
    bare = _bare_switches(plugin, config)
    observe = _observe_flags(plugin)

    transfer_enabled = bool(getattr(plugin, "_transfer_enabled", False))
    rename_enabled = bool(getattr(plugin, "_rename_enabled", False))
    tag_enabled = bool(getattr(plugin, "_tag_enabled", False))
    hr_enabled = bool(getattr(plugin, "_hr_enabled", False))
    autoremove_enabled = bool(getattr(plugin, "_remover_enabled", False))
    failclean_enabled = bool(getattr(plugin, "_failcleanup_enabled", False))
    upload_enabled = bool(getattr(plugin, "_upload_limit_enabled", False))

    hr_service = getattr(plugin, "_hr_service", None)
    hr_runtime = _hr_runtime_config(hr_service)
    autoremove_status = _service_status(plugin, "_autoremove_service")
    failclean_status = _service_status(plugin, "_failclean_service")
    upload_status = _upload_limit_status(plugin)
    tag_config = getattr(plugin, "_site_tag_config", None)

    transfer_active = bool(getattr(plugin, "_transfer_active", False))
    upload_active = _upload_limit_active(plugin, upload_status)
    hr_guard_effective = _hr_guard_effective(hr_runtime)

    modules = {}

    modules["transfer"] = {
        "key": "transfer",
        "title": "转移做种",
        "enabled": transfer_enabled,
        "bare_switch": bool(bare.get("transfer")),
        "observe_only": bool(observe.get("transfer")),
        "active": transfer_active,
        "scope": _scope_view("按任务配置（源 → 目标下载器）", "配置键 transfer_tasks"),
        "schedule": _schedule_view(
            f"兜底每 {str(_cfg(config, defaults, 'transfer_fallback_interval_minutes', 60)).strip()} 分钟",
            "配置键 transfer_fallback_interval_minutes"),
        "protection": _protection_view(
            hr_guard_effective, _bool_display(hr_guard_effective),
            "H&R 保护闸门（转移删源跳过）"),
        "fields": _transfer_fields(config, defaults),
    }

    modules["rename"] = {
        "key": "rename",
        "title": "种子重命名",
        "enabled": rename_enabled,
        "bare_switch": bool(bare.get("rename")),
        "observe_only": bool(observe.get("rename")),
        "active": rename_enabled,
        "scope": _scope_view(
            _list_display(_cfg(config, defaults, "rename_downloaders", [])),
            "配置键 rename_downloaders"),
        "schedule": _schedule_view(
            str(_cfg(config, defaults, "rename_cron", "") or "").strip() or "未配置",
            "配置键 rename_cron（受 rename_cron_enabled 门控）"),
        "protection": _protection_view(None, "不适用（无删除动作）", "固有"),
        "fields": _rename_fields(config, defaults),
    }

    modules["hr"] = {
        "key": "hr",
        "title": "H&R 管理",
        "enabled": hr_enabled,
        "bare_switch": bool(bare.get("hr")),
        "observe_only": bool(observe.get("hr")),
        "active": hr_enabled,
        "scope": _scope_view(
            f"下载器 {_list_display(hr_runtime.get('downloaders'))} · "
            f"站点 {_list_display(hr_runtime.get('sites'))}",
            "配置键 hr_downloader + hr_sites"),
        "schedule": _schedule_view(
            f"每 {str(_cfg(config, defaults, 'hr_check_period', 10)).strip()} 分钟检查",
            "配置键 hr_check_period"),
        "protection": _protection_view(
            hr_guard_effective, _bool_display(hr_guard_effective),
            "配置键 hr_protection_enabled"),
        "fields": _hr_fields(config, defaults, hr_runtime),
    }

    modules["autoremove"] = {
        "key": "autoremove",
        "title": "自动删种",
        "enabled": autoremove_enabled,
        "bare_switch": bool(bare.get("autoremove")),
        "observe_only": bool(observe.get("autoremove") or autoremove_status.get("observe_only")),
        "active": autoremove_enabled,
        "scope": _scope_view(
            _list_display(_cfg(config, defaults, "remover_downloaders", [])),
            "配置键 remover_downloaders"),
        "schedule": _schedule_view(
            str(_cfg(config, defaults, "remover_cron", "") or "").strip(),
            "配置键 remover_cron"),
        "protection": _protection_view(
            bool(autoremove_status.get("guard_enabled")),
            _bool_display(autoremove_status.get("guard_enabled")),
            "H&R 保护闸门（自动删种路径）"),
        "fields": _autoremove_fields(
            config, defaults, autoremove_status, autoremove_enabled,
            bool(observe.get("autoremove") or autoremove_status.get("observe_only"))),
    }

    modules["failclean"] = {
        "key": "failclean",
        "title": "失败清理",
        "enabled": failclean_enabled,
        "bare_switch": bool(bare.get("failclean")),
        "observe_only": bool(observe.get("failclean")),
        "active": failclean_enabled,
        "scope": _scope_view("本地下载目录", "固有行为"),
        "schedule": _schedule_view(
            str(_cfg(config, defaults, "failcleanup_cron", "") or "").strip(),
            "配置键 failcleanup_cron"),
        "protection": _protection_view(
            hr_guard_effective,
            f"跳过 {sum(int(v or 0) for v in (failclean_status.get('skip_stats') or {}).values())} 次",
            "H&R 保护闸门（整理失败删源路径）"),
        "fields": _failclean_fields(config, defaults),
    }

    modules["tag"] = {
        "key": "tag",
        "title": "站点标签",
        "enabled": tag_enabled,
        "bare_switch": bool(bare.get("tag")),
        "observe_only": bool(observe.get("tag")),
        "active": tag_enabled,
        "scope": _scope_view(
            _list_display((tag_config or {}).get("downloaders", [])),
            "配置键 tag_downloaders"),
        "schedule": _schedule_view(
            str((tag_config or {}).get("interval_cron") or "").strip(),
            "配置键 tag_interval_cron"),
        "protection": _protection_view(None, "不适用（无删除动作）", "固有"),
        "fields": _tag_fields(config, defaults, tag_config, tag_enabled),
    }

    modules["upload_limit"] = {
        "key": "upload_limit",
        "title": "上传限速",
        "enabled": upload_enabled,
        "bare_switch": bool(bare.get("upload_limit")),
        "observe_only": bool(observe.get("upload_limit") or upload_status.get("observe_only")),
        "active": upload_active,
        "scope": _scope_view(
            _list_display(_cfg(config, defaults, "upload_limit_downloaders", [])),
            "配置键 upload_limit_downloaders"),
        "schedule": _schedule_view("后台自动协调（固有）", "固有行为（非配置项）"),
        "protection": _protection_view(
            None,
            f"受保护种子 {int(upload_status.get('protected_torrents') or 0)} 个",
            "上传限速受保护种子（额度为 0 的任务）"),
        "fields": _upload_limit_fields(config, defaults, upload_status),
    }

    return {"code": 0, "modules": modules}


__all__ = ("build_module_config_summary",)
