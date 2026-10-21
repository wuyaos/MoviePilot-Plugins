"""ForumSignin V3 backend skeleton; frontend delivered in the next iteration."""
import asyncio
import json
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from threading import Lock, RLock
from uuid import uuid4

from .core.credentials import resolve
from .core.history import HistoryStore
from .core.models import SignResult, SignStatus
from .core.registry import ADAPTERS, get_registry, get_site
from .core.runner import run_page
from .http_client import HttpClient

try:
    from app.sdk.plugin import _PluginBase
except ImportError:
    class _PluginBase:
        pass


class ForumSignin(_PluginBase):
    plugin_id = "ForumSignin"
    plugin_name = "论坛签到"
    plugin_desc = "蜂巢、药丸与 SSDForum 论坛签到"
    plugin_version = "3.0.1"
    plugin_author = "wuyaos"
    plugin_icon = "Moviepilot_A.png"
    plugin_config_prefix = "forumsignin_"
    auth_level = 1
    SITE_KEYS = ("enabled_sites", "fengchao_api_key", "yaowan_cookie", "ssdforum_cookie",
                 "yaowan_managed_site_id", "ssdforum_managed_site_id")

    def __init__(self):
        super().__init__()
        self._config = self.get_form()[1]
        self._locks = {key: Lock() for key in ADAPTERS}
        self._config_lock = RLock()
        self._services = []
        self._stopped = True
        self._memory = {}
        self._history = HistoryStore(self._get, self._save)
        self._schedule_error = None

    def _get(self, key):
        return self.get_data(key) if hasattr(self, "get_data") else deepcopy(self._memory.get(key))

    def _save(self, key, value):
        if hasattr(self, "save_data"):
            self.save_data(key, value)
        else:
            self._memory[key] = deepcopy(value)

    def init_plugin(self, config=None):
        self.stop_service()
        self._config = {**self.get_form()[1], **deepcopy(config or {})}
        self._stopped = False
        self._schedule_error = None
        if not self._get("fengchao_instance_id"):
            self._save("fengchao_instance_id", str(uuid4()))
        if self._config["enabled"] and self._config["timed_update_enabled"]:
            try:
                from apscheduler.triggers.cron import CronTrigger
                try:
                    from app.sdk.config import settings
                    timezone = settings.TZ
                except ImportError:
                    timezone = None
                trigger = CronTrigger.from_crontab(self._config["timed_update_cron"], timezone=timezone)
                self._services = [{"id": "ForumSigninInfoUpdate", "name": "蜂巢个人信息同步",
                                   "trigger": trigger, "func": self.update_info, "kwargs": {}}]
            except (ValueError, TypeError):
                self._schedule_error = "invalid_sync_cron"

    def get_state(self):
        return bool(self._config["enabled"]) and not self._stopped

    def get_service(self):
        return list(self._services)

    def stop_service(self):
        self._stopped = True
        self._services = []
        try:
            from app.sdk.scheduler import remove_plugin_job
        except ImportError:
            return
        remove_plugin_job(self.plugin_id)

    def get_render_mode(self):
        return "vue", "dist/assets"

    def get_form(self):
        return None, json.loads((Path(__file__).parent / "config_defaults.json").read_text(encoding="utf-8"))

    def get_page(self):
        return None

    def get_api(self):
        specs = [("/config", self.api_config, "GET"), ("/config", self.api_save_config, "PUT"),
                 ("/site_config", self.api_site_config, "GET"), ("/site_config", self.api_save_site_config, "PUT"),
                 ("/stats", self.api_stats, "GET"), ("/history", self.api_history, "GET"),
                 ("/status", self.api_status, "GET"), ("/signin_by_domain", self.api_signin_by_domain, "POST"),
                 ("/verify_site", self.api_verify_site, "POST"), ("/update_info", self.api_update_info, "POST")]
        return [{"path": path, "endpoint": endpoint, "methods": [method], "auth": "bear"}
                for path, endpoint, method in specs]

    @staticmethod
    def _response(data=None, success=True, message=""):
        return {"success": success, "message": message, "data": data}

    async def api_config(self):
        return self._response(deepcopy(self._config))

    async def api_site_config(self):
        return self._response({key: deepcopy(self._config[key]) for key in self.SITE_KEYS})

    def _save_config(self, config):
        with self._config_lock:
            merged = {**self._config, **deepcopy(config)}
            if hasattr(self, "update_config"):
                self.update_config(merged)
            self.init_plugin(merged)
            try:
                from app.sdk.scheduler import update_plugin_job
            except ImportError:
                return
            update_plugin_job(self.plugin_id)

    async def api_save_config(self, config: dict):
        if set(config) - set(self.get_form()[1]):
            return self._response(success=False, message="unknown_config_key")
        await asyncio.to_thread(self._save_config, config)
        return self._response()

    async def api_save_site_config(self, config: dict):
        if set(config) - set(self.SITE_KEYS):
            return self._response(success=False, message="unknown_site_key")
        return await self.api_save_config(config)

    async def api_stats(self):
        return self._response({"today": self._history.today_counts(), "sites": get_registry(),
                               "next_schedule": None, "fengchao_sync": self._get("fengchao_sync_status")})

    async def api_history(self, page: int = 1, size: int = 20):
        return self._response(self._history.list(page, size))

    async def api_status(self):
        return self._response({"state": "running" if self.get_state() else "stopped",
                               "version": self.plugin_version, "schedule_error": self._schedule_error,
                               "busy_sites": [key for key, lock in self._locks.items() if lock.locked()]})

    @staticmethod
    def _managed_sites():
        try:
            from app.db.site_oper import SiteOper
        except ImportError:
            return []
        return [{key: getattr(row, key, None) for key in ("id", "url", "cookie", "ua", "proxy")}
                for row in SiteOper().list_order_by_pri()]

    def _client(self, site):
        credential = resolve(site, self._config, self._managed_sites() if site["id"] != "fengchao" else ())
        if credential is None:
            return None
        return HttpClient(site["adapter"].base, credential, self._get("fengchao_instance_id") or "")

    def _execute(self, domain, readonly=False):
        site = get_site(domain)
        if not site:
            return self._response(success=False, message="unknown_site")
        site_id = site["id"]
        lock = self._locks[site_id]
        acquired = lock.acquire(blocking=False)
        client = None
        try:
            if not acquired:
                result = SignResult.skipped()
            elif not self.get_state() or site_id not in self._config["enabled_sites"]:
                result = SignResult.skipped("站点未启用")
            else:
                client = self._client(site)
                if client is None:
                    result = SignResult(SignStatus.AUTH_FAILED, "缺少凭证，未提交")
                else:
                    adapter = site["adapter"](client)
                    if site_id == "fengchao":
                        result = adapter.run(readonly=readonly)
                    else:
                        bound = self._get("identity." + site_id) or ""
                        result = run_page(adapter, bound, readonly,
                                          bind=lambda uid: self._save("identity." + site_id, uid))
        except ValueError:
            result = SignResult(SignStatus.UNCONFIRMED, "凭证绑定或协议数据未确认，未自动切换")
        except Exception:
            result = SignResult(SignStatus.UNCONFIRMED, "请求或解析异常，需只读核验")
        finally:
            try:
                if client:
                    client.close()
            except Exception:
                pass  # Cleanup must not replace the result or prevent history persistence.
            finally:
                if acquired:
                    lock.release()
        result.site_id = site_id
        result.metadata["trigger"] = "verify" if readonly else "manual"
        self._history.append(result)
        return self._response(asdict(result))

    async def api_signin_by_domain(self, domain: str):
        return await asyncio.to_thread(self._execute, domain)

    async def api_verify_site(self, domain: str):
        return await asyncio.to_thread(self._execute, domain, True)

    def update_info(self):
        lock = self._locks["fengchao"]
        if not self.get_state():
            return self._response(success=False, message="plugin_disabled")
        if not lock.acquire(blocking=False):
            return self._response(success=False, message="site_busy")
        client = None
        try:
            site = get_site("fengchao")
            client = self._client(site)
            if client is None:
                return self._response(success=False, message="missing_api_key")
            info, identity = site["adapter"](client).sync(self._get("_fengchao_identity"))
            now = datetime.now().astimezone().isoformat()
            if identity:
                self._save("_fengchao_identity", identity)
            self._save("fengchao_user_info", info)
            self._save("fengchao_user_info_updated_at", now)
            self._save("fengchao_sync_status", {"success": True, "time": now})
            return self._response(info)
        except Exception:
            self._save("fengchao_sync_status", {"success": False, "message": "sync_unconfirmed",
                                                "time": datetime.now().astimezone().isoformat()})
            return self._response(success=False, message="sync_unconfirmed")
        finally:
            try:
                if client:
                    client.close()
            except Exception:
                pass  # Cleanup must not replace the synchronization result.
            finally:
                lock.release()

    async def api_update_info(self):
        return await asyncio.to_thread(self.update_info)
