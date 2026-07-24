"""站点自动任务插件入口。

入口只负责 MoviePilot 生命周期与模块委托；执行、调度、历史、UI 分别位于 core/ 与 ui/。
"""
from typing import Any, Dict, List, Optional, Tuple

from app.plugins import _PluginBase
from app.db.site_oper import SiteOper
from app.schemas import NotificationType

from .core.config import PluginConfig
from .core.engine import TaskEngine
from .core.history import HistoryStore
from .core.scheduler import TaskScheduler
from .sites import load_site_classes
from .ui.form import build_form
from .ui.page import build_page


class SiteAutoTask(_PluginBase):
    plugin_name = "站点自动任务"
    plugin_desc = "站点周期任务合集：签到、喊话、领勋章、抽奖、兑换、任务申领，并解析喊话反馈奖励。"
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/ptautotask.png"
    plugin_version = "1.0.0"
    plugin_author = "wuyaos"
    author_url = "https://github.com/wuyaos"
    plugin_config_prefix = "siteautotask_"
    plugin_order = 24
    auth_level = 2

    def __init__(self):
        super().__init__()
        self.config = PluginConfig()
        self.siteoper = None
        self._site_classes = []
        self.handler_classes = []
        self.engine = None
        self.history = HistoryStore(self)
        self.scheduler = TaskScheduler(self)
        self.notification_type = NotificationType.SiteMessage

    def init_plugin(self, config: Optional[dict] = None):
        self.stop_service()
        self.siteoper = SiteOper()
        self.config = PluginConfig.from_dict(config)
        if not self._site_classes:
            self._site_classes = load_site_classes()
            self.handler_classes = [x["handler_cls"] for x in self._site_classes if x.get("handler_cls")]
        self.engine = TaskEngine(self)
        if config is not None:
            self.update_config(self.config.to_dict())
        if self.config.enabled or self.config.onlyonce:
            self.scheduler.start()
            if self.config.onlyonce:
                self.config.onlyonce = False
                self.update_config(self.config.to_dict())

    def get_state(self) -> bool:
        return self.config.enabled

    def run_once(self):
        return self.engine.run() if self.engine else []

    def all_sites(self):
        sites = []
        try:
            sites.extend(s for s in self.siteoper.list_order_by_pri() if not getattr(s, "public", False))
        except Exception:
            pass
        custom = self.get_config("CustomSites") or {}
        if custom.get("enabled"):
            sites.extend(custom.get("sites") or [])
        return [self._site_to_dict(s) for s in sites]

    @staticmethod
    def _site_to_dict(site):
        if isinstance(site, dict):
            return dict(site)
        return {
            "id": getattr(site, "id", None), "name": getattr(site, "name", ""),
            "url": getattr(site, "url", ""), "cookie": getattr(site, "cookie", ""),
            "ua": getattr(site, "ua", ""), "render": getattr(site, "render", False),
            "domain": getattr(site, "domain", ""),
        }

    def selected_sites(self):
        """按 MP 站点真实 id 选择站点，并兼容旧配置中的域名值。"""
        selected = {str(value) for value in self.config.chat_sites}
        result = []
        for site in self.all_sites():
            site_id = site.get("id")
            domain = site.get("domain") or ""
            if str(site_id) in selected or domain in selected:
                result.append(site)
        return result

    def tasks_for(self, handler):
        entry = next((x for x in self._site_classes if x.get("handler_cls") is type(handler)), None)
        if not entry or not entry.get("tasks_cls"):
            return []
        tasks = entry["tasks_cls"](cookie=None)
        tasks.client = handler
        return tasks.get_registered_tasks()

    def support_site_options(self):
        """返回配置页站点选项，id 必须使用 MP 站点真实 id。"""
        options = []
        for site in self.all_sites():
            domain = site.get("domain") or ""
            entry = next((item for item in self._site_classes
                          if item.get("domain") == domain or
                          item.get("site_name") == site.get("name")), None)
            if not entry:
                continue
            tasks = [{k: v for k, v in task.items() if k != "func"}
                     for task in entry.get("tasks_meta", [])]
            options.append({
                "id": site.get("id"),
                "name": site.get("name") or entry.get("site_name") or domain,
                "domain": domain,
                "tasks": tasks,
            })
        return options

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return build_form(self)

    def get_page(self) -> List[dict]:
        return build_page(self)

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        return []

    def get_service(self):
        return self.scheduler.services()

    def stop_service(self):
        if hasattr(self, "scheduler") and self.scheduler:
            self.scheduler.stop()
