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
    plugin_version = "3.1.0"
    plugin_author = "wuyaos"
    plugin_icon = "Moviepilot_A.png"
    plugin_config_prefix = "forumsignin_"
    auth_level = 1
    SITE_KEYS = ("enabled_sites", "fengchao_api_key", "yaowan_cookie", "yaowan_username", "yaowan_password", "ssdforum_cookie",
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
        if self._config["enabled"] and self._config.get("onlyonce"):
            from apscheduler.triggers.date import DateTrigger
            self._services = [{"id": "ForumSigninRunOnce", "name": "论坛签到单次运行", "trigger": DateTrigger(), "func": self.run_once, "kwargs": {}}]
        elif self._config["enabled"] and self._config.get("cron"):
            try:
                from apscheduler.triggers.cron import CronTrigger
                from app.sdk.config import settings
                self._services = [{"id": "ForumSigninScheduled", "name": "论坛定时签到", "trigger": CronTrigger.from_crontab(self._config["cron"], timezone=settings.TZ), "func": self.run_once, "kwargs": {}}]
            except (ValueError, TypeError, ImportError):
                self._schedule_error = "invalid_signin_cron"
        if self._config["enabled"] and self._config["timed_update_enabled"]:
            try:
                from apscheduler.triggers.cron import CronTrigger
                try:
                    from app.sdk.config import settings
                    timezone = settings.TZ
                except ImportError:
                    timezone = None
                trigger = CronTrigger.from_crontab(self._config["timed_update_cron"], timezone=timezone)
                self._services.append({"id": "ForumSigninInfoUpdate", "name": "蜂巢个人信息同步",
                                      "trigger": trigger, "func": self.update_info, "kwargs": {}})
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
                 ("/run_once", self.api_run_once, "POST"), ("/clean_cache", self.api_clean_cache, "POST"),
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
        page = self._history.list(1, 100)
        records = list(page["items"])
        for number in range(2, (page["total"] + 99) // 100 + 1):
            records.extend(self._history.list(number, 100)["items"])
        latest = {}
        site_counts = {site["id"]: {"success": 0, "failed": 0, "unconfirmed": 0} for site in get_registry()}
        today = datetime.now().astimezone().date()
        for record in records:
            try:
                record_date = datetime.fromisoformat(record["time"].replace("Z", "+00:00")).astimezone().date()
            except (TypeError, ValueError):
                continue
            if record_date == today and record["site"] in site_counts:
                state = "failed" if record["status"] == "auth_failed" else record["status"]
                if state in site_counts[record["site"]]:
                    site_counts[record["site"]][state] += 1
        for record in records:
            latest.setdefault(record["site"], record)
        sites = get_registry()
        for site in sites:
            result = latest.get(site["id"], {})
            site.update({"enabled": site["id"] in self._config.get("enabled_sites", []),
                         "status": result.get("status", "disabled"), "message": result.get("message", "")})
        return self._response({"today": self._history.today_counts(), "latest": latest, "sites": sites,
                               "next_schedule": self._next_schedule(), "site_counts": site_counts, "fengchao_sync": self._get("fengchao_sync_status"),
                               "fengchao_user_info": self._get("fengchao_user_info")})

    def _next_schedule(self):
        now = datetime.now().astimezone()
        times = []
        for service in self._services:
            trigger = service.get("trigger")
            try:
                value = trigger.get_next_fire_time(None, now)
                if value:
                    times.append(value.astimezone().isoformat())
            except Exception:
                continue
        return min(times) if times else None

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
        except PermissionError:
            result = SignResult(SignStatus.AUTH_FAILED, "凭证已失效或无权限，未提交")
        except ValueError:
            result = SignResult(SignStatus.UNCONFIRMED, "凭证绑定或协议数据未确认，未自动切换")
        except Exception:
            result = SignResult(SignStatus.UNCONFIRMED, "请求或解析异常，需只读核验")
        finally:
            try:
                if client and client.credential.source == "local_cookie":
                    cookie_key = next((field["key"] for field in site.get("fields", [])
                                       if field.get("key", "").endswith("_cookie")), "")
                    refreshed = client.credential.value
                    if cookie_key and refreshed and refreshed != self._config.get(cookie_key):
                        self._config[cookie_key] = refreshed
                        if hasattr(self, "update_config"):
                            self.update_config(deepcopy(self._config))
            except Exception:
                pass  # Cookie renewal persistence must not replace the sign-in result.
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
        if not readonly and self._config.get("notify"):
            self._notify_result(result)
        return self._response(asdict(result))

    def _notify_result(self, result):
        try:
            from app.sdk.notification import NotificationType
            name = next((site["name"] for site in get_registry() if site["id"] == result.site_id), result.site_id)
            labels = {SignStatus.SUCCESS: "签到成功", SignStatus.ALREADY: "今日已签到",
                      SignStatus.FAILED: "签到失败", SignStatus.UNCONFIRMED: "结果未确认",
                      SignStatus.AUTH_FAILED: "认证失败", SignStatus.NETWORK_ERROR: "网络异常"}
            state = labels.get(result.status, "签到完成")
            self.post_message(mtype=NotificationType.SiteMessage, title=f"【{name}{state}】",
                              text=f"时间：{datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")}\n状态：{state}\n原因：{result.message or "—"}")
        except Exception:
            pass  # Notification delivery must not alter the sign-in result.

    async def api_signin_by_domain(self, domain: str):
        return await asyncio.to_thread(self._execute, domain)

    def run_once(self):
        results = []
        for site in get_registry():
            if site["id"] in self._config.get("enabled_sites", []):
                results.append(self._execute(site["domain"]))
        return self._response(results)

    async def api_run_once(self):
        return await asyncio.to_thread(self.run_once)

    def clean_cache(self):
        keys = ("identity.yaowan", "identity.ssdforum", "_fengchao_identity", "fengchao_user_info",
                "fengchao_user_info_updated_at", "fengchao_sync_status", "yaowan_user_info", "ssdforum_user_info")
        for key in keys:
            self._save(key, None)
            self._memory.pop(key, None)
        return self._response({"cleared": list(keys)})

    async def api_clean_cache(self):
        return await asyncio.to_thread(self.clean_cache)

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
