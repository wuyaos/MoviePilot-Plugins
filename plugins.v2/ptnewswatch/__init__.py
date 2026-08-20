"""PTNewsWatch：PT 论坛、RSS 与 Atom 动态汇总。"""
from __future__ import annotations

import threading
from typing import Any

from apscheduler.triggers.cron import CronTrigger

from app import schemas
from app.core.config import settings
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import NotificationType

from .core.config import PluginConfig
from .core.engine import DigestEngine
from .core.source_instances import validate_source_config
from .core.source_registry import SOURCE_BY_ID
from .ui.form import build_form
from .ui.page import build_page


class PTNewsWatch(_PluginBase):
    plugin_name = "PT 资讯动态监控"
    plugin_desc = "汇总 PT 论坛主题、RSS 与 Atom 新消息"
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/signin.png"
    plugin_version = "0.2.0"
    plugin_author = "wuyaos"
    author_url = "https://github.com/wuyaos"
    plugin_config_prefix = "ptnewswatch_"
    plugin_order = 37
    auth_level = 2

    _run_lock = threading.Lock()

    def __init__(self):
        super().__init__()
        self.config = PluginConfig()
        self._pending_config: dict | None = None
        self._config_error = ""

    def init_plugin(self, config: dict | None = None):
        raw_config = config or {}
        self.config = PluginConfig.from_dict(raw_config)
        try:
            validate_source_config(self.config)
            self._config_error = ""
        except ValueError as error:
            self._config_error = str(error)
            logger.error("PTNewsWatch 配置错误：%s", self._config_error)
        manual_requested = self.config.onlyonce
        remove_legacy_first_run = "first_run_push_recent" in raw_config
        if manual_requested or remove_legacy_first_run:
            self.config.onlyonce = False
            # 完整回写已知字段，移除不再使用的首次运行开关且不覆盖其它配置。
            self.update_config(self.config.to_dict())
            if manual_requested and not self._config_error:
                self._start_run("")

    def get_state(self) -> bool:
        return self.config.enabled

    @staticmethod
    def get_command() -> list[dict]:
        return []

    def get_api(self) -> list[dict]:
        return [
            {
                "path": "/run",
                "endpoint": self.api_run,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "立即检查全部 PT 资讯来源",
            },
            {
                "path": "/source/{source_id}/run",
                "endpoint": self.api_source_run,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "立即检查指定 PT 资讯来源",
            },
            {
                "path": "/status",
                "endpoint": self.api_status,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取 PTNewsWatch 状态",
            },
        ]

    def api_run(self) -> schemas.Response:
        started = self._start_run("")
        return schemas.Response(success=started, message="任务已启动" if started else "已有任务运行中")

    def api_source_run(self, source_id: str) -> schemas.Response:
        if source_id not in SOURCE_BY_ID:
            return schemas.Response(success=False, message="来源不存在")
        started = self._start_run(source_id)
        return schemas.Response(success=started, message="任务已启动" if started else "已有任务运行中")

    def api_status(self) -> schemas.Response:
        state = self.get_data("state") or {}
        return schemas.Response(success=True, data={
            "enabled": self.config.enabled,
            "cron": self.config.cron,
            "sources": state.get("sources") or {},
            "last_run": state.get("last_run") or {},
            "recent_count": len(state.get("recent_entries") or []),
        })

    def get_service(self) -> list[dict]:
        if not self.config.enabled or not self.config.cron or self._config_error:
            return []
        try:
            trigger = CronTrigger.from_crontab(self.config.cron, timezone=settings.TZ)
        except Exception as error:
            logger.error("PTNewsWatch Cron 无效：%r，%s", self.config.cron, error)
            return []
        return [{
            "id": "PTNewsWatch",
            "name": "PT 资讯动态监控",
            "trigger": trigger,
            "func": self.run_scheduled,
            "kwargs": {},
        }]

    def run_scheduled(self):
        return self.run_once("")

    def _start_run(self, source_filter: str) -> bool:
        if self._config_error or type(self)._run_lock.locked():
            return False
        threading.Thread(
            target=self.run_once,
            kwargs={"source_filter": source_filter},
            daemon=True,
            name="ptnewswatch_run",
        ).start()
        return True

    def run_once(self, source_filter: str = ""):
        if not type(self)._run_lock.acquire(blocking=False):
            logger.info("PTNewsWatch 已有任务运行中，跳过")
            return None
        self._pending_config = None
        try:
            engine = DigestEngine(
                config=self.config,
                state=self.get_data("state") or {},
                save_state=lambda state: self.save_data("state", state),
                save_config=self._stage_config,
                notify=self._notify,
            )
            return engine.run(source_filter)
        finally:
            type(self)._run_lock.release()
            self._flush_pending_config()

    def _stage_config(self, config: PluginConfig):
        self.config = config
        self._pending_config = config.to_dict()

    def _flush_pending_config(self):
        pending = self._pending_config
        self._pending_config = None
        if pending:
            self.update_config(pending)

    def _notify(self, title: str, text: str):
        self.post_message(mtype=NotificationType.Plugin, title=title, text=text)

    def get_form(self) -> tuple[list[dict], dict[str, Any]]:
        return build_form(self.config, self._config_error)

    def get_page(self) -> list[dict]:
        try:
            return build_page(self.get_data("state") or {}, settings.TZ, config=self.config)
        except Exception as error:
            logger.error("PTNewsWatch 数据页构建失败：%s", error)
            return [{"component": "VAlert", "props": {
                "type": "error", "variant": "tonal",
                "text": f"数据页构建失败：{error}",
            }}]

    def stop_service(self):
        return None
