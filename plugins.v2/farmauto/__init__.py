"""MoviePilot V2 农场自动化插件入口。"""
import json
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from apscheduler.triggers.interval import IntervalTrigger
from app.core.event import Event, eventmanager
from app.db.site_oper import SiteOper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import NotificationType
from app.schemas.types import EventType

from .core.executor import FarmExecutor
from .core.http_client import FarmHttpClient
from .core.models import RunReport, SiteRunReport
from .core.reporting import (
    build_history_rows,
    build_price_sections,
    build_stat_cards,
    format_notification,
)
from .core.strategy import effective_site_mode, effective_site_policy, site_is_enabled
from .core.trend import PriceTrendStore
from .sites import SITE_CONFIGS, SITE_OPTIONS, get_site_config


class FarmAuto(_PluginBase):
    plugin_name = "农场自动化Pro"
    plugin_desc = "多站点农场自动化，支持智能交易与自动收获"
    plugin_icon = "farm.png"
    plugin_version = "3.0"
    plugin_author = "bfjy"
    author_url = "https://bfjy2024.github.io/bfjy"
    plugin_config_prefix = "farmauto_"
    plugin_order = 30
    auth_level = 2

    _enabled = False
    _notify = True
    _run_lock = threading.Lock()

    def __init__(self):
        super().__init__()
        self._raw_config: Dict[str, Any] = {}
        self._mode = "smart"
        self._site_ids: List[str] = []
        self._interval_minutes = 61
        self._harvest_interval_minutes = 61
        self._expire_threshold_minutes = 120
        self._min_profit_rate = 0.0
        self._max_profit_rate = 0.0
        self._max_sell_per_run = 50
        self._request_interval = 1.0
        self._retry_count = 3
        self._use_proxy = False
        self._dry_run = False
        self._siqi_options: Dict[str, bool] = {
            "auto_captcha_harvest": False,
            "auto_steal": False,
            "auto_like": False,
            "auto_buy_slot": False,
            "captcha_ocr": True,
        }
        self._site_overrides: Dict[str, Dict[str, Any]] = {}
        self._trend_store = PriceTrendStore()
        self._stats = self._empty_stats()
        self._market_prices: Dict[str, Dict[str, int]] = {}

    @staticmethod
    def _empty_stats() -> Dict[str, Any]:
        return {
            "total_profit": 0,
            "total_trades": 0,
            "last_run": None,
            "history": [],
            "last_result": {},
        }

    @staticmethod
    def _to_int(value: Any, default: int, min_value: int = 0) -> int:
        try:
            return max(min_value, int(value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _to_float(value: Any, default: float, min_value: float = 0.0) -> float:
        try:
            return max(min_value, float(value))
        except (TypeError, ValueError):
            return default

    def init_plugin(self, config: Optional[dict] = None):
        config = config or {}
        self._raw_config = dict(config)
        self._enabled = bool(config.get("enabled", False))
        self._notify = bool(config.get("notify", True))
        run_once = bool(config.get("run_once", False))
        self._mode = config.get("mode") if config.get("mode") in ("smart", "harvest") else "smart"
        site_ids = config.get("site_ids", [])
        if isinstance(site_ids, list):
            self._site_ids = [str(site_id) for site_id in site_ids if str(site_id) in SITE_CONFIGS]
        elif site_ids:
            self._site_ids = [str(site_ids)] if str(site_ids) in SITE_CONFIGS else []
        else:
            self._site_ids = []
        self._interval_minutes = self._to_int(config.get("interval_minutes"), 61, 1)
        self._harvest_interval_minutes = self._to_int(
            config.get("harvest_interval_minutes"), 61, 5
        )
        self._expire_threshold_minutes = self._to_int(
            config.get("expire_threshold_minutes"), 120, 10
        )
        self._min_profit_rate = self._to_float(config.get("min_profit_rate"), 0.0, 0.0)
        self._max_profit_rate = self._to_float(config.get("max_profit_rate"), 0.0, 0.0)
        self._max_sell_per_run = self._to_int(config.get("max_sell_per_run"), 50, 1)
        self._request_interval = self._to_float(config.get("request_interval"), 1.0, 0.0)
        self._retry_count = self._to_int(config.get("retry_count"), 3, 0)
        self._use_proxy = bool(config.get("use_proxy", False))
        self._dry_run = bool(config.get("dry_run", False))
        self._siqi_options = {
            "auto_captcha_harvest": bool(config.get("siqi_auto_captcha_harvest", False)),
            "auto_steal": bool(config.get("siqi_auto_steal", False)),
            "auto_like": bool(config.get("siqi_auto_like", False)),
            "auto_buy_slot": bool(config.get("siqi_auto_buy_slot", False)),
            "captcha_ocr": bool(config.get("siqi_captcha_ocr", True)),
        }
        try:
            overrides = json.loads(config.get("site_overrides") or "{}")
            if not isinstance(overrides, dict):
                raise ValueError("顶层必须是 JSON 对象")
            self._site_overrides = {
                str(site_id): override
                for site_id, override in overrides.items()
                if isinstance(override, dict)
            }
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            logger.warning(f"农场自动化单站策略覆盖解析失败，已忽略：{error}")
            self._site_overrides = {}

        stored_stats = config.get("stats", self.get_data("stats") or {})
        self._stats = {**self._empty_stats(), **stored_stats} if isinstance(stored_stats, dict) else self._empty_stats()
        stored_prices = config.get("market_prices", self.get_data("market_prices") or {})
        self._market_prices = stored_prices if isinstance(stored_prices, dict) else {}
        stored_trends = config.get("trends", self.get_data("trends") or {})
        self._trend_store = PriceTrendStore.from_dict(stored_trends)

        if run_once:
            self._raw_config["run_once"] = False
            self.update_config(self._raw_config)
            if self._site_ids:
                self._start_background_task("配置页立即运行")
            else:
                logger.warning("农场自动化未选择站点，忽略配置页立即运行请求")

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        return "vue", "dist/assets"

    def _start_background_task(self, source: str) -> bool:
        if not type(self)._run_lock.acquire(blocking=False):
            logger.warning(f"农场自动化任务正在运行，忽略{source}请求")
            return False
        try:
            threading.Thread(
                target=self.run_farm_task,
                kwargs={"lock_acquired": True},
                daemon=True,
                name="farmauto_run",
            ).start()
        except Exception:
            type(self)._run_lock.release()
            raise
        return True

    @staticmethod
    def _site_value(site: Any, name: str, default: Any = "") -> Any:
        if isinstance(site, dict):
            return site.get(name, default)
        return getattr(site, name, default)

    @classmethod
    def _cookie_from_site(cls, site: Any) -> str:
        site_cookie = cls._site_value(site, "cookie", "") if site else ""
        if isinstance(site_cookie, dict):
            return "; ".join(
                f"{key}={value}" for key, value in site_cookie.items()
            ).strip()
        return str(site_cookie or "").strip()

    @classmethod
    def _site_matches_domain(cls, site: Any, candidate: str) -> bool:
        candidate = candidate.lower().lstrip(".")
        domain = str(cls._site_value(site, "domain", "") or "").lower().lstrip(".")
        url = str(cls._site_value(site, "url", "") or "").lower()
        return (
            domain == candidate
            or domain.endswith(f".{candidate}")
            or candidate.endswith(f".{domain}")
            or f"//{candidate}" in url
            or f".{candidate}" in url
        )

    def _get_site_cookie(self, site_config) -> str:
        site_oper = SiteOper()
        for domain in site_config.domains:
            try:
                site = site_oper.get_by_domain(domain)
                cookie = self._cookie_from_site(site)
                if cookie:
                    logger.info(f"{site_config.site_name} 已读取站点 Cookie")
                    return cookie
            except Exception as error:
                logger.debug(f"{site_config.site_name} 按域名读取 Cookie 失败：{error}")

        try:
            sites = site_oper.list() or []
        except Exception as error:
            logger.warning(f"{site_config.site_name} 读取站点列表失败：{error}")
            sites = []
        for site in sites:
            if any(self._site_matches_domain(site, candidate) for candidate in site_config.domains):
                cookie = self._cookie_from_site(site)
                if cookie:
                    logger.info(f"{site_config.site_name} 已从站点列表读取 Cookie")
                    return cookie
        logger.warning(f"{site_config.site_name} 未找到可用 Cookie")
        return ""

    def get_effective_policy(self, site_id: str) -> dict:
        global_policy = {
            "min_profit_rate": self._min_profit_rate,
            "max_profit_rate": self._max_profit_rate,
            "max_sell_per_run": self._max_sell_per_run,
            "expire_threshold_minutes": self._expire_threshold_minutes,
            "request_interval": self._request_interval,
            "use_proxy": self._use_proxy,
            "dry_run": self._dry_run,
        }
        return effective_site_policy(global_policy, self._site_overrides, site_id)

    def get_effective_mode(self, site_id: str) -> str:
        return effective_site_mode(self._mode, self._site_overrides, site_id)

    def is_site_enabled(self, site_id: str) -> bool:
        return site_is_enabled(self._site_overrides, site_id)

    def _build_http_client(self, policy: dict) -> FarmHttpClient:
        return FarmHttpClient(
            timeout=15,
            retry_count=self._retry_count,
            use_proxy=bool(policy.get("use_proxy", False)),
            min_interval=max(float(policy.get("request_interval", 0)), 0.3),
        )

    def _siqi_daily_state(self) -> Dict[str, Any]:
        today = datetime.now().strftime("%Y-%m-%d")
        stored = self.get_data("siqi_daily") or {}
        if not isinstance(stored, dict) or stored.get("date") != today:
            stored = {"date": today, "steal": False, "like": False}
            self.save_data("siqi_daily", stored)
        return stored

    def _run_siqi_extras(self, executor, site_config, cookie, policy, report) -> None:
        if site_config.site_id != "siqi" or policy.get("dry_run", False):
            return
        daily = self._siqi_daily_state()
        results = executor.run_siqi_extras(
            cookie,
            site_config,
            self._siqi_options,
            {"steal": bool(daily.get("steal")), "like": bool(daily.get("like"))},
        )
        for result in results:
            report.actions.append(result)
            if result.success:
                report.trades_count += 1
            if result.action in ("steal", "like"):
                daily[result.action] = True
                self.save_data("siqi_daily", daily)
        if results:
            failures = sum(not result.success for result in report.actions)
            report.status = "partial" if failures else "completed"
            report.message = f"完成 {report.trades_count} 个操作"

    @staticmethod
    def _site_report_dict(report: SiteRunReport) -> Dict[str, Any]:
        return {
            "site_id": report.site_id,
            "site_name": report.site_name,
            "mode": report.mode,
            "market_prices": report.market_prices,
            "bonus": getattr(report, "bonus", None),
            "crop_status": report.crop_status,
            "warehouse": report.warehouse,
            "total_profit": report.total_profit,
            "trades_count": report.trades_count,
            "status": report.status,
            "message": report.message,
            "actions": [vars(action) for action in report.actions],
        }

    def run_farm_task(self, lock_acquired: bool = False) -> Optional[RunReport]:
        if not lock_acquired and not type(self)._run_lock.acquire(blocking=False):
            logger.warning("农场自动化任务正在运行，跳过本次触发")
            return None
        started_at = time.time()
        try:
            per_site_clients = any(
                isinstance(override, dict) and "use_proxy" in override
                for override in self._site_overrides.values()
            )
            shared_executor = None
            if not per_site_clients:
                shared_executor = FarmExecutor(
                    self._build_http_client(self.get_effective_policy("")),
                    logger,
                    self._trend_store,
                )
            site_reports: List[SiteRunReport] = []
            for site_id in self._site_ids:
                if not self.is_site_enabled(site_id):
                    logger.info(f"农场自动化站点 {site_id} 已被单站策略禁用，跳过")
                    continue
                site_config = get_site_config(site_id)
                if not site_config:
                    continue
                policy = self.get_effective_policy(site_id)
                mode = self.get_effective_mode(site_id)
                executor = shared_executor or FarmExecutor(
                    self._build_http_client(policy), logger, self._trend_store
                )
                cookie = self._get_site_cookie(site_config)
                site_report = executor.run_site(cookie, site_config, mode, policy)
                self._run_siqi_extras(executor, site_config, cookie, policy, site_report)
                site_reports.append(site_report)
                self._market_prices[site_id] = dict(site_report.market_prices)

            total_profit = sum(item.total_profit for item in site_reports)
            total_trades = sum(item.trades_count for item in site_reports)
            failed = sum(item.status == "failed" for item in site_reports)
            partial = sum(item.status == "partial" for item in site_reports)
            if not site_reports:
                status, message = "skipped", "未选择有效站点"
            elif failed == len(site_reports):
                status, message = "failed", "全部站点执行失败"
            elif failed or partial:
                status, message = "partial", "部分站点或操作未完成"
            else:
                status, message = "completed", "全部站点执行完成"
            report = RunReport(
                started_at=started_at,
                finished_at=time.time(),
                site_reports=site_reports,
                total_profit=total_profit,
                total_trades=total_trades,
                status=status,
                message=message,
            )
            try:
                self._record_report(report)
            except Exception as error:
                logger.error(f"农场自动化统计持久化失败：{error}")
            if self._notify:
                try:
                    self.post_message(
                        mtype=NotificationType.SiteMessage,
                        title="【农场自动化Pro】",
                        text=format_notification(report),
                    )
                except Exception as error:
                    logger.error(f"农场自动化通知发送失败：{error}")
            return report
        except Exception as error:
            logger.error(f"农场自动化多站编排失败：{error}")
            report = RunReport(
                started_at=started_at,
                finished_at=time.time(),
                status="failed",
                message=str(error),
            )
            try:
                self._record_report(report)
            except Exception as save_error:
                logger.error(f"农场自动化失败统计持久化失败：{save_error}")
            return report
        finally:
            type(self)._run_lock.release()

    def _record_report(self, report: RunReport) -> None:
        site_results = [self._site_report_dict(item) for item in report.site_reports]
        last_result = {
            "started_at": report.started_at,
            "finished_at": report.finished_at,
            "total_profit": report.total_profit,
            "total_trades": report.total_trades,
            "status": report.status,
            "message": report.message,
            "site_reports": site_results,
        }
        history = list(self._stats.get("history") or [])
        for site_report in report.site_reports:
            history.append({
                "time": report.finished_at,
                "site": site_report.site_name,
                "action": site_report.message,
                "profit": site_report.total_profit,
                "status": site_report.status,
            })
        if not report.site_reports:
            history.append({
                "time": report.finished_at,
                "site": "-",
                "action": report.message,
                "profit": 0,
                "status": report.status,
            })
        updated_stats = {
            "total_profit": int(self._stats.get("total_profit", 0)) + report.total_profit,
            "total_trades": int(self._stats.get("total_trades", 0)) + report.total_trades,
            "last_run": report.finished_at,
            "history": history[-20:],
            "last_result": last_result,
        }
        trends = self._trend_store.to_dict()
        self.save_data("stats", updated_stats)
        self.save_data("market_prices", self._market_prices)
        self.save_data("trends", trends)
        self._stats = updated_stats
        persisted_config = dict(self._raw_config)
        persisted_config["run_once"] = False
        persisted_config.update({
            "stats": updated_stats,
            "market_prices": self._market_prices,
            "trends": trends,
        })
        self.update_config(persisted_config)
        self._raw_config = persisted_config

    def get_service(self) -> List[Dict[str, Any]]:
        if not self._enabled or not self._site_ids:
            return []
        interval = (
            self._harvest_interval_minutes
            if self._mode == "harvest"
            else self._interval_minutes
        )
        return [{
            "id": "FarmAuto",
            "name": "农场自动化定时任务",
            "trigger": IntervalTrigger(minutes=interval),
            "func": self.run_farm_task,
            "kwargs": {},
        }]

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return [{
            "cmd": "/farmauto_run",
            "event": EventType.PluginAction,
            "desc": "立即执行农场自动化任务",
            "category": "站点",
            "data": {"action": "farmauto_run"},
        }]

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/run",
                "endpoint": self._api_run,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "立即运行农场自动化任务",
            },
            {
                "path": "/stats",
                "endpoint": self._api_stats,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取农场统计与市场价格",
            },
            {
                "path": "/prices",
                "endpoint": self._api_prices,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取最新市场价格",
            },
            {
                "path": "/status",
                "endpoint": self._api_status,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取农场工作台总览",
            },
            {
                "path": "/site/{site_id}",
                "endpoint": self._api_site_detail,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取单站农场详情",
            },
            {
                "path": "/site/{site_id}/action",
                "endpoint": self._api_site_action,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "手动执行单站农场操作",
            },
        ]

    def _api_run(self) -> Dict[str, Any]:
        started = self._start_background_task("API")
        return {
            "success": started,
            "message": "任务已在后台启动" if started else "已有任务正在运行",
        }

    def _api_stats(self) -> Dict[str, Any]:
        return {
            "success": True,
            "stats": self._stats,
            "market_prices": self._market_prices,
            "trends": self._trend_store.to_dict(),
        }

    def _api_prices(self) -> Dict[str, Any]:
        return {"success": True, "market_prices": self._market_prices}

    @staticmethod
    def _timestamp_text(value: Any) -> Optional[str]:
        if value in (None, ""):
            return None
        if isinstance(value, str):
            return value
        try:
            return datetime.fromtimestamp(float(value)).isoformat(timespec="seconds")
        except (TypeError, ValueError, OSError):
            return str(value)

    def _next_run_text(self) -> Optional[str]:
        if not self._enabled or not self._site_ids:
            return None
        interval = (
            self._harvest_interval_minutes
            if self._mode == "harvest"
            else self._interval_minutes
        )
        last_run = self._stats.get("last_run")
        if last_run in (None, ""):
            return None
        try:
            return datetime.fromtimestamp(float(last_run) + interval * 60).isoformat(
                timespec="seconds"
            )
        except (TypeError, ValueError, OSError):
            return None

    def _last_site_report(self, site_id: str) -> Dict[str, Any]:
        last_result = self._stats.get("last_result") or {}
        if not isinstance(last_result, dict):
            return {}
        reports = last_result.get("site_reports") or []
        for report in reports:
            if isinstance(report, dict) and str(report.get("site_id")) == site_id:
                return report
        return {}

    @staticmethod
    def _trend_point_count(site_trends: Any) -> int:
        if not isinstance(site_trends, dict):
            return 0
        return sum(len(samples) for samples in site_trends.values() if isinstance(samples, list))

    @staticmethod
    def _normalize_crop_status(crop_status: Any) -> Dict[str, Dict[str, Any]]:
        if not isinstance(crop_status, dict):
            return {}
        result: Dict[str, Dict[str, Any]] = {}
        for crop_key, raw_status in crop_status.items():
            status = dict(raw_status) if isinstance(raw_status, dict) else {
                "can_harvest": bool(raw_status)
            }
            status.setdefault("remaining_minutes", None)
            result[str(crop_key)] = status
        return result

    @staticmethod
    def _normalize_warehouse(warehouse: Any) -> List[Dict[str, Any]]:
        if not isinstance(warehouse, list):
            return []
        result = []
        for raw_item in warehouse:
            if not isinstance(raw_item, dict):
                continue
            item = dict(raw_item)
            item.setdefault("expire_minutes", None)
            result.append(item)
        return result

    def _site_history(self, site_id: str, site_name: str) -> List[Dict[str, Any]]:
        history = self._stats.get("history") or []
        return [
            dict(item)
            for item in history
            if isinstance(item, dict)
            and str(item.get("site", "")) in (site_id, site_name)
        ]

    def _api_status(self) -> Dict[str, Any]:
        trends = self._trend_store.to_dict()
        site_ids = list(dict.fromkeys(list(SITE_CONFIGS.keys())))
        sites = []
        for site_id in site_ids:
            site_config = get_site_config(site_id)
            if not site_config:
                continue
            report = self._last_site_report(site_id)
            crop_status = self._normalize_crop_status(report.get("crop_status"))
            warehouse = self._normalize_warehouse(report.get("warehouse"))
            prices = self._market_prices.get(site_id) or report.get("market_prices") or {}
            actions = report.get("actions") or []
            recent_action = (
                actions[-1].get("action")
                if actions and isinstance(actions[-1], dict)
                else None
            )
            sites.append({
                "site_id": site_id,
                "site_name": site_config.site_name,
                "currency": site_config.currency,
                "bonus": report.get("bonus"),
                "prices_count": len(prices) if isinstance(prices, dict) else 0,
                "harvestable": [
                    crop_key
                    for crop_key in site_config.crops
                    if crop_status.get(crop_key, {}).get("can_harvest")
                ],
                "warehouse_count": len(warehouse),
                "trend_points": self._trend_point_count(trends.get(site_id)),
                "recent_action": recent_action,
            })
        return {
            "success": True,
            "data": {
                "enabled": bool(self._enabled),
                "mode": self._mode,
                "dry_run": bool(self._dry_run),
                "next_run": self._next_run_text(),
                "total_profit": self._to_int(self._stats.get("total_profit"), 0),
                "total_trades": self._to_int(self._stats.get("total_trades"), 0),
                "last_run": self._timestamp_text(self._stats.get("last_run")),
                "sites": sites,
            },
        }

    def _api_site_detail(self, site_id: str) -> Dict[str, Any]:
        site_config = get_site_config(site_id)
        if not site_config:
            return {"success": False, "message": "站点不存在"}
        report = self._last_site_report(site_id)
        history = self._site_history(site_id, site_config.site_name)
        site_trends = self._trend_store.to_dict().get(site_id, {})
        data = {
            "site_id": site_id,
            "site_name": site_config.site_name,
            "market_prices": self._market_prices.get(site_id)
            or report.get("market_prices")
            or {},
            "crop_status": self._normalize_crop_status(report.get("crop_status")),
            "crops": {
                crop_key: {
                    field: crop.get(field)
                    for field in ("name", "cost", "type", "id", "action")
                }
                for crop_key, crop in site_config.crops.items()
            },
            "warehouse": self._normalize_warehouse(report.get("warehouse")),
            "trends": {
                crop_key: samples[-20:]
                for crop_key, samples in site_trends.items()
                if isinstance(samples, list)
            } if isinstance(site_trends, dict) else {},
            "recent_actions": history[-10:],
        }
        if site_id == "siqi":
            daily = self.get_data("siqi_daily") or {}
            is_today = (
                isinstance(daily, dict)
                and daily.get("date") == datetime.now().strftime("%Y-%m-%d")
            )
            data["siqi_extra"] = {
                "captcha_ready": True,
                "steal_done_today": is_today and bool(daily.get("steal")),
                "like_done_today": is_today and bool(daily.get("like")),
                "buy_slot_available": 0,
            }
        return {"success": True, "data": data}

    def _api_site_action(self, site_id: str, payload: dict) -> Dict[str, Any]:
        action = str((payload or {}).get("action") or "")
        crop_key = str((payload or {}).get("crop_key") or "")
        dry_run = bool(self._dry_run)
        target = crop_key or site_id
        if action not in ("harvest", "plant", "sell", "harvest_all"):
            return {
                "success": False,
                "message": "不支持的操作",
                "action": action,
                "target": target,
                "dry_run": dry_run,
            }
        site_config = get_site_config(site_id)
        if not site_config:
            return {
                "success": False,
                "message": "站点不存在",
                "action": action,
                "target": target,
                "dry_run": dry_run,
            }
        policy = self.get_effective_policy(site_id)
        dry_run = bool(policy.get("dry_run", False))
        crop = site_config.crops.get(crop_key) if crop_key else None
        target = site_config.site_name if action == "harvest_all" else (
            crop.get("name", crop_key) if crop else crop_key
        )
        if action != "harvest_all" and not crop:
            return {
                "success": False,
                "message": "作物不存在",
                "action": action,
                "target": target,
                "dry_run": dry_run,
            }
        if dry_run:
            return {
                "success": True,
                "message": "dry-run：仅记录计划",
                "action": action,
                "target": target,
                "dry_run": True,
            }

        try:
            http_client = self._build_http_client(policy)
            cookies = FarmExecutor._cookie_dict(self._get_site_cookie(site_config))
            if not cookies:
                raise ValueError("未提供有效 Cookie")
            if action == "harvest_all":
                response = http_client.get(site_config.get_harvest_all_url(), cookies)
                response.raise_for_status()
                parsed = site_config.parse_harvest_result(response.text)
            elif action == "harvest":
                response = http_client.get(
                    site_config.get_harvest_url(crop["type"], crop["id"]), cookies
                )
                response.raise_for_status()
                parsed = site_config.parse_harvest_result(response.text)
            elif action == "plant":
                crop_action = crop.get("action", "plant")
                url = (
                    site_config.get_breed_url(crop["type"], crop["id"])
                    if crop_action == "breed"
                    else site_config.get_plant_url(crop["type"], crop["id"])
                )
                response = http_client.get(url, cookies)
                response.raise_for_status()
                parsed = site_config.parse_plant_result(response.text, crop_action)
            else:
                farm_response = http_client.get(site_config.get_farm_url(), cookies)
                farm_response.raise_for_status()
                sell_key = site_config.get_sell_key(
                    farm_response.text, crop["type"], crop["id"]
                ) or f"{crop['type']}_{crop['id']}"
                response = http_client.get(site_config.get_sell_url(sell_key), cookies)
                response.raise_for_status()
                parsed = site_config.parse_sell_result(response.text)
            return {
                "success": bool(parsed.get("success")),
                "message": parsed.get("message", ""),
                "action": action,
                "target": target,
                "dry_run": False,
            }
        except Exception as error:
            return {
                "success": False,
                "message": str(error),
                "action": action,
                "target": target,
                "dry_run": False,
            }

    @eventmanager.register(EventType.PluginAction)
    def run_once_command(self, event: Event = None):
        event_data = event.event_data if event and event.event_data else {}
        if event_data.get("action") != "farmauto_run":
            return
        started = self._start_background_task("命令")
        self.post_message(
            channel=event_data.get("channel"),
            userid=event_data.get("user"),
            mtype=NotificationType.SiteMessage,
            title="【农场自动化Pro】",
            text="任务已在后台启动。" if started else "已有任务正在运行。",
        )

    def _last_run_report(self) -> RunReport:
        last_result = self._stats.get("last_result") or {}
        site_reports = []
        for item in last_result.get("site_reports", []):
            site_reports.append(SiteRunReport(
                site_id=item.get("site_id", ""),
                site_name=item.get("site_name", item.get("site_id", "")),
                mode=item.get("mode", self._mode),
                market_prices=item.get("market_prices", {}),
                total_profit=int(item.get("total_profit", 0)),
                trades_count=int(item.get("trades_count", 0)),
                status=item.get("status", "completed"),
                message=item.get("message", ""),
            ))
        if not site_reports:
            for site_id, prices in self._market_prices.items():
                config = get_site_config(site_id)
                site_reports.append(SiteRunReport(
                    site_id=site_id,
                    site_name=config.site_name if config else site_id,
                    mode=self._mode,
                    market_prices=prices,
                ))
        return RunReport(
            started_at=float(last_result.get("started_at", 0)),
            finished_at=float(last_result.get("finished_at", 0)),
            site_reports=site_reports,
            total_profit=int(last_result.get("total_profit", 0)),
            total_trades=int(last_result.get("total_trades", 0)),
            status=last_result.get("status", "暂无数据"),
            message=last_result.get("message", ""),
        )

    def get_page(self) -> List[dict]:
        try:
            report = self._last_run_report()
            prices = build_price_sections(
                report.site_reports, SITE_CONFIGS, self._trend_store
            )
            price_content = prices or [{
                "component": "VAlert",
                "props": {
                    "type": "info",
                    "variant": "tonal",
                    "text": "暂无市场价格，请先运行一次任务。",
                },
            }]
            history_rows = build_history_rows(self._stats.get("history") or [])
            history_content = [{
                "component": "VTable",
                "props": {"density": "comfortable"},
                "content": [{
                    "component": "thead",
                    "content": [{
                        "component": "tr",
                        "content": [
                            {"component": "th", "text": title}
                            for title in ("时间", "站点", "结果", "利润", "状态")
                        ],
                    }],
                }, {
                    "component": "tbody",
                    "content": history_rows,
                }],
            }] if history_rows else [{
                "component": "VAlert",
                "props": {"type": "info", "variant": "tonal", "text": "暂无执行记录。"},
            }]
            return [
                {
                    "component": "VCard",
                    "props": {"title": "数据面板", "class": "mb-4"},
                    "content": [{
                        "component": "VCardText",
                        "content": [{"component": "VRow", "content": build_stat_cards(report)}] + price_content,
                    }],
                },
                {
                    "component": "VCard",
                    "props": {"title": "执行记录"},
                    "content": [{"component": "VCardText", "content": history_content}],
                },
            ]
        except Exception as error:
            logger.error(f"农场自动化详情页加载失败：{error}")
            return [{
                "component": "VAlert",
                "props": {"type": "error", "variant": "tonal", "text": f"详情页加载失败：{error}"},
            }]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        def col(cols: int, component: dict) -> dict:
            return {
                "component": "VCol",
                "props": {"cols": 12, "md": cols},
                "content": [component],
            }

        def switch(model: str, label: str) -> dict:
            return {"component": "VSwitch", "props": {"model": model, "label": label}}

        def number(model: str, label: str, minimum: Any, hint: str = "") -> dict:
            props = {"model": model, "label": label, "type": "number", "min": minimum}
            if hint:
                props.update({"hint": hint, "persistent-hint": True})
            return {"component": "VTextField", "props": props}

        return [{
            "component": "VForm",
            "content": [
                {"component": "VAlert", "props": {
                    "type": "warning", "variant": "tonal", "class": "mb-4",
                    "text": "思齐的验证码收获、偷菜、点赞和扩地属于高风险行为，默认全部关闭；开启即表示自行承担账号风控风险。OCR 不可用时验证码收获会安全降级为逐格收获。",
                }},
                {"component": "VAlert", "props": {
                    "type": "info", "variant": "tonal", "class": "mb-4",
                    "text": "支持 PlayLet、NovaHD、好学、包子、拾刻和思齐；智能交易会按最低与最高利润率组成的盈利区间执行仓库出售、收获与补种，超过上限时保留囤货待涨；自动收获模式侧重收获和临期处理。可在表单末尾用 JSON 为单个站点覆盖策略、模式或启用状态。",
                }},
                {"component": "VRow", "content": [
                    col(4, switch("enabled", "启用插件")),
                    col(4, switch("notify", "发送通知")),
                    col(4, switch("run_once", "立即运行一次")),
                ]},
                {"component": "VRow", "content": [
                    col(4, {"component": "VSelect", "props": {
                        "model": "mode", "label": "运行模式",
                        "items": [
                            {"title": "智能交易", "value": "smart"},
                            {"title": "自动收获", "value": "harvest"},
                        ],
                    }}),
                    col(8, {"component": "VSelect", "props": {
                        "model": "site_ids", "label": "站点", "items": SITE_OPTIONS,
                        "multiple": True, "chips": True,
                    }}),
                ]},
                {"component": "VRow", "content": [
                    col(4, number("interval_minutes", "智能交易间隔（分钟）", 1)),
                    col(4, number("harvest_interval_minutes", "自动收获间隔（分钟）", 5)),
                    col(4, number("expire_threshold_minutes", "临期阈值（分钟）", 10)),
                ]},
                {"component": "VRow", "content": [
                    col(3, number("min_profit_rate", "最低利润率", 0, "0 表示售价高于成本即售；0.1 表示 10%")),
                    col(3, number("max_profit_rate", "最高利润率", 0, "0=无上限，0.5=50%封顶，超过则不卖防囤货")),
                    col(3, number("max_sell_per_run", "单轮单站最大出售数", 1)),
                    col(3, number("request_interval", "请求间隔（秒）", 0)),
                ]},
                {"component": "VRow", "content": [
                    col(4, number("retry_count", "重试次数", 0)),
                    col(4, switch("use_proxy", "使用 MP 系统代理")),
                    col(4, switch("dry_run", "仅模拟（不发送操作请求）")),
                ]},
                {"component": "VAlert", "props": {
                    "type": "warning", "variant": "tonal", "class": "mt-2 mb-2",
                    "text": "思齐专用执行开关（仅选择思齐站点时生效，除 OCR 优先外默认全关）",
                }},
                {"component": "VRow", "content": [
                    col(4, switch("siqi_auto_captcha_harvest", "思齐：验证码收获")),
                    col(4, switch("siqi_captcha_ocr", "思齐：OCR 优先")),
                    col(4, switch("siqi_auto_buy_slot", "思齐：自动扩地")),
                ]},
                {"component": "VRow", "content": [
                    col(6, switch("siqi_auto_steal", "思齐：每日偷菜")),
                    col(6, switch("siqi_auto_like", "思齐：每日点赞")),
                ]},
                {"component": "VRow", "content": [
                    col(12, {"component": "VTextarea", "props": {
                        "model": "site_overrides",
                        "label": "单站策略覆盖（JSON，可选）",
                        "hint": "示例：{\"playlet\":{\"min_profit_rate\":0.1,\"max_profit_rate\":0.5,\"max_sell_per_run\":20}}；支持 min_profit_rate/max_profit_rate/max_sell_per_run/expire_threshold_minutes/request_interval/use_proxy/dry_run/mode/enabled",
                        "persistent-hint": True,
                        "rows": 4,
                    }}),
                ]},
            ],
        }], {
            "enabled": False,
            "notify": True,
            "run_once": False,
            "mode": "smart",
            "site_ids": [],
            "interval_minutes": 61,
            "harvest_interval_minutes": 61,
            "expire_threshold_minutes": 120,
            "min_profit_rate": 0.0,
            "max_profit_rate": 0.0,
            "max_sell_per_run": 50,
            "request_interval": 1.0,
            "retry_count": 3,
            "use_proxy": False,
            "dry_run": False,
            "siqi_auto_captcha_harvest": False,
            "siqi_auto_steal": False,
            "siqi_auto_like": False,
            "siqi_auto_buy_slot": False,
            "siqi_captcha_ocr": True,
            "site_overrides": "{}",
        }

    def stop_service(self):
        pass
