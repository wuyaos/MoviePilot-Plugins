"""稳定配置键与执行键。

配置键必须是顶层扁平字符串，供 MoviePilot Vuetify 表单双向绑定。
``Task.name`` 是持久化契约；发布后禁止随意改名。
"""
import re


def _clean(value) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "")).strip("_").lower()


def site_identity(site) -> str:
    """优先使用 MP 站点真实 id，缺失时退回域名。"""
    return _clean(getattr(site, "site_id", "") or getattr(site, "domain", "") or "site")


def site_task_key(site, task_name: str) -> str:
    return f"task_{site_identity(site)}_{_clean(task_name)}"
