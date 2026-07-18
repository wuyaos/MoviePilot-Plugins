# input: MoviePilot 站点 Cookie、插件配置、定时调度器
# output: 不可躺红包任务执行、事件记录和通知
# pos: V2 站点任务插件，按 Cron 自动发现并串行领取不可躺红包
import json
import math
import re
import threading
import time
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
    plugin_version = "1.0.10"
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
    DAILY_LIMIT = 100
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
            events = self.__get_events()
            recent_events = events[-50:]
            event_text_map = {
                "claim_ok": "成功",
                "claim_fail": "失败",
                "claim_skip": "跳过",
                "round_summary": "本轮汇总"
            }
            packet_type_text_map = {
                "random": "拼手气",
                "equal": "平均"
            }
            table_items = []
            for event in reversed(recent_events):
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
            round_rows = [self.__round_history_row(event) for event in reversed(events)
                          if event.get("event") == "round_summary"]
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
                claimed_label = {
                    "site": "本站今日已领",
                    "reconciled": "校准后今日已领",
                }.get(daily_claimed_source, "本插件今日已领（估）")
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
                                                self.__summary_chart("发送者魔力分布", by_sender_items),
                                                self.__summary_chart("发送者平均单笔魔力", by_sender_items, mode="avg")
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
                                                self.__summary_chart("头衔魔力分布", by_title_items),
                                                self.__summary_chart("头衔平均单笔魔力", by_title_items, mode="avg")
                                            ]
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
            if not round_rows and last_round:
                round_rows = [self.__round_history_row({
                    **last_round,
                    "event": "round_summary",
                    "time": updated_at,
                    "status": last_round.get("status") or "-",
                    "message": last_round.get("message") or "最近本轮汇总"
                })]
            history_table_rows = []
            for row in round_rows[:50]:
                history_table_rows.append({
                    "component": "tr",
                    "content": [
                        {"component": "td", "props": {"class": "text-caption text-no-wrap"}, "text": row.get("time") or "-"},
                        {"component": "td", "props": {"class": "text-caption text-no-wrap"}, "text": row.get("total_seen")},
                        {"component": "td", "props": {"class": "text-caption text-no-wrap", "style": "color: rgb(var(--v-theme-success));"}, "text": row.get("claimed_count")},
                        {"component": "td", "props": {"class": "text-caption text-no-wrap", "style": "color: rgb(var(--v-theme-error));" if row.get("failed_count") not in ("0", 0, "-") else ""}, "text": row.get("failed_count")},
                        {"component": "td", "props": {"class": "text-caption text-no-wrap"}, "text": row.get("skipped_count")},
                        {"component": "td", "props": {"class": "text-caption text-no-wrap font-weight-medium"}, "text": row.get("quota_status")},
                        {"component": "td", "props": {"class": "text-caption text-no-wrap", "style": "color: rgb(var(--v-theme-success));"}, "text": row.get("bonus_delta")},
                        {"component": "td", "props": {"class": "text-caption text-no-wrap"}, "text": row.get("user_bonus_after")},
                        {"component": "td", "props": {"class": "text-caption", "style": "white-space: normal; min-width: 180px;"}, "text": row.get("message") or "-"}
                    ]
                })
            history_body = [
                {
                    "component": "VTable",
                    "props": {"hover": True, "density": "comfortable", "class": "text-no-wrap"},
                    "content": [
                        {
                            "component": "thead",
                            "content": [{
                                "component": "tr",
                                "content": [
                                    {"component": "th", "text": "时间"},
                                    {"component": "th", "text": "本轮红包"},
                                    {"component": "th", "text": "成功"},
                                    {"component": "th", "text": "失败"},
                                    {"component": "th", "text": "跳过"},
                                    {"component": "th", "text": "状态"},
                                    {"component": "th", "text": "魔力增加"},
                                    {"component": "th", "text": "当前魔力"},
                                    {"component": "th", "text": "说明"}
                                ]
                            }]
                        },
                        {"component": "tbody", "content": history_table_rows}
                    ]
                }
            ] if history_table_rows else [
                {
                    "component": "VAlert",
                    "props": {"type": "info", "variant": "tonal", "class": "ma-2"},
                    "text": "暂无本轮汇总，新一轮领取完成后会显示每轮统计"
                }
            ]
            content.append({
                "component": "VCard",
                "props": {"variant": "outlined", "class": "mt-4"},
                "content": [
                    {
                        "component": "VCardTitle",
                        "props": {"class": "d-flex align-center"},
                        "content": [
                            {"component": "VIcon", "props": {"style": "color: #9C27B0;", "class": "mr-2"}, "text": "mdi-history"},
                            {"component": "span", "props": {"class": "text-h6 font-weight-bold"}, "text": "领取历史（本轮汇总）"}
                        ]
                    },
                    {"component": "VDivider"},
                    {
                        "component": "VCardText",
                        "props": {"class": "pa-0 pa-md-2", "style": "height: 400px; overflow-y: auto;"},
                        "content": history_body
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
            return False
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
            return False
        if self._lock.locked():
            logger.warning("TG 命令立即执行请求被忽略：已有红包领取任务正在执行")
            self.post_message(
                channel=channel,
                userid=userid,
                mtype=NotificationType.Plugin,
                title="【不可躺自动领红包】",
                text="已有红包领取任务正在执行，请等待当前任务结束。"
            )
            return False
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
    def __summary_chart(title: str, items: List[dict], mode: str = "total") -> Dict[str, Any]:
        labels = []
        values = []
        for item in items:
            count = item.get("count")
            if not isinstance(count, (int, float)):
                continue
            count_value = float(count)
            if count_value <= 0:
                continue
            claimed = item.get("claimed")
            if isinstance(claimed, (int, float)):
                claimed_value = float(claimed)
            else:
                claimed_value = 0
            if mode == "avg":
                if claimed_value <= 0:
                    continue
                value = count_value / claimed_value
            else:
                value = count_value
            if value <= 0:
                continue
            labels.append(str(item.get("name")))
            values.append(value)
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
                        "position": "right"
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
                "series": values
            }
        }

    def run_claim_task(self) -> Dict[str, Any]:
        if not self._lock.acquire(blocking=False):
            logger.warning("领红包任务启动失败：已有任务正在执行")
            return {"status": "running", "message": "已有领红包任务正在执行"}
        try:
            result = self.__new_result()
            result["quota_date"] = self.__local_date()
            result["daily_claimed_before"] = self.__get_daily_quota_state(result["quota_date"])["claimed_count"]
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
                result["skipped_count"] = len(items)
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
            stopped_at_limit = False
            batch_items = items[:self.MAX_BATCH]
            for index, item in enumerate(batch_items):
                try:
                    if self.__process_packet(session, rate_limit, item, claimed_ids, dead_ids, result):
                        result["skipped_count"] += len(items) - index - 1
                        stopped_at_limit = True
                        break
                except CookieExpiredError:
                    auth_fail_count += 1
                    result["failed_count"] += 1
                except Exception as err:
                    logger.error(f"处理单个红包异常，已隔离并继续后续红包：{err}")
                    result["failed_count"] += 1
                    self.__append_event({
                        "event": "claim_fail",
                        "packet_id": item.get("id") if isinstance(item, dict) else None,
                        "reason": f"处理异常：{err}"
                    })
            if not stopped_at_limit:
                result["skipped_count"] += len(items) - len(batch_items)

            # 网站达上限消息可给出权威累计；否则按本插件当日 claim_ok 记录统计
            reached_limit = self.__apply_daily_quota(result)
            attempted_count = self.__safe_int(result.get("attempted_count"), 0)
            if attempted_count and auth_fail_count == attempted_count:
                result.update({"status": "auth_failed", "message": "detail/claim 全部返回 401/403，Cookie 可能已过期"})
                self.__append_event({"event": "auth_failed", "message": result["message"]})
            else:
                if reached_limit:
                    result.update({"status": "completed", "message": f"今日领取已达上限（每天最多领 {result.get('daily_limit')} 个）"})
                else:
                    result.update({"status": "completed", "message": "领红包任务完成"})
            self.save_data("claimed_ids", sorted(claimed_ids))
            self.save_data("dead_ids", sorted(dead_ids))
            self.__append_event({
                "event": "round_summary",
                "summary_text": self.__format_round_summary(result),
                "status": result.get("status"),
                "total_seen": result.get("total_seen", 0),
                "claimed_count": result.get("claimed_count", 0),
                "failed_count": result.get("failed_count", 0),
                "skipped_count": result.get("skipped_count", 0),
                "bonus_delta": result.get("bonus_delta", 0),
                "user_bonus_after": result.get("user_bonus_after"),
                "quota_date": result.get("quota_date"),
                "daily_claimed": result.get("daily_claimed"),
                "daily_claimed_before": result.get("daily_claimed_before"),
                "daily_limit": result.get("daily_limit"),
                "daily_claimed_source": result.get("daily_claimed_source", ""),
                "reached_limit": bool(result.get("reached_limit")),
                "remaining_claimable_count": result.get("remaining_claimable_count"),
                "message": result.get("message") or "-"
            })
            self.__update_summary(last_round=self.__build_last_round(result))
            # 达上限去重：同一天只对「纯达上限轮」去重；有成功领取仍通知
            quota_date = str(result.get("quota_date") or self.__local_date())
            notified_date = self.get_data("limit_notified_date")
            pure_limit_round = reached_limit and not result.get("claimed_count")
            skip_for_limit = pure_limit_round and notified_date == quota_date
            if self._notify and skip_for_limit:
                logger.info(f"今日已发送过达上限通知，跳过本次重复通知：{quota_date}")
            elif self._notify and (result.get("claimed_count") or result.get("failed_count") or result.get("status") == "auth_failed"):
                self.__send_notification(result)
                if pure_limit_round:
                    self.save_data("limit_notified_date", quota_date)
            elif not self._notify:
                logger.info("领红包任务通知未发送：发送通知开关未开启")
            logger.info(f"领红包任务结束：{self.__to_log_text(result)}")
            return result
        finally:
            self._lock.release()

    def __process_packet(self, session: requests.Session, rate_limit: RateLimitState, item: Dict[str, Any],
                         claimed_ids: set, dead_ids: set, result: Dict[str, Any]) -> bool:
        packet_id = item.get("id")
        if packet_id is None:
            result["skipped_count"] += 1
            self.__append_event({"event": "claim_skip", "reason": "missing_id"})
            return False
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
            return False
        if packet_key in dead_ids:
            result["skipped_count"] += 1
            logger.info(f"CLAIM_SKIP packet_id={packet_key} sender={sender} reason=dead")
            self.__append_event({
                "event": "claim_skip", "packet_id": packet_id, "sender": sender,
                "title_name": title, "reason": "dead"
            })
            return False

        if self._fast_mode:
            logger.info(f"红包 #{packet_key} 来自 {sender} 剩余{remain_count if remain_count is not None else '?'}个/共{total_count or '?'}个")
            if remain_count is not None and remain_count <= 0:
                result["skipped_count"] += 1
                dead_ids.add(packet_key)
                self.__append_event({
                    "event": "claim_skip", "packet_id": packet_id, "sender": sender,
                    "title_name": title, "title_class": title_class, "reason": "snatched_empty"
                })
                return False
        else:
            result["attempted_count"] += 1
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
                return False
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
                    return False

        if self._dry_run:
            result["skipped_count"] += 1
            self.__append_event({
                "event": "claim_skip", "packet_id": packet_id, "sender": sender,
                "title_name": title, "title_class": title_class, "reason": "dry_run"
            })
            return False

        if self._fast_mode:
            result["attempted_count"] += 1
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
                snapshot_date = self.__local_date()
                result["quota_date"] = snapshot_date
                result["site_quota_date"] = snapshot_date
                result["site_daily_claimed"] = parsed_quota[0]
                result["site_quota_claimed_count"] = self.__safe_int(
                    (result.get("claimed_count_by_date") or {}).get(snapshot_date), 0
                )
                result["daily_limit"] = parsed_quota[1]
                if parsed_quota[0] >= parsed_quota[1]:
                    result["reached_limit"] = True
                    return True
            if self.__is_terminal_message(fail_message):
                dead_ids.add(packet_key)
            return False

        amount = claim.get("magic_amount")
        after = claim.get("user_bonus_after")
        record = {
            "event": "claim_ok",
            "time": self.__local_time_iso(),
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
        claim_date = self.__local_date_from_iso(record["time"])
        daily_state = self.__record_daily_claim(packet_key, claim_date)
        claimed_ids.add(packet_key)
        self.save_data("claimed_ids", sorted(claimed_ids))
        try:
            self.__append_event(record)
        except Exception as err:
            logger.error(f"领取成功但事件保存失败：packet_id={packet_key}，error={err}")
        result["claimed_count"] += 1
        claimed_count_by_date = result.setdefault("claimed_count_by_date", {})
        claimed_count_by_date[claim_date] = self.__safe_int(claimed_count_by_date.get(claim_date), 0) + 1
        result["quota_date"] = claim_date
        result["daily_claimed"] = daily_state["claimed_count"]
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
    def __local_date() -> str:
        return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")

    @staticmethod
    def __local_date_from_iso(value: Any) -> str:
        text = str(value or "")
        return text[:10] if re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", text) else TangRedPacket.__local_date()

    @staticmethod
    def __new_result() -> Dict[str, Any]:
        return {
            "task_id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
            "time": TangRedPacket.__local_time_iso(),
            "status": "running",
            "message": "",
            "total_seen": 0,
            "claimed_count": 0,
            "claimed_count_by_date": {},
            "attempted_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "bonus_delta": 0.0,
            "user_bonus_after": "-",
            "latest_total_packet_count": None,
            "latest_items_count": 0,
            "remaining_claimable_count": None,
            "remaining_claimable_source": "",
            "quota_date": TangRedPacket.__local_date(),
            "daily_limit": None,
            "daily_claimed": 0,
            "daily_claimed_before": None,
            "daily_claimed_source": "",
            "reached_limit": False
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
            "quota_date": result.get("quota_date"),
            "daily_limit": result.get("daily_limit"),
            "daily_claimed": result.get("daily_claimed"),
            "daily_claimed_before": result.get("daily_claimed_before"),
            "daily_claimed_source": result.get("daily_claimed_source", ""),
            "reached_limit": bool(result.get("reached_limit"))
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

    def __get_daily_quota_state(self, quota_date: Optional[str] = None) -> Dict[str, Any]:
        """读取指定本地日期的独立配额下界；首次升级时从现存事件保守初始化。"""
        quota_date = quota_date or self.__local_date()
        state = self.get_data("daily_quota_state") or {}
        if isinstance(state, dict) and state.get("date") == quota_date:
            return {
                "date": quota_date,
                "claimed_count": max(0, self.__safe_int(state.get("claimed_count"), 0)),
                "packet_ids": [str(item) for item in state.get("packet_ids", []) if item is not None]
                if isinstance(state.get("packet_ids"), list) else []
            }
        packet_ids = []
        anonymous_count = 0
        for event in self.__get_events():
            if event.get("event") != "claim_ok" or self.__local_date_from_iso(event.get("time")) != quota_date:
                continue
            packet_id = event.get("packet_id")
            if packet_id is None:
                anonymous_count += 1
            elif str(packet_id) not in packet_ids:
                packet_ids.append(str(packet_id))
        migrated = {"date": quota_date, "claimed_count": len(packet_ids) + anonymous_count, "packet_ids": packet_ids}
        self.save_data("daily_quota_state", migrated)
        return migrated

    def __record_daily_claim(self, packet_id: Any, quota_date: str) -> Dict[str, Any]:
        """在写事件前持久化成功领取，按日期和 packet_id 保证重复调用不重复计数。"""
        state = self.__get_daily_quota_state(quota_date)
        packet_key = str(packet_id)
        packet_ids = list(state.get("packet_ids") or [])
        if packet_key not in packet_ids:
            packet_ids.append(packet_key)
            state = {
                "date": quota_date,
                "claimed_count": state["claimed_count"] + 1,
                "packet_ids": packet_ids[-self.DAILY_LIMIT:]
            }
            self.save_data("daily_quota_state", state)
        return state

    def __apply_daily_quota(self, result: Dict[str, Any]) -> bool:
        """以任务结束日（或最后成功日）为口径，对账同日站点快照且绝不降低本地下界。"""
        quota_date = str(result.get("quota_date") or self.__local_date())
        if not result.get("claimed_count"):
            quota_date = self.__local_date()
        local_daily_claimed = self.__get_daily_quota_state(quota_date)["claimed_count"]
        site_daily_claimed = self.__to_int(result.get("site_daily_claimed"))
        site_daily_limit = self.__to_int(result.get("daily_limit"))
        site_quota_known = (
            site_daily_claimed is not None
            and site_daily_limit is not None
            and result.get("site_quota_date") == quota_date
        )
        daily_limit = site_daily_limit if site_quota_known and site_daily_limit > 0 else self.DAILY_LIMIT
        if site_quota_known:
            claimed_on_date = self.__safe_int((result.get("claimed_count_by_date") or {}).get(quota_date), 0)
            claimed_after_snapshot = max(
                0, claimed_on_date - self.__safe_int(result.get("site_quota_claimed_count"), 0)
            )
            site_candidate = site_daily_claimed + claimed_after_snapshot
            daily_claimed = min(daily_limit, max(local_daily_claimed, site_candidate))
            if claimed_after_snapshot == 0 and daily_claimed == site_daily_claimed >= local_daily_claimed:
                source = "site"
            else:
                source = "reconciled"
            if daily_claimed > local_daily_claimed:
                state = self.__get_daily_quota_state(quota_date)
                state["claimed_count"] = daily_claimed
                self.save_data("daily_quota_state", state)
        else:
            daily_claimed = min(daily_limit, local_daily_claimed)
            source = "plugin"
        result["quota_date"] = quota_date
        result["daily_claimed"] = daily_claimed
        result["daily_limit"] = daily_limit
        result["daily_claimed_source"] = source
        result["remaining_claimable_count"] = max(0, daily_limit - daily_claimed)
        reached_limit = bool(result.get("reached_limit")) or daily_claimed >= daily_limit
        result["reached_limit"] = reached_limit
        return reached_limit

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

    def __quota_status_text(self, result: Dict[str, Any]) -> str:
        daily_limit = result.get("daily_limit")
        daily_claimed = result.get("daily_claimed")
        if daily_limit is None or daily_claimed is None:
            return "-"
        source = result.get("daily_claimed_source")
        suffix = "" if source == "site" else "（校准）" if source == "reconciled" else "（估）"
        return f"{min(self.__safe_int(daily_claimed), self.__safe_int(daily_limit))}/{daily_limit}{suffix}"

    def __round_history_row(self, result: Dict[str, Any]) -> Dict[str, Any]:
        quota_status = self.__quota_status_text(result)
        if quota_status == "-":
            summary_text = result.get("summary_text")
            if isinstance(summary_text, str):
                matched = re.search(r"(?:^|[；;\n])今日：\s*(\d+)\s*/\s*(\d+)(（(?:估|校准)）)?", summary_text)
                if matched:
                    quota_status = f"{matched.group(1)}/{matched.group(2)}{matched.group(3) or ''}"
        return {
            "time": str(result.get("time") or result.get("updated_at") or "")[:19] or "-",
            "total_seen": result.get("total_seen", 0),
            "claimed_count": result.get("claimed_count", 0),
            "failed_count": result.get("failed_count", 0),
            "skipped_count": result.get("skipped_count", 0),
            "quota_status": quota_status,
            "bonus_delta": self.__format_number(result.get("bonus_delta", 0)),
            "user_bonus_after": result.get("user_bonus_after") if result.get("user_bonus_after") not in (None, "") else "-",
            "message": result.get("message") or "-"
        }

    def __format_round_summary(self, result: Dict[str, Any]) -> str:
        row = self.__round_history_row(result)
        return (
            f"本轮：发现 {row['total_seen']} 个，成功 {row['claimed_count']} 个，"
            f"失败 {row['failed_count']} 个，跳过 {row['skipped_count']} 个；"
            f"今日：{row['quota_status']}；"
            f"收益：+{row['bonus_delta']} 魔力，当前 {row['user_bonus_after']}；"
            f"说明：{row['message']}"
        )

    def __safe_int(self, value: Any, default: int = 0) -> int:
        if value is None or isinstance(value, bool):
            return default
        try:
            number = float(value)
            if not math.isfinite(number):
                return default
            return int(number)
        except (TypeError, ValueError, OverflowError):
            return default

    def __format_round_notification(self, result: Dict[str, Any]) -> str:
        status = result.get("status")
        failed = self.__safe_int(result.get("failed_count"), 0)
        total_seen = self.__safe_int(result.get("total_seen"), 0)
        if status == "auth_failed":
            icon = "❌"
            summary_title = "不可躺红包领取失败"
        elif total_seen == 0:
            icon = "ℹ️"
            summary_title = "不可躺暂无可领红包"
        elif failed:
            icon = "⚠️"
            summary_title = "不可躺红包领取完成（有失败）"
        else:
            icon = "✅"
            summary_title = "不可躺红包领取完成"
        remaining = result.get("remaining_claimable_count")
        remaining_text = f"（剩余 {remaining}）" if remaining is not None else ""
        row = self.__round_history_row(result)
        return (
            f"{icon} {summary_title}\n\n"
            f"本轮：发现 {row['total_seen']} 个，成功 {row['claimed_count']} 个，"
            f"失败 {row['failed_count']} 个，跳过 {row['skipped_count']} 个\n"
            f"今日：{row['quota_status']}{remaining_text}\n"
            f"收益：+{row['bonus_delta']} 魔力（当前 {row['user_bonus_after']}）\n\n"
            f"说明：{row['message']}"
        )

    def __send_notification(self, result: Dict[str, Any]):
        title = "【不可躺自动领红包】"
        text = self.__format_round_notification(result)
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
