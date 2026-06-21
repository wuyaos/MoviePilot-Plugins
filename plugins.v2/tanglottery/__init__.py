# input: MoviePilot 站点 Cookie、插件配置、定时调度器
# output: 不可躺抽奖任务执行、历史记录和通知
# pos: V2 站点任务插件，按 Cron 自动拆分并调用不可躺抽奖接口
import json
import random
import re
import threading
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from html import unescape
from typing import Any, Dict, List, Optional, Tuple

import requests
from apscheduler.triggers.cron import CronTrigger

from app.core.event import Event, eventmanager
from app.db.site_oper import SiteOper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import NotificationType
from app.schemas.types import EventType


class TangLottery(_PluginBase):
    plugin_name = "不可躺自动抽奖助手"
    plugin_desc = "按每日目标次数自动拆解并执行不可躺抽奖。"
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/tanglottery.png"
    plugin_version = "3.0.2"
    plugin_author = "jiangbkvir,bfjy,wuyaos"
    author_url = "https://github.com/jiangbkvir/MoviePilot-Plugins"
    plugin_config_prefix = "tanglottery_"
    plugin_order = 30
    auth_level = 1

    SPIN_URL = "https://www.tangpt.top/web/omnibot/lottery/draw"
    REFERER = "https://www.tangpt.top/omnibot_lottery.php"
    SITE_DOMAIN = "www.tangpt.top"
    MAX_HISTORY = 30
    MAX_BATCH_COUNT = 100
    DAILY_LIMIT_COUNT = 1000
    REQUEST_RETRY_DELAYS = [30, 60, 120, 180, 300]

    _enabled = False
    _target_count = 100
    _cron = "10 2 * * *"
    _notify = True
    _run_once = False
    _lock = threading.Lock()

    def init_plugin(self, config: dict = None):
        config = config or {}
        if "enabled" in config:
            self._enabled = bool(config.get("enabled"))
        self._target_count = self.__safe_int(config.get("target_count"), 100, min_value=1,
                                           max_value=self.DAILY_LIMIT_COUNT)
        self._cron = self.__normalize_cron(config.get("cron"))
        self._notify = bool(config.get("notify", True))
        self._run_once = bool(config.get("run_once", False))
        logger.info(
            f"不可躺自动抽奖助手初始化完成：enabled={self._enabled}, "
            f"target_count={self._target_count}, cron={repr(self._cron)}, "
            f"raw_cron_type={type(config.get('cron')).__name__}, notify={self._notify}"
        )
        if self._run_once:
            self._run_once = False
            self.update_config({
                "enabled": self._enabled,
                "target_count": self._target_count,
                "cron": self._cron,
                "notify": self._notify,
                "run_once": False
            })
            logger.info("收到配置页立即运行请求，后台启动抽奖任务")
            threading.Thread(target=self.run_lottery_task, daemon=True).start()

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return [
            {
                "cmd": "/tang_lottery_run",
                "event": EventType.PluginAction,
                "desc": "立即执行不可躺抽奖",
                "category": "站点",
                "data": {
                    "action": "tang_lottery_run"
                }
            }
        ]

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/TangLottery/run",
                "endpoint": self.run_once_api,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "立即执行不可躺抽奖",
                "description": "按当前插件配置立即执行一次不可躺抽奖任务。"
            }
        ]

    def get_service(self) -> List[Dict[str, Any]]:
        if not self._enabled:
            logger.info("不可躺自动抽奖助手定时服务未注册：插件未启用")
            return []
        if not self._cron:
            logger.warning("不可躺自动抽奖助手定时服务未注册：Cron 为空")
            return []
        try:
            trigger = CronTrigger.from_crontab(self._cron)
        except Exception as err:
            logger.warning(f"不可躺自动抽奖助手 Cron 配置无效：cron={repr(self._cron)}，error={err}")
            return []
        return [
            {
                "id": "TangLottery",
                "name": "不可躺自动抽奖",
                "trigger": "cron",
                "func": self.run_lottery_task,
                "kwargs": {
                    "minute": str(trigger.fields[6]),
                    "hour": str(trigger.fields[5]),
                    "day": str(trigger.fields[2]),
                    "month": str(trigger.fields[1]),
                    "day_of_week": str(trigger.fields[4])
                }
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
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {"model": "enabled", "label": "启用插件"}
                                    }
                                ]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {"model": "notify", "label": "发送通知"}
                                    }
                                ]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
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
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "target_count",
                                            "label": "每日目标总次数",
                                            "type": "number",
                                            "min": 1,
                                            "hint": "每天计划抽奖次数，单次接口最多 100 次，大于 100 会自动拆分"
                                        }
                                    }
                                ]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VCronField",
                                        "props": {
                                            "model": "cron",
                                            "label": "执行周期",
                                            "placeholder": "10 2 * * *",
                                            "hint": "5位 Cron 表达式，例如 10 2 * * *"
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
            "target_count": self._target_count,
            "cron": self._cron,
            "notify": self._notify,
            "run_once": False
        }

    def get_page(self) -> List[dict]:
        records = self.__get_records()
        for record in records:
            record["status_text"] = record.get("status_text") or self.__status_text(record.get("status"))
        logger.info("详情页加载 不可躺抽奖信息，开始请求 不可躺抽奖页面")
        lottery_info = self.__fetch_lottery_info()
        self.__fill_lottery_info_from_records(lottery_info, records)
        today_summary, yesterday_summary = self.__build_recent_prize_summary(records)
        return [
            {
                "component": "VCard",
                "props": {"variant": "tonal", "class": "mb-4"},
                "content": [
                    {
                        "component": "VCardTitle",
                        "text": "我的抽奖信息"
                    },
                    {
                        "component": "VCardText",
                        "content": [
                            {
                                "component": "VRow",
                                "content": [
                                    self.__info_col("当前魔力", lottery_info.get("current_magic")),
                                    self.__info_col("单次消耗", lottery_info.get("cost_per_draw")),
                                    self.__info_col("今日剩余", lottery_info.get("remaining_count")),
                                    self.__info_col("今日已抽", lottery_info.get("today_drawn")),
                                ]
                            },
                            {
                                "component": "div",
                                "props": {"class": "text-caption text-medium-emphasis mt-2"},
                                "text": lottery_info.get("message") or f"最近同步时间：{lottery_info.get('updated_at')}"
                            }
                        ]
                    }
                ]
            },
            {
                "component": "VDataTable",
                "props": {
                    "headers": [
                        {"title": "日期", "key": "date"},
                        {"title": "目标", "key": "target_count"},
                        {"title": "完成", "key": "completed_count"},
                        {"title": "批次数", "key": "batch_requests"},
                        {"title": "总消耗", "key": "total_cost"},
                        {"title": "魔力值", "key": "bonus"},
                        {"title": "折算魔力", "key": "compensated_bonus"},
                        {"title": "剩余魔力", "key": "user_bonus_after"},
                        {"title": "流量", "key": "traffic_text"},
                        {"title": "其他奖励", "key": "other_text"},
                        {"title": "状态", "key": "status_text"},
                        {"title": "消息", "key": "message"}
                    ],
                    "items": records,
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
                "component": "div",
                "props": {"class": "text-h6 mb-3"},
                "text": "奖品名称汇总"
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
                                        "text": "今日汇总"
                                    },
                                    {
                                        "component": "VCardText",
                                        "content": [
                                            self.__summary_chart("今日奖品分布", today_summary),
                                            {
                                                "component": "VRow",
                                                "props": {"dense": True},
                                                "content": self.__summary_grid(today_summary)
                                            }
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
                                        "text": "昨日汇总"
                                    },
                                    {
                                        "component": "VCardText",
                                        "content": [
                                            self.__summary_chart("昨日奖品分布", yesterday_summary),
                                            {
                                                "component": "VRow",
                                                "props": {"dense": True},
                                                "content": self.__summary_grid(yesterday_summary)
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]

    def stop_service(self):
        pass

    def run_once_api(self) -> Dict[str, Any]:
        if not self._enabled:
            logger.warning("立即执行请求被忽略：插件未启用")
            return {"success": False, "message": "插件未启用"}
        if self._lock.locked():
            logger.warning("立即执行请求被忽略：已有抽奖任务正在执行")
            return {"success": False, "message": "已有抽奖任务正在执行"}
        logger.info("收到 API 立即执行请求，后台启动抽奖任务")
        threading.Thread(target=self.run_lottery_task, daemon=True).start()
        return {"success": True, "message": "任务已开始，完成后会写入历史记录并按配置发送通知"}

    @eventmanager.register(EventType.PluginAction)
    def run_once_command(self, event: Event = None):
        event_data = event.event_data if event else {}
        if not event_data or event_data.get("action") != "tang_lottery_run":
            return
        channel = event_data.get("channel")
        userid = event_data.get("user")
        if not self._enabled:
            logger.warning("TG 命令立即执行请求被忽略：插件未启用")
            self.post_message(
                channel=channel,
                userid=userid,
                mtype=NotificationType.Plugin,
                title="【不可躺自动抽奖助手】",
                text="插件未启用，无法执行抽奖任务。"
            )
            return
        if self._lock.locked():
            logger.warning("TG 命令立即执行请求被忽略：已有抽奖任务正在执行")
            self.post_message(
                channel=channel,
                userid=userid,
                mtype=NotificationType.Plugin,
                title="【不可躺自动抽奖助手】",
                text="已有抽奖任务正在执行，请等待当前任务结束。"
            )
            return
        logger.info("收到 TG 命令立即执行请求，后台启动抽奖任务")
        threading.Thread(target=self.run_lottery_task, daemon=True).start()
        self.post_message(
            channel=channel,
            userid=userid,
            mtype=NotificationType.Plugin,
            title="【不可躺自动抽奖助手】",
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
                    "text": str(value or "-")
                }
            ]
        }

    def run_lottery_task(self) -> Dict[str, Any]:
        if not self._lock.acquire(blocking=False):
            logger.warning("抽奖任务启动失败：已有任务正在执行")
            return {"status": "running", "message": "已有抽奖任务正在执行"}
        try:
            cookie = (self.__get_site_cookie() or "").strip()
            if not cookie or "c_secure_pass=" not in cookie:
                logger.warning("抽奖任务终止：缺少包含 c_secure_pass 的 不可躺 Cookie")
                result = self.__new_result(status="auth_failed", message="缺少包含 c_secure_pass 的 不可躺 Cookie")
                self.__finish_task(result)
                return result

            target_count = self.__safe_int(self._target_count, 100, min_value=1, max_value=self.DAILY_LIMIT_COUNT)
            planned_counts = self.__build_plan(target_count)
            logger.info(
                f"抽奖任务开始：目标={target_count}，批次数={len(planned_counts)}，"
                f"拆分计划={planned_counts}"
            )
            result = self.__new_result(target_count=target_count, planned_batches=len(planned_counts))
            consecutive_auth_errors = 0
            consecutive_request_errors = 0
            plan_index = 0

            while plan_index < len(planned_counts):
                count = planned_counts[plan_index]
                response_data, error_kind, message = self.__post_spin(count=count, cookie=cookie)
                if error_kind == "quota_exhausted":
                    remaining_count = self.__extract_remaining_count(message)
                    remaining_int = self.__safe_int(remaining_count, 0, min_value=0)
                    if remaining_int > 0 and remaining_int < count:
                        logger.warning(
                            f"抽奖额度不足但仍有剩余次数，调整当前请求：原 count={count}，"
                            f"剩余可抽={remaining_int}，接口消息={message}"
                        )
                        planned_counts[plan_index] = remaining_int
                        result["message"] = f"接口提示剩余 {remaining_int} 次，已自动改为抽剩余次数"
                        continue
                    logger.warning(f"抽奖额度不足，任务停止：{message}")
                    result["status"] = "quota_exhausted"
                    result["message"] = message
                    break
                if error_kind == "auth_failed":
                    consecutive_auth_errors += 1
                    consecutive_request_errors = 0
                    result["message"] = message
                    logger.warning(f"抽奖请求出现 Cookie/权限类错误：{message}")
                    if consecutive_auth_errors >= 3:
                        result["status"] = "auth_failed"
                        result["message"] = "连续 3 次 Cookie/权限类失败，任务已熔断"
                        logger.warning("抽奖任务因连续 3 次 Cookie/权限类失败熔断")
                        break
                    self.__sleep_between_requests(30, 60)
                    continue
                if error_kind:
                    consecutive_request_errors += 1
                    consecutive_auth_errors = 0
                    result["message"] = message
                    retry_delay = self.__request_retry_delay(consecutive_request_errors)
                    logger.warning(
                        f"抽奖请求失败：{message}。将重试当前 count={count} 请求，"
                        f"连续失败次数={consecutive_request_errors}，等待={retry_delay} 秒"
                    )
                    if consecutive_request_errors >= len(self.REQUEST_RETRY_DELAYS):
                        result["status"] = "failed"
                        result["message"] = f"连续 {len(self.REQUEST_RETRY_DELAYS)} 次请求失败，任务已熔断"
                        logger.warning(f"抽奖任务因连续 {len(self.REQUEST_RETRY_DELAYS)} 次请求失败熔断")
                        break
                    time.sleep(retry_delay)
                    continue

                consecutive_auth_errors = 0
                consecutive_request_errors = 0
                self.__merge_response(result, response_data, count)
                plan_index += 1
                result["message"] = f"抽奖进行中：已完成 {result.get('completed_count')} / {result.get('target_count')} 次"
                self.__save_progress(result)
                self.__sleep_between_requests()

            if result["status"] == "running":
                result["status"] = "completed"
                result["message"] = "抽奖任务完成"
            self.__finish_task(result)
            logger.info(
                f"抽奖任务结束：状态={result.get('status_text')}，目标={result.get('target_count')}，"
                f"完成={result.get('completed_count')}，批次数={result.get('batch_requests')}，"
                f"总消耗={result.get('total_cost')}，剩余魔力={result.get('user_bonus_after')}"
            )
            return result
        finally:
            self._lock.release()

    def __post_spin(self, count: int, cookie: str) -> Tuple[Optional[dict], Optional[str], str]:
        headers = {
            "accept": "application/json, text/javascript, */*; q=0.01",
            "accept-language": "zh-CN,zh;q=0.9",
            "cache-control": "no-cache",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": "https://www.tangpt.top",
            "pragma": "no-cache",
            "referer": self.REFERER,
            "sec-ch-ua": "\"Google Chrome\";v=\"147\", \"Not.A/Brand\";v=\"8\", \"Chromium\";v=\"147\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"macOS\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
            "x-requested-with": "XMLHttpRequest"
        }
        logger.info(f"准备请求 不可躺抽奖接口：count={count}，url={self.SPIN_URL}")
        try:
            response = requests.post(
                self.SPIN_URL,
                headers=headers,
                cookies=self.__cookie_to_dict(cookie),
                data={"count": str(count)},
                timeout=30
            )
        except requests.RequestException as err:
            logger.error(f"不可躺抽奖接口请求异常：count={count}，错误={err}")
            return None, "request_failed", f"请求失败：{err}"

        text = response.text or ""
        logger.info(
            f"不可躺抽奖接口 HTTP 响应：count={count}，"
            f"status_code={response.status_code}，content_type={response.headers.get('content-type')}"
        )
        if response.status_code in {401, 403}:
            logger.warning(f"不可躺抽奖接口权限错误：count={count}，HTTP {response.status_code}，响应={self.__to_log_text(text)}")
            return None, "auth_failed", f"接口返回权限错误：HTTP {response.status_code}"
        try:
            data = response.json()
        except ValueError:
            logger.warning(
                f"不可躺抽奖接口返回非 JSON：count={count}，"
                f"HTTP={response.status_code}，headers={self.__to_log_text(dict(response.headers))}，"
                f"响应长度={len(text)}，响应预览={self.__response_preview(text)}"
            )
            if self.__is_auth_message(text):
                return None, "auth_failed", "接口返回 Cookie/权限类错误"
            return None, "request_failed", "接口返回非 JSON 响应"

        logger.info(f"不可躺抽奖接口 JSON 响应：count={count}，data={self.__to_log_text(data)}")
        if data.get("ok") is False:
            message = str(data.get("message") or "接口返回失败")
            logger.warning(f"不可躺抽奖接口返回失败：count={count}，message={message}")
            if any(word in message for word in ["剩余 0 次", "剩余0次", "最多可抽奖", "次数不足", "今日还可以抽 0 次"]):
                return data, "quota_exhausted", message
            if self.__is_auth_message(message):
                return data, "auth_failed", message
            return data, "request_failed", message
        if data.get("ok") is not True:
            message = str(data.get("message") or "接口返回未知状态")
            logger.warning(f"不可躺抽奖接口返回未知状态：count={count}，message={message}，data={self.__to_log_text(data)}")
            return data, "request_failed", message

        result_count = len(data.get("results") or [])
        logger.info(
            f"不可躺抽奖接口请求成功：count={count}，返回结果数量={result_count}，"
            f"draw_count={data.get('draw_count')}，total_cost={data.get('total_cost')}，"
            f"total_awarded_bonus={data.get('total_awarded_bonus')}，"
            f"total_compensated_bonus={data.get('total_compensated_bonus')}，"
            f"user_bonus_after={data.get('user_bonus_after')}"
        )
        return data, None, ""

    def __fetch_lottery_info(self) -> Dict[str, Any]:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        info = {
            "current_magic": "-",
            "cost_per_draw": "-",
            "remaining_count": "-",
            "today_drawn": "-",
            "updated_at": now,
            "message": ""
        }
        cookie = (self.__get_site_cookie() or "").strip()
        if not cookie or "c_secure_pass=" not in cookie:
            info["message"] = "缺少 不可躺 Cookie，无法读取抽奖信息"
            logger.warning("读取 不可躺抽奖页面失败：缺少包含 c_secure_pass 的 Cookie")
            return info

        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "zh-CN,zh;q=0.9",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "priority": "u=0, i",
            "referer": "https://www.tangpt.top/",
            "sec-ch-ua": "\"Google Chrome\";v=\"147\", \"Not.A/Brand\";v=\"8\", \"Chromium\";v=\"147\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"macOS\"",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
        }
        logger.info(f"准备请求 不可躺抽奖页面：url={self.REFERER}")
        try:
            response = requests.get(
                self.REFERER,
                headers=headers,
                cookies=self.__cookie_to_dict(cookie),
                timeout=30
            )
        except requests.RequestException as err:
            info["message"] = f"读取抽奖页面失败：{err}"
            logger.error(f"读取 不可躺抽奖页面请求异常：错误={err}")
            return info

        logger.info(
            f"不可躺抽奖页面 HTTP 响应：status_code={response.status_code}，"
            f"content_type={response.headers.get('content-type')}"
        )
        if response.status_code in {401, 403}:
            info["message"] = f"读取抽奖页面权限错误：HTTP {response.status_code}"
            logger.warning(f"读取 不可躺抽奖页面权限错误：HTTP {response.status_code}")
            return info
        if response.status_code != 200:
            info["message"] = f"读取抽奖页面失败：HTTP {response.status_code}"
            logger.warning(f"读取 不可躺抽奖页面失败：HTTP {response.status_code}，响应预览={self.__to_log_text(response.text or '')}")
            return info

        plain_text = self.__html_to_text(response.text or "")
        if any(word in plain_text for word in ["Cookie失效", "非法访问", "请先登录", "未登录"]):
            info["message"] = "抽奖页面返回登录/权限提示，请检查 Cookie"
            logger.warning(f"读取 不可躺抽奖页面返回登录/权限提示，页面文本预览={self.__to_log_text(plain_text)}")
            return info

        info["current_magic"] = self.__extract_magic_balance(plain_text)
        info["cost_per_draw"] = self.__extract_number_near_label(plain_text, "单次消耗")
        info["remaining_count"] = self.__extract_remaining_count(plain_text)
        info["today_drawn"] = self.__calculate_today_drawn(info.get("remaining_count"))
        logger.info(f"不可躺抽奖页面解析结果：{self.__to_log_text(info)}")
        return info

    def __fill_lottery_info_from_records(self, info: Dict[str, Any], records: List[Dict[str, Any]]):
        if not records:
            return
        if info.get("current_magic") in ["", "-"]:
            for record in records:
                user_bonus_after = record.get("user_bonus_after")
                if user_bonus_after not in [None, "", "-"]:
                    info["current_magic"] = self.__format_number(user_bonus_after)
                    logger.info(f"详情页当前魔力使用最近历史回填：{info['current_magic']}")
                    break

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

    @classmethod
    def __build_plan(cls, target_count: int) -> List[int]:
        target_count = max(int(target_count or 0), 1)
        full_batches = target_count // cls.MAX_BATCH_COUNT
        remainder = target_count % cls.MAX_BATCH_COUNT
        plan = [cls.MAX_BATCH_COUNT] * full_batches
        if remainder:
            plan.append(remainder)
        return plan or [1]

    def __merge_response(self, task: Dict[str, Any], data: dict, request_count: int):
        task["batch_requests"] += 1
        results = data.get("results") or []
        draw_count = self.__safe_int(data.get("draw_count"), len(results), min_value=0)
        task["completed_count"] += draw_count
        task["total_cost"] += self.__safe_float(data.get("total_cost"), 0)
        task["bonus"] += self.__safe_float(data.get("total_awarded_bonus"), 0)
        task["compensated_bonus"] += self.__safe_float(data.get("total_compensated_bonus"), 0)
        if data.get("user_bonus_after") is not None:
            task["user_bonus_after"] = self.__normalize_number(data.get("user_bonus_after"))
        if data.get("summary_text"):
            task["summary_texts"].append(str(data.get("summary_text")))
        if data.get("detail_text"):
            task["detail_texts"].append(str(data.get("detail_text")))
        logger.info(
            f"开始合并抽奖接口结果：本次请求 count={request_count}，接口 draw_count={draw_count}，"
            f"返回结果数量={len(results)}，累计完成={task['completed_count']}，"
            f"本次消耗={data.get('total_cost')}，本次奖励魔力={data.get('total_awarded_bonus')}，"
            f"本次折算魔力={data.get('total_compensated_bonus')}，剩余魔力={data.get('user_bonus_after')}"
        )

        for index, item in enumerate(results, 1):
            prize_name = str(item.get("prize_name") or "未知奖品").strip() or "未知奖品"
            content = str(item.get("content") or "").strip()
            display_name = prize_name
            if content and content not in prize_name:
                display_name = f"{prize_name}：{content}"
            task["prize_summary"][prize_name] += 1
            logger.info(
                f"抽奖结果明细：本次第 {index} 条，奖品={prize_name}，"
                f"原始结果={self.__to_log_text(item)}"
            )
            if prize_name != "谢谢惠顾":
                task["winning_summary"][prize_name] += 1

            summary_entries = item.get("summary_entries") or []
            if any((entry.get("key") == "uploaded") for entry in summary_entries if isinstance(entry, dict)):
                traffic_gb = 0
                for entry in summary_entries:
                    if not isinstance(entry, dict) or entry.get("key") != "uploaded":
                        continue
                    traffic_gb += self.__traffic_to_gb(
                        self.__safe_float(entry.get("amount"), 0),
                        str(entry.get("unit") or ""),
                        content or prize_name
                    )
                task["traffic"] += traffic_gb
                logger.info(f"累计上传量奖励：本次={traffic_gb} GB，累计={task['traffic']} GB")
                continue

            marker = f"{prize_name} {content}".lower()
            if any(word in marker for word in ["上传", "流量", "upload", "traffic", "gb", "mb", "tb"]):
                value, unit = self.__extract_traffic_value(content or prize_name)
                if not value:
                    value = self.__safe_float(item.get("amount"), 0)
                traffic_gb = self.__traffic_to_gb(value, unit, content or prize_name)
                task["traffic"] += traffic_gb
                logger.info(f"累计流量奖励：本次={traffic_gb} GB，累计={task['traffic']} GB")
                continue

            if prize_name not in {"魔力", "谢谢惠顾"}:
                task["other_rewards"][display_name] += 1
                logger.info(f"累计其他奖励：{display_name}，累计次数={task['other_rewards'][display_name]}")

    def __finish_task(self, result: Dict[str, Any]):
        self.__prepare_record(result)
        logger.info(f"抽奖任务最终结果：{self.__to_log_text(result)}")
        self.__save_record(result)
        if self._notify:
            self.__send_notification(result)
        else:
            logger.info("抽奖任务通知未发送：发送通知开关未开启")

    def __save_progress(self, result: Dict[str, Any]):
        self.__prepare_record(result)
        logger.info(f"抽奖任务进度保存：{self.__to_log_text(result)}")
        self.__save_record(result)

    def __prepare_record(self, result: Dict[str, Any]):
        result["date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        result["status_text"] = self.__status_text(result.get("status"))
        result["bonus"] = self.__normalize_number(result.get("bonus", 0))
        result["compensated_bonus"] = self.__normalize_number(result.get("compensated_bonus", 0))
        result["total_cost"] = self.__normalize_number(result.get("total_cost", 0))
        result["traffic"] = self.__normalize_number(result.get("traffic", 0))
        result["traffic_text"] = f"{result['traffic']} GB"
        result["other_text"] = self.__counter_to_text(result.get("other_rewards") or {})
        result["prize_text"] = self.__counter_to_text(result.get("prize_summary") or {})
        result["summary_text"] = "\n".join([text for text in result.get("summary_texts") or [] if text])
        result["detail_text"] = "\n\n".join([text for text in result.get("detail_texts") or [] if text])

    def __send_notification(self, result: Dict[str, Any]):
        title = "【不可躺自动抽奖助手】"
        text = (
            f"任务概况：目标抽奖 {result.get('target_count')} 次，实际完成 {result.get('completed_count')} 次。\n"
            f"拆解详情：共请求 {result.get('batch_requests')} 批，每批最多 {self.MAX_BATCH_COUNT} 次。\n"
            f"魔力统计：总消耗 {result.get('total_cost')}，奖励 {result.get('bonus')}，折算 {result.get('compensated_bonus')}，剩余 {result.get('user_bonus_after')}。\n\n"
            f"奖品名称汇总：\n{result.get('prize_text') or '无'}\n\n"
            f"接口汇总：\n{result.get('summary_text') or '无'}\n\n"
            f"状态：{result.get('status_text') or self.__status_text(result.get('status'))}\n"
            f"说明：{result.get('message')}"
        )
        logger.info(f"准备发送抽奖任务通知：title={title}，text={text}")
        self.post_message(mtype=NotificationType.Plugin, title=title, text=text)

    def __save_record(self, record: Dict[str, Any]):
        stored = self.__get_records()
        serializable = record.copy()
        serializable["prize_summary"] = dict(serializable.get("prize_summary") or {})
        serializable["winning_summary"] = dict(serializable.get("winning_summary") or {})
        serializable["other_rewards"] = dict(serializable.get("other_rewards") or {})
        task_id = serializable.get("task_id")
        replaced = False
        if task_id:
            for index, item in enumerate(stored):
                if item.get("task_id") == task_id:
                    stored[index] = serializable
                    replaced = True
                    break
        if not replaced:
            stored.insert(0, serializable)
        self.save_data("records", stored[:self.MAX_HISTORY])
        logger.info(f"抽奖历史记录已保存：当前保存条数={min(len(stored), self.MAX_HISTORY)}")

    def __get_records(self) -> List[Dict[str, Any]]:
        records = self.get_data("records") or []
        return records if isinstance(records, list) else []

    def __build_recent_prize_summary(self, records: List[Dict[str, Any]]) -> Tuple[List[dict], List[dict]]:
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        buckets = {
            today: Counter(),
            yesterday: Counter()
        }
        for record in records:
            record_date = str(record.get("date") or "")[:10]
            if record_date not in buckets:
                continue
            prize_summary = record.get("prize_summary") or {}
            for name, count in prize_summary.items():
                buckets[record_date][name] += count

        return (
            self.__summary_to_items(buckets[today]),
            self.__summary_to_items(buckets[yesterday])
        )

    @staticmethod
    def __summary_to_items(counter: Counter) -> List[dict]:
        if not counter:
            return [{"name": "无抽奖记录", "count": ""}]
        return [
            {"name": name, "count": count}
            for name, count in sorted(counter.items(), key=lambda item: item[1], reverse=True)
        ]

    @staticmethod
    def __summary_grid(items: List[dict]) -> List[Dict[str, Any]]:
        return [
            {
                "component": "VCol",
                "props": {"cols": 12, "sm": 6, "md": 3},
                "content": [
                    {
                        "component": "VChip",
                        "props": {
                            "variant": "tonal",
                            "color": "primary",
                            "class": "ma-1"
                        },
                        "text": str(item.get("name")) + (f" x {item.get('count')}" if item.get("count") != "" else "")
                    }
                ]
            }
            for item in items
        ]

    @staticmethod
    def __summary_chart(title: str, items: List[dict]) -> Dict[str, Any]:
        chart_items = [
            item for item in items
            if isinstance(item.get("count"), (int, float)) and item.get("count") > 0
        ]
        return {
            "component": "VApexChart",
            "props": {
                "height": 260,
                "options": {
                    "chart": {
                        "type": "pie"
                    },
                    "labels": [item.get("name") for item in chart_items],
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

    def __get_site_cookie(self) -> str:
        for domain in [self.SITE_DOMAIN, "tangpt.top"]:
            try:
                site = SiteOper().get_by_domain(domain)
                cookie = (site.cookie or "").strip() if site else ""
                if cookie:
                    logger.info(f"读取不可躺站点 Cookie 成功：domain={domain}")
                    return cookie
            except Exception as err:
                logger.debug(f"读取不可躺站点 Cookie 失败：domain={domain}，错误={err}")
        return ""

    @staticmethod
    def __html_to_text(content: str) -> str:
        text = re.sub(r"<(script|style).*?</\1>", " ", content, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = unescape(text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def __extract_number_near_label(text: str, label: str) -> str:
        number = r"([\d,]+(?:\s*/\s*[\d,]+)?)"
        label_pattern = re.escape(label)
        before = re.search(number + r"\s*(?:魔力|次|点)?\s*" + label_pattern, text)
        if before:
            return re.sub(r"\s+", " ", before.group(1)).strip()
        after = re.search(label_pattern + r"\s*[：:·，,\s]*(?:消耗|还可以抽)?\s*" + number, text)
        if after:
            return re.sub(r"\s+", " ", after.group(1)).strip()
        return "-"

    @staticmethod
    def __extract_remaining_count(text: str) -> str:
        patterns = [
            r"今天还可以抽\s*([\d,]+)\s*次",
            r"今日还可以抽\s*([\d,]+)\s*次",
            r"剩余\s*([\d,]+)\s*次",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).replace(",", "")
        return "-"

    @staticmethod
    def __extract_draw_quota(text: str) -> Tuple[str, str]:
        match = re.search(r"今天最多可抽奖\s*([\d,]+)\s*次.*?当前已抽\s*([\d,]+)\s*次", text)
        if not match:
            match = re.search(r"今日最多可抽奖\s*([\d,]+)\s*次.*?当前已抽\s*([\d,]+)\s*次", text)
        if match:
            return match.group(1).replace(",", ""), match.group(2).replace(",", "")
        return "-", "-"

    @classmethod
    def __calculate_today_drawn(cls, remaining_count: Any) -> str:
        remaining = cls.__safe_int(remaining_count, -1, min_value=-1)
        if remaining < 0:
            return "-"
        return str(max(cls.DAILY_LIMIT_COUNT - remaining, 0))

    @staticmethod
    def __extract_magic_balance(text: str) -> str:
        patterns = [
            r"当前魔力\s*[：:]\s*([\d,.]+)",
            r"魔力值\s*(?:\[[^\]]+\])?\s*[：:]\s*([\d,.]+)",
            r"魔力\s*(?:\[[^\]]+\])?\s*[：:]\s*([\d,.]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                value = match.group(1).replace(",", "")
                return value[:-2] if value.endswith(".0") else value
        return "-"

    @staticmethod
    def __new_result(status: str = "running", message: str = "", target_count: int = 0,
                     planned_batches: int = 0) -> Dict[str, Any]:
        return {
            "task_id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
            "date": "",
            "status": status,
            "status_text": TangLottery.__status_text(status),
            "message": message,
            "target_count": target_count,
            "planned_batches": planned_batches,
            "completed_count": 0,
            "batch_requests": 0,
            "total_cost": 0,
            "bonus": 0,
            "compensated_bonus": 0,
            "user_bonus_after": "-",
            "traffic": 0,
            "traffic_text": "0 GB",
            "other_rewards": defaultdict(int),
            "other_text": "",
            "prize_summary": Counter(),
            "winning_summary": Counter(),
            "prize_text": "",
            "summary_texts": [],
            "detail_texts": [],
            "summary_text": "",
            "detail_text": ""
        }

    @staticmethod
    def __status_text(status: str) -> str:
        return {
            "completed": "已完成",
            "quota_exhausted": "次数不足",
            "auth_failed": "Cookie失效",
            "failed": "执行失败",
            "running": "执行中"
        }.get(status or "", status or "未知")

    @staticmethod
    def __is_auth_message(message: str) -> bool:
        lowered = (message or "").lower()
        return any(word in lowered for word in ["cookie", "非法访问", "未登录", "登录", "权限", "auth"])

    @staticmethod
    def __sleep_between_requests(min_seconds: int = 10, max_seconds: int = 20):
        delay = random.randint(min_seconds, max_seconds)
        logger.info(f"抽奖请求间隔等待：{delay} 秒")
        time.sleep(delay)

    @classmethod
    def __request_retry_delay(cls, failed_count: int) -> int:
        index = max(0, min(failed_count - 1, len(cls.REQUEST_RETRY_DELAYS) - 1))
        return cls.REQUEST_RETRY_DELAYS[index]

    @staticmethod
    def __safe_str(value: Any, default: str = "") -> str:
        if isinstance(value, str):
            return value.strip()
        return default

    @staticmethod
    def __normalize_cron(value: Any) -> str:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return "10 2 * * *"

    @staticmethod
    def __safe_int(value: Any, default: int, min_value: Optional[int] = None,
                   max_value: Optional[int] = None) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = default
        if min_value is not None:
            number = max(number, min_value)
        if max_value is not None:
            number = min(number, max_value)
        return number

    @staticmethod
    def __safe_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def __traffic_to_gb(value: float, unit: str, prize_name: str) -> float:
        marker = f"{unit} {prize_name}".lower()
        if "tb" in marker:
            return value * 1024
        if "mb" in marker:
            return value / 1024
        return value

    @staticmethod
    def __extract_traffic_value(text: str) -> Tuple[float, str]:
        match = re.search(r"([\d.]+)\s*(TB|GB|MB)", text or "", flags=re.IGNORECASE)
        if not match:
            return 0, ""
        try:
            return float(match.group(1)), match.group(2).upper()
        except ValueError:
            return 0, match.group(2).upper()

    @staticmethod
    def __normalize_number(value: Any) -> float:
        number = TangLottery.__safe_float(value, 0)
        return int(number) if number.is_integer() else round(number, 4)

    @staticmethod
    def __format_number(value: Any) -> str:
        number = TangLottery.__safe_float(value, 0)
        if number.is_integer():
            return str(int(number))
        return str(round(number, 4))

    @staticmethod
    def __counter_to_text(counter: Dict[str, int]) -> str:
        if not counter:
            return ""
        return "\n".join(
            f"{name} x {count}"
            for name, count in sorted(counter.items(), key=lambda item: item[1], reverse=True)
        )

    @staticmethod
    def __to_log_text(value: Any, max_length: int = 6000) -> str:
        try:
            if isinstance(value, str):
                text = value
            else:
                text = json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
            text = str(value)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > max_length:
            return f"{text[:max_length]}...（已截断，原始长度 {len(text)}）"
        return text

    @staticmethod
    def __response_preview(text: str, max_length: int = 3000) -> str:
        if text is None:
            return "响应体为 None"
        if text == "":
            return "响应体为空"
        return TangLottery.__to_log_text(text, max_length=max_length)
