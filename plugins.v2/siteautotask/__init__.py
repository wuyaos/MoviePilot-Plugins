"""站点自动任务插件入口。

入口只负责 MoviePilot 生命周期与模块委托；执行、调度、历史、UI 分别位于 core/ 与 ui/。
"""
import threading
from typing import Any, Dict, List, Optional, Tuple

from app.plugins import _PluginBase
from app.db.site_oper import SiteOper
from app.log import logger
from app.schemas import NotificationType
from app.core.event import Event, eventmanager
from app.schemas.types import EventType

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
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/siteautotask.png"
    plugin_version = "1.0.2"
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
        self.retry_records = []
        self.retry_attempt = 0
        self._raw_config: dict = {}

    def init_plugin(self, config: Optional[dict] = None):
        self.stop_service()
        self.siteoper = SiteOper()
        self.config = PluginConfig.from_dict(config)
        self._raw_config = dict(config or {})
        # 兼容旧 task_switches 字典配置，迁移为扁平 key（补 task_ 前缀）
        legacy = self._raw_config.pop("task_switches", None)
        if isinstance(legacy, dict):
            for key, value in legacy.items():
                new_key = key if str(key).startswith("task_") else f"task_{key}"
                self._raw_config.setdefault(new_key, value)
        if not self._site_classes:
            self._site_classes = load_site_classes()
            self.handler_classes = [x["handler_cls"] for x in self._site_classes if x.get("handler_cls")]
        self.engine = TaskEngine(self)
        if config is not None:
            self.update_config(self._raw_config)
        if self.config.enabled or self.config.onlyonce:
            self.scheduler.start()
            if self.config.onlyonce:
                self.config.onlyonce = False
                self._raw_config["onlyonce"] = False
                self.update_config(self._raw_config)

    def task_enabled(self, task_key: str) -> bool:
        """读取任务开关（扁平顶层配置 key）。"""
        return bool(self._raw_config.get(task_key, False))

    def get_state(self) -> bool:
        return self.config.enabled

    def run_once(self):
        return self.engine.run() if self.engine else []

    def run_retry(self):
        return self.engine.retry_failed() if self.engine else []

    def run_debug(self, site_filter=None, task_filter=None):
        """调试执行：绕过配置开关，按站点/任务过滤器直接执行。"""
        return self.engine.run_debug(site_filter, task_filter) if self.engine else []

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
            # 未有专用适配的站点不展示任务；NexusPHP 仅作为能力组合，不提供通用任务。
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
        return [
            {
                "cmd": "/siteautotask_run",
                "event": EventType.PluginAction,
                "desc": "立即执行站点自动任务",
                "category": "站点",
                "data": {"action": "siteautotask_run"},
            }
        ]

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/run",
                "endpoint": self.api_run,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "执行站点任务（可指定站点和任务用于调试）",
                "description": (
                    "site_id 指定站点(id 或域名)，task_name 指定任务名(模糊匹配)；"
                    "都不传则按配置全量后台执行。调试指定站点/任务时同步返回执行记录。"
                ),
            }
        ]

    def api_run(self, site_id: str = "", task_name: str = "") -> Dict[str, Any]:
        """立即执行任务。

        - site_id 和 task_name 都为空：按配置全量后台执行（避免 API 超时）。
        - 指定 site_id：调试执行该站点全部任务，同步返回记录。
        - 指定 site_id + task_name：调试执行该站点匹配任务，同步返回记录。
        """
        if not self.engine:
            return {"success": False, "message": "插件未初始化"}
        if not site_id and not task_name:
            threading.Thread(target=self.run_once, daemon=True).start()
            return {"success": True, "message": "已后台启动全量任务，结果写入历史记录"}
        logger.info(f"调试执行请求：site_id={site_id!r}，task_name={task_name!r}")
        records = self.run_debug(site_filter=site_id or None, task_filter=task_name or None)
        return {
            "success": True,
            "message": f"执行完成，共 {len(records)} 个任务",
            "records": records,
        }

    @eventmanager.register(EventType.PluginAction)
    def run_command(self, event: Event = None):
        event_data = event.event_data if event else {}
        if not event_data or event_data.get("action") != "siteautotask_run":
            return
        channel = event_data.get("channel")
        userid = event_data.get("user")
        if not self.config.enabled:
            logger.warning("命令执行请求被忽略：插件未启用")
            self.post_message(
                channel=channel, userid=userid, mtype=self.notification_type,
                title="【站点自动任务】", text="插件未启用，无法执行任务。",
            )
            return
        threading.Thread(target=self.run_once, daemon=True).start()
        self.post_message(
            channel=channel, userid=userid, mtype=self.notification_type,
            title="【站点自动任务】", text="已后台启动任务执行，完成后按配置发送通知。",
        )

    def get_service(self):
        return self.scheduler.services()

    def stop_service(self):
        if hasattr(self, "scheduler") and self.scheduler:
            self.scheduler.stop()
