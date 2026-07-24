"""站点任务唯一键。"""
import re


def site_task_key(site, task):
    """生成按站点隔离的任务键，避免通用 Handler 的任务开关串站。"""
    domain = site.get("domain") if isinstance(site, dict) else getattr(site, "domain", "")
    site_id = site.get("id") if isinstance(site, dict) else getattr(site, "id", "")
    identity = str(site_id or domain or "site")
    identity = re.sub(r"[^A-Za-z0-9_-]+", "_", identity).strip("_").lower() or "site"
    return f"{identity}_{task.get('name') or task.get('id', 'task').split('_')[-1]}"
