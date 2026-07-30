"""SiteAutoTask 配置到 PtTaskFlow 的确定性迁移。

只迁移可证明的站点/控件值；不确定的下拉选项保持关闭。
"""
from .models import ControlKind


SPECIAL_SWITCHES = {
    ("qingwapt.com", "daily_exchange"): "qingwa_daily_bonus",
    ("longpt.org", "daily_lottery"): "longpt_daily_lottery",
    ("13city.org", "buy_blessing"): "thirteencity_auto_buy_blessing",
}


def _sites(value):
    if isinstance(value, dict):
        return value.get("data") or value.get("items") or []
    return value or []


def migrate_siteautotask_config(legacy, remote_sites, local_sites, site_classes):
    remote_sites = _sites(remote_sites); local_sites = _sites(local_sites)
    remote_domain = {str(site.get("id")): (site.get("domain") or "").lower() for site in remote_sites}
    local_by_domain = {(site.get("domain") or "").lower(): dict(site) for site in local_sites}
    selected = [str(value) for value in (legacy.get("chat_sites") or legacy.get("site_ids") or [])]
    output = {}
    for old, new in {
        "enabled": "enabled", "cron": "cron", "notify": "notify", "use_proxy": "use_proxy",
        "get_feedback": "get_feedback", "feedback_timeout": "feedback_timeout",
        "interval_cnt": "interval", "interval": "interval", "retry_count": "retry_count",
        "retry_interval": "retry_interval", "retry_notify": "retry_notify",
        "history_days": "history_days", "zm_cooldown": "zm_cooldown",
        "zm_mail_time": "zm_mail_time", "last_zm_execution_time": "last_zm_execution_time",
    }.items():
        if old in legacy and new not in output:
            output[new] = legacy[old]
    class_by_domain = {cls.domain.lower(): cls for cls in site_classes}
    for cls in site_classes:
        for alias in getattr(cls, "domain_aliases", ()):
            class_by_domain[str(alias).lower()] = cls
    mapped = []
    summary = {"mapped_sites": [], "skipped_sites": [], "migrated_controls": [], "skipped_controls": []}
    for remote_id in selected:
        domain = remote_domain.get(remote_id, "")
        local = local_by_domain.get(domain)
        site_cls = class_by_domain.get(domain)
        if not site_cls:
            site_cls = next((cls for cls in site_classes if cls.matches({"name": "", "domain": domain})), None)
        if not local or not site_cls:
            summary["skipped_sites"].append(domain or remote_id)
            continue
        local_id = str(local.get("id")); mapped.append(local_id)
        summary["mapped_sites"].append(domain)
        instance = site_cls(local)
        for task in instance.tasks:
            control = task.controls(instance)[0]
            old_task_key = f"task_{remote_id}_{task.name}"
            target = control.key
            value = None
            if control.kind == ControlKind.SWITCH:
                if old_task_key in legacy:
                    value = bool(legacy[old_task_key])
                special = SPECIAL_SWITCHES.get((domain, task.name))
                if special in legacy:
                    value = bool(legacy[special])
            elif control.kind == ControlKind.SELECT_ONE:
                candidate = legacy.get(f"claim_{remote_id}_{task.name}", legacy.get(old_task_key))
                if task.name == "claim":
                    candidate = legacy.get(f"claim_{remote_id}_claim",
                                           legacy.get(f"claim_{remote_id}", candidate))
                if domain == "longpt.org" and task.name == "daily_shotbox":
                    messages = str(legacy.get("sites_messages") or "")
                    source = str(candidate or messages)
                    candidate = "upload" if "求上传" in source else (
                        "bonus" if "求魔力" in source else candidate)
                valid = {str(item.get("id")) for item in control.options}
                if candidate not in (True, False, None, "") and str(candidate) in valid:
                    value = str(candidate)
            elif control.kind == ControlKind.SELECT_MANY:
                candidate = legacy.get(f"claim_{remote_id}_{task.name}", legacy.get(old_task_key))
                if not isinstance(candidate, (list, tuple, set)):
                    candidate = legacy.get(f"medal_{remote_id}") or legacy.get(f"medals_{remote_id}") or []
                valid = {str(item.get("id")) for item in control.options}
                value = [str(item) for item in candidate if str(item) in valid]
            if value not in (None, "", []):
                output[target] = value
                summary["migrated_controls"].append(target)
            elif legacy.get(old_task_key):
                summary["skipped_controls"].append(old_task_key)
    output["site_ids"] = mapped
    return output, summary
