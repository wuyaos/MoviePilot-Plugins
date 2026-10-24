# -*- coding: utf-8 -*-
"""PT 签到中心 V3：PT 站点签到、登录与回读。"""
import json
import asyncio
import threading
from datetime import datetime
from dataclasses import asdict
from .core.scheduler import Scheduler
from .core.runner import SignRunner
from .core.models import SignResult, SignStatus
from .core.registry import managed_site, site_id_for_domain, hostname
from pathlib import Path
from copy import deepcopy
from .core.history import HistoryStore
from .core.migration import Migration, MigrationError
from .core.registry import get_registry, get_native_module
from .core.native import run_native, run_native_login, run_integration
from .core import cloudsign
from .core.custom import run_custom, CustomNexusSignin
from .core.state_store import DISABLED, FAILED, GATE_SKIPS, PENDING, SUCCESS, TrackStateStore
from .core.notify import PARSE_MODES, build_rich_blocks, format_round_notifications
from typing import Any

try:
    from app.sdk.plugin import _PluginBase
    from app.core.event import eventmanager
    from app.schemas.types import EventType
except ImportError:  # 离线契约测试无宿主
    class _PluginBase:
        pass
    eventmanager = None
    EventType = None

class AutoPtCheckin(_PluginBase):
    plugin_id = "AutoPtCheckin"
    plugin_name = "PT 签到中心"
    plugin_desc = "PT 站点自动签到与模拟登录"
    plugin_version = "4.0.7"
    plugin_author = "wuyaos"
    plugin_config_prefix = "autoptcheckin_"

    SITE_KEYS = ("enabled_sites", "sign_sites", "login_sites", "site_browserless", "custom_sites_data",
                 "rousi_username", "rousi_password", "sunnypt_username",
                 "sunnypt_password", "sunnypt_token", "mteam_username", "mteam_password", "mteam_totp",
                 "yzyy_username", "yzyy_password")

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
        self._state = None
        self._last_round = []
        self._round_active = False

    def init_plugin(self, config: dict | None = None) -> None:
        # 宿主配置保存走 init_plugin（PluginConfigCommand.update）；在途轮次同样保护，
        # 否则 _init_config 默认的 stop_service 会打断运行中的队列（reviewer 3b24554a P1-2）。
        with self._migration.lock:
            self._init_config(config, preserve_round=self._round_active)
        self._register_commands()
    def _init_config(self, config: dict | None = None, preserve_round: bool = False) -> None:
        if not preserve_round:
            self.stop_service()
            self._runner.stop.clear()
        self._config = deepcopy(config or {})
        # 迁移/前端多次确认可能累积重复站点 ID：保序去重，避免队列重复执行。
        for key in ("enabled_sites", "sign_sites", "login_sites", "site_browserless"):
            values = self._config.get(key)
            if isinstance(values, list):
                self._config[key] = list(dict.fromkeys(str(v) for v in values))
        self._running = bool(self._config.get("enabled", False))
        if preserve_round:
            self._runner.stop.clear()
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

        store = self._track_store()
        if not store.snapshot()["sites"]:
            # 首次/损坏重建：从最近历史派生初始结论（历史层已把 already 归一为 signed）。
            store.rebuild_from_history(self._recent_records())
        store.rollover()
        self._recompute_track_states()
    def get_state(self) -> bool:
        return self._running or (not self._runner.stop.is_set() and bool(self._config.get("scheduler_enabled", False)) and bool(self._config.get("onlyonce", False)))

    def get_service(self) -> list:
        # 不以 stop 门控注册：宿主任何 stop_service（重建/重载）都会置位 stop，
        # 若在此返回空列表，宿主将移除全部服务且再无调度器去清除 stop（死锁）。
        # stop 只用于中断在途执行；注册始终按当前配置给出。
        if self._scheduler is None:
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
                "version": self.plugin_version, "today": self._history.today_counts(), "next_schedule": self._next_schedule()}}

    async def api_config(self) -> dict:
        """仅经宿主认证 API 读取配置；不写日志或回显至统计。"""
        return {"success": True, "data": deepcopy(self._config)}

    async def api_save_config(self, config: dict) -> dict:
        """与宿主保存使用同一配置存储；Vue 视图优先 emit save。"""
        await asyncio.to_thread(self._save_config, config)
        return {"success": True, "data": None}

    def _save_config(self, config: dict) -> None:
        with self._migration.lock:
            round_active = self._round_active
            self.update_config(config)
            if round_active:
                self._runner.stop.clear()
            self._init_config(config, preserve_round=round_active)
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

    def _resolve_favicon(self, base: str) -> str:
        """解析站点图标：首页 <link rel=icon> → /favicon.ico；失败返回空串。结果缓存于 icon.cache。"""
        import base64
        import re
        try:
            from app.sdk.network import RequestUtils
            ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"
            origin = base.rstrip("/")
            fetched = {}

            def get(url, referer=None):
                try:
                    resp = RequestUtils(timeout=8, ua=ua, referer=referer or origin).get_res(url, allow_redirects=True)
                    if resp is not None and resp.status_code == 200 and resp.content:
                        fetched[resp.headers.get("Content-Type", "")] = resp.content
                        return resp
                except Exception:
                    pass
                return None

            home = get(origin + "/")
            icon_url = ""
            if home is not None:
                match = re.search(r'<link[^>]+rel=["\'][^"\']*icon[^"\']*["\'][^>]*href=["\']([^"\']+)["\']', home.text or "", re.I)
                if match:
                    icon_url = match.group(1)
                    if icon_url.startswith("//"):
                        icon_url = "https:" + icon_url
                    elif not icon_url.startswith("http"):
                        icon_url = origin + "/" + icon_url.lstrip("/")
            resp = get(icon_url or origin + "/favicon.ico", referer=origin + "/")
            for ctype, content in fetched.items():
                if content and len(content) > 24:
                    mime = ctype.split(";")[0].strip() or "image/x-icon"
                    if "text" not in mime:
                        return "data:" + mime + ";base64," + base64.b64encode(content).decode()
        except Exception:
            pass
        return ""

    async def api_sites(self) -> dict:
        registry = get_registry(self._config.get('custom_sites_data', []))
        sites = deepcopy(registry["sites"])
        emulate_ids = {str(v) for v in self._config.get('site_browserless', [])}
        icon_cache = self.get_data("icon.cache") or {} if hasattr(self, "get_data") else {}
        pending_icons = []
        for site in sites:
            site.setdefault('cf', 'unknown')
            site['emulate'] = str(site.get('id')) in emulate_ids or bool(site.get('emulate', False))
            sid = str(site.get('id', ''))
            if not site.get('icon') and icon_cache.get(sid):
                site['icon'] = icon_cache[sid]
            # 自定义站点同样解析图标；失败写 '' 占位，避免每次 /sites 都重试同一批 URL。
            if (not site.get('icon') and icon_cache.get(sid) is None and site.get('url')):
                pending_icons.append((sid, site['url']))
        if pending_icons:
            import asyncio
            changed = False
            for sid, url in pending_icons:
                icon = await asyncio.to_thread(self._resolve_favicon, url)
                if icon:
                    icon_cache[sid] = icon
                    changed = True
            if changed and hasattr(self, "save_data"):
                self.save_data("icon.cache", icon_cache)
                for site in sites:
                    if not site.get('icon') and icon_cache.get(str(site.get('id', ''))):
                        site['icon'] = icon_cache[str(site.get('id', ''))]
        return {"success": True, "data": {"sites": sites, "sources": deepcopy(registry["sources"])}}

    async def api_stats(self) -> dict:
        mode = self._config.get("cron_mode", "interval")
        schedule = {"mode": mode}
        if mode == "cron":
            schedule["cron"] = self._config.get("cron", "")
        else:
            schedule.update({"interval_hours": self._config.get("interval_hours", 2),
                             "begin_hour": self._config.get("begin_hour", 9),
                             "end_hour": self._config.get("end_hour", 23)})
        # 站点行与三卡统计全部来自状态表；历史仅作流水审计。
        self._track_store().rollover()
        rows = self._site_rows()
        # 三卡统计与站点列表同源：直接按启用站点行汇总，状态表残留条目不再进数字。
        latest = {}
        for track in ("sign", "login"):
            buckets = {"success": 0, "failed": 0, "unconfirmed": 0}
            for row in rows:
                state = row.get(f"{track}_state")
                if state == SUCCESS:
                    buckets["success"] += 1
                elif state == FAILED:
                    raw = row.get(f"{track}_status", "")
                    buckets["unconfirmed" if raw == "unconfirmed" else "failed"] += 1
            latest[track] = buckets
        return {"success": True, "data": {"latest": latest,
                "next_schedule": self._next_schedule(), "schedule_status": self._schedule_status(), "schedule": schedule, "sites": rows}}

    def _site_rows(self) -> list[dict]:
        """数据页站点行：状态表提供轨道状态，registry 提供元数据与控制位。"""
        registry = get_registry(self._config.get('custom_sites_data', []))['sites']
        enabled = {str(v) for v in self._config.get('enabled_sites', [])}
        sign_sel = {str(v) for v in self._config.get('sign_sites', [])}
        login_sel = {str(v) for v in self._config.get('login_sites', [])}
        rows = []
        icon_cache = self.get_data("icon.cache") or {} if hasattr(self, "get_data") else {}
        for site in registry:
            sid = str(site['id'])
            # 卡片严格随配置：仅显示启用站点。
            if sid not in enabled:
                continue
            sign = self._track_store().entry_of(sid, 'sign')
            login = self._track_store().entry_of(sid, 'login')
            cf_markers = ('cf-chl', 'cloudflare', 'just a moment', 'verify you are human', 'challenge-platform')
            latest_messages = f"{sign.get('message', '')} {login.get('message', '')}".lower()
            cf_hit = any(marker in latest_messages for marker in cf_markers)
            icon = site.get('icon', '') or icon_cache.get(sid, '')
            rows.append({'id': sid, 'name': site.get('name', sid), 'url': site.get('url', ''),
                'icon': icon, 'source': site.get('source', ''),
                'cf': True if cf_hit else site.get('cf', 'unknown'),
                'emulate': sid in {str(v) for v in self._config.get('site_browserless', [])} or bool(site.get('emulate', False)),
                'shield': site.get('shield'),
                                'sign_state': sign.get('state', 'disabled' if sid not in enabled else 'pending'),
                'sign_status': sign.get('status', ''), 'sign_time': sign.get('time', ''),
                'sign_message': sign.get('message', ''),
                'page_action': (sign.get('metadata') or {}).get('page_action'),
                'login_state': login.get('state', 'disabled' if sid not in enabled else 'pending'),
                'login_status': login.get('status', ''), 'login_time': login.get('time', ''),
                'login_message': login.get('message', ''),
                'enabled': sid in enabled,
                'can_signin': sid in enabled and sid in sign_sel and sign.get('state') != DISABLED,
                'can_login': sid in enabled and sid in login_sel and login.get('state') != DISABLED,
                'sign_disabled_struct': sign.get('state') == DISABLED and sign.get('reason') in (
                    'signin_not_applicable', 'signin_not_supported', 'site_disabled'),
                'login_disabled_struct': login.get('state') == DISABLED and login.get('reason') in (
                    'login_not_supported', 'login_not_selected', 'site_disabled'),
                'can_verify': sid in enabled,
                'sign_selected': sid in sign_sel, 'login_selected': sid in login_sel})
        return rows
    async def api_history(self, page: int = 1, size: int = 20) -> dict:
        return {"success": True, "data": self._history.list(page, size)}

    def _record_result(self, result):
        self._history.append(result)
        metadata = getattr(result, "metadata", None) or {}
        status = getattr(getattr(result, "status", None), "value", "")
        # already 在入口统一归一为 signed：状态表与任何下游都不再出现 already。
        if status == "already":
            status = "signed"
        # read_only 核验不改表；纯空转（锁忙/取消）只写历史；门控类 skip（带 reason）写 disabled，
        # 否则门控站停留 FAILED 会被当场重试并在每轮重复执行。
        reason = metadata.get("reason")
        gate_skip = status in ("skipped", "cancelled") and (reason or "") in GATE_SKIPS
        if not metadata.get("read_only") and (status not in ("skipped", "cancelled") or gate_skip):
            diag = {k: metadata[k] for k in ("page_action", "steps", "error") if k in metadata}
            self._track_store().apply_result(
                str(result.site_id), metadata.get("action", "sign"), status,
                message=getattr(result, "message", "") or "", reason=reason,
                metadata=diag or None)
        if result.account and result.site_id not in self._bound_uids:
            self._bound_uids[result.site_id] = result.account
            if hasattr(self, "save_data"):
                self.save_data("identity.bindings", dict(self._bound_uids))

    def _track_store(self) -> TrackStateStore:
        """惰性构造：测试/宿主在构造后才注入 get_data/save_data，因此不能在 __init__ 固化。"""
        if self._state is None:
            self._state = TrackStateStore(getattr(self, "get_data", None), getattr(self, "save_data", None))
        return self._state

    def _recompute_track_states(self) -> None:
        """配置变更后全量重算 pending/disabled；已有 success/failed 结论保留。"""
        decisions: dict[str, dict[str, tuple[str, str | None]]] = {}
        enabled = {str(v) for v in self._config.get("enabled_sites", [])}
        sign_sel = {str(v) for v in self._config.get("sign_sites", [])}
        login_sel = {str(v) for v in self._config.get("login_sites", [])}
        unlock = bool(self._config.get("unlock_all_sites", False))
        for site in get_registry(self._config.get("custom_sites_data", []))["sites"]:
            sid = str(site["id"])
            if sid not in enabled and not self._track_store().entry_of(sid, "sign") and not self._track_store().entry_of(sid, "login"):
                continue
            decisions[sid] = {}
            if sid not in enabled:
                decisions[sid]["sign"] = (DISABLED, "site_disabled")
                decisions[sid]["login"] = (DISABLED, "site_disabled")
                continue
            if sid not in sign_sel:
                decisions[sid]["sign"] = (DISABLED, "signin_not_selected")
            elif site.get("signin_capable") is False:
                decisions[sid]["sign"] = (DISABLED, "signin_not_supported")
            elif not site.get("signin_applicable", False):
                decisions[sid]["sign"] = (DISABLED, "signin_not_applicable")
            elif not unlock and site.get("native") and not site.get("verified"):
                decisions[sid]["sign"] = (DISABLED, "native_unverified")
            elif not unlock and site.get("native") and not site.get("hook_implemented", True):
                decisions[sid]["sign"] = (DISABLED, "hook_not_implemented")
            elif site.get("source") == "自定义站点":
                # 自定义站在 _execute_site 的 custom 分支执行，不受非原生站点门控。
                decisions[sid]["sign"] = (PENDING, None)
            elif not unlock and not site.get("native") and sid not in ("rousi", "sunnypt", "mteam"):
                decisions[sid]["sign"] = (DISABLED, "pilot_not_enabled")
            else:
                decisions[sid]["sign"] = (PENDING, None)
            if sid not in login_sel or site.get("login_capable") is False:
                decisions[sid]["login"] = (DISABLED, "login_not_selected" if sid not in login_sel else "login_not_supported")
            elif site.get("source") == "自定义站点":
                # 自定义站在 _execute_site 的 custom 分支执行，不受非原生站点门控。
                decisions[sid]["login"] = (PENDING, None)
            elif not unlock and not site.get("native") and sid not in ("rousi", "sunnypt", "mteam"):
                decisions[sid]["login"] = (DISABLED, "pilot_not_enabled")
            else:
                decisions[sid]["login"] = (PENDING, None)
        self._track_store().reconfigure(decisions)
    def _recent_records(self, pages: int = 4):
        """按时间倒序聚合最近多页历史（每页 100），供轨道最新状态计算使用。"""
        items = []
        for page in range(1, max(1, pages) + 1):
            batch = self._history.list(page, 100)['items']
            items.extend(batch)
            if len(batch) < 100:
                break
        return items



    def _execute_site(self, site_id, read_only=False, trigger="manual", action="sign"):
        registry = {site['id']: site for site in get_registry(self._config.get('custom_sites_data', []))['sites']}
        # “今日已签”由状态表 success 态承担：成功站不进队列，这里不再重复拦截。
        custom = next((item for item in self._config.get('custom_sites_data', [])
                       if isinstance(item, dict) and str(item.get('id')) == str(site_id)), None)
        if custom is not None or str(site_id).isdigit() or str(site_id).startswith(('600', 'custom-')):
            result = run_custom(self._runner, str(site_id), {**(custom or registry.get(site_id, {})), 'uid': self._bound_uids.get(str(site_id), '')},
                                enabled=str(site_id) in {str(value) for value in self._config.get('enabled_sites', [])},
                                read_only=read_only, trigger=trigger, action=action, config=self._config,
                                selected=str(site_id) in {str(value) for value in self._config.get('login_sites' if action == 'login' else 'sign_sites', [])})
            return asdict(result)
        reason = None
        unlock = bool(self._config.get('unlock_all_sites', False))
        # 手动签到绕过 native verified/hook 门控（调度轮仍门控）。
        manual_bypass = trigger == 'manual' and action == 'sign'
        site = registry.get(site_id, {})
        if action == 'sign' and site_id in ('darkland', 'digitalcore'):
            reason = 'signin_not_applicable'
        elif action == 'sign' and not unlock and not manual_bypass and site.get('native') and not site.get('verified'):
            reason = 'native_unverified'
        elif action == 'sign' and not unlock and not manual_bypass and site.get('native') and not site.get('hook_implemented', True):
            reason = 'hook_not_implemented'
        elif not unlock and not manual_bypass and not site.get('native') and site.get('source') != '自定义站点' and site_id not in ('rousi', 'sunnypt', 'mteam'):
            reason = 'pilot_not_enabled'
        elif not unlock and not manual_bypass and action == 'login' and not site.get('native') and site.get('source') != '自定义站点' and site_id not in ('rousi', 'sunnypt', 'mteam'):
            reason = 'pilot_not_enabled'
        elif site_id not in self._config.get('enabled_sites', []):
            reason = 'site_disabled'
        elif action == 'login' and not site.get('login_capable', True):
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
        if action != 'login' and not site.get('native') and site_id not in ('rousi', 'sunnypt', 'mteam'):
            result = SignResult(SignStatus.SKIPPED, 'skipped(site_removed)')
            result.site_id = site_id
            result.metadata.update({'reason': 'site_removed', 'trigger': trigger, 'action': action})
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
        for callback in ('get_data', 'save_data', 'del_data'):
            setattr(self._runner, callback, getattr(self, callback, None))
        if site_id in ('rousi', 'sunnypt'):
            result = run_integration(self._runner, site_id, site.get('name', site_id), info, self._config, action=action, trigger=trigger)
            return asdict(result)
        if site_id == "mteam":
            info.update({key: self._config.get(key, "") for key in ("mteam_username", "mteam_password", "mteam_totp")})
        if site.get('native') or action == 'login':
            custom_cookie = ''
            customs = self._config.get('custom_sites_data') or []
            site_dom = (site.get('url') or info.get('url') or (str(site_id) if action == 'login' else '')).split('//')[-1].split('/')[0].lower().removeprefix('www.')
            for c in customs:
                cdom = (c.get('url') or '').split('//')[-1].split('/')[0].lower().removeprefix('www.')
                if site_dom and cdom == site_dom and c.get('cookie'):
                    custom_cookie = c['cookie']
                    if action == 'login' and not site.get('native') and not info.get('url'):
                        info.update({key: c[key] for key in ('url', 'name') if key in c})
                    break
            if action == 'login':
                module = get_native_module(site_id) if site.get('native') else CustomNexusSignin(site_id, {**info, 'url': info.get('url') or ''})
                result = run_native_login(self._runner, module, info, custom_cookie=custom_cookie, trigger=trigger, config=self._config)
                return asdict(result)
            result = run_native(self._runner, get_native_module(site_id), info,
                                read_only=read_only, trigger=trigger,
                                get_data=getattr(self, "get_data", None), save_data=getattr(self, "save_data", None),
                                custom_cookie=custom_cookie, config=self._config)
            return asdict(result)

    async def api_signin_by_domain(self, domain: str = '') -> dict:
        site_id = site_id_for_domain(domain)
        if not site_id:
            site_id = next((str(item.get('id')) for item in self._config.get('custom_sites_data', [])
                            if isinstance(item, dict) and str(item.get('id')) == str(domain)), None)
        if not site_id and self._config.get('unlock_all_sites', False) and domain:
            registry_ids = {s['id'] for s in get_registry(self._config.get('custom_sites_data', []))['sites']}
            if domain in registry_ids:
                site_id = domain
        if not site_id:
            return {'success': False, 'message': '未找到可用站点', 'data': None}
        result = await asyncio.to_thread(self._execute_site, site_id)
        return {'success': True, 'data': result}

    async def api_login_by_domain(self, domain: str = '') -> dict:
        site_id = site_id_for_domain(domain, include_legacy=True)
        if not site_id:
            site_id = next((str(item.get('id')) for item in self._config.get('custom_sites_data', [])
                            if isinstance(item, dict) and (str(item.get('id')) == str(domain) or (domain and hostname(item.get('url', '')) == hostname(domain)))), None)
        if not site_id:
            site_id = next((str(value) for value in self._config.get('enabled_sites', [])
                            if hostname(str(value)) == hostname(domain)), None)
        if not site_id and self._config.get('unlock_all_sites', False) and domain:
            registry_ids = {s['id'] for s in get_registry(self._config.get('custom_sites_data', []))['sites']}
            if domain in registry_ids:
                site_id = domain
        if not site_id:
            return {'success': False, 'message': '未找到可用站点', 'data': None}
        result = await asyncio.to_thread(self._execute_site, site_id, action='login')
        return {'success': True, 'data': result}

    async def api_verify_site(self, domain: str = '') -> dict:
        site_id = site_id_for_domain(domain)
        if not site_id:
            site_id = next((str(item.get('id')) for item in self._config.get('custom_sites_data', [])
                            if isinstance(item, dict) and str(item.get('id')) == str(domain)), None)
        if not site_id and self._config.get('unlock_all_sites', False) and domain:
            registry_ids = {s['id'] for s in get_registry(self._config.get('custom_sites_data', []))['sites']}
            if domain in registry_ids:
                site_id = domain
        if not site_id:
            return {'success': False, 'message': '未找到可用站点', 'data': None}
        result = await asyncio.to_thread(self._execute_site, site_id, True)
        return {'success': True, 'data': result}

    def _execute_all(self, trigger="manual"):
        """执行完整轮次；配置保存不会终止在途轮次。"""
        self._round_active = True
        self._last_round = []
        try:
            return self._execute_all_round(trigger)
        finally:
            self._round_active = False

    def _execute_all_round(self, trigger="manual"):
        """双队列串行：先签到后登录；队列=状态表 failed/pending；单站失败当场重试 ≤ retry_count。"""
        self._recompute_track_states()
        self._track_store().rollover()
        # 仿真名单站点共用一个 CloakBrowser 会话（轮内挨个执行，省去逐站开关）。
        # 已配 token 的云签站整条走 Browserless，不占本地浏览器，不计入共享基数。
        emulated = {str(v) for v in self._config.get('site_browserless', [])
                    if not (cloudsign.enabled(str(v)) and cloudsign.configured(self._config))}
        round_sites = [str(sid) for action in ("sign", "login") for sid in self._due_for(action)]
        shared = None
        if sum(1 for sid in round_sites if sid in emulated) >= 2:
            try:
                from .core.cloak import CloakSession, _resolve_cloak_proxy, site_requires_headful
                shared = CloakSession(url='https://example.com/', headless=not any(site_requires_headful(sid) for sid in round_sites),
                                      proxy=_resolve_cloak_proxy(None, None, self._config))
                shared.__enter__()
                self._runner.shared_cloak = shared
            except Exception:
                shared = None
        try:
            results = []
            executed = []
            for action in ("sign", "login"):
                for site_id in self._due_for(action):
                    if self._runner.stop.is_set():
                        break
                    executed.append((str(site_id), action))
                    results.append(self._run_with_retry(site_id, action, trigger))
            self._last_round = executed
        finally:
            self._runner.shared_cloak = None
            if shared is not None:
                try:
                    shared.close()
                except Exception:
                    pass
        self._notify_round(trigger)
        return results

    def _due_for(self, action: str) -> list[str]:
        enabled = {str(v) for v in self._config.get('enabled_sites', [])}
        selected = {str(v) for v in self._config.get('sign_sites' if action == 'sign' else 'login_sites', [])}
        due = set(self._track_store().due_sites(action))
        return [sid for sid in dict.fromkeys(self._config.get('enabled_sites', []))
                if str(sid) in enabled and str(sid) in selected and str(sid) in due]

    def _run_with_retry(self, site_id, action, trigger):
        result = self._execute_site(site_id, trigger=trigger, action=action)
        if (result or {}).get("status") in ("skipped", "cancelled"):
            return result
        attempts = max(0, int(self._config.get("retry_count", 3) or 0))
        for _ in range(attempts):
            if self._track_store().state_of(str(site_id), action) != FAILED:
                break
            result = self._execute_site(site_id, trigger=trigger, action=action)
        return result

    def _round_summary(self) -> dict:
        """状态表当日快照与本轮实际执行集合合并为逐站通知数据。"""
        snapshot = self._track_store().snapshot()["sites"]
        enabled = {str(v) for v in self._config.get("enabled_sites", [])}
        site_rows = get_registry(self._config.get("custom_sites_data", []))["sites"]
        labels = {str(row["id"]): row.get("name", str(row["id"])) for row in site_rows}
        credential_kinds = {str(row["id"]): (row.get("credential") or {}).get("kind", "cookie")
                            for row in site_rows}
        summary = {track: {"total": 0, "executed": 0, "next": 0, "entries": []}
                   for track in ("sign", "login")}
        executed = set(self._last_round)
        for track, key in (("sign", "sign_sites"), ("login", "login_sites")):
            selected = {str(v) for v in self._config.get(key, [])}
            due = set(self._track_store().due_sites(track))
            data = summary[track]
            data["total"] = len(enabled & selected)
            data["next"] = len(enabled & selected & due)
            data["executed"] = sum(1 for site, action in executed if action == track)
            # 逐站行：本轮实际执行的站点 + 当日有待办结论的站点（failed 与 pending 均显示明细）。
            today = datetime.now().date().isoformat()
            due_today = {site for site in enabled & selected & due
                         if str(snapshot.get(site, {}).get(track, {}).get("time", "")).startswith(today)}
            shown = {site for site, action in executed if action == track} | due_today
            for site in shown:
                entry = snapshot.get(site, {}).get(track, {})
                if entry and str(entry.get("time", "")).startswith(today):
                    entry = dict(entry)
                    entry["credential"] = credential_kinds.get(site, "cookie")
                    data["entries"].append((labels.get(site, site), entry))
        for track in summary:
            summary[track]["entries"].sort(key=lambda row: row[0].casefold())
        return summary

    def _notify_round(self, trigger: str) -> None:
        """轮次结束分别推送签到与登录逐站摘要。"""
        try:
            if not self._config.get("notify"):
                return
            fmt = self._config.get("notify_format", "plain")
            summary = self._round_summary()
            rich_map = {}
            try:
                from app.schemas.notification import NotificationBlock, NotificationContent

                for key, blocks in build_rich_blocks(summary).items():
                    try:
                        rich_map[key] = NotificationContent(
                            title="【PT 签到中心】",
                            blocks=[NotificationBlock(**b) for b in blocks],
                        )
                    except Exception:
                        pass
            except Exception:
                rich_map = {}
            for track, title, text in format_round_notifications(summary, fmt):
                if track in rich_map:
                    self.post_message(title=title, text=text, parse_mode=PARSE_MODES.get(fmt),
                                      rich_content=rich_map[track])
                else:
                    self.post_message(title=title, text=text, parse_mode=PARSE_MODES.get(fmt))
        except Exception:
            pass

    async def api_run_once(self) -> dict:
        """立即运行：参考 V2，直接以独立线程执行一轮，不经宿主调度器
        （qnap 等环境宿主 APScheduler 回调可能静默不触发）。"""
        if getattr(self, "_round_active", False):
            return {"success": False, "message": "已有轮次在运行"}
        import threading

        def _worker():
            try:
                self._config["onlyonce"] = True
                self._scheduled_once()
            except Exception:
                from app.runtime.log import logger
                logger.error("【PT 签到中心】立即运行异常", exc_info=True)

        threading.Thread(target=_worker, daemon=True, name="autoptcheckin-run-once").start()
        return {"success": True, "data": {"started": True}}


    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """远程命令：立即签到 / 强制签到（清理本日缓存后全量重跑）。"""
        if EventType is None:
            return []
        return [
            {"cmd": "/checkin_now", "event": EventType.PluginAction,
             "desc": "立即签到", "category": "签到",
             "data": {"action": "checkin_now"}},
            {"cmd": "/checkin_force", "event": EventType.PluginAction,
             "desc": "强制签到", "category": "签到",
             "data": {"action": "checkin_force"}},
        ]

    def _handle_remote_command(self, event: Any) -> None:
        """PluginAction：checkin_now=立即运行；checkin_force=先清本日缓存再全量运行。"""
        if not event or EventType is None:
            return
        data = getattr(event, "event_data", None) or {}
        action = data.get("action")
        if action not in ("checkin_now", "checkin_force"):
            return
        if getattr(self, "_round_active", False):
            return
        import threading

        def _worker():
            try:
                if action == "checkin_force":
                    self._history.clear_today()
                    self._track_store().clear_transient()
                self._config["onlyonce"] = True
                self._scheduled_once()
            except Exception:
                from app.runtime.log import logger
                logger.error(f"【PT 签到中心】远程命令 {action} 执行异常", exc_info=True)

        threading.Thread(target=_worker, daemon=True, name="autoptcheckin-remote-command").start()

    def _register_commands(self) -> None:
        """init_plugin 时注册远程命令监听（幂等）。"""
        if eventmanager is None or EventType is None:
            return
        if getattr(self.__class__, "_command_registered", False):
            return
        eventmanager.register(EventType.PluginAction)(self._handle_remote_command)
        self.__class__._command_registered = True
    async def api_clean_today(self) -> dict:
        """清理本日缓存：清当日历史，并把状态表非禁用轨道重置为 pending（强制今天重跑）。"""
        removed = await asyncio.to_thread(self._history.clear_today)
        self._track_store().clear_transient()
        return {"success": True, "data": {"removed": removed}}

    def _scheduled_once(self):
        """一次性执行（立即签到/立即运行一次）不受 scheduler_enabled 门控，直接全量执行。"""
        stop_before = self._runner.stop.is_set()
        with self._migration.lock:
            if not self._config.get("onlyonce", False):
                return
            self._config["onlyonce"] = False
            if hasattr(self, "update_config"):
                self.update_config(deepcopy(self._config))
            self._scheduler.clear()
        # update_config 触发宿主任务重建时会回调 stop_service 置位 stop；
        # 这不是真实取消（round 尚未开始），恢复进入前状态，否则一次性执行必被拦。
        if not stop_before and self._runner.stop.is_set():
            self._runner.stop.clear()
        try:
            return self._execute_all("scheduler")
        finally:
            # once 消费后宿主已移除该服务且 reconcile 不会重召零任务插件：
            # 主动重建 interval 服务并通知宿主重注册（否则次日 9:00 槽丢失）。
            try:
                self._scheduler.clear()
                self._scheduler.build(self._config, self._scheduled_signin)
                if self._scheduler.services:
                    from app.sdk.scheduler import update_plugin_job
                    update_plugin_job(self.plugin_id)
            except Exception:
                pass

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
