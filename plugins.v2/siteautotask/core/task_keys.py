"""站点任务唯一键，同时作为插件配置的扁平 key。

注意：此 key 必须是顶层扁平字符串（如 ``task_7_daily_checkin``），
不能使用点号嵌套（如 ``task_switches.xxx``），否则 MoviePilot 前端表单
无法正确双向绑定，会导致配置保存失效。
"""
import re


def _identity(site):
    domain = site.get("domain") if isinstance(site, dict) else getattr(site, "domain", "")
    site_id = site.get("id") if isinstance(site, dict) else getattr(site, "id", "")
    identity = str(site_id or domain or "site")
    return re.sub(r"[^A-Za-z0-9_-]+", "_", identity).strip("_").lower() or "site"


def _task_name(task):
    name = task.get("name") or task.get("id", "task").split("_")[-1]
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(name)).strip("_").lower()


def site_task_key(site, task):
    """生成按站点隔离的任务键，同时作为顶层配置 key。

    格式：``task_{site_id}_{task_name}``，例如 ``task_7_daily_checkin``。
    加 ``task_`` 前缀避免与 enabled/cron 等内置字段冲突，也避免纯数字开头。
    """
    return f"task_{_identity(site)}_{_task_name(task)}"


def claim_task_key(site, task):
    """CLAIM 任务配置的 task_id 键。格式：``claim_{site_id}_{task_name}``。

    与 site_task_key 区分：task_ 前缀存布尔开关，claim_ 前缀存用户选择的 task_id。
    """
    return f"claim_{_identity(site)}_{_task_name(task)}"
