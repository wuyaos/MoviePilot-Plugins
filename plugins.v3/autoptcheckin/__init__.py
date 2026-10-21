# -*- coding: utf-8 -*-
"""PT 签到中心 V3：HDSky / 海棠试点执行与回读。"""
import json
import asyncio
from datetime import datetime
from dataclasses import asdict
from .core.scheduler import Scheduler
from .core.runner import SignRunner
from .core.models import SignResult, SignStatus
from .core.pilot import PILOTS, PilotBridge, managed_site, site_id_for_domain
from pathlib import Path
from copy import deepcopy
from .core.history import HistoryStore
from .core.migration import Migration, MigrationError
from .core.registry import get_registry, get_native_module
from .core.native import run_native
from typing import Any

try:
    from app.sdk.plugin import _PluginBase
except ImportError:  # 离线契约测试无宿主
    class _PluginBase:
        pass


class AutoPtCheckin(_PluginBase):
    plugin_id = "AutoPtCheckin"
    plugin_name = "PT 签到中心"
    plugin_desc = "PT 站点自动签到与模拟登录"
    plugin_version = "3.8.5"
    plugin_author = "wuyaos"
    plugin_config_prefix = "autoptcheckin_"

    SITE_KEYS = ("enabled_sites", "sign_sites", "login_sites", "custom_sites_data",
                 "rousi_username", "rousi_password", "sunnypt_username",
                 "sunnypt_password", "sunnypt_token")

    def __init__(self):
        super().__init__()
        self._scheduler = None
        self._migration = Migration(self)
        self._running = False
        self._bound_uids = {}
        self._config: dict[str, Any] = {}
        self._site_config: dict[str, Any] = {}
        self._runner = SignRunner(history=self._record_result)
        self._history = HistoryStore(getattr(self, "get_data", None), getattr(self, "save_data", None))

    def init_plugin(self, config: dict | None = None) -> None:
        with self._migration.lock:
            self._init_config(config)

    def _init_config(self, config: dict | None = None) -> None:
        self.stop_service()
        self._runner.stop.clear()
        self._config = deepcopy(config or {})
        self._running = bool(self._config.get("enabled", False))
        if hasattr(self, "get_data"):
            self._site_config = self.get_data("site_config") or {}
            self._bound_uids = self.get_data("identity.bindings") or {}
        self._site_config.update({key: deepcopy(self._config[key]) for key in self.SITE_KEYS if key in self._config})
        self._config.update(deepcopy(self._site_config))
        if hasattr(self, "save_data"):
            self.save_data("site_config", deepcopy(self._site_config))

        try:
            from app.sdk.config import settings
            timezone = settings.TZ
        except ImportError:
            timezone = None
        self._scheduler = Scheduler(getattr(self, "get_data", None), getattr(self, "save_data", None), timezone)

    def get_state(self) -> bool:
        return self._running or (not self._runner.stop.is_set() and bool(self._config.get("scheduler_enabled", False)) and bool(self._config.get("onlyonce", False)))

    def get_service(self) -> list:
        if self._scheduler is None or self._runner.stop.is_set():
            return []
        if self._scheduler.services:
            return list(self._scheduler.services)
        callback = self._scheduled_once if self._config.get("onlyonce") else self._scheduled_signin
        return self._scheduler.build(self._config, callback)

    def get_render_mode(self) -> tuple[str, str]:
        return "vue", "dist/assets"

    def get_form(self):
        defaults = json.loads((Path(__file__).parent / "config_defaults.json").read_text(encoding="utf-8"))
        return None, defaults

    def get_page(self):
        return None

    def get_api(self) -> list[dict[str, Any]]:
        routes = [
            {"path": "/migrate/preview", "endpoint": self.api_migrate_preview, "methods": ["GET"]},
            {"path": "/migrate/execute", "endpoint": self.api_migrate_execute, "methods": ["POST"]},
            {"path": "/manual_signin", "endpoint": self.api_manual_signin, "methods": ["POST"]},
            {"path": "/run_once", "endpoint": self.api_run_once, "methods": ["POST"]},
            {"path": "/clean_today", "endpoint": self.api_clean_today, "methods": ["POST"]},
            {"path": "/verify_site", "endpoint": self.api_verify_site, "methods": ["POST"]},
            {"path": "/status", "endpoint": self.api_status, "methods": ["GET"]},
            {"path": "/sites", "endpoint": self.api_sites, "methods": ["GET"]},
            {"path": "/login_by_domain", "endpoint": self.api_login_by_domain, "methods": ["POST"]},
            {"path": "/signin_by_domain", "endpoint": self.api_signin_by_domain, "methods": ["POST"]},
            {"path": "/config", "endpoint": self.api_config, "methods": ["GET"]},
            {"path": "/config", "endpoint": self.api_save_config, "methods": ["PUT"]},
            {"path": "/site_config", "endpoint": self.api_site_config, "methods": ["GET"]},
            {"path": "/site_config", "endpoint": self.api_save_site_config, "methods": ["PUT"]},
            {"path": "/stats", "endpoint": self.api_stats, "methods": ["GET"]},
            {"path": "/history", "endpoint": self.api_history, "methods": ["GET"]},
        ]

        for route in routes:
            route["auth"] = "bear"
        return routes

    async def api_migrate_preview(self) -> dict:
        try:
            data = await asyncio.to_thread(self._migration.preview)
            return {"success": True, "message": "", "data": data}
        except Exception:
            return {"success": False, "message": "migration_preview_failed", "data": None}

    async def api_migrate_execute(self, body: dict) -> dict:
        try:
            data = await asyncio.to_thread(self._migration.execute, body.get("confirm"), body.get("overwrite_conflicts", False))
            return {"success": True, "message": "", "data": data}
        except MigrationError as exc:
            return {"success": False, "message": str(exc), "data": None}
        except Exception:
            return {"success": False, "message": "migration_execute_failed", "data": None}

    async def api_status(self) -> dict:
        return {"success": True, "data": {"state": "running" if self._running else "stopped",
                "version": self.plugin_version, "current_stage": "pilot", "today": self._history.today_counts(), "next_schedule": self._next_schedule()}}

    async def api_config(self) -> dict:
        """仅经宿主认证 API 读取配置；不写日志或回显至统计。"""
        return {"success": True, "data": deepcopy(self._config)}

    async def api_save_config(self, config: dict) -> dict:
        """与宿主保存使用同一配置存储；Vue 视图优先 emit save。"""
        await asyncio.to_thread(self._save_config, config)
        return {"success": True, "data": None}

    def _save_config(self, config: dict) -> None:
        with self._migration.lock:
            self.update_config(config)
            self.init_plugin(config)
            try:
                from app.sdk.scheduler import update_plugin_job
            except ImportError:
                return
            update_plugin_job(self.plugin_id)

    async def api_site_config(self) -> dict:
        return {"success": True, "data": deepcopy(self._site_config)}

    async def api_save_site_config(self, config: dict) -> dict:
        """保存站点级动作与凭据；阶段1不发送站点请求。"""
        if set(config) - set(self.SITE_KEYS):
            return {"success": False, "message": "未知站点配置字段", "data": None}
        return await self.api_save_config({**self._config, **deepcopy(config)})

    async def api_sites(self) -> dict:
        registry = get_registry(self._config.get('custom_sites_data', []))
        return {"success": True, "data": {"sites": deepcopy(registry["sites"]), "sources": deepcopy(registry["sources"])}}

    async def api_stats(self) -> dict:
        mode = self._config.get("cron_mode", "interval")
        schedule = {"mode": mode}
        if mode == "cron":
            schedule["cron"] = self._config.get("cron", "")
        else:
            schedule.update({"interval_hours": self._config.get("interval_hours", 2),
                             "begin_hour": self._config.get("begin_hour", 9),
                             "end_hour": self._config.get("end_hour", 23)})
        return {"success": True, "data": {"today": self._history.today_counts(),
                "next_schedule": self._next_schedule(), "schedule_status": self._schedule_status(), "schedule": schedule, "sites": self._site_results()}}

    async def api_history(self, page: int = 1, size: int = 20) -> dict:
        return {"success": True, "data": self._history.list(page, size)}

    def _record_result(self, result):
        self._history.append(result)
        if result.account and result.site_id not in self._bound_uids:
            self._bound_uids[result.site_id] = result.account
            if hasattr(self, "save_data"):
                self.save_data("identity.bindings", dict(self._bound_uids))

    def _site_results(self):
        latest = {}
        for item in self._history.list(1, 100)['items']:
            if item.get('action', 'sign') == 'sign':
                latest.setdefault(item['site'], item)
        enabled = self._config.get('enabled_sites', [])
        rows = []
        for site in get_registry(self._config.get('custom_sites_data', []))['sites']:
            sid = site['id']
            if sid not in enabled and sid not in latest:
                continue
            record = latest.get(sid, {})
            active = sid in enabled
            rows.append({**site, **record, 'id': sid,
                'status': record.get('status', 'unconfirmed') if active else 'disabled',
                'uid': record.get('evidence', {}).get('uid', ''),
                'sign_selected': sid in self._config.get('sign_sites', []),
                'login_selected': sid in self._config.get('login_sites', []),
                'can_login': active and sid in self._config.get('login_sites', []) and site.get('pilot_enabled', False) and site.get('login_capable', False),
                'can_signin': active and sid in self._config.get('sign_sites', []) and site.get('pilot_enabled', False),
                'can_verify': active and site.get('pilot_enabled', False)})
        return rows

    def _execute_site(self, site_id, read_only=False, trigger="manual", action="sign"):
        registry = {site['id']: site for site in get_registry(self._config.get('custom_sites_data', []))['sites']}
        reason = None
        site = registry.get(site_id, {})
        if action == 'sign' and site_id in ('darkland', 'digitalcore'):
            reason = 'signin_not_applicable'
        elif site.get('native') and not site.get('verified'):
            reason = 'native_unverified'
        elif site.get('native') and not site.get('hook_implemented', True):
            reason = 'hook_not_implemented'
        elif not site.get('native') and site_id not in PILOTS:
            reason = 'pilot_not_enabled'
        elif action == 'login' and site_id not in PILOTS:
            reason = 'pilot_not_enabled'
        elif site_id not in self._config.get('enabled_sites', []):
            reason = 'site_disabled'
        elif action == 'login' and not registry.get(site_id, {}).get('login_capable'):
            reason = 'login_not_supported'
        elif action == 'login' and site_id not in self._config.get('login_sites', []):
            reason = 'login_not_selected'
        elif action == 'sign' and not registry.get(site_id, {}).get('signin_capable'):
            reason = 'signin_not_supported'
        elif action == 'sign' and not read_only and site_id not in self._config.get('sign_sites', []):
            reason = 'signin_not_selected'
        if reason:
            result = SignResult.skipped(reason)
            result.site_id = site_id
            result.metadata['reason'] = reason
            result.metadata["trigger"] = trigger
            result.metadata["action"] = action
            self._record_result(result)
            return asdict(result)
        try:
            info = managed_site(site_id)
        except Exception:
            result = SignResult(SignStatus.UNCONFIRMED, '读取宿主站点配置失败', site_id=site_id)
            result.metadata["trigger"] = trigger
            result.metadata["action"] = action
            self._record_result(result)
            return asdict(result)
        info["uid"] = self._bound_uids.get(site_id, "")
        if site.get('native') and action == 'sign':
            result = run_native(self._runner, get_native_module(site_id), info,
                                read_only=read_only, trigger=trigger,
                                get_data=getattr(self, "get_data", None), save_data=getattr(self, "save_data", None))
            return asdict(result)
        bridge = PilotBridge(site_id, info)
        if action == 'login':
            result = self._runner.run_login(site_id, str(info.get('uid') or ''),
                resolve=bridge.resolve, fetch_page=bridge.fetch_login_page, verifier=bridge.verifier, trigger=trigger)
            return asdict(result)
        result = self._runner.run(site_id, str(info.get('uid') or ''), datetime.now().astimezone().date().isoformat(),
            resolve=bridge.resolve, fetch_page=bridge.fetch_page, verifier=bridge.verifier,
            submit=bridge.submit, read_only=read_only, allow_page_identity=True, trigger=trigger)
        return asdict(result)

    async def api_signin_by_domain(self, domain: str = '') -> dict:
        site_id = site_id_for_domain(domain)
        if not site_id:
            return {'success': False, 'message': 'pilot_not_enabled：仅开放 HDSky、海棠', 'data': None}
        result = await asyncio.to_thread(self._execute_site, site_id)
        return {'success': True, 'data': result}

    async def api_login_by_domain(self, domain: str = '') -> dict:
        site_id = site_id_for_domain(domain)
        if not site_id:
            return {'success': False, 'message': 'pilot_not_enabled：仅开放 HDSky、海棠', 'data': None}
        result = await asyncio.to_thread(self._execute_site, site_id, action='login')
        return {'success': True, 'data': result}

    async def api_verify_site(self, domain: str = '') -> dict:
        site_id = site_id_for_domain(domain)
        if not site_id:
            return {'success': False, 'message': 'pilot_not_enabled：仅开放 HDSky、海棠', 'data': None}
        result = await asyncio.to_thread(self._execute_site, site_id, True)
        return {'success': True, 'data': result}

    def _execute_all(self, trigger="manual"):
        return [self._execute_site(site_id, trigger=trigger,
                    action="login" if site_id in self._config.get("login_sites", []) and site_id not in self._config.get("sign_sites", []) else "sign")
                for site_id in dict.fromkeys(self._config.get('enabled_sites', []))]

    async def api_run_once(self) -> dict:
        """从数据页注册一次性 DateTrigger；不受常规调度门控影响。"""
        with self._migration.lock:
            self._config["onlyonce"] = True
            if hasattr(self, "update_config"):
                self.update_config(deepcopy(self._config))
            self._scheduler.clear()
            self._scheduler.build(self._config, self._scheduled_once)
        return {"success": True, "data": {"scheduled": True}}

    async def api_clean_today(self) -> dict:
        """清理签到历史中的当日缓存，保留历史存储契约。"""
        removed = await asyncio.to_thread(self._history.clear_today)
        return {"success": True, "data": {"removed": removed}}

    async def api_manual_signin(self) -> dict:
        results = await asyncio.to_thread(self._execute_all)
        return {'success': True, 'data': {'results': results}}

    def _scheduled_once(self):
        with self._migration.lock:
            if not self._config.get("onlyonce", False):
                return
            return self._scheduled_signin()

    def _scheduled_signin(self):
        with self._migration.lock:
            if self._runner.stop.is_set() or not self._config.get("scheduler_enabled", False):
                return
            if self._config.get("onlyonce", False):
                self._config["onlyonce"] = False
                if hasattr(self, "update_config"):
                    self.update_config(deepcopy(self._config))
                self._scheduler.clear()
            elif not self._running:
                return
        return self._execute_all("scheduler")

    def _next_schedule(self):
        return self._scheduler.next_schedule() if self._scheduler else None

    def _schedule_status(self):
        if not self._config.get("scheduler_enabled", False):
            return "scheduler_disabled：生产切换完成并显式开启后注册"
        if self._scheduler and self._scheduler.error:
            return self._scheduler.error
        return "registered" if self._scheduler and self._scheduler.services else "stopped"

    def stop_service(self) -> None:
        self._running = False
        self._runner.stop.set()
        if self._scheduler:
            self._scheduler.clear()
        try:
            from app.sdk.scheduler import remove_plugin_job
        except ImportError:
            return
        remove_plugin_job(self.plugin_id)
