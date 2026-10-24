"""ForumSignin V3 backend skeleton; frontend delivered in the next iteration."""
import asyncio
import logging
import json
from copy import deepcopy
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from threading import Lock, RLock
from uuid import uuid4

from .core.credentials import Credential, cookiecloud_cookie, resolve
from .core.history import HistoryStore
from .core.models import SignResult, SignStatus
from .core.registry import ADAPTERS, get_registry, get_site
from .core.runner import run_page
from .http_client import HttpClient

try:
    from app.core.event import eventmanager
    from app.sdk.plugin import _PluginBase
    from app.schemas.types import EventType
except ImportError:  # 离线契约测试无宿主
    eventmanager = None

    class _PluginBase:
        pass

    EventType = None


logger = logging.getLogger("ForumSignin")


class ForumSignin(_PluginBase):
    plugin_id = "ForumSignin"
    plugin_name = "论坛签到"
    plugin_desc = "蜂巢、药丸与 SSDForum 论坛签到"
    plugin_version = "3.1.10"
    plugin_author = "wuyaos"
    plugin_icon = "Moviepilot_A.png"
    plugin_config_prefix = "forumsignin_"
    auth_level = 1
    SITE_KEYS = ("enabled_sites", "fengchao_api_key", "yaowan_cookie", "yaowan_username", "yaowan_password", "ssdforum_cookie",
                 "yaowan_managed_site_id", "ssdforum_managed_site_id")

    def __init__(self):
        self._notify_buffer = []
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
        self._migrate_legacy_invites()
        self._migrate_legacy_data()
        self._stopped = False
        self._schedule_error = None
        self._register_commands()
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

    def _migrate_legacy_invites(self):
        """V2 迁移兼容：旧 InvitesSignin 配置键（invites_*）映射为 yaowan_*，站点 id 同步。

        宿主 API 对凭据读取做掩码，无法在进程外搬运；本方法在进程内用真实值完成键名
        迁移并 update_config 持久化，凭据不出插件边界。
        """
        config = self._config
        legacy_map = {"invites_username": "yaowan_username",
                      "invites_password": "yaowan_password",
                      "invites_cookie": "yaowan_cookie",
                      "ssdforumsignin_cookie": "ssdforum_cookie"}
        moved = False
        for old_key, new_key in legacy_map.items():
            if old_key not in config:
                continue
            legacy_value = config.pop(old_key)
            if legacy_value and not config.get(new_key):
                config[new_key] = legacy_value
                moved = True
        for key in ("enabled_sites", "sign_sites"):
            values = config.get(key)
            if isinstance(values, list) and "invites" in {str(v) for v in values}:
                config[key] = ["yaowan" if str(v) == "invites" else str(v) for v in values]
                moved = True
        if moved:
            self.update_config(deepcopy(config))
            logger.info("论坛签到：已迁移旧版论坛签到配置键（InvitesSignin/SSDForumSignin）")

    def _migrate_legacy_data(self):
        info = self._get("fengchao_user_info")
        data = info.get("data") if isinstance(info, dict) else None
        if isinstance(data, dict) and isinstance(data.get("attributes"), dict):
            self._save("fengchao_user_info", None)

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


    @staticmethod
    def get_command() -> list:
        """远程命令：论坛签到（立即执行一轮已启用站点）。"""
        if EventType is None:
            return []
        return [{"cmd": "/forum_signin", "event": EventType.PluginAction,
                 "desc": "论坛签到", "category": "签到",
                 "data": {"action": "signin_once"}}]

    def _handle_remote_command(self, event) -> None:
        """PluginAction：signin_once=立即运行一轮论坛签到。"""
        if not event or EventType is None:
            return
        data = getattr(event, "event_data", None) or {}
        if data.get("action") != "signin_once":
            return
        import threading

        def _worker():
            try:
                self.run_once()
            except Exception:
                logger.error("论坛签到：远程命令执行异常", exc_info=True)

        threading.Thread(target=_worker, daemon=True, name="forumsignin-remote-command").start()

    def _register_commands(self) -> None:
        """init_plugin 时注册远程命令监听（幂等）。"""
        if eventmanager is None or EventType is None:
            return
        if getattr(self.__class__, "_command_registered", False):
            return
        eventmanager.register(EventType.PluginAction)(self._handle_remote_command)
        self.__class__._command_registered = True

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
        icons = self._get("icon.cache") or {}
        for site in sites:
            result = latest.get(site["id"], {})
            if site["id"] not in icons:
                icon = await asyncio.to_thread(self._resolve_favicon, site.get("url") or "https://" + site.get("domain", ""))
                if icon:
                    icons[site["id"]] = icon
                    self._save("icon.cache", icons)
            site.update({"enabled": site["id"] in self._config.get("enabled_sites", []),
                         "can_sync": site["id"] == "fengchao", "icon": icons.get(site["id"], ""),
                         "status": result.get("status", "disabled"), "message": result.get("message", "")})
        return self._response({"today": self._history.today_counts(), "latest": latest, "sites": sites,
                               "next_schedule": self._next_schedule(), "site_counts": site_counts, "fengchao_sync": self._get("fengchao_sync_status") or {},
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

    def _resolve_favicon(self, base: str) -> str:
        """解析论坛站点图标：首页 <link rel=icon> → /favicon.ico；失败返回空串。结果缓存于 icon.cache。"""
        import base64
        import re
        try:
            from app.sdk.network import RequestUtils
            ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"
            origin = base.rstrip("/")
            fetched = {}

            def get(url, referer=None):
                try:
                    resp = RequestUtils(timeout=10, ua=ua, referer=referer or origin).get_res(url, allow_redirects=True)
                    if resp is not None and resp.status_code == 200 and resp.content:
                        fetched[resp.headers.get("Content-Type", "")] = resp.content
                        return resp
                except Exception:
                    pass
                return None

            home = get(origin + "/")
            icon_url = ""
            if home is not None:
                match = re.search(r'<link\b[^>]*>', home.text or "", re.I)
                if match:
                    tag = match.group(0)
                    rel = re.search(r'\brel=["\']([^"\']*)["\']', tag, re.I)
                    href = re.search(r'\bhref=["\']([^"\']+)["\']', tag, re.I)
                    if rel and href and "icon" in rel.group(1).lower():
                        icon_url = href.group(1)
                        if icon_url.startswith("//"):
                            icon_url = "https:" + icon_url
                        elif not icon_url.startswith("http"):
                            icon_url = origin + "/" + icon_url.lstrip("/")
            resp = get(icon_url or origin + "/favicon.ico", referer=origin + "/")
            for ctype, content in fetched.items():
                if content and len(content) > 24:
                    mime = ctype.split(";")[0].strip() or "image/x-icon"
                    if "text" not in mime:
                        return f"data:{mime};base64," + base64.b64encode(content).decode()
            return ""
        except Exception:
            return ""

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
        if credential is None and site["credential"].kind != "api":
            # 凭据链：本地 Cookie 缺失时取 CookieCloud 并回写配置；失效续期由 adapter（药丸账密）或回写承担。
            cookie = cookiecloud_cookie(site["adapter"].base)
            if cookie:
                logger.info("%s：本地凭据缺失，已从 CookieCloud 获取并回写配置", site["id"])
                cookie_key = next((f["key"] for f in site.get("fields", [])
                                   if f.get("key", "").endswith("_cookie")), "")
                if cookie_key:
                    with self._config_lock:
                        self._config[cookie_key] = cookie
                        if hasattr(self, "update_config"):
                            self.update_config(deepcopy(self._config))
                credential = Credential("cookiecloud", cookie)
        if credential is None:
            return None
        return HttpClient(site["adapter"].base, credential, self._get("fengchao_instance_id") or "")

    def _execute_with_retry(self, domain, readonly=False):
        # V2 语义：失败/网络异常按 retry_count/retry_interval 分钟退避重试；成功/已签/未确认/认证失败不重试（未确认重放有重复提交风险）。
        result = self._execute_result(domain, readonly=readonly)
        if readonly:
            return asdict(result)
        attempts = max(0, int(self._config.get('retry_count', 0) or 0))
        interval = max(1, int(self._config.get('retry_interval', 10) or 10))
        for _ in range(attempts):
            if result.status not in (SignStatus.FAILED, SignStatus.NETWORK_ERROR):
                break
            time.sleep(interval * 60)
            result = self._execute_result(domain, readonly=readonly)
        return asdict(result)

    def _execute(self, domain, readonly=False):
        return self._response(asdict(self._execute_result(domain, readonly=readonly)))

    def _execute_result(self, domain, readonly=False):
        site = get_site(domain)
        if not site:
            result = SignResult.skipped("站点未注册")
            result.site_id = str(domain)
            self._history.append(result)
            return result
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
                                          bind=lambda uid: self._save("identity." + site_id, uid),
                                          sample_sink=(lambda html, status: self._save("sample." + site_id + ".html", html))
                                          if site_id in ("yaowan", "ssdforum") else None)
                    cookie_key = next((field["key"] for field in site.get("fields", [])
                                       if field.get("key", "").endswith("_cookie")), "")
                    has_login_fallback = bool(self._config.get(site_id + "_username") and
                                              self._config.get(site_id + "_password"))
                    if (not readonly and result.status == SignStatus.AUTH_FAILED and client and
                            client.credential.source == "local_cookie" and cookie_key and
                            not has_login_fallback):
                        client.close()
                        client = None
                        with self._config_lock:
                            self._config[cookie_key] = ""
                            if hasattr(self, "update_config"):
                                self.update_config(deepcopy(self._config))
                        retry_client = self._client(site)
                        if retry_client is not None:
                            client = retry_client
                            adapter = site["adapter"](client)
                            if site_id == "fengchao":
                                result = adapter.run(readonly=False)
                            else:
                                result = run_page(adapter, bound, False,
                                                  bind=lambda uid: self._save("identity." + site_id, uid),
                                                  sample_sink=(lambda html, status: self._save("sample." + site_id + ".html", html))
                                                  if site_id in ("yaowan", "ssdforum") else None)
        except PermissionError:
            result = SignResult(SignStatus.AUTH_FAILED, "凭证已失效或无权限，未提交")
        except ValueError:
            result = SignResult(SignStatus.UNCONFIRMED, "凭证绑定或协议数据未确认，未自动切换")
        except Exception as exc:
            if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
                result = SignResult(SignStatus.NETWORK_ERROR, "网络连接失败，可重试")
            else:
                result = SignResult(SignStatus.UNCONFIRMED, "请求或解析异常，需只读核验")
        finally:
            logger.info("论坛签到 %s：%s（%s）", site_id, result.status.value, result.message or "—")
            try:
                if client and client.credential.source in ("local_cookie", "cookiecloud"):
                    cookie_key = next((field["key"] for field in site.get("fields", [])
                                       if field.get("key", "").endswith("_cookie")), "")
                    refreshed = client.credential.value
                    if cookie_key and refreshed:
                        with self._config_lock:
                            changed = refreshed != self._config.get(cookie_key)
                            if changed:
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
            self._notify_buffer.append((site_id, result))
        return result

    def _flush_notify(self):
        """一轮结果合并为一条通知；空缓冲不发送。"""
        if not self._notify_buffer:
            return
        results, self._notify_buffer = self._notify_buffer, []
        try:
            registry = get_registry()
            labels = {SignStatus.SUCCESS: "✅ 签到成功", SignStatus.ALREADY: "📅 今日已签到",
                      SignStatus.FAILED: "❌ 签到失败", SignStatus.UNCONFIRMED: "⚠️ 结果未确认",
                      SignStatus.AUTH_FAILED: "🔒 认证失败", SignStatus.NETWORK_ERROR: "🌐 网络异常"}
            blocks = []
            for site_id, result in results:
                name = next((site["name"] for site in registry if site["id"] == site_id), site_id)
                state = labels.get(result.status, "签到完成")
                note = (result.message or "—").replace("签到成功，", "")
                blocks.append(f"论坛：{name}\n状态：{state}\n说明：{note}")
            blocks.append(f"时间：{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S')}")
            self.post_message(title="【论坛签到】", text="\n\n".join(blocks))
        except Exception as exc:
            logger.warning("通知发送失败（不影响签到结果）：%s", exc)

    async def api_signin_by_domain(self, domain: str):
        result = await asyncio.to_thread(self._execute, domain)
        self._flush_notify()
        return result

    def run_once(self):
        results = []
        for site in get_registry():
            if site["id"] in self._config.get("enabled_sites", []):
                results.append(self._execute_with_retry(site["domain"]))
        self._flush_notify()
        return self._response(results)

    async def api_run_once(self):
        return await asyncio.to_thread(self.run_once)

    def clean_cache(self):
        keys = ("identity.yaowan", "identity.ssdforum", "_fengchao_identity", "fengchao_user_info",
                "fengchao_user_info_updated_at", "fengchao_sync_status")
        keys = keys + ("icon.cache", "sample.yaowan.html", "sample.ssdforum.html")
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
        except Exception as exc:
            # 保留可诊断的异常类型/HTTP 状态；不记录 API key 或响应凭据。
            detail = self._safe_sync_error(exc)
            logger.warning("蜂巢个人信息同步失败：%s", detail)
            self._save("fengchao_sync_status", {"success": False, "message": detail,
                                                "time": datetime.now().astimezone().isoformat()})
            return self._response(success=False, message=detail)
        finally:
            try:
                if client:
                    client.close()
            except Exception:
                pass  # Cleanup must not replace the synchronization result.
            finally:
                lock.release()

    @staticmethod
    def _safe_sync_error(exc):
        """同步错误只保留类型和短消息，避免把凭据/响应正文写入数据或日志。"""
        message = str(exc or "").replace("\n", " ").strip()
        if len(message) > 240:
            message = message[:240] + "…"
        return f"{type(exc).__name__}: {message or 'unknown_error'}"

    async def api_update_info(self, domain: str = "fengchao.chat"):
        if domain not in ("fengchao.chat", "pting.club"):
            return self._response(success=False, message="unknown_site")
        result = await asyncio.to_thread(self.update_info)
        try:
            if self._config.get("notify"):
                state = ("🔄 同步完成" if result and result.get("success", True) else "❌ 同步失败")
                self.post_message(title="【论坛签到】",
                                  text=f"论坛：蜂巢\n状态：{state}\n说明：{(result or {}).get('message') or '—'}\n时间：{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception as exc:
            logger.warning("同步通知发送失败：%s", exc)
        return result
