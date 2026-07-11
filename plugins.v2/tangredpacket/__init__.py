# input: MoviePilot 站点 Cookie、插件配置、定时调度器
# output: 不可躺红包任务执行、事件记录和通知
# pos: V2 站点任务插件，按 Cron 自动发现并串行领取不可躺红包
import json
import re
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from apscheduler.triggers.cron import CronTrigger

from app.core.event import Event, eventmanager
from app.db.site_oper import SiteOper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import NotificationType
from app.schemas.types import EventType


class CookieExpiredError(RuntimeError):
    """Cookie 失效或无权限访问红包接口。"""


class RateLimitState:
    """记录接口限流头，并在额度接近耗尽时延长等待。"""

    def __init__(self):
        self.limit = None
        self.remaining = None

    def update(self, headers):
        limit = TangRedPacket._TangRedPacket__to_int(headers.get("x-ratelimit-limit"))
        remaining = TangRedPacket._TangRedPacket__to_int(headers.get("x-ratelimit-remaining"))
        if limit is not None:
            self.limit = limit
        if remaining is not None:
            self.remaining = remaining
            logger.info(f"不可躺红包接口限流剩余额度：{self.remaining}/{self.limit or '?'}")

    def sleep_seconds(self, normal_seconds: float, interval: float) -> float:
        if self.remaining is None:
            return normal_seconds
        if self.remaining <= 0:
            return max(normal_seconds, interval)
        if self.limit and self.remaining <= max(1, int(self.limit * 0.1)):
            return max(normal_seconds, min(interval, normal_seconds * 5))
        return normal_seconds


class TangRedPacket(_PluginBase):
    plugin_name = "不可躺自动领红包"
    plugin_desc = "自动发现并串行领取不可躺红包,支持限流感知和历史统计。"
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/tangredpacket.png"
    plugin_version = "1.0.3"
    plugin_author = "wuyaos"
    author_url = "https://github.com/wuyaos/MoviePilot-Plugins"
    plugin_config_prefix = "tangredpacket_"
    plugin_order = 31
    auth_level = 1

    SITE_DOMAIN = "www.tangpt.top"
    BASE = "https://www.tangpt.top"
    LATEST = f"{BASE}/api/redpacket/latest"
    DETAIL = f"{BASE}/api/redpacket/detail"
    CLAIM = f"{BASE}/api/redpacket/claim"
    REFERER = f"{BASE}/index.php"
    MAX_BATCH = 100
    MAX_EVENTS = 500
    MAX_RETRIES = 3
    HEADERS = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": REFERER,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
        ),
    }

    _enabled = False
    _notify = True
    _cron = "*/10 * * * *"
    _site_domain = "www.tangpt.top"
    _fast_mode = False
    _claim_interval = 1.0
    _poll_interval = 60.0
    _run_once = False
    _dry_run = False
    _lock = threading.Lock()

    def init_plugin(self, config: dict = None):
        config = config or {}
        if "enabled" in config:
            self._enabled = bool(config.get("enabled"))
        self._notify = bool(config.get("notify", True))
        self._cron = self.__safe_str(config.get("cron"), "*/10 * * * *")
        self._site_domain = self.__safe_str(config.get("site_domain"), self.SITE_DOMAIN)
        self._fast_mode = bool(config.get("fast_mode", False))
        self._claim_interval = self.__safe_float(config.get("claim_interval"), 1.0, min_value=0.0)
        self._poll_interval = self.__safe_float(config.get("poll_interval"), 60.0, min_value=1.0)
        self._dry_run = bool(config.get("dry_run", False))
        self._run_once = bool(config.get("run_once", False))
        logger.info(
            f"不可躺自动领红包初始化完成：enabled={self._enabled}, notify={self._notify}, "
            f"cron={repr(self._cron)}, site_domain={self._site_domain}, fast_mode={self._fast_mode}, "
            f"dry_run={self._dry_run}, claim_interval={self._claim_interval}, poll_interval={self._poll_interval}"
        )
        if self._run_once:
            self._run_once = False
            self.update_config({
                "enabled": self._enabled,
                "notify": self._notify,
                "cron": self._cron,
                "site_domain": self._site_domain,
                "fast_mode": self._fast_mode,
                "claim_interval": self._claim_interval,
                "poll_interval": self._poll_interval,
                "dry_run": self._dry_run,
                "run_once": False
            })
            logger.info("收到配置页立即运行请求，后台启动领红包任务")
            threading.Thread(target=self.run_claim_task, daemon=True).start()

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return [
            {
                "cmd": "/tang_redpacket_run",
                "event": EventType.PluginAction,
                "desc": "立即执行不可躺红包领取",
                "category": "站点",
                "data": {
                    "action": "tang_redpacket_run"
                }
            }
        ]

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/TangRedPacket/run",
                "endpoint": self.run_once_api,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "立即执行不可躺红包领取",
                "description": "按当前插件配置立即执行一次不可躺红包领取任务。"
            },
            {
                "path": "/TangRedPacket/summary",
                "endpoint": self.summary_api,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "查询红包领取汇总",
                "description": "查询不可躺红包领取历史汇总。"
            }
        ]

    def get_service(self) -> List[Dict[str, Any]]:
        if not self._enabled:
            logger.info("不可躺自动领红包定时服务未注册：插件未启用")
            return []
        if not self._cron:
            logger.warning("不可躺自动领红包定时服务未注册：Cron 为空")
            return []
        try:
            trigger = CronTrigger.from_crontab(self._cron)
        except Exception as err:
            logger.warning(f"不可躺自动领红包 Cron 配置无效：cron={repr(self._cron)}，error={err}")
            return []
        return [
            {
                "id": "TangRedPacket",
                "name": "不可躺自动领红包",
                "trigger": trigger,
                "func": self.run_claim_task
            }
        ]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [{"component": "VSwitch", "props": {"model": "enabled", "label": "启用插件"}}]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [{"component": "VSwitch", "props": {"model": "notify", "label": "发送通知"}}]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [{"component": "VSwitch", "props": {"model": "dry_run", "label": "仅检测不领取"}}]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "run_once",
                                            "label": "立即运行一次",
                                            "hint": "保存配置后执行，并自动关闭"
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VCronField",
                                        "props": {
                                            "model": "cron",
                                            "label": "执行周期",
                                            "placeholder": "*/10 * * * *",
                                            "hint": "5位 Cron 表达式，例如 */10 * * * *"
                                        }
                                    }
                                ]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "site_domain",
                                            "label": "站点域名",
                                            "placeholder": "www.tangpt.top"
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "fast_mode",
                                            "label": "快速模式",
                                            "hint": "跳过 detail 直接 claim，平均分配红包安全"
                                        }
                                    }
                                ]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "claim_interval",
                                            "label": "领取间隔(秒)",
                                            "type": "number",
                                            "min": 0
                                        }
                                    }
                                ]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "poll_interval",
                                            "label": "限流轮询间隔(秒)",
                                            "type": "number",
                                            "min": 1
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "enabled": self._enabled,
            "notify": self._notify,
            "run_once": False,
            "dry_run": self._dry_run,
            "cron": self._cron,
            "site_domain": self._site_domain,
            "fast_mode": self._fast_mode,
            "claim_interval": self._claim_interval,
            "poll_interval": self._poll_interval
        }

    def get_page(self) -> List[dict]:
        try:
            summary = self.__get_summary()
            events = self.__get_events()[-50:]
            event_text_map = {
                "claim_ok": "成功",
                "claim_fail": "失败",
                "claim_skip": "跳过"
            }
            packet_type_text_map = {
                "random": "拼手气",
                "equal": "平均"
            }
            table_items = []
            for event in reversed(events):
                item = event.copy()
                item["event_text"] = event_text_map.get(item.get("event"), item.get("event") or "-")
                item["packet_type_text"] = packet_type_text_map.get(
                    item.get("packet_type"), item.get("packet_type") or "-"
                )
                item["reason_or_message"] = item.get("reason") or item.get("message") or ""
                table_items.append(item)

            by_sender_items = [
                {"name": name, "count": value.get("magic", 0), "claimed": value.get("claimed", 0)}
                for name, value in sorted(
                    (summary.get("by_sender") or {}).items(),
                    key=lambda item: item[1].get("magic", 0) if isinstance(item[1], dict) else 0,
                    reverse=True
                )
                if isinstance(value, dict)
            ]
            by_title_items = [
                {"name": name, "count": value.get("magic", 0), "claimed": value.get("claimed", 0)}
                for name, value in sorted(
                    (summary.get("by_title") or {}).items(),
                    key=lambda item: item[1].get("magic", 0) if isinstance(item[1], dict) else 0,
                    reverse=True
                )
                if isinstance(value, dict)
            ]
            by_date_items = [
                {"name": name, "count": value.get("magic", 0)}
                for name, value in sorted((summary.get("by_date") or {}).items())
                if isinstance(value, dict) and self.__safe_float(value.get("magic"), 0) > 0
            ]
            trend_data = [
                {"x": item.get("name"), "y": self.__safe_float(item.get("count"), 0)}
                for item in by_date_items
            ]
            updated_at = str(summary.get("updated_at") or "")[:19]
            last_round = summary.get("last_round") if isinstance(summary.get("last_round"), dict) else {}
            remaining_claimable_count = last_round.get("remaining_claimable_count")
            latest_total_packet_count = last_round.get("latest_total_packet_count")
            latest_items_count = last_round.get("latest_items_count", 0)
            daily_limit = last_round.get("daily_limit")
            daily_claimed = last_round.get("daily_claimed")
            daily_claimed_source = last_round.get("daily_claimed_source")
            quota_known = daily_limit is not None and daily_claimed is not None
            remaining_display = remaining_claimable_count if quota_known else "-"
            mode_text = []
            if self._fast_mode:
                mode_text.append("快速模式")
            if self._dry_run:
                mode_text.append("仅检测不领取")
            tip_text = " / ".join(mode_text) if mode_text else "暂无记录"
            if updated_at:
                tip_text = f"{tip_text}，最近更新时间：{updated_at}" if mode_text else f"最近更新时间：{updated_at}"
            tip_text = f"{tip_text}，接口待领数 {latest_total_packet_count if latest_total_packet_count is not None else '-'} / items {latest_items_count}"
            if quota_known:
                claimed_label = "本站今日已领" if daily_claimed_source == "site" else "本插件今日已领"
                tip_text = f"{tip_text}，每日上限 {daily_limit}，{claimed_label} {daily_claimed}，离上限 {remaining_display}"

            content = [
                {
                    "component": "VCard",
                    "props": {"variant": "tonal", "class": "mb-4"},
                    "content": [
                        {
                            "component": "VCardTitle",
                            "text": "红包领取概览"
                        },
                        {
                            "component": "VCardText",
                            "content": [
                                {
                                    "component": "VRow",
                                    "content": [
                                        self.__info_col("累计领取数", summary.get("total_claimed")),
                                        self.__info_col("累计失败数", summary.get("total_failed")),
                                        self.__info_col("累计魔力", summary.get("total_magic_gained")),
                                        self.__info_col("剩余可领(离上限)", remaining_display),
                                    ]
                                },
                                {
                                    "component": "div",
                                    "props": {"class": "text-caption text-medium-emphasis mt-2"},
                                    "text": tip_text
                                }
                            ]
                        }
                    ]
                },
                {
                    "component": "VDataTable",
                    "props": {
                        "headers": [
                            {"title": "时间", "key": "time"},
                            {"title": "事件", "key": "event_text"},
                            {"title": "红包ID", "key": "packet_id"},
                            {"title": "发送者", "key": "sender"},
                            {"title": "头衔", "key": "title_name"},
                            {"title": "类型", "key": "packet_type_text"},
                            {"title": "获得魔力", "key": "magic_amount"},
                            {"title": "领取后魔力", "key": "user_bonus_after"},
                            {"title": "剩余个数", "key": "remain_count"},
                            {"title": "剩余魔力", "key": "remain_magic"},
                            {"title": "原因/消息", "key": "reason_or_message"}
                        ],
                        "items": table_items,
                        "items-per-page": 10,
                        "hide-default-footer": True,
                        "density": "compact"
                    }
                },
                {
                    "component": "VDivider",
                    "props": {"class": "my-4"}
                },
                {
                    "component": "VRow",
                    "content": [
                        {
                            "component": "VCol",
                            "props": {"cols": 12, "md": 6},
                            "content": [
                                {
                                    "component": "VCard",
                                    "props": {"variant": "tonal", "class": "h-100"},
                                    "content": [
                                        {
                                            "component": "VCardTitle",
                                            "text": "按发送者统计"
                                        },
                                        {
                                            "component": "VCardText",
                                            "content": [
                                                self.__summary_chart("发送者魔力分布", by_sender_items)
                                            ]
                                        }
                                    ]
                                }
                            ]
                        },
                        {
                            "component": "VCol",
                            "props": {"cols": 12, "md": 6},
                            "content": [
                                {
                                    "component": "VCard",
                                    "props": {"variant": "tonal", "class": "h-100"},
                                    "content": [
                                        {
                                            "component": "VCardTitle",
                                            "text": "按头衔统计"
                                        },
                                        {
                                            "component": "VCardText",
                                            "content": [
                                                self.__summary_chart("头衔魔力分布", by_title_items)
                                            ]
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
            content.append({
                "component": "VCard",
                "props": {"variant": "tonal", "class": "mt-4"},
                "content": [
                    {
                        "component": "VCardTitle",
                        "text": "按日期趋势"
                    },
                    {
                        "component": "VCardText",
                        "content": [
                            {
                                "component": "VApexChart",
                                "props": {
                                    "height": 260,
                                    "type": "bar",
                                    "options": {
                                        "chart": {"type": "bar", "toolbar": {"show": False}},
                                        "xaxis": {"type": "category"},
                                        "title": {"text": "每日领取魔力"},
                                        "noData": {"text": "暂无数据"}
                                    },
                                    "series": [
                                        {
                                            "name": "魔力",
                                            "data": trend_data
                                        }
                                    ] if trend_data else []
                                }
                            }
                        ]
                    }
                ]
            })
            return content
        except Exception as err:
            logger.error(f"不可躺红包详情页渲染失败：{err}")
            return [
                {
                    "component": "VAlert",
                    "props": {"type": "error", "variant": "tonal"},
                    "text": f"详情页加载失败：{err}"
                }
            ]

    def stop_service(self):
        pass

    def run_once_api(self) -> Dict[str, Any]:
        if not self._enabled:
            logger.warning("立即执行请求被忽略：插件未启用")
            return {"success": False, "message": "插件未启用"}
        if self._lock.locked():
            logger.warning("立即执行请求被忽略：已有红包领取任务正在执行")
            return {"success": False, "message": "已有红包领取任务正在执行"}
        logger.info("收到 API 立即执行请求，后台启动领红包任务")
        threading.Thread(target=self.run_claim_task, daemon=True).start()
        return {"success": True, "message": "任务已开始，完成后会写入历史记录并按配置发送通知"}

    def summary_api(self) -> Dict[str, Any]:
        summary = self.__get_summary()
        if not summary:
            return {
                "message": "暂无数据",
                "fast_mode": self._fast_mode,
                "dry_run": self._dry_run,
                "claim_interval": self._claim_interval,
                "poll_interval": self._poll_interval
            }
        result = summary.copy()
        result.update({
            "fast_mode": self._fast_mode,
            "dry_run": self._dry_run,
            "claim_interval": self._claim_interval,
            "poll_interval": self._poll_interval
        })
        return result

    @eventmanager.register(EventType.PluginAction)
    def run_once_command(self, event: Event = None):
        event_data = event.event_data if event else {}
        if not event_data or event_data.get("action") != "tang_redpacket_run":
            return
        channel = event_data.get("channel")
        userid = event_data.get("user")
        if not self._enabled:
            logger.warning("TG 命令立即执行请求被忽略：插件未启用")
            self.post_message(
                channel=channel,
                userid=userid,
                mtype=NotificationType.Plugin,
                title="【不可躺自动领红包】",
                text="插件未启用，无法执行红包领取任务。"
            )
            return
        if self._lock.locked():
            logger.warning("TG 命令立即执行请求被忽略：已有红包领取任务正在执行")
            self.post_message(
                channel=channel,
                userid=userid,
                mtype=NotificationType.Plugin,
                title="【不可躺自动领红包】",
                text="已有红包领取任务正在执行，请等待当前任务结束。"
            )
            return
        logger.info("收到 TG 命令立即执行请求，后台启动领红包任务")
        threading.Thread(target=self.run_claim_task, daemon=True).start()
        self.post_message(
            channel=channel,
            userid=userid,
            mtype=NotificationType.Plugin,
            title="【不可躺自动领红包】",
            text="任务已开始，完成后会写入历史记录并按配置发送通知。"
        )

    @staticmethod
    def __info_col(label: str, value: Any) -> Dict[str, Any]:
        return {
            "component": "VCol",
            "props": {"cols": 6, "md": 3},
            "content": [
                {
                    "component": "div",
                    "props": {"class": "text-caption text-medium-emphasis"},
                    "text": label
                },
                {
                    "component": "div",
                    "props": {"class": "text-h6"},
                    "text": str("-" if value is None or value == "" else value)
                }
            ]
        }

    @staticmethod
    def __summary_chart(title: str, items: List[dict]) -> Dict[str, Any]:
        chart_items = []
        labels = []
        for item in items:
            count = item.get("count")
            if not isinstance(count, (int, float)):
                continue
            count_value = float(count)
            if count_value <= 0:
                continue
            claimed = item.get("claimed") if isinstance(item.get("claimed"), (int, float)) else 0
            average = count_value / claimed if claimed else 0
            chart_items.append(item)
            labels.append(
                f"{item.get('name')}（总魔力 {TangRedPacket.__format_number(count_value)} / "
                f"{TangRedPacket.__format_number(claimed)} 个，平均 {TangRedPacket.__format_number(average)}）"
            )
        return {
            "component": "VApexChart",
            "props": {
                "height": 260,
                "type": "pie",
                "options": {
                    "chart": {
                        "type": "pie"
                    },
                    "labels": labels,
                    "title": {
                        "text": title
                    },
                    "legend": {
                        "show": True,
                        "position": "bottom"
                    },
                    "plotOptions": {
                        "pie": {
                            "expandOnClick": False
                        }
                    },
                    "noData": {
                        "text": "暂无数据"
                    }
                },
                "series": [item.get("count") for item in chart_items]
            }
        }

    def run_claim_task(self) -> Dict[str, Any]:
        if not self._lock.acquire(blocking=False):
            logger.warning("领红包任务启动失败：已有任务正在执行")
            return {"status": "running", "message": "已有领红包任务正在执行"}
        try:
            result = self.__new_result()
            cookie = (self.__get_site_cookie() or "").strip()
            if not cookie or "c_secure_pass=" not in cookie:
                logger.warning("领红包任务终止：缺少包含 c_secure_pass 的 不可躺 Cookie")
                result.update({"status": "auth_failed", "message": "缺少包含 c_secure_pass 的 不可躺 Cookie"})
                self.__append_event({"event": "auth_failed", "message": result["message"]})
                self.__apply_daily_quota(result)
                if self._notify:
                    self.__send_notification(result)
                return result

            session = requests.Session()
            session.headers.update(self.HEADERS)
            session.cookies.update(self.__cookie_to_dict(cookie))
            rate_limit = RateLimitState()
            claimed_ids = self.__get_claimed_ids()
            dead_ids = self.__get_dead_ids()

            try:
                latest = self.__fetch_latest(session, rate_limit)
                self.__ensure_cookie_alive(latest)
            except CookieExpiredError as err:
                result.update({"status": "auth_failed", "message": str(err)})
                self.__append_event({"event": "auth_failed", "message": str(err)})
                self.__apply_daily_quota(result)
                if self._notify:
                    self.__send_notification(result)
                return result
            except Exception as err:
                logger.error(f"领红包任务请求 latest 失败：{err}")
                result.update({"status": "failed", "message": f"请求 latest 失败：{err}"})
                self.__append_event({"event": "round_fail", "message": result["message"]})
                self.__apply_daily_quota(result)
                return result

            items = latest.get("items") or []
            result.update(self.__build_availability_snapshot(latest, items, claimed_ids, dead_ids))
            result["total_seen"] = len(items)
            # 空轮/禁用时也展示本插件当天已领取及离每日上限的估算值。
            self.__apply_daily_quota(result)

            if latest.get("enabled") is False:
                logger.warning("红包功能已被管理员全局关闭，停止本轮处理")
                result.update({"status": "disabled", "message": "红包功能已被管理员全局关闭"})
                self.__append_event({"event": "round_disabled", "message": result["message"]})
                self.__update_summary(last_round=self.__build_last_round(result))
                return result

            if not items:
                logger.info(f"暂无可领红包：total_packet_count={latest.get('total_packet_count', 0)}")
                result.update({"status": "empty", "message": "暂无可领红包"})
                self.__append_event({"event": "round_empty", "total_packet_count": latest.get("total_packet_count", 0)})
                self.__update_summary(last_round=self.__build_last_round(result))
                return result

            logger.info(
                f"发现 {len(items)} 个可领红包，fast_mode={self._fast_mode}，dry_run={self._dry_run}，开始串行处理"
            )
            auth_fail_count = 0
            for item in items[:self.MAX_BATCH]:
                try:
                    self.__process_packet(session, rate_limit, item, claimed_ids, dead_ids, result)
                except CookieExpiredError:
                    auth_fail_count += 1
                except Exception as err:
                    logger.error(f"处理单个红包异常，已隔离并继续后续红包：{err}")
                    result["failed_count"] += 1
                    self.__append_event({
                        "event": "claim_fail",
                        "packet_id": item.get("id") if isinstance(item, dict) else None,
                        "reason": f"处理异常：{err}"
                    })

            # 网站达上限消息可给出权威累计；否则按本插件当日 claim_ok 记录统计
            reached_limit = self.__apply_daily_quota(result)
            if items and auth_fail_count == len(items):
                result.update({"status": "auth_failed", "message": "detail/claim 全部返回 401/403，Cookie 可能已过期"})
                self.__append_event({"event": "auth_failed", "message": result["message"]})
            else:
                if reached_limit:
                    result.update({"status": "completed", "message": f"今日领取已达上限（每天最多领 {result.get('daily_limit')} 个）"})
                else:
                    result.update({"status": "completed", "message": "领红包任务完成"})
            self.save_data("claimed_ids", sorted(claimed_ids))
            self.save_data("dead_ids", sorted(dead_ids))
            self.__update_summary(last_round=self.__build_last_round(result))
            # 达上限去重：同一天只对「纯达上限轮」去重；有成功领取仍通知
            today_str = datetime.now().strftime("%Y-%m-%d")
            notified_date = self.get_data("limit_notified_date")
            pure_limit_round = reached_limit and not result.get("claimed_count")
            skip_for_limit = pure_limit_round and notified_date == today_str
            if self._notify and skip_for_limit:
                logger.info(f"今日已发送过达上限通知，跳过本次重复通知：{today_str}")
            elif self._notify and (result.get("claimed_count") or result.get("failed_count") or result.get("status") == "auth_failed"):
                self.__send_notification(result)
                if pure_limit_round:
                    self.save_data("limit_notified_date", today_str)
            elif not self._notify:
                logger.info("领红包任务通知未发送：发送通知开关未开启")
            logger.info(f"领红包任务结束：{self.__to_log_text(result)}")
            return result
        finally:
            self._lock.release()

    def __process_packet(self, session: requests.Session, rate_limit: RateLimitState, item: Dict[str, Any],
                         claimed_ids: set, dead_ids: set, result: Dict[str, Any]):
        packet_id = item.get("id")
        if packet_id is None:
            result["skipped_count"] += 1
            self.__append_event({"event": "claim_skip", "reason": "missing_id"})
            return
        packet_key = str(packet_id)
        sender = item.get("sender", "?")
        title = item.get("title_name", "")
        title_class = item.get("title_class")
        message = item.get("message", "")
        packet_type = item.get("type")
        total_count = item.get("total_count")
        remain_count = self.__to_int(item.get("remain_count"))
        remain_magic = None

        if packet_key in claimed_ids:
            result["skipped_count"] += 1
            logger.info(f"CLAIM_SKIP packet_id={packet_key} sender={sender} reason=already_claimed")
            self.__append_event({
                "event": "claim_skip", "packet_id": packet_id, "sender": sender,
                "title_name": title, "reason": "already_claimed"
            })
            return
        if packet_key in dead_ids:
            result["skipped_count"] += 1
            logger.info(f"CLAIM_SKIP packet_id={packet_key} sender={sender} reason=dead")
            self.__append_event({
                "event": "claim_skip", "packet_id": packet_id, "sender": sender,
                "title_name": title, "reason": "dead"
            })
            return

        if self._fast_mode:
            logger.info(f"红包 #{packet_key} 来自 {sender} 剩余{remain_count if remain_count is not None else '?'}个/共{total_count or '?'}个")
            if remain_count is not None and remain_count <= 0:
                result["skipped_count"] += 1
                dead_ids.add(packet_key)
                self.__append_event({
                    "event": "claim_skip", "packet_id": packet_id, "sender": sender,
                    "title_name": title, "title_class": title_class, "reason": "snatched_empty"
                })
                return
        else:
            detail = self.__fetch_detail(session, rate_limit, packet_key)
            if self.__is_auth_fail(detail):
                logger.error(f"红包 #{packet_key} detail 返回 401/403，疑似 Cookie 过期")
                raise CookieExpiredError("detail 返回 401/403，Cookie 可能已过期")
            if self.__is_fail(detail):
                detail_message = str(detail.get("message") or detail)
                result["skipped_count"] += 1
                logger.warning(f"CLAIM_SKIP packet_id={packet_key} sender={sender} reason=detail_error")
                self.__append_event({
                    "event": "claim_skip", "packet_id": packet_id, "sender": sender,
                    "title_name": title, "reason": "detail_error", "message": detail_message
                })
                if self.__is_terminal_message(detail_message):
                    dead_ids.add(packet_key)
                return
            packet = detail.get("packet") or {}
            if isinstance(packet, dict):
                sender = packet.get("sender") or sender
                title = packet.get("title_name") or title
                title_class = packet.get("title_class") or title_class
                message = packet.get("message") or message
                packet_type = packet.get("type")
                total_count = packet.get("total_count")
                remain_count = self.__to_int(packet.get("remain_count"))
                remain_magic = self.__to_int(packet.get("remain_magic"))
                if (remain_count is not None and remain_count <= 0) or remain_magic == 0:
                    result["skipped_count"] += 1
                    logger.info(f"CLAIM_SKIP packet_id={packet_key} sender={sender} reason=snatched_empty")
                    dead_ids.add(packet_key)
                    self.__append_event({
                        "event": "claim_skip", "packet_id": packet_id, "sender": sender,
                        "title_name": title, "title_class": title_class, "reason": "snatched_empty"
                    })
                    return

        if self._dry_run:
            result["skipped_count"] += 1
            self.__append_event({
                "event": "claim_skip", "packet_id": packet_id, "sender": sender,
                "title_name": title, "title_class": title_class, "reason": "dry_run"
            })
            return

        claim = self.__claim_one(session, rate_limit, packet_key)
        if self.__is_auth_fail(claim):
            logger.error(f"红包 #{packet_key} claim 返回 401/403，疑似 Cookie 过期")
            raise CookieExpiredError("claim 返回 401/403，Cookie 可能已过期")
        if self.__is_fail(claim):
            fail_message = str(claim.get("message") or claim)
            result["failed_count"] += 1
            logger.warning(f"CLAIM_FAIL packet_id={packet_key} sender={sender} reason={fail_message} http={claim.get('_http')}")
            self.__append_event({
                "event": "claim_fail", "packet_id": packet_id, "sender": sender,
                "title_name": title, "title_class": title_class, "reason": fail_message,
                "http": claim.get("_http")
            })
            # 解析每日领取上限（如「今天已经领取100个，每天最多领100个。」）
            parsed_quota = self.__parse_daily_quota(fail_message)
            if parsed_quota is not None:
                result["daily_claimed"] = parsed_quota[0]
                result["daily_limit"] = parsed_quota[1]
            if self.__is_terminal_message(fail_message):
                dead_ids.add(packet_key)
            return

        amount = claim.get("magic_amount")
        after = claim.get("user_bonus_after")
        record = {
            "event": "claim_ok",
            "packet_id": packet_id,
            "sender": sender,
            "title_name": title,
            "title_class": title_class,
            "packet_type": packet_type,
            "message": message,
            "total_count": total_count,
            "remain_count": remain_count,
            "remain_magic": remain_magic,
            "magic_amount": amount,
            "user_bonus_after": after,
        }
        self.__append_event(record)
        claimed_ids.add(packet_key)
        result["claimed_count"] += 1
        result["bonus_delta"] += self.__safe_float(amount, 0)
        result["user_bonus_after"] = after
        logger.info(
            f"CLAIM_OK packet_id={packet_key} sender={sender} title={title or ''} "
            f"type={packet_type} amount={amount if amount is not None else '?'} bonus_after={after if after is not None else '?'}"
        )
        sleep_seconds = rate_limit.sleep_seconds(self._claim_interval, self._poll_interval)
        logger.info(f"claim 后等待 {sleep_seconds:.1f} 秒防风控/限流")
        time.sleep(sleep_seconds)

    @staticmethod
    def __cookie_to_dict(cookie: str) -> Dict[str, str]:
        cookies = {}
        for item in (cookie or "").split(";"):
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            key = key.strip()
            if key:
                cookies[key] = value.strip()
        return cookies

    def __get_site_cookie(self) -> str:
        domains = []
        if self._site_domain:
            domains.append(self._site_domain)
        for domain in [self.SITE_DOMAIN, "tangpt.top"]:
            if domain not in domains:
                domains.append(domain)
        for domain in domains:
            try:
                site = SiteOper().get_by_domain(domain)
                cookie = (site.cookie or "").strip() if site else ""
                if cookie:
                    logger.info(f"读取不可躺站点 Cookie 成功：domain={domain}")
                    return cookie
            except Exception as err:
                logger.debug(f"读取不可躺站点 Cookie 失败：domain={domain}，错误={err}")
        return ""

    def __request_json(self, session: requests.Session, method: str, url: str,
                       rate_limit: RateLimitState, **kwargs) -> Dict[str, Any]:
        last_error = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = session.request(method, url, timeout=15, **kwargs)
                rate_limit.update(response.headers)
                try:
                    body = response.json()
                except ValueError:
                    body = {
                        "status": "error",
                        "message": f"非 JSON 响应 HTTP {response.status_code}: {(response.text or '')[:120]}"
                    }
                body["_http"] = response.status_code
                return body
            except requests.RequestException as err:
                last_error = err
                if attempt >= self.MAX_RETRIES:
                    break
                delay = 2 ** (attempt - 1)
                logger.warning(f"网络异常，第 {attempt}/{self.MAX_RETRIES} 次重试，{delay}s 后重试：{err}")
                time.sleep(delay)
        raise RuntimeError(f"网络请求失败，已重试 {self.MAX_RETRIES} 次：{last_error}")

    def __fetch_latest(self, session: requests.Session, rate_limit: RateLimitState) -> Dict[str, Any]:
        return self.__request_json(session, "GET", self.LATEST, rate_limit)

    def __fetch_detail(self, session: requests.Session, rate_limit: RateLimitState, packet_id: Any) -> Dict[str, Any]:
        return self.__request_json(session, "GET", f"{self.DETAIL}/{packet_id}", rate_limit)

    def __claim_one(self, session: requests.Session, rate_limit: RateLimitState, packet_id: Any) -> Dict[str, Any]:
        return self.__request_json(session, "POST", self.CLAIM, rate_limit, data={"packet_id": str(packet_id)})

    @staticmethod
    def __is_fail(body: Dict[str, Any]) -> bool:
        if body.get("_http") in (401, 403):
            return True
        if body.get("status") == "error":
            return True
        if body.get("ok") is False:
            return True
        # 红包 claim/detail 接口用 ret 字段：ret == -1 表示失败
        if body.get("ret") == -1:
            return True
        return False

    @staticmethod
    def __is_auth_fail(body: Dict[str, Any]) -> bool:
        return body.get("_http") in (401, 403)

    @staticmethod
    def __is_terminal_message(message: str) -> bool:
        # 每日达上限不是红包死亡：明天仍可领取，故不再将「每天最多」视为终态
        return "已领取" in message or "领取过" in message or "抢完" in message

    @staticmethod
    def __parse_daily_quota(message: str) -> Optional[Tuple[int, int]]:
        """从 claim 失败 message 解析每日已领数与每日上限。

        匹配「今天已经领取100个，每天最多领100个。」格式，兼容「今日/每日」。
        解析失败返回 None（不要猜）。
        """
        if not message:
            return None
        m = re.search(
            r"(?:今天|今日|每日)已经领取\s*(\d+)\s*个[，,]?\s*(?:每天|每日)最多领?\s*(\d+)\s*个",
            message,
        )
        if m:
            try:
                claimed = int(m.group(1))
                limit = int(m.group(2))
                return (claimed, limit)
            except ValueError:
                return None
        return None

    def __ensure_cookie_alive(self, latest_body: Dict[str, Any]):
        if self.__is_auth_fail(latest_body):
            raise CookieExpiredError("latest 返回 401/403，Cookie 可能已过期，请更新 c_secure_pass")

    @staticmethod
    def __to_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def __safe_str(value: Any, default: str = "") -> str:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return default

    @staticmethod
    def __safe_float(value: Any, default: float, min_value: Optional[float] = None) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = default
        if min_value is not None:
            number = max(number, min_value)
        return number

    @staticmethod
    def __local_time_iso() -> str:
        return datetime.now(timezone.utc).astimezone().isoformat()

    @staticmethod
    def __new_result() -> Dict[str, Any]:
        return {
            "task_id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
            "time": TangRedPacket.__local_time_iso(),
            "status": "running",
            "message": "",
            "total_seen": 0,
            "claimed_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "bonus_delta": 0.0,
            "user_bonus_after": "-",
            "latest_total_packet_count": None,
            "latest_items_count": 0,
            "remaining_claimable_count": None,
            "remaining_claimable_source": "",
            "daily_limit": None,
            "daily_claimed": 0,
            "daily_claimed_source": ""
        }

    def __build_availability_snapshot(self, latest: Dict[str, Any], items: List[Dict[str, Any]],
                                      claimed_ids: set, dead_ids: set) -> Dict[str, Any]:
        latest_total_packet_count = self.__to_int(latest.get("total_packet_count"))
        latest_items_count = len(items)
        remaining_claimable_count = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            packet_id = item.get("id")
            if packet_id is None:
                continue
            packet_key = str(packet_id)
            if packet_key in claimed_ids or packet_key in dead_ids:
                continue
            remain_count = self.__to_int(item.get("remain_count"))
            if remain_count is not None and remain_count <= 0:
                continue
            remaining_claimable_count += 1
        return {
            "latest_total_packet_count": latest_total_packet_count,
            "latest_items_count": latest_items_count,
            "remaining_claimable_count": remaining_claimable_count,
            "remaining_claimable_source": "total_packet_count" if latest_total_packet_count is not None else "items_inferred"
        }

    @staticmethod
    def __build_last_round(result: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "latest_total_packet_count": result.get("latest_total_packet_count"),
            "latest_items_count": result.get("latest_items_count", 0),
            "remaining_claimable_count": result.get("remaining_claimable_count"),
            "remaining_claimable_source": result.get("remaining_claimable_source", ""),
            "daily_limit": result.get("daily_limit"),
            "daily_claimed": result.get("daily_claimed"),
            "daily_claimed_source": result.get("daily_claimed_source", "")
        }

    def __append_event(self, record: Dict[str, Any]):
        event = record.copy()
        event.setdefault("time", self.__local_time_iso())
        events = self.__get_events()
        events.append(event)
        self.__save_events(events[-self.MAX_EVENTS:])
        if event.get("event") == "claim_ok" and event.get("packet_id") is not None:
            claimed_ids = self.__get_claimed_ids()
            claimed_ids.add(str(event.get("packet_id")))
            self.save_data("claimed_ids", sorted(claimed_ids))
        if event.get("event") in {"claim_fail", "claim_skip"} and event.get("packet_id") is not None:
            message = str(event.get("reason") or event.get("message") or "")
            if self.__is_terminal_message(message) or event.get("reason") in {"dead", "snatched_empty"}:
                dead_ids = self.__get_dead_ids()
                dead_ids.add(str(event.get("packet_id")))
                self.save_data("dead_ids", sorted(dead_ids))

    def __get_events(self) -> List[Dict[str, Any]]:
        events = self.get_data("events") or []
        return events if isinstance(events, list) else []

    def __get_summary(self) -> Dict[str, Any]:
        summary = self.get_data("summary") or {}
        return summary if isinstance(summary, dict) else {}

    def __save_events(self, events: List[Dict[str, Any]]):
        self.save_data("events", events[-self.MAX_EVENTS:])

    def __get_claimed_ids(self) -> set:
        data = self.get_data("claimed_ids") or []
        return {str(item) for item in data if item is not None} if isinstance(data, list) else set()

    def __get_dead_ids(self) -> set:
        data = self.get_data("dead_ids") or []
        return {str(item) for item in data if item is not None} if isinstance(data, list) else set()

    def __get_local_daily_claimed(self) -> int:
        """统计本插件在本地时区当天成功领取的红包数量。"""
        today = datetime.now().astimezone().strftime("%Y-%m-%d")
        return sum(
            1 for event in self.__get_events()
            if event.get("event") == "claim_ok" and str(event.get("time") or "").startswith(today)
        )

    def __apply_daily_quota(self, result: Dict[str, Any]) -> bool:
        """填充每日领取统计；网站上限消息优先于本插件本地统计。"""
        site_daily_claimed = result.get("daily_claimed")
        site_daily_limit = result.get("daily_limit")
        site_quota_known = site_daily_claimed is not None and site_daily_limit is not None
        if site_quota_known:
            daily_claimed = site_daily_claimed
            daily_limit = site_daily_limit
            result["daily_claimed_source"] = "site"
        else:
            daily_claimed = self.__get_local_daily_claimed()
            daily_limit = self.MAX_BATCH
            result["daily_claimed_source"] = "plugin"
        result["daily_claimed"] = daily_claimed
        result["daily_limit"] = daily_limit
        result["remaining_claimable_count"] = max(0, daily_limit - daily_claimed)
        return site_quota_known and daily_claimed >= daily_limit

    def __update_summary(self, last_round: Optional[Dict[str, Any]] = None):
        old_summary = self.__get_summary()
        summary = {
            "updated_at": self.__local_time_iso(),
            "total_claimed": 0,
            "total_failed": 0,
            "total_magic_gained": 0,
            "by_sender": {},
            "by_title": {},
            "by_date": {},
            "recent": [],
            "last_round": last_round if last_round is not None else old_summary.get("last_round", {}),
        }
        for event in self.__get_events():
            event_name = event.get("event")
            if event_name == "claim_fail":
                summary["total_failed"] += 1
                continue
            if event_name != "claim_ok":
                continue
            magic_value = self.__safe_float(event.get("magic_amount"), 0)
            summary["total_claimed"] += 1
            summary["total_magic_gained"] += magic_value
            sender = str(event.get("sender") or "未知")
            title = str(event.get("title_name") or "未知头衔")
            date_key = str(event.get("time") or "")[:10] or "未知日期"
            for bucket_name, key in (("by_sender", sender), ("by_title", title), ("by_date", date_key)):
                bucket = summary[bucket_name].setdefault(key, {"claimed": 0, "magic": 0})
                bucket["claimed"] += 1
                bucket["magic"] += magic_value
            summary["recent"].append(event)
        summary["recent"] = summary["recent"][-10:]
        for bucket_name in ("by_sender", "by_title", "by_date"):
            for item in summary[bucket_name].values():
                if isinstance(item.get("magic"), float) and item["magic"].is_integer():
                    item["magic"] = int(item["magic"])
        if isinstance(summary["total_magic_gained"], float) and summary["total_magic_gained"].is_integer():
            summary["total_magic_gained"] = int(summary["total_magic_gained"])
        self.save_data("summary", summary)

    def __send_notification(self, result: Dict[str, Any]):
        title = "【不可躺自动领红包】"
        remaining_claimable_count = result.get("remaining_claimable_count")
        latest_total_packet_count = result.get("latest_total_packet_count")
        daily_limit = result.get("daily_limit")
        daily_claimed = result.get("daily_claimed")
        daily_claimed_source = result.get("daily_claimed_source")
        quota_known = daily_limit is not None and daily_claimed is not None
        remaining_display = remaining_claimable_count if quota_known else "-"
        claimed_label = "本站今日已领" if daily_claimed_source == "site" else "本插件今日已领"
        quota_text = (
            f"{claimed_label}：{daily_claimed} 个，每日上限：{daily_limit} 个\n"
            if quota_known else "本插件今日已领：-（暂无本地成功记录）\n"
        )
        text = (
            f"任务状态：{result.get('status')}\n"
            f"本轮发现：{result.get('total_seen', 0)} 个红包\n"
            f"{quota_text}"
            f"剩余可领：{remaining_display} 个\n"
            f"领取成功：{result.get('claimed_count', 0)} 个，失败：{result.get('failed_count', 0)} 个，跳过：{result.get('skipped_count', 0)} 个\n"
            f"魔力增加：{self.__format_number(result.get('bonus_delta', 0))}，当前魔力：{result.get('user_bonus_after', '-')}\n"
            f"说明：{result.get('message') or '-'}"
        )
        logger.info(f"准备发送领红包任务通知：title={title}，text={text}")
        self.post_message(mtype=NotificationType.Plugin, title=title, text=text)

    @staticmethod
    def __format_number(value: Any) -> Any:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return value
        return int(number) if number.is_integer() else round(number, 4)

    @staticmethod
    def __to_log_text(value: Any, max_length: int = 6000) -> str:
        try:
            if isinstance(value, str):
                text = value
            else:
                text = json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
            text = str(value)
        text = " ".join(text.split())
        if len(text) > max_length:
            return f"{text[:max_length]}...（已截断，原始长度 {len(text)}）"
        return text
