# -*- coding: utf-8 -*-
"""PT 签到中心 V3：PT 站点签到、登录与回读。"""
import json
import asyncio
import threading
from datetime import datetime
from dataclasses import asdict
from .core.scheduler import Scheduler
from .core.runner import SignRunner
from .core.models import SignResult, SignStatus, unify_result
from .core.state_store import RAW_RESULT_STATUSES
from .core.registry import managed_site, site_id_for_domain, hostname
from pathlib import Path
from copy import deepcopy
from .core.history import HistoryStore, IconCacheDB
from .core.migration import Migration, MigrationError
from .core.registry import get_registry, get_native_module, builtin_site_ids
from .core import cloudsign
from .core.cloudsign import CLOUD_SITES
from .core.siteconf import resolve as resolve_site_flags
from .core.native import run_native, run_native_login, run_integration
from .core.custom import run_custom, CustomNexusSignin
from .core.state_store import DISABLED, FAILED, GATE_SKIPS, PENDING, SUCCESS, TrackStateStore
from .core.notify import format_round_notifications
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
    plugin_version = "4.3.8"
    plugin_author = "wuyaos"
    plugin_config_prefix = "autoptcheckin_"

    SITE_KEYS = ("enabled_sites", "paused_sites", "sign_sites", "login_sites", "site_proxy", "site_emulate",
                 "site_cloudsign", "custom_sites_data",
                 "rousi_username", "rousi_password", "sunnypt_username",
                 "sunnypt_password", "sunnypt_token", "mteam_username", "mteam_password", "mteam_totp",
                 "yzyy_username", "yzyy_password",
                 "ourbits_username", "ourbits_password", "ourbits_totp")

    def __init__(self):
        super().__init__()
        self._scheduler = None
        self._migration = Migration(self)
        self._running = False
        self._config: dict[str, Any] = {}
        self._site_config: dict[str, Any] = {}
        self._runner = SignRunner(history=self._record_result)
        data_dir = getattr(self, "get_data_path", None)
        db_path = data_dir() / "autoptcheckin.db" if data_dir else None
        self._history = HistoryStore(getattr(self, "get_data", None), getattr(self, "save_data", None), db_path=db_path)
        self._icons = IconCacheDB(db_path)
        self._state = None
        self._last_round_results = {}
        self._round_active = False
        self._round_lock = threading.Lock()

    def init_plugin(self, config: dict | None = None) -> None:
        # 本地库迁移必须先于 _init_config：track.state 为空/损坏时 _init_config 会
        # rebuild_from_history 读本地库，若迁移未跑读到空表，已成功站点全部标 pending
        # 下一轮被重复签到（reviewer fc08b8c1 P1-2）。迁移不依赖 _init_config 产物。
        self._migrate_local_store()
        # 宿主配置中心路径无法在保存前校验（PluginConfigService.update 先持久化再
        # init，P1-1）：非法调度配置在此拒绝应用并保留现有配置继续运行，宿主存储中
        # 的非法值由用户在配置页改正；插件不因非法保存进入 invalid_schedule 无任务态。
        if config:
            try:
                self._validate_schedule({**deepcopy(getattr(self, "_config", {}) or {}), **deepcopy(config)})
            except ValueError as exc:
                try:
                    from app.runtime.log import logger as _mp_logger
                    _mp_logger.warning(f'【PT 签到中心】忽略非法调度配置，保留现有配置运行：{exc}')
                except ImportError:
                    pass
                config = deepcopy(getattr(self, "_config", None))
        # 宿主配置保存走 init_plugin（PluginConfigCommand.update）；在途轮次同样保护，
        # 否则 _init_config 默认的 stop_service 会打断运行中的队列（reviewer 3b24554a P1-2）。
        with self._migration.lock:
            self._init_config(config, preserve_round=self._round_active)
        self._register_commands()
        # 完整注册同步（4.1.0）：宿主 update_plugin_job 自带「detach 未触发 once →
        # remove 全部 → 重新注册」（reconcile.py:418-428），任何路径 init 完成后
        # 宿主任务必须等于当前配置；不在此显式 remove，避免绕过 live once 保留语义。
        self._sync_jobs()

    def _sync_jobs(self) -> None:
        """按当前 get_service 重建宿主任务；仅在无宿主调度 SDK（单测/离线）时跳过。"""
        try:
            from app.sdk.scheduler import update_plugin_job
        except ImportError:
            return
        update_plugin_job(self.plugin_id)

    def _migrate_local_store(self) -> None:
        """一次性迁移：宿主 plugindata 的 history/icon JSON 与 V2 时代按日 key → 本地 SQLite。

        幂等：源 key 不存在即跳过；日期 key 候选枚举（宿主无 list API）逐个探删。
        """
        if self._icons.get_flag("migrated:localstore"):
            return
        get_dp = getattr(self, "get_data_path", None)
        if not get_dp:
            return
        try:
            migrated = []
            records = self.get_data("history.records")
            if records:
                migrated.append(f"history.records:{self._history.import_json(get_dp() / 'autoptcheckin.db', records)}")
                self.del_data("history.records")
            icons = self.get_data("icon.cache")
            if icons:
                migrated.append(f"icon.cache:{self._icons.import_json(get_dp() / 'autoptcheckin.db', icons)}")
                self.del_data("icon.cache")
            purged = 0
            for month in range(1, 13):
                for day in range(1, 32):
                    key = f"{month}月{day}日"
                    if self.get_data(key) is not None:
                        self.del_data(key)
                        purged += 1
            self._icons.set_flag("migrated:localstore")
            if migrated or purged:
                try:
                    from app.runtime.log import logger as _mp_logger
                    _mp_logger.info(f'【PT 签到中心】本地库迁移完成：{", ".join(migrated) or "无"}，清理遗留按日 key {purged} 个')
                except ImportError:
                    pass
        except Exception as exc:  # 迁移失败不阻塞插件启动，下次启动重试
            try:
                from app.runtime.log import logger as _mp_logger
                _mp_logger.warning(f'【PT 签到中心】本地库迁移跳过：{type(exc).__name__}: {exc}')
            except ImportError:
                pass

    def _init_config(self, config: dict | None = None, preserve_round: bool = False) -> None:
        disabling = bool(self._config.get("enabled")) and not bool((config or {}).get("enabled"))
        if preserve_round:
            if disabling:
                self.stop_service()
        else:
            self.stop_service()
            self._runner.stop.clear()
        # 全量替换（迁移恢复要求精确回滚）；partial 保护由 _save_config 合并承担。
        self._config = deepcopy(config or {})
        self._normalize_site_keys(self._config)
        self._running = bool(self._config.get("enabled", False))
        if hasattr(self, "get_data"):
            self._site_config = self.get_data("site_config") or {}
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
        if not self._config.get("scheduler_enabled", False):
            try:
                from app.runtime.log import logger as _mp_logger
                _mp_logger.warning('【PT 签到中心】调度开关未启用（scheduler_enabled=False），不注册定时服务')
            except ImportError:
                pass

        store = self._track_store()
        if not store.snapshot()["sites"]:
            # 首次/损坏重建：从最近历史派生初始结论（历史层已把 already 归一为 signed）。
            store.rebuild_from_history(self._recent_records())
        store.rollover()
        self._recompute_track_states()

    @staticmethod
    def _normalize_site_keys(config: dict) -> None:
        """站点级键就地归一化：列表键 str+去重（site_cloudsign 仅保留有实现的能力站），
        覆盖表键转 str、值转 bool。未配置的键不凭空创建。"""
        config.pop("onlyonce", None)
        for key in ("enabled_sites", "paused_sites", "sign_sites", "login_sites", "site_cloudsign"):
            values = config.get(key)
            if isinstance(values, list):
                config[key] = list(dict.fromkeys(str(v) for v in values))
        if isinstance(config.get("site_cloudsign"), list):
            # 云签仅保留已实现站点：塞入任意其他 ID 的脏项静默忽略，不保留。
            config["site_cloudsign"] = [v for v in config["site_cloudsign"] if v in CLOUD_SITES]
        for key in ("site_proxy", "site_emulate"):
            values = config.get(key)
            if isinstance(values, dict):
                config[key] = {str(k): bool(v) for k, v in values.items()}

    def _apply_effective_flags(self, site: dict) -> None:
        """把有效执行配置写入站点响应副本：proxy/emulate 有效 bool、云签能力与实际选择。

        声明 emulate 只作缺键继承来源（不反写注册表声明）；云签徽标（shield=cloud）
        仅在用户实际选择时显示，未选中但有仿真时回退仿真徽标。
        """
        flags = resolve_site_flags(site.get("id"), self._config,
                                   declared_emulate=bool(site.get("emulate")),
                                   mp_proxy=bool(site.get("mp_proxy")),
                                   mp_render=bool(site.get("mp_render")),
                                   cloudsign_capable=site.get("cloudsign_capable"))
        site["proxy"] = flags["proxy"]
        site["emulate"] = flags["emulate"]
        site["cloudsign_capable"] = flags["cloudsign_capable"]
        site["cloudsign_selected"] = flags["cloudsign_selected"]
        site["shield"] = "cloud" if flags["cloudsign_selected"] else ("emulate" if flags["emulate"] else None)

    def get_state(self) -> bool:
        return self._running

    def get_service(self) -> list:
        # 不以 stop 门控注册：宿主任何 stop_service（重建/重载）都会置位 stop，
        # 若在此返回空列表，宿主将移除全部服务且再无调度器去清除 stop（死锁）。
        # stop 只用于中断在途执行；注册始终按当前配置给出。
        if self._scheduler is None:
            return []
        if self._scheduler.services:
            return list(self._scheduler.services)
        return self._scheduler.build(self._config, self._scheduled_signin)

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
            {"path": "/notify_test", "endpoint": self.api_notify_test, "methods": ["POST"]},
            {"path": "/site_track", "endpoint": self.api_site_track, "methods": ["POST"]},
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
        try:
            await asyncio.to_thread(self._save_config, config)
        except ValueError as exc:
            return {"success": False, "message": str(exc), "data": None}
        return {"success": True, "data": None}

    def _save_config(self, config: dict) -> None:
        with self._migration.lock:
            round_active = self._round_active
            # 合并语义：partial body 不得静默重置既有键（对齐 forumsignin 惯例）。
            merged = {**deepcopy(getattr(self, "_config", {})), **deepcopy(config or {})}
            merged.pop("onlyonce", None)
            self._purge_custom_overrides(merged)
            self._validate_schedule(merged)
            self.update_config(merged)
            # SDK update_config 仅持久化；不可清除写入期间到达的真实取消信号。
            self._init_config(merged, preserve_round=round_active)
            self._sync_jobs()

    def _purge_custom_overrides(self, merged: dict) -> None:
        """删除 custom 条目时同步清理 site_emulate/site_proxy 的对应覆盖脏项，
        防止 ID 复用后脏项静默为新站开启仿真/代理；内置与未知 ID 一律不清。"""
        if "custom_sites_data" not in merged:
            return
        old_ids = {str(item.get("id")) for item in (getattr(self, "_config", {}) or {}).get("custom_sites_data", [])
                   if isinstance(item, dict) and item.get("id")}
        new_ids = {str(item.get("id")) for item in merged.get("custom_sites_data", [])
                   if isinstance(item, dict) and item.get("id")}
        removed = old_ids - new_ids
        if not removed:
            return
        builtin = builtin_site_ids()
        for key in ("site_emulate", "site_proxy"):
            overrides = merged.get(key)
            if not isinstance(overrides, dict):
                continue
            cleaned = {k: v for k, v in overrides.items() if not (k in removed and k not in builtin)}
            if cleaned != overrides:
                merged[key] = cleaned

    @staticmethod
    def _validate_schedule(config: dict) -> None:
        """保存前校验调度配置：非法 cron/interval 直接拒绝，避免保存成功但 build 全失败、宿主无任务。"""
        mode = config.get("cron_mode", "interval")
        if mode == "cron":
            from apscheduler.triggers.cron import CronTrigger
            expr = str(config.get("cron", "")).strip()
            try:
                CronTrigger.from_crontab(expr)
            except Exception as exc:
                raise ValueError(f"cron 表达式非法：{expr!r}（{exc}）") from exc
            return
        if mode == "interval":
            interval = float(config.get("interval_hours", 2))
            begin, end = int(config.get("begin_hour", 8)), int(config.get("end_hour", 24))
            import math
            if not math.isfinite(interval) or interval < 0.5 or not 0 <= begin < end <= 24:
                raise ValueError("interval 窗口非法：需 interval>=0.5 且 0<=开始<结束<=24")
            return
        raise ValueError(f"未知调度模式：{mode!r}")

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

    def _registry(self) -> dict:
        """站点注册表：自定义站签到能力跟随 dialog 勾选（sign_sites）。"""
        return get_registry(self._config.get('custom_sites_data', []),
                            sign_sites=self._config.get('sign_sites', []))

    async def api_sites(self) -> dict:
        registry = self._registry()
        sites = deepcopy(registry["sites"])
        icon_cache = self._icons.all()
        pending_icons = []
        for site in sites:
            site.setdefault('cf', 'unknown')
            self._apply_effective_flags(site)
            sid = str(site.get('id', ''))
            if not site.get('icon') and icon_cache.get(sid):
                site['icon'] = icon_cache[sid]
            # 自定义站点同样解析图标；失败写 '' 占位，避免每次 /sites 都重试同一批 URL。
            if (not site.get('icon') and icon_cache.get(sid) is None and site.get('url')):
                pending_icons.append((sid, site['url']))
        if pending_icons:
            # 后台异步解析：/sites 立即返回（icon 空），解析完写缓存，下次打开命中。
            # 不在请求内等待——MP 重启后缓存全空时即使并发也要等最慢单站（8s 超时）。
            import threading

            def _resolve_batch(cache: dict, pairs: list, plugin):
                for sid, url in pairs:
                    cache[sid] = plugin._resolve_favicon(url) or ''
                plugin._icons.put_many({sid: cache[sid] for sid, _ in pairs})

            threading.Thread(target=_resolve_batch, args=(icon_cache, pending_icons, self), daemon=True).start()
            for sid, _ in pending_icons:
                icon_cache[sid] = ''

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
        # 三卡：成功/失败=启用勾选轨道的今日结论；待处理=有效队列 pending（含未执行）。
        today = datetime.now().date().isoformat()
        latest = {}
        for track in ("sign", "login"):
            buckets = {"success": 0, "failed": 0, "pending": 0}
            for row in rows:
                if row.get("site_paused") or not row.get(f"{track}_selected"):
                    continue
                state = row.get(f"{track}_state")
                if state == PENDING:
                    # 未执行或 pending 结论均为有效队列待办；无能力/门控站不会处于 pending。
                    if row.get(f"{track}_track_available", True):
                        buckets["pending"] += 1
                elif state in (SUCCESS, FAILED) and str(row.get(f"{track}_time", "")).startswith(today):
                    buckets["success" if state == SUCCESS else "failed"] += 1
            latest[track] = buckets
        return {"success": True, "data": {"latest": latest,
                "next_schedule": self._next_schedule(), "schedule_status": self._schedule_status(), "schedule": schedule, "sites": rows,
                "sign_sites": [str(v) for v in self._config.get("sign_sites", [])],
                "login_sites": [str(v) for v in self._config.get("login_sites", [])]}}

    def _site_rows(self) -> list[dict]:
        """数据页站点行：状态表提供轨道状态，registry 提供元数据与控制位。"""
        registry = self._registry()['sites']
        enabled = {str(v) for v in self._config.get('enabled_sites', [])}
        paused = {str(v) for v in self._config.get('paused_sites', [])}
        sign_sel = {str(v) for v in self._config.get('sign_sites', [])}
        login_sel = {str(v) for v in self._config.get('login_sites', [])}
        rows = []
        icon_cache = self._icons.all()
        for site in registry:
            sid = str(site['id'])
            # 卡片严格随配置：仅显示启用站点。
            if sid not in enabled:
                continue
            self._apply_effective_flags(site)
            sign = self._track_store().entry_of(sid, 'sign')
            login = self._track_store().entry_of(sid, 'login')
            cf_markers = ('cf-chl', 'cloudflare', 'just a moment', 'verify you are human', 'challenge-platform')
            latest_messages = f"{sign.get('message', '')} {login.get('message', '')}".lower()
            cf_hit = any(marker in latest_messages for marker in cf_markers)
            icon = site.get('icon', '') or icon_cache.get(sid, '')
            rows.append({'id': sid, 'name': site.get('name', sid), 'url': site.get('url', ''),
                'icon': icon, 'source': site.get('source', ''),
                'cf': True if cf_hit else site.get('cf', 'unknown'),
                'emulate': site['emulate'], 'proxy': site['proxy'],
                'cloudsign_capable': site['cloudsign_capable'],
                'cloudsign_selected': site['cloudsign_selected'],
                'shield': site['shield'],
                                'sign_state': sign.get('state', 'disabled' if sid not in enabled else 'pending'),
                'sign_status': sign.get('status', ''), 'sign_reason': sign.get('reason', ''),
                'sign_time': sign.get('time', ''),
                'sign_message': sign.get('message', ''),
                'page_action': (sign.get('metadata') or {}).get('page_action'),
                'login_state': login.get('state', 'disabled' if sid not in enabled else 'pending'),
                'login_status': login.get('status', ''), 'login_reason': login.get('reason', ''),
                'login_time': login.get('time', ''),
                'login_message': login.get('message', ''),
                'enabled': sid in enabled, 'site_paused': sid in paused,
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
        """记录边界：history 与状态表共用同一 unify_result 映射（与 API 载荷一致，
        不会出现 API 已归一而记录/重试仍看旧值）。原细分 reason 保留在 metadata。"""
        self._history.append(result)
        metadata = getattr(result, "metadata", None) or {}
        raw_status = getattr(getattr(result, "status", None), "value", "")
        status, reason = unify_result(raw_status, metadata.get("reason"))
        if raw_status not in RAW_RESULT_STATUSES and raw_status != status and raw_status:
            # 未知原始值归 pending：原值保留在 metadata，不进入状态/统计口径。
            metadata.setdefault("raw_status", raw_status)
        # read_only 核验不改表；纯空转（锁忙/取消）只写历史；门控类 skip（带 reason）写 disabled，
        # 否则门控站停留 FAILED 会被当场重试并在每轮重复执行。
        gate_skip = status in ("skipped", "cancelled") and (reason or "") in GATE_SKIPS
        if not metadata.get("read_only") and (status not in ("skipped", "cancelled") or gate_skip):
            diag = {k: metadata[k] for k in ("page_action", "steps", "error", "raw_status") if k in metadata}
            self._track_store().apply_result(
                str(result.site_id), metadata.get("action", "sign"), status,
                message=getattr(result, "message", "") or "", reason=reason or None,
                metadata=diag or None)

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
        for site in self._registry()["sites"]:
            sid = str(site["id"])
            if sid in {str(v) for v in self._config.get("paused_sites", [])}:
                continue
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
            elif not site.get("signin_capable", False):
                decisions[sid]["sign"] = (DISABLED, "signin_not_applicable")
            else:
                # 启用并勾选即允许执行：verified/hook/legacy 审批门控已移除，
                # 旧审批 reason 仍由 state_store 兼容（历史记录不重写）。
                decisions[sid]["sign"] = (PENDING, None)
            if sid not in login_sel or site.get("login_capable") is False:
                decisions[sid]["login"] = (DISABLED, "login_not_selected" if sid not in login_sel else "login_not_supported")
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
        """执行与返回的统一边界：API/轮次载荷在此归一（status 统一值 + reason 精确值），
        适配器内部原始值不动。"""
        return self._unify_payload(
            self._execute_site_raw(site_id, read_only=read_only, trigger=trigger, action=action))

    @staticmethod
    def _unify_payload(result):
        if not isinstance(result, dict):
            return result
        raw = result.get("status")
        status, reason = unify_result(raw, result.get("reason",
                                      (result.get("metadata") or {}).get("reason")))
        result["status"] = status
        if reason:
            result["reason"] = reason
        metadata = result.setdefault("metadata", {})
        if raw not in RAW_RESULT_STATUSES and raw != status and raw:
            # 未知原始值归 pending 时保留原值供排障。
            metadata.setdefault("raw_status", raw)
        return result

    def _execute_site_raw(self, site_id, read_only=False, trigger="manual", action="sign"):
        for callback in ('get_data', 'save_data', 'del_data'):
            setattr(self._runner, callback, getattr(self, callback, None))
        registry = {site['id']: site for site in self._registry()['sites']}
        # “今日已签”由状态表 success 态承担：成功站不进队列，这里不再重复拦截。
        custom = next((item for item in self._config.get('custom_sites_data', [])
                       if isinstance(item, dict) and str(item.get('id')) == str(site_id)), None)
        if str(site_id) in {str(v) for v in self._config.get('paused_sites', [])}:
            return asdict(SignResult.skipped('site_paused'))
        if custom is not None or str(site_id).isdigit() or str(site_id).startswith(('600', 'custom-')):
            result = run_custom(self._runner, str(site_id), dict(custom or registry.get(site_id, {})),
                                enabled=str(site_id) in {str(value) for value in self._config.get('enabled_sites', [])},
                                read_only=read_only, trigger=trigger, action=action, config=self._config,
                                selected=str(site_id) in {str(value) for value in self._config.get('login_sites' if action == 'login' else 'sign_sites', [])})
            return asdict(result)
        reason = None
        site = registry.get(site_id, {})
        if action == 'sign' and site_id in ('darkland', 'digitalcore'):
            reason = 'signin_not_applicable'
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
        if site_id in ('rousi', 'sunnypt'):
            result = run_integration(self._runner, site_id, site.get('name', site_id), info, self._config, action=action, trigger=trigger)
            return asdict(result)
        if site_id == "mteam":
            info.update({key: self._config.get(key, "") for key in ("mteam_username", "mteam_password", "mteam_totp")})
        if site_id == "ourbits":
            info.update({key: self._config.get(key, "") for key in ("ourbits_username", "ourbits_password", "ourbits_totp")})
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
        if not site_id and domain:
            registry_ids = {s['id'] for s in self._registry()['sites']}
            if domain in registry_ids:
                site_id = domain
        if not site_id:
            return {'success': False, 'message': '未找到可用站点', 'data': None}
        if str(site_id) in {str(v) for v in self._config.get("paused_sites", [])}:
            return {'success': False, 'message': '站点已暂停执行', 'data': None}
        result = await asyncio.to_thread(self._execute_site, site_id)
        return {'success': True, 'data': result}

    async def api_login_by_domain(self, domain: str = '') -> dict:
        site_id = site_id_for_domain(domain)
        if not site_id:
            site_id = next((str(item.get('id')) for item in self._config.get('custom_sites_data', [])
                            if isinstance(item, dict) and (str(item.get('id')) == str(domain) or (domain and hostname(item.get('url', '')) == hostname(domain)))), None)
        if not site_id:
            site_id = next((str(value) for value in self._config.get('enabled_sites', [])
                            if hostname(str(value)) == hostname(domain)), None)
        if not site_id and domain:
            registry_ids = {s['id'] for s in self._registry()['sites']}
            if domain in registry_ids:
                site_id = domain
        if not site_id:
            return {'success': False, 'message': '未找到可用站点', 'data': None}
        if str(site_id) in {str(v) for v in self._config.get("paused_sites", [])}:
            return {'success': False, 'message': '站点已暂停执行', 'data': None}
        result = await asyncio.to_thread(self._execute_site, site_id, action='login')
        return {'success': True, 'data': result}

    async def api_verify_site(self, domain: str = '') -> dict:
        site_id = site_id_for_domain(domain)
        if not site_id:
            site_id = next((str(item.get('id')) for item in self._config.get('custom_sites_data', [])
                            if isinstance(item, dict) and str(item.get('id')) == str(domain)), None)
        if not site_id and domain:
            registry_ids = {s['id'] for s in self._registry()['sites']}
            if domain in registry_ids:
                site_id = domain
        if not site_id:
            return {'success': False, 'message': '未找到可用站点', 'data': None}
        result = await asyncio.to_thread(self._execute_site, site_id, True)
        return {'success': True, 'data': result}

    def _execute_all(self, trigger="manual", _lock_held=False):
        """执行完整轮次；配置保存不会终止在途轮次。"""
        if not _lock_held and not self._round_lock.acquire(blocking=False):
            return None
        self._round_active = True
        try:
            return self._execute_all_round(trigger)
        finally:
            self._round_active = False
            if not _lock_held:
                self._round_lock.release()

    def _execute_all_round(self, trigger="manual"):
        """双队列串行：先签到后登录；队列=状态表 failed/pending；单站失败当场重试 ≤ retry_count。"""
        self._last_round_results = {}
        self._recompute_track_states()
        self._track_store().rollover()
        # 每站客户端由独立 actor 创建、操作和关闭浏览器；不跨线程共享上下文。
        results = []
        for action in ("sign", "login"):
            for site_id in self._due_for(action):
                if self._runner.stop.is_set():
                    break
                result = self._run_with_retry(site_id, action, trigger)
                results.append(result)
                # 锁忙/取消等空转不算实际执行，通知不得把旧成功快照当本轮结论。
                if (result or {}).get("status") not in ("skipped", "cancelled"):
                    self._last_round_results[(str(site_id), action)] = deepcopy(result)
        self._notify_round(trigger)
        return results

    def _due_for(self, action: str) -> list[str]:
        selected = {str(v) for v in self._config.get('sign_sites' if action == 'sign' else 'login_sites', [])}
        paused = {str(v) for v in self._config.get('paused_sites', [])}
        sites = self._registry()['sites']
        if action == 'sign':
            capable = {str(site['id']) for site in sites
                       if site.get('signin_capable', False)}
        else:
            capable = {str(site['id']) for site in sites if site.get('login_capable') is not False}
        due = set(self._track_store().due_sites(action)) & selected & capable
        return [sid for sid in dict.fromkeys(self._config.get('enabled_sites', [])) if str(sid) in due and str(sid) not in paused]

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
        """本轮结果固定快照；当日待办仅补明细，下轮数直接复用执行队列。"""
        snapshot = self._track_store().snapshot()["sites"]
        enabled = {str(v) for v in self._config.get("enabled_sites", [])}
        paused = {str(v) for v in self._config.get("paused_sites", [])}
        sites = self._registry()["sites"]
        labels = {str(row["id"]): row.get("name", str(row["id"])) for row in sites}
        credentials = {str(row["id"]): (row.get("credential") or {}).get("kind", "cookie") for row in sites}
        today = datetime.now().date().isoformat()
        summary = {}
        for track in ("sign", "login"):
            selected = {str(v) for v in self._config.get(f"{track}_sites", [])} - paused
            due = set(self._due_for(track))
            current = {sid: dict(result) for (sid, action), result in self._last_round_results.items() if action == track}
            shown = {sid: dict(snapshot.get(sid, {}).get(track, {})) for sid in due
                     if str(snapshot.get(sid, {}).get(track, {}).get("time", "")).startswith(today)}
            shown.update(current)
            entries = []
            round_entries = []
            for sid, result in sorted(shown.items(), key=lambda item: labels.get(item[0], item[0]).casefold()):
                result["credential"] = credentials.get(sid, "cookie")
                row = (labels.get(sid, sid), result)
                entries.append(row)
                if sid in current:
                    round_entries.append(row)
            summary[track] = {"total": len(enabled & selected), "executed": len(current),
                              "next": len(due), "entries": entries, "round_entries": round_entries}
        return summary

    def _notify_round(self, trigger: str) -> None:
        """轮次结束分别推送签到与登录逐站摘要（纯文本，成功/失败分节）。"""
        try:
            if not self._config.get("notify"):
                return
            summary = self._round_summary()
            if not any(data["executed"] for data in summary.values()):
                return
            for track, title, text in format_round_notifications(summary):
                self.post_message(title=title, text=text)
        except Exception:
            from app.runtime.log import logger
            logger.error("【PT 签到中心】轮次通知发送失败", exc_info=True)

    async def api_site_track(self, domain: str = '', track: str = '', on: int = 0) -> dict:
        """数据页快捷开关：增删站点在 sign_sites/login_sites 的轨道选择（站点保持启用）。"""
        site_id = site_id_for_domain(domain) or (domain or '').strip()
        enabled = {str(v) for v in self._config.get('enabled_sites', [])}
        if track not in ('sign', 'login') or site_id not in enabled:
            return {"success": False, "message": "站点未启用或参数无效", "data": None}
        key = f"{track}_sites"
        ids = [str(v) for v in self._config.get(key, [])]
        if bool(on) == (site_id in ids):
            return {"success": True, "data": {"track": track, "on": bool(on)}}
        ids = [*ids, site_id] if bool(on) else [v for v in ids if v != site_id]
        await asyncio.to_thread(self._save_config, {**deepcopy(self._config), key: ids})
        return {"success": True, "data": {"track": track, "on": bool(on)}}

    async def api_notify_test(self) -> dict:
        """发送测试通知（不受「发送通知」开关限制，验证渠道连通）。"""
        try:
            messages = format_round_notifications(self._round_summary())
        except Exception as exc:
            return {"success": False, "message": f"构造测试通知失败: {exc}", "data": None}
        if not messages:
            return {"success": False, "message": "暂无可通知数据，请先完成一轮签到", "data": None}
        sent = []
        for track, title, text in messages:
            try:
                self.post_message(title=title, text=text)
            except Exception as exc:
                return {"success": False, "message": f"通知发送失败: {exc}", "data": sent}
            sent.append(track)
        return {"success": True, "message": f"已发送 {len(sent)} 条测试通知", "data": sent}

    async def api_run_once(self) -> dict:
        """立即运行：参考 V2，直接以独立线程执行一轮，不经宿主调度器
        （qnap 等环境宿主 APScheduler 回调可能静默不触发）。"""
        if not self._round_lock.acquire(blocking=False):
            return {"success": False, "message": "已有轮次在运行"}
        if self._runner.stop.is_set():
            self._round_lock.release()
            return {"success": False, "message": "任务已停止，请重新启用或保存配置后再运行"}
        self._round_active = True
        import threading

        def _worker():
            try:
                self._execute_all("manual", _lock_held=True)
            except Exception:
                from app.runtime.log import logger
                logger.error("【PT 签到中心】立即运行异常", exc_info=True)
            finally:
                self._round_active = False
                self._round_lock.release()

        try:
            threading.Thread(target=_worker, daemon=True, name="autoptcheckin-run-once").start()
        except Exception:
            self._round_active = False
            self._round_lock.release()
            raise
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
        if not self._round_lock.acquire(blocking=False):
            return
        self._round_active = True
        import threading

        def _worker():
            try:
                if self._runner.stop.is_set():
                    return
                if action == "checkin_force":
                    self._history.clear_today()
                    self._track_store().clear_transient()
                self._execute_all("manual", _lock_held=True)
            except Exception:
                from app.runtime.log import logger
                logger.error(f"【PT 签到中心】远程命令 {action} 执行异常", exc_info=True)
            finally:
                self._round_active = False
                self._round_lock.release()

        try:
            threading.Thread(target=_worker, daemon=True, name="autoptcheckin-remote-command").start()
        except Exception:
            self._round_active = False
            self._round_lock.release()
            raise
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


    def _scheduled_signin(self):
        with self._migration.lock:
            if self._runner.stop.is_set() or not self._config.get("scheduler_enabled", False):
                return
            if not self._running:
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
        # 本地库连接不在此关闭（reviewer fc08b8c1 P2，评估后不修）：宿主没有独立的
        # 卸载钩子，配置保存也走 init_plugin→stop_service，关闭后 append/list 会因
        # _conn=None 静默失效，惰性重开的复杂度不值；句柄靠 GC 释放无正确性影响。
        try:
            from app.sdk.scheduler import remove_plugin_job
        except ImportError:
            return
        remove_plugin_job(self.plugin_id)
