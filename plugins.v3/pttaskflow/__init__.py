"""PtTaskFlow：Task / Control / Unit / Site 声明式 PT 站点任务流（V3 前端版）。"""
import logging
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.db.oper import SiteOper
from app.sdk.events import Event, eventmanager
from app.sdk.plugin import _PluginBase
from app.schemas.types import EventType

logger = logging.getLogger("PtTaskFlow")

from .core.config import (
    PluginConfig,
    filter_stale_site_ids,
    migrate_legacy_config,
)
from .core.cookie_cache import CookieCache, cookiecloud_cookies
from .core.engine import TaskEngine
from .core.history import HistoryStore
from .core.notify import send_summary
from .core.scheduler import TaskScheduler
from .sites import match_site
from .ui.form import build_form
from .ui.page import build_page


class PtTaskFlow(_PluginBase):
    plugin_name = "PT任务流"
    plugin_desc = "自动执行 PT 站点喊话、申领、勋章和抽奖任务"
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/pttaskflow.png"
    plugin_version = "1.0.8"
    plugin_author = "wuyaos"
    author_url = "https://github.com/wuyaos"
    plugin_config_prefix = "pttaskflow_"
    plugin_id = "PtTaskFlow"
    plugin_order = 25
    auth_level = 2

    def __init__(self):
        super().__init__()
        self.config = PluginConfig()
        self.raw_config = {}
        self.siteoper = None
        self._cookiecloud_cache = CookieCache()
        self._stop_event = threading.Event()
        self._zm_retry_at = None
        self.history = HistoryStore(self)
        self.engine = TaskEngine(self)

    def init_plugin(self, config: Optional[dict] = None):
        self.siteoper = SiteOper()
        manual_requested = bool((config or {}).get("onlyonce", False))
        self.raw_config = migrate_legacy_config(config or {})
        self.raw_config.pop("onlyonce", None)
        self.config = PluginConfig.from_dict(self.raw_config)
        self.raw_config = self._clean_config(self.raw_config)
        self.config = PluginConfig.from_dict(self.raw_config)
        self._stop_event = threading.Event()
        self.engine = TaskEngine(self)
        if config is not None and self.raw_config != config:
            self.update_config(self.raw_config)
        if manual_requested and self.config.enabled:
            threading.Thread(target=self.run_manual, daemon=True,
                             name="pttaskflow_manual").start()

    def _clean_config(self, raw):
        site_ids = list(raw.get("site_ids") or [])
        try:
            valid_site_ids = {
                self._site_dict(site).get("id")
                for site in self.siteoper.list_order_by_pri()
                if not getattr(site, "public", False)
            }
        except Exception as error:
            logger.warning(f"[PtTaskFlow] [配置] 站点表读取失败，保留现有站点 id：{error}")
        else:
            valid_site_ids.add("builtin_vclib")
            cleaned_site_ids = filter_stale_site_ids(site_ids, valid_site_ids)
            removed_site_count = len(site_ids) - len(cleaned_site_ids)
            if removed_site_count:
                logger.info(f"[PtTaskFlow] [配置] 清理 {removed_site_count} 个失效站点 id")
                site_ids = cleaned_site_ids
                raw["site_ids"] = site_ids

        valid = set(PluginConfig.__dataclass_fields__)
        valid.update({"task_" + str(site_id) + "_" + str(name)
                      for site_id in site_ids for name in (
                          "daily_shotbox", "claim", "buy_medal",
                          "daily_lottery", "daily_exchange",
                      )})
        for option in self.available_site_options():
            site = self.build_site(option["site"])
            for task in site.tasks:
                valid.update(control.key for control in task.controls(site))
        removed = set(raw) - valid
        if removed:
            logger.info(f"[PtTaskFlow] [配置] 清理 {len(removed)} 个失效字段")
        return {key: value for key, value in raw.items() if key in valid}

    @staticmethod
    def _site_dict(site):
        if isinstance(site, dict):
            result = dict(site)
        else:
            result = {
                "id": getattr(site, "id", None), "name": getattr(site, "name", ""),
                "domain": getattr(site, "domain", ""), "url": getattr(site, "url", ""),
                "cookie": getattr(site, "cookie", ""), "ua": getattr(site, "ua", ""),
            }
        # 好学的 FluxTorrent API 认证 Cookie 可能由 CookieCloud 更新；
        # 站点表中的旧 Cookie 失效后，build_site() 才会刷新并重试。
        host = str(result.get("domain") or result.get("url") or "").lower()
        host = host.split("//", 1)[-1].split("/", 1)[0].removeprefix("www.")
        result["cookiecloud"] = host in ("hxpt.org", "haoxue.net")
        return result
    def all_sites(self):
        try:
            sites = [self._site_dict(site) for site in self.siteoper.list_order_by_pri()
                     if not getattr(site, "public", False)]
        except Exception as error:
            logger.error(f"[PtTaskFlow] [站点] 读取 MoviePilot 站点失败：{error}")
            sites = []
        if not any((site.get("domain") or "").lower() == "vclib.online" for site in sites):
            sites.append({
                "id": "builtin_vclib", "name": "Vc-Lib", "domain": "vclib.online",
                "url": "https://vclib.online", "cookie": "", "ua": "",
                "cookiecloud": True,
            })
        return sites

    def _cookiecloud_cookie(self, site_url, refresh=False):
        def load():
            return cookiecloud_cookies()
        try:
            return self._cookiecloud_cache.get(site_url, load, refresh=refresh)
        except Exception as error:
            self._cookiecloud_cache.clear(site_url)
            logger.warning(f"[PtTaskFlow] [站点] CookieCloud 获取失败：{error}")
            return ""

    def available_site_options(self):
        options = []
        for site in self.all_sites():
            site_cls = match_site(site)
            if not site_cls:
                continue
            options.append({
                "id": site.get("id"), "name": site.get("name") or site_cls.site_name,
                "domain": site.get("domain"), "site": site,
            })
        return options

    def build_site(self, site_info, require_cookie=False):
        site_info = dict(site_info)
        cookie_refresher = None
        if site_info.get("cookiecloud"):
            site_url = site_info.get("url", "")
            if not site_info.get("cookie"):
                site_info["cookie"] = self._cookiecloud_cookie(site_url)
            cookie_refresher = lambda: self._cookiecloud_cookie(site_url, refresh=True)
            if require_cookie and not site_info["cookie"]:
                logger.warning(f"[PtTaskFlow] [{site_info.get('name')}] CookieCloud 未匹配 Cookie，跳过")
                return None
        site_cls = match_site(site_info)
        if not site_cls:
            return None
        return site_cls(
            site_info, use_proxy=self.config.use_proxy, interval=self.config.interval,
            collect_feedback=self.config.get_feedback,
            feedback_timeout=self.config.feedback_timeout,
            cookie_refresher=cookie_refresher,
        )

    def runtime_sites(self, selected_only=True):
        selected = {str(value) for value in self.config.site_ids}
        sites = []
        for site_info in self.all_sites():
            if selected_only and str(site_info.get("id")) not in selected:
                continue
            site = self.build_site(site_info, require_cookie=True)
            if site:
                sites.append(site)
        return sites

    def run_scheduled(self):
        # 织梦和朱雀技能均由独立 date 服务负责，主 cron 不重复执行。
        records = self.engine.run(
            scene="主定时", exclude_domains={"zmpt.cc"},
            exclude_tasks={("zhuque.in", "skill_release")},
        )
        send_summary(self, records)
        self._retry_failures(records)
        return records

    @staticmethod
    def _retryable_keys(records):
        return {
            record["execution_key"] for record in records
            if record.get("retryable") and not record.get("success")
        }

    def _retry_failures(self, records, scene_prefix="失败重试", site_filter="", task_filter=""):
        failed_keys = self._retryable_keys(records)
        for attempt in range(1, self.config.retry_count + 1):
            if not failed_keys:
                break
            wait_seconds = self.config.retry_interval * 60
            if self._stop_event.wait(wait_seconds):
                logger.info(f"[PtTaskFlow] [{scene_prefix}] 收到停止信号，取消剩余重试")
                break
            retry_records = self.engine.run_if_idle(
                scene=f"{scene_prefix} {attempt}/{self.config.retry_count}",
                site_filter=site_filter,
                task_filter=task_filter,
                execution_keys=failed_keys,
            )
            if retry_records is None:
                logger.info(f"[PtTaskFlow] [{scene_prefix}] 引擎忙碌，本轮重试未执行")
                continue
            send_summary(self, retry_records, retry=True)
            failed_keys = self._retryable_keys(retry_records)
        return failed_keys

    def run_manual(self):
        # 织梦喊话由邮件时间 +24h 的独立 date 服务负责，手动补跑不重复执行。
        records = self.engine.run(scene="手动补跑", exclude_domains={"zmpt.cc"})
        send_summary(self, records)
        return records

    def run_zm(self):
        """织梦独立 date 调度；只执行织梦，并按最新赠送邮件时间续排。"""
        now = datetime.now()
        self._zm_retry_at = None
        if self.config.last_zm_execution_time:
            try:
                last = datetime.fromisoformat(self.config.last_zm_execution_time)
                if (now - last).total_seconds() < self.config.zm_cooldown:
                    logger.info("[PtTaskFlow] [织梦24h调度] 冷却中，跳过重复执行并续排")
                    self._refresh_plugin_schedule()
                    return []
            except ValueError:
                pass
        records = self.engine.run_if_idle(
            scene="织梦24h调度", site_filter="zmpt.cc", task_filter="daily_shotbox")
        if records is None:
            self._schedule_zm_retry(now)
            return []
        send_summary(self, records)
        self._retry_failures(
            records, scene_prefix="织梦失败重试",
            site_filter="zmpt.cc", task_filter="daily_shotbox",
        )
        self.config.last_zm_execution_time = now.isoformat()
        for site in self.runtime_sites():
            if site.domain == "zmpt.cc":
                mail_time = site.get_latest_message_time()
                if mail_time:
                    self.config.zm_mail_time = str(mail_time)
                break
        self.save_config()
        self._refresh_plugin_schedule()
        return records
    def run_zhuque(self):
        """朱雀技能独立 date 调度；执行后按接口返回的 next_time 续排。"""
        records = self.engine.run_if_idle(
            scene="朱雀技能", site_filter="zhuque.in", task_filter="skill_release"
        )
        next_time = None
        for site in self.runtime_sites():
            if site.domain == "zhuque.in":
                next_time = site.get_skill_next_time()
                break
        if next_time:
            self.config.zq_skill_next_time = datetime.fromtimestamp(next_time).strftime("%Y-%m-%d %H:%M:%S")
        else:
            self.config.zq_skill_next_time = ""
        self.save_config()
        self._refresh_plugin_schedule()
        return records


    def _schedule_zm_retry(self, now):
        delay_minutes = max(1, self.config.retry_interval)
        self._zm_retry_at = now + timedelta(minutes=delay_minutes)
        logger.info(f"[PtTaskFlow] [织梦24h调度] 引擎忙碌，{delay_minutes} 分钟后重试")
        self._refresh_plugin_schedule()

    def _refresh_plugin_schedule(self):
        try:
            from app.sdk.scheduler import update_plugin_job
            update_plugin_job(self.plugin_id)
        except Exception as error:
            logger.warning(f"[PtTaskFlow] [织梦24h调度] 重注册服务失败：{error}")

    def save_config(self):
        merged = dict(self.raw_config)
        merged.update(self.config.to_dict())
        self.raw_config = self._clean_config(merged)
        self.update_config(self.raw_config)

    def run_debug(self, site_filter="", task_filter=""):
        return self.engine.run(scene="调试", debug=True,
                               site_filter=site_filter, task_filter=task_filter)

    def _next_run_text(self) -> Optional[str]:
        """下次触发说明；V3 宿主无公共查询 API，显示 cron 文本。"""
        if not self.config.enabled:
            return None
        # V3 宿主未暴露读取服务下次运行时间的公共 API，回退显示 cron 文本。
        return f"按配置执行: {self.config.cron}" if self.config.cron else None

    def get_state(self) -> bool:
        return self.config.enabled

    def get_render_mode(self):
        """沿用宿主 Vuetify 渲染（配置/数据页均为 VForm dict）。"""
        return "vuetify", None

    def get_form(self):
        return build_form(self)

    def get_page(self):
        return build_page(self)

    def get_service(self):
        return TaskScheduler(self).services()

    def stop_service(self):
        """通知运行中任务尽快退出；引擎在当前单元完成后响应停止信号。"""
        if not self._stop_event.is_set():
            self._stop_event.set()
            logger.info("[PtTaskFlow] 服务停止，已通知运行中任务退出")
        return

    @staticmethod
    def get_command():
        return [{
            "cmd": "/pttaskflow_run", "event": EventType.PluginAction,
            "desc": "执行 PT 任务流", "category": "站点",
            "data": {"action": "pttaskflow_run"},
        }, {
            "cmd": "/pttaskflow_manual_run", "event": EventType.PluginAction,
            "desc": "补跑当天未成功的 PT 任务", "category": "站点",
            "data": {"action": "pttaskflow_manual_run"},
        }]

    def get_api(self):
        return [{
            "path": "/run", "endpoint": self.api_run, "methods": ["POST"], "auth": "bear",
            "summary": "调试执行 PT 任务流（可按站点/任务过滤）",
        }, {
            "path": "/manual-run", "endpoint": self.api_manual_run,
            "methods": ["POST"], "auth": "bear", "summary": "当天补跑未成功任务",
        }, {
            "path": "/config", "endpoint": self.api_config, "methods": ["GET"], "auth": "bear",
            "summary": "读取插件配置、站点任务结构与历史",
        }, {
            "path": "/config", "endpoint": self.api_save_config, "methods": ["PUT"], "auth": "bear",
            "summary": "保存插件配置",
        }]

    def api_manual_run(self):
        if not self.engine or not self.config.enabled:
            return self._response(success=False, message="插件未启用或未初始化")
        threading.Thread(target=self.run_manual, daemon=True,
                         name="pttaskflow_manual_api").start()
        return self._response(message="已后台启动当天补跑")

    @staticmethod
    def _response(data=None, success=True, message=""):
        return {"success": success, "message": message, "data": data}

    def _site_task_payload(self):
        """站点与任务控件结构，替代 V2 form JSON 供前端渲染。"""
        payload = []
        for option in self.available_site_options():
            try:
                site = self.build_site(option["site"])
            except Exception:
                continue
            if site is None:
                continue
            tasks = []
            for task in site.tasks:
                controls = []
                for control in task.controls(site):
                    item = {
                        "key": control.key,
                        "kind": str(control.kind).rsplit(".", maxsplit=1)[-1],
                        "label": control.label,
                    }
                    if control.options:
                        item["options"] = list(control.options)
                    controls.append(item)
                tasks.append({
                    "name": task.name,
                    "label": task.label(site),
                    "type": getattr(task.task_type, "value", str(task.task_type)),
                    "controls": controls,
                })
            payload.append({
                "id": option["id"], "name": option["name"],
                "domain": option["domain"], "tasks": tasks,
            })
        return payload

    def api_config(self):
        """配置 + 站点任务结构 + 近期历史，前端 Config/Page 共用。"""
        data = {
            "config": dict(self.raw_config),
            "sites": self._site_task_payload(),
            "status": {
                "enabled": self.config.enabled,
                "next_run_text": self._next_run_text(),
                "running": bool(self.engine and self.engine._lock.locked()),
            },
            "history": self.history.latest(limit=50) if self.history else [],
        }
        return self._response(data)

    def api_save_config(self, config: dict = None):
        if not isinstance(config, dict):
            return self._response(success=False, message="invalid_config")
        merged = dict(self.raw_config)
        merged.update(config)
        self.raw_config = self._clean_config(merged)
        self.config = PluginConfig.from_dict(self.raw_config)
        self.update_config(self.raw_config)
        self._refresh_plugin_schedule()
        return self._response(message="已保存")

    @eventmanager.register(EventType.PluginAction)
    def run_command(self, event: Event = None):
        data = event.event_data if event else {}
        action = data.get("action")
        if action not in {"pttaskflow_run", "pttaskflow_manual_run"}:
            return
        if not self.config.enabled:
            return
        target = self.run_manual if action == "pttaskflow_manual_run" else self.run_scheduled
        threading.Thread(target=target, daemon=True,
                         name=f"pttaskflow_{action}").start()

    def api_run(self, site_id: str = "", task_name: str = ""):
        if not self.engine:
            return self._response(success=False, message="插件未初始化")
        if not site_id and not task_name:
            threading.Thread(target=self.run_scheduled, daemon=True,
                             name="pttaskflow_run").start()
            return self._response(message="已后台启动任务流")
        records = self.run_debug(site_filter=site_id, task_filter=task_name)
        return self._response(records, message=f"执行完成，共 {len(records)} 个单元")
