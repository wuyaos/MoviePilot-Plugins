import base64
import json
import re
import threading
from datetime import datetime, timedelta
from html import unescape
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urljoin

import requests
import urllib3
from apscheduler.triggers.cron import CronTrigger
from urllib3.exceptions import InsecureRequestWarning

from app.db.site_oper import SiteOper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import NotificationType

urllib3.disable_warnings(InsecureRequestWarning)


class GGPTMedalBuyer(_PluginBase):
    plugin_name = "GGPT勋章购买"
    plugin_desc = "自动续购 7 天有效的 GGPT 疯狂星期四勋章，避免到期后忘记手动购买。"
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/medal.png"
    plugin_version = "1.0.1"
    plugin_author = "jiangbkvir,wuyaos"
    author_url = "https://github.com/jiangbkvir/MoviePilot-Plugins"
    plugin_config_prefix = "ggptmedalbuyer_"
    plugin_order = 60
    auth_level = 1

    SITE_DOMAIN = "gamegamept.com"
    SITE_NAME = "GGPT"
    MEDAL_PATH = "/medal.php"
    USERDETAILS_PATH = "/userdetails.php"
    DEFAULT_MEDAL_ID = "35"
    DEFAULT_MEDAL_NAME = "疯狂星期四"
    DEFAULT_VALID_DAYS = 7
    DAILY_REFRESH_HOUR = 8
    DAILY_REFRESH_MINUTE = 0
    MAX_HISTORY = 30
    REQUEST_TIMEOUT = 30

    _enabled = False
    _notify = True
    _run_once = False
    _medal_id = DEFAULT_MEDAL_ID
    _offset_seconds = 0
    _lock = threading.Lock()
    _timer_lock = threading.Lock()
    _purchase_timer: Optional[threading.Timer] = None
    _purchase_timer_at = ""

    def init_plugin(self, config: dict = None):
        config = config or {}
        self._enabled = bool(config.get("enabled", False))
        self._notify = bool(config.get("notify", True))
        self._run_once = bool(config.get("run_once", False))
        self._medal_id = str(config.get("medal_id") or self.DEFAULT_MEDAL_ID).strip()
        self._offset_seconds = self.__safe_int(config.get("offset_seconds"), 0, min_value=0)
        logger.info(
            f"GGPT 勋章购买初始化完成：enabled={self._enabled}, medal_id={self._medal_id}, "
            f"offset_seconds={self._offset_seconds}, notify={self._notify}"
        )
        if self._run_once:
            self._run_once = False
            self.update_config(self.__config_snapshot(run_once=False))
            logger.info("收到配置页立即运行请求，后台启动 GGPT 勋章检查任务")
            threading.Thread(target=self.run_buy_task, kwargs={"force": False}, daemon=True).start()
        elif self._enabled:
            logger.info("插件配置已保存，后台启动 GGPT 勋章检查任务")
            threading.Thread(target=self.run_buy_task, kwargs={"force": False}, daemon=True).start()
        else:
            self.__cancel_purchase_timer()

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/GGPTMedalBuyer/run",
                "endpoint": self.run_once_api,
                "methods": ["POST"],
                "auth": "apikey",
                "summary": "立即检查 GGPT 勋章",
                "description": "按当前插件配置立即检查 GGPT 勋章状态；未购买或已到期时才会购买。"
            }
        ]

    def get_service(self) -> List[Dict[str, Any]]:
        if not self._enabled:
            return []
        return [
            {
                "id": "GGPTMedalBuyerDailyRefresh",
                "name": "GGPT勋章每日刷新预计购买时间",
                "trigger": CronTrigger(hour=self.DAILY_REFRESH_HOUR, minute=self.DAILY_REFRESH_MINUTE),
                "func": self.daily_refresh_task,
                "kwargs": {}
            }
        ]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return self.__form_components(), self.__form_data()

    def get_page(self) -> List[dict]:
        return self.__page_components()

    def __form_components(self) -> List[dict]:
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "enabled",
                                            "label": "启用插件"
                                        }
                                    }
                                ]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "notify",
                                            "label": "购买成功提醒",
                                            "hint": "勾选后购买成功或失败都会发送通知"
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
                                        "component": "VTextField",
                                        "props": {
                                            "model": "medal_id",
                                            "label": "勋章 ID",
                                            "placeholder": self.DEFAULT_MEDAL_ID,
                                            "hint": "疯狂星期四当前为 35"
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
                                            "model": "offset_seconds",
                                            "label": "偏移量（秒）",
                                            "type": "number",
                                            "min": 0,
                                            "hint": "到期后延迟多少秒购买勋章"
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]

    def __page_components(self) -> List[dict]:
        site = self.__get_ggpt_site()
        state = self.__get_state_data()
        next_purchase_at = self.__next_purchase_time(state) or "未解析到到期时间，将在启用后立即购买一次"
        site_status = self.__site_status_text(site)
        record_rows = self.__record_rows(state)
        return [
            {
                "component": "div",
                "props": {"class": "text-h6 mb-3"},
                "text": "当前状态"
            },
            {
                "component": "VRow",
                "content": self.__status_cards(site, state, next_purchase_at, site_status)
            },
            {
                "component": "div",
                "props": {"class": "text-h6 mt-4 mb-3"},
                "text": "购买记录"
            },
            {
                "component": "VRow",
                "content": self.__record_cards(record_rows)
            }
        ]

    def __form_data(self) -> Dict[str, Any]:
        site = self.__get_ggpt_site()
        state = self.__get_state_data()
        next_purchase_at = self.__next_purchase_time(state) or "未解析到到期时间，将在启用后立即购买一次"
        site_status = self.__site_status_text(site)
        return {
            "enabled": self._enabled,
            "notify": self._notify,
            "medal_id": self._medal_id,
            "offset_seconds": self._offset_seconds,
            "next_purchase_at": next_purchase_at,
            "site_status": site_status
        }

    def __status_cards(self, site, state: Dict[str, Any], next_purchase_at: str, site_status: str) -> List[dict]:
        owned = bool(state.get("page_expire_at") or state.get("last_success_at"))
        expire_at = state.get("page_expire_at") or "-"
        user_id = state.get("user_id") or self.__parse_user_id_from_cookie(getattr(site, "cookie", "") if site else "") or "-"
        site_name = state.get("last_site_name") or getattr(site, "name", None) or self.SITE_NAME
        site_domain = state.get("last_site_domain") or getattr(site, "domain", None) or self.SITE_DOMAIN
        medal_status = "有" if owned else "未确认"
        status_color = "success" if owned else "warning"
        fields = [
            ("UID", user_id),
            ("站点", f"{site_name}（{site_domain}）"),
            ("到期时间", expire_at),
            ("预计下次购买", next_purchase_at)
        ]
        return [
            {
                "component": "VCol",
                "props": {"cols": 12},
                "content": [
                    {
                        "component": "VCard",
                        "props": {"variant": "tonal"},
                        "content": [
                            {
                                "component": "VCardText",
                                "props": {"class": "py-4"},
                                "content": [
                                    {
                                        "component": "VRow",
                                        "props": {"class": "align-center"},
                                        "content": [
                                            {
                                                "component": "VCol",
                                                "props": {"cols": 12, "md": 3},
                                                "content": [
                                                    {
                                                        "component": "div",
                                                        "props": {"class": "text-caption text-medium-emphasis mb-1"},
                                                        "text": "疯狂星期四勋章"
                                                    },
                                                    {
                                                        "component": "div",
                                                        "props": {"class": "text-h6 font-weight-bold mb-2"},
                                                        "text": "GGPT 勋章"
                                                    },
                                                    {
                                                        "component": "VChip",
                                                        "props": {
                                                            "size": "small",
                                                            "color": status_color,
                                                            "variant": "tonal"
                                                        },
                                                        "text": f"持有状态：{medal_status}"
                                                    }
                                                ]
                                            },
                                            {
                                                "component": "VCol",
                                                "props": {"cols": 12, "md": 9},
                                                "content": [
                                                    {
                                                        "component": "VRow",
                                                        "content": [
                                                            {
                                                                "component": "VCol",
                                                                "props": {"cols": 12, "sm": 6, "lg": 3},
                                                                "content": [
                                                                    {
                                                                        "component": "div",
                                                                        "props": {"class": "text-caption text-medium-emphasis mb-1"},
                                                                        "text": label
                                                                    },
                                                                    {
                                                                        "component": "div",
                                                                        "props": {"class": "text-body-2 font-weight-medium"},
                                                                        "text": str(value)
                                                                    }
                                                                ]
                                                            }
                                                            for label, value in fields
                                                        ]
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
            }
        ]

    def __record_cards(self, rows: List[Dict[str, Any]]) -> List[dict]:
        if not rows:
            return [
                {
                    "component": "VCol",
                    "props": {"cols": 12},
                    "content": [
                        {
                            "component": "VCard",
                            "props": {"variant": "tonal"},
                            "content": [
                                {
                                    "component": "VCardText",
                                    "props": {"class": "text-medium-emphasis"},
                                    "text": "暂无购买记录"
                                }
                            ]
                        }
                    ]
                }
            ]

        cards = []
        for item in rows:
            medal_name = item.get("medal_name") or self.DEFAULT_MEDAL_NAME
            status_text = item.get("status_text") or "-"
            status_color = item.get("status_color") or "default"
            date_text = item.get("date") or "-"
            date_part, time_part = self.__split_record_datetime(date_text)
            message = item.get("message") or "-"
            cards.append(
                {
                    "component": "VCol",
                    "props": {
                        "cols": "auto",
                        "style": "flex: 0 0 16.6667%; max-width: 16.6667%; min-width: 160px;"
                    },
                    "content": [
                        {
                            "component": "VCard",
                            "props": {"variant": "tonal", "class": "h-100 d-flex flex-column"},
                            "content": [
                                {
                                    "component": "VCardText",
                                    "props": {"class": "pb-2"},
                                    "content": [
                                        {
                                            "component": "div",
                                            "props": {"class": "d-flex align-center justify-space-between mb-3"},
                                            "content": [
                                                {
                                                    "component": "div",
                                                    "props": {"class": "text-subtitle-2 font-weight-bold text-truncate"},
                                                    "text": medal_name
                                                },
                                                {
                                                    "component": "VChip",
                                                    "props": {
                                                        "size": "x-small",
                                                        "color": status_color,
                                                        "variant": "tonal"
                                                    },
                                                    "text": status_text
                                                }
                                            ]
                                        },
                                        {
                                            "component": "div",
                                            "props": {"class": "text-caption text-medium-emphasis mb-1"},
                                            "text": "时间"
                                        },
                                        {
                                            "component": "div",
                                            "props": {
                                                "class": "text-body-2 font-weight-medium",
                                                "style": "white-space: nowrap;"
                                            },
                                            "text": date_part
                                        },
                                        {
                                            "component": "div",
                                            "props": {
                                                "class": "text-body-2 font-weight-medium mb-2",
                                                "style": "white-space: nowrap;"
                                            },
                                            "text": time_part
                                        },
                                        {
                                            "component": "VDivider",
                                            "props": {"class": "my-2"}
                                        },
                                        {
                                            "component": "div",
                                            "props": {"class": "text-caption text-medium-emphasis mb-1"},
                                            "text": "说明"
                                        },
                                        {
                                            "component": "div",
                                            "props": {
                                                "class": "text-body-2 text-medium-emphasis",
                                                "style": "line-height: 1.45;"
                                            },
                                            "text": message
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            )
        return cards

    def __record_rows(self, state: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        rows = []
        for item in self.__get_records():
            status = self.__record_status(item)
            rows.append(
                {
                    "date": self.__record_date(item),
                    "site_name": item.get("site_name") or item.get("site") or item.get("base_url") or self.SITE_NAME,
                    "medal_name": item.get("medal_name") or item.get("name") or self.DEFAULT_MEDAL_NAME,
                    "status_text": item.get("status_text") or self.__status_text(status),
                    "status_color": self.__status_color(status),
                    "message": item.get("message") or item.get("msg") or "-"
                }
            )
        if rows:
            return rows

        state = state or self.__get_state_data()
        if state.get("last_success_at") or state.get("page_expire_at"):
            expire_at = state.get("page_expire_at") or "-"
            return [
                {
                    "date": state.get("last_success_at") or state.get("page_expire_at") or state.get("updated_at") or "-",
                    "site_name": state.get("last_site_name") or self.SITE_NAME,
                    "medal_name": state.get("last_medal_name") or self.DEFAULT_MEDAL_NAME,
                    "status_text": "已购买",
                    "status_color": "success",
                    "message": f"当前勋章已购买，已读取到期时间：{expire_at}"
                }
            ]
        return []

    @staticmethod
    def __record_date(item: Dict[str, Any]) -> str:
        return (
            item.get("purchase_time")
            or item.get("date")
            or item.get("time")
            or item.get("created_at")
            or item.get("updated_at")
            or "-"
        )

    def __record_status(self, item: Dict[str, Any]) -> str:
        status = str(item.get("status") or "").strip()
        if status:
            return status
        status_text = str(item.get("status_text") or "").strip()
        if "成功" in status_text:
            return "success"
        if "失败" in status_text:
            return "failed"
        if item.get("success") is True or item.get("ok") is True or item.get("purchase_time"):
            return "success"
        if item.get("success") is False or item.get("ok") is False:
            return "failed"
        return ""

    @staticmethod
    def __split_record_datetime(value: Any) -> Tuple[str, str]:
        text = str(value or "-").strip()
        if " " not in text:
            return text, ""
        date_part, time_part = text.split(" ", 1)
        return date_part.strip(), time_part.strip()

    @staticmethod
    def __status_color(status: str) -> str:
        return {
            "success": "success",
            "failed": "error",
            "auth_failed": "warning",
            "config_error": "warning",
            "skipped": "info"
        }.get(status or "", "default")

    def stop_service(self):
        self.__cancel_purchase_timer()

    def run_once_api(self) -> Dict[str, Any]:
        if self._lock.locked():
            logger.warning("立即检查请求被忽略：已有 GGPT 勋章任务正在执行")
            return {"success": False, "message": "已有购买任务正在执行"}
        logger.info("收到 API 立即检查请求，后台启动 GGPT 勋章检查任务")
        threading.Thread(target=self.run_buy_task, kwargs={"force": False}, daemon=True).start()
        return {"success": True, "message": "任务已开始，完成后会写入购买记录并按配置发送通知"}

    def daily_refresh_task(self) -> Dict[str, Any]:
        logger.info("开始执行 GGPT 勋章每日刷新任务：刷新预计购买时间，若已到期则自动购买")
        return self.run_buy_task(force=False)

    def run_buy_task(self, force: bool = False) -> Dict[str, Any]:
        if not self._lock.acquire(blocking=False):
            logger.warning("GGPT 勋章购买任务启动失败：已有任务正在执行")
            return {"success": False, "message": "已有购买任务正在执行"}
        result = self.__result("failed", "未知错误")
        try:
            if not self._medal_id:
                result = self.__result("config_error", "请先填写勋章 ID")
                return self.__finish_task(result)

            site = self.__get_ggpt_site()
            if not site:
                result = self.__result("config_error", "未找到 MoviePilot 站点管理中的 GGPT/gamegamept.com 站点")
                return self.__finish_task(result)
            if not (site.cookie or "").strip():
                result = self.__result("auth_failed", "GGPT 站点缺少 Cookie，请先在 MoviePilot 站点管理维护 Cookie")
                return self.__finish_task(result, site=site)

            page_response = self.__request("GET", self.__medal_url(site), site=site)
            page_text = page_response.text or ""
            medal_info = self.__parse_medal_info(page_text)
            state = self.__get_state_data()
            self.__refresh_state_from_page(state, page_text, medal_info, site)

            if not force and not self.__is_due(state):
                next_at = self.__next_purchase_time(state)
                logger.info(f"GGPT 勋章未到购买时间：预计下次购买={next_at or '-'}")
                self.__schedule_next_purchase_timer(state)
                result = self.__result("skipped", f"未到购买时间，预计下次购买：{next_at or '-'}", success=True)
                return self.__finish_task(result, site=site, medal_info=medal_info, save_record=False, notify=False)

            logger.info(
                f"GGPT 勋章购买任务开始：site={site.name}({site.domain})，medal_id={self._medal_id}，"
                f"medal_name={medal_info.get('name')}，force={force}"
            )
            buy_response = self.__buy_medal(site)
            status, message = self.__judge_purchase_result(buy_response.text or "", buy_response.status_code)
            result = self.__result(status, message, success=status == "success")
            if result["success"]:
                purchase_time = self.__now_text()
                valid_days = medal_info.get("valid_days") or self.DEFAULT_VALID_DAYS
                next_expire_at = datetime.strptime(purchase_time, "%Y-%m-%d %H:%M:%S") + timedelta(days=valid_days)
                state["last_success_at"] = purchase_time
                state["last_site_name"] = site.name or self.SITE_NAME
                state["last_site_domain"] = site.domain or self.SITE_DOMAIN
                state["last_medal_name"] = medal_info.get("name") or self.DEFAULT_MEDAL_NAME
                state["valid_days"] = valid_days
                state["page_expire_at"] = next_expire_at.strftime("%Y-%m-%d %H:%M:%S")
                self.save_data("state", state)
                self.__schedule_next_purchase_timer(state)
            else:
                self.__schedule_next_purchase_timer(state, fallback_daily=True)
            return self.__finish_task(result, site=site, medal_info=medal_info)
        except Exception as err:
            logger.error(f"GGPT 勋章购买任务异常：{err}")
            result = self.__result("failed", f"购买异常：{err}")
            return self.__finish_task(result)
        finally:
            self._lock.release()

    def __buy_medal(self, site) -> requests.Response:
        ajax_url = urljoin(self.__base_url(site) + "/", "ajax.php")
        data = {
            "action": "buyMedal",
            "params[medal_id]": self._medal_id
        }
        headers = self.__ajax_headers(site)
        logger.info(f"提交 GGPT 勋章购买接口：url={ajax_url}，medal_id={self._medal_id}")
        response = requests.post(
            ajax_url,
            headers=headers,
            data=data,
            timeout=self.REQUEST_TIMEOUT,
            verify=False
        )
        preview = self.__to_log_text(response.text, 800)
        logger.info(f"GGPT 勋章购买接口响应：status_code={response.status_code}，响应预览={preview}")
        if response.status_code in [401, 403]:
            raise RuntimeError(f"登录态无效或无权限：HTTP {response.status_code}")
        if response.status_code >= 500:
            raise RuntimeError(f"站点服务异常：HTTP {response.status_code}")
        return response

    def __request(self, method: str, url: str, site, referer: str = "", label: str = "GGPT 页面") -> requests.Response:
        headers = self.__page_headers(site, referer=referer)
        logger.info(f"请求 {label}：method={method}, url={url}")
        response = requests.get(url, headers=headers, timeout=self.REQUEST_TIMEOUT, verify=False)
        logger.info(f"{label}响应：status_code={response.status_code}, url={url}")
        if response.status_code in [401, 403]:
            raise RuntimeError(f"登录态无效或无权限：HTTP {response.status_code}")
        if response.status_code >= 500:
            raise RuntimeError(f"站点服务异常：HTTP {response.status_code}")
        return response

    def __page_headers(self, site, referer: str = "") -> Dict[str, str]:
        return {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "zh-CN,zh;q=0.9",
            "cache-control": "max-age=0",
            "cookie": (site.cookie or "").strip(),
            "priority": "u=0, i",
            "referer": referer or urljoin(self.__base_url(site) + "/", "mybonus.php"),
            "sec-ch-ua": '"Google Chrome";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": (site.ua or "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36").strip()
        }

    def __ajax_headers(self, site) -> Dict[str, str]:
        return {
            "accept": "application/json, text/javascript, */*; q=0.01",
            "accept-language": "zh-CN,zh;q=0.9",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "cookie": (site.cookie or "").strip(),
            "origin": self.__base_url(site),
            "referer": self.__medal_url(site),
            "sec-ch-ua": '"Google Chrome";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "user-agent": (site.ua or "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36").strip(),
            "x-requested-with": "XMLHttpRequest"
        }

    def __judge_purchase_result(self, text: str, status_code: int) -> Tuple[str, str]:
        plain = self.__html_to_text(text)
        preview = self.__to_log_text(plain, 500)
        logger.info(f"GGPT 勋章购买响应预览：{preview}")
        if status_code >= 400:
            return "failed", f"购买请求失败：HTTP {status_code}"
        try:
            data = requests.models.complexjson.loads(text or "{}")
            if isinstance(data, dict):
                raw_message = str(data.get("message") or data.get("msg") or data.get("info") or preview or "接口未返回说明")
                message = self.__translate_site_message(raw_message)
                ret_value = data.get("ret")
                code_value = data.get("code")
                ok_value = data.get("ok")
                success_value = data.get("success")
                status_value = data.get("status")
                if ret_value in [0, "0"] or code_value in [0, "0"]:
                    return "success", f"购买成功：{message}"
                if ret_value not in [None, 0, "0"] or code_value not in [None, 0, "0"]:
                    return "failed", f"站点返回失败信息：{message}"
                if ok_value is False or success_value is False or status_value in ["error", "fail", "failed"]:
                    return "failed", f"站点返回失败信息：{message}"
                if ok_value is True or success_value is True or status_value in ["success", "ok", 1, "1"]:
                    return "success", f"购买成功：{message}"
        except Exception:
            logger.warning(f"GGPT 勋章购买接口返回非 JSON：响应预览={preview}")
        fail_words = ["魔力不足", "余额不足", "权限", "未登录", "登录", "失败", "错误", "error", "forbidden"]
        if any(word.lower() in plain.lower() for word in fail_words):
            return "failed", f"站点返回失败信息：{self.__translate_site_message(preview)}"
        success_words = ["成功", "购买", "领取", "兑换", "已获得", "success"]
        if any(word.lower() in plain.lower() for word in success_words):
            return "success", f"购买请求已提交：{preview}"
        return "failed", f"购买接口返回无法确认成功：{preview or '空响应'}"

    @staticmethod
    def __translate_site_message(message: str) -> str:
        text = str(message or "").strip()
        lowered = text.lower()
        if "user bonus not enough" in lowered or "bonus not enough" in lowered:
            return "G 值/魔力不足，无法购买勋章"
        if "permission denied" in lowered or "forbidden" in lowered:
            return "权限不足或登录态无效，请检查 GGPT Cookie"
        if "login" in lowered or "unauthorized" in lowered:
            return "登录态无效，请更新 MoviePilot 站点管理中的 GGPT Cookie"
        if "already" in lowered and ("own" in lowered or "bought" in lowered or "have" in lowered):
            return "站点提示已拥有或已购买该勋章"
        return text

    def __parse_medal_info(self, html: str) -> Dict[str, Any]:
        plain = self.__html_to_text(html)
        context = self.__medal_html_context(html)
        info = {
            "id": self._medal_id,
            "name": self.DEFAULT_MEDAL_NAME if self._medal_id == self.DEFAULT_MEDAL_ID else f"勋章 {self._medal_id}",
            "valid_days": self.DEFAULT_VALID_DAYS,
            "owned": False
        }
        if context and ("已经购买" in unescape(context) or 'value="已经购买"' in context or "value='已经购买'" in context):
            info["owned"] = True
        pattern = (
            rf"(?:^|\s){re.escape(self._medal_id)}\s+"
            rf"(?P<name>\S+)\s+.*?"
            rf"(?:不限|\d{{4}}-\d{{2}}-\d{{2}}\s+\d{{2}}:\d{{2}}:\d{{2}})\s+~\s+"
            rf"(?:不限|\d{{4}}-\d{{2}}-\d{{2}}\s+\d{{2}}:\d{{2}}:\d{{2}})\s+"
            rf"(?P<days>永久有效|\d+)"
        )
        match = re.search(pattern, plain)
        if match:
            info["name"] = match.group("name").strip()
            days_text = match.group("days").strip()
            if days_text != "永久有效":
                info["valid_days"] = self.__safe_int(days_text, self.DEFAULT_VALID_DAYS, min_value=1)
        logger.info(
            f"GGPT 勋章页面解析结果：medal_id={info.get('id')}，medal_name={info.get('name')}，"
            f"valid_days={info.get('valid_days')}，owned={info.get('owned')}"
        )
        return info

    def __refresh_state_from_page(self, state: Dict[str, Any], html: str, medal_info: Dict[str, Any], site):
        expire_at = self.__parse_owned_expire_time(html, medal_info.get("name") or "")
        if expire_at:
            state["page_expire_at"] = expire_at.strftime("%Y-%m-%d %H:%M:%S")
            state["valid_days"] = medal_info.get("valid_days") or self.DEFAULT_VALID_DAYS
            state["last_site_name"] = getattr(site, "name", None) or self.SITE_NAME
            state["last_site_domain"] = getattr(site, "domain", None) or self.SITE_DOMAIN
            state["last_medal_name"] = medal_info.get("name") or self.DEFAULT_MEDAL_NAME
            state["updated_at"] = self.__now_text()
            self.save_data("state", state)
            logger.info(f"从 GGPT 页面解析到当前勋章到期时间：{state['page_expire_at']}")
            return

        if medal_info.get("owned"):
            user_id = self.__parse_user_id_from_cookie(getattr(site, "cookie", "") or "")
            if user_id:
                try:
                    details_url = self.__userdetails_url(site, user_id)
                    details_response = self.__request(
                        "GET",
                        details_url,
                        site=site,
                        referer=self.__medal_url(site),
                        label="GGPT 个人中心页面"
                    )
                    details_expire_at = self.__parse_userdetails_expire_time(
                        details_response.text or "",
                        medal_info
                    )
                    if details_expire_at:
                        state["page_expire_at"] = details_expire_at.strftime("%Y-%m-%d %H:%M:%S")
                        state["valid_days"] = medal_info.get("valid_days") or self.DEFAULT_VALID_DAYS
                        state["user_id"] = str(user_id)
                        state["last_site_name"] = getattr(site, "name", None) or self.SITE_NAME
                        state["last_site_domain"] = getattr(site, "domain", None) or self.SITE_DOMAIN
                        state["last_medal_name"] = medal_info.get("name") or self.DEFAULT_MEDAL_NAME
                        state["updated_at"] = self.__now_text()
                        self.save_data("state", state)
                        logger.info(f"从 GGPT 个人中心解析到当前勋章到期时间：{state['page_expire_at']}")
                        return
                    logger.warning("GGPT 个人中心未解析到当前勋章到期时间，将使用兜底规则")
                except Exception as err:
                    logger.warning(f"读取 GGPT 个人中心到期时间失败：{err}")
            else:
                logger.warning("未能从 GGPT Cookie 解析 user_id，无法读取个人中心到期时间")

            valid_days = medal_info.get("valid_days") or self.DEFAULT_VALID_DAYS
            state["valid_days"] = valid_days
            now = datetime.now()
            current_expire_at = self.__parse_time_text(state.get("page_expire_at"))
            last_success_at = self.__parse_time_text(state.get("last_success_at"))
            if current_expire_at and current_expire_at > now:
                expire_at = current_expire_at
                reason = "沿用已保存的未来到期时间"
            elif last_success_at:
                expire_at = last_success_at + timedelta(days=valid_days)
                reason = "按最近成功购买时间推算"
            else:
                expire_at = now + timedelta(days=valid_days)
                reason = "页面显示已购买但未解析到精确到期时间，按当前时间推算"
            state["page_expire_at"] = expire_at.strftime("%Y-%m-%d %H:%M:%S")
            state["last_site_name"] = getattr(site, "name", None) or self.SITE_NAME
            state["last_site_domain"] = getattr(site, "domain", None) or self.SITE_DOMAIN
            state["last_medal_name"] = medal_info.get("name") or self.DEFAULT_MEDAL_NAME
            state["updated_at"] = self.__now_text()
            self.save_data("state", state)
            logger.info(f"GGPT 页面显示勋章已购买：{reason}，预计到期={state['page_expire_at']}")

    def __parse_owned_expire_time(self, html: str, medal_name: str) -> Optional[datetime]:
        """从勋章页面解析当前勋章的到期时间。

        只在目标勋章所在 <tr> 行内查找日期，避免在全页文本中用勋章 ID
        搜索（例如 ID=35 会误命中 "分享率: 3.935" 里的 35，从而取到其他
        勋章的结束日期）。疯狂星期四的可购买时间为 "不限 ~ 不限"，行内
        无日期，返回 None 由上层走个人中心分支读取真实到期时间。
        """
        _ = medal_name  # 保留参数兼容旧调用，精确解析依赖 data-id 锚定
        row = self.__medal_html_context(html)
        if not row:
            return None
        times = re.findall(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}", row)
        if not times:
            return None
        try:
            return datetime.strptime(times[-1], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

    def __parse_userdetails_expire_time(self, html: str, medal_info: Dict[str, Any]) -> Optional[datetime]:
        """从个人中心页面解析目标勋章的到期时间。

        用 title="勋章名" 的 <img> 锚定，取其后最近的 "过期时间" span，
        精确匹配到当前勋章；不再用 min(future_times) 碰运气，否则当
        用户持有多个到期时间不同的勋章时，可能返回错误勋章的时间。
        """
        if not html:
            return None
        medal_name = medal_info.get("name") or self.DEFAULT_MEDAL_NAME
        img_match = re.search(
            rf'<img[^>]*title=["\']{re.escape(medal_name)}["\'][^>]*/?>',
            html, flags=re.IGNORECASE
        )
        if img_match:
            pos = img_match.start()
            after = html[pos:pos + 2000]
            expire_match = re.search(
                r"过期时间\s*[:：]?\s*(\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?|永久有效)",
                after
            )
            if expire_match:
                val = expire_match.group(1)
                if val == "永久有效":
                    return None
                t = self.__parse_time_text(val)
                if t:
                    return t
        # 兜底：页面结构变化导致 img 锚定失败时，沿用原标签解析逻辑
        plain = self.__html_to_text(html)
        return self.__parse_expire_label_time(plain)

    def __parse_expire_label_time(self, text: str) -> Optional[datetime]:
        now = datetime.now()
        matches = re.findall(
            r"(?<!魔力加成)过期时间\s*[:：]\s*(\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?)",
            text or ""
        )
        times = [item for item in [self.__parse_time_text(match) for match in matches] if item]
        future_times = [item for item in times if item > now - timedelta(minutes=5)]
        if future_times:
            return min(future_times)
        return max(times) if times else None

    def __medal_html_context(self, html: str) -> str:
        """提取目标勋章所在 <tr> 行的精确 HTML。

        用 data-id="勋章ID" 的购买按钮锚定位置，向前取最近的 <tr>，
        向后取最近的 <tr>（下一行开始）或 </table> 作为行边界，避免
        正则贪婪跨行匹配到整个表格，也兼容 NexusPHP 省略 </tr> 的写法。
        """
        if not html:
            return ""
        medal_id = re.escape(str(self._medal_id))
        input_match = re.search(
            rf'<input[^>]*data-id=["\']?{medal_id}["\']?[^>]*>',
            html, flags=re.IGNORECASE
        )
        if not input_match:
            # 兜底：data-id 锚定失败时回退到 id 文本单元格
            text_match = re.search(rf">\s*{medal_id}\s*<", html)
            if not text_match:
                return ""
            input_match = text_match
        pos = input_match.start()
        tr_start = html.rfind("<tr", 0, pos)
        if tr_start < 0:
            return ""
        next_tr = html.find("<tr", pos)
        if next_tr > tr_start:
            return html[tr_start:next_tr]
        tbl_end = html.find("</table", pos)
        if tbl_end > tr_start:
            return html[tr_start:tbl_end]
        return html[tr_start:]

    def __finish_task(
        self,
        result: Dict[str, Any],
        site=None,
        medal_info: Optional[Dict[str, Any]] = None,
        save_record: bool = True,
        notify: bool = True
    ) -> Dict[str, Any]:
        state = self.__get_state_data()
        medal_info = medal_info or {}
        result["site_name"] = getattr(site, "name", None) or self.SITE_NAME
        result["site_domain"] = getattr(site, "domain", None) or self.SITE_DOMAIN
        result["medal_id"] = self._medal_id
        result["medal_name"] = medal_info.get("name") or state.get("last_medal_name") or self.DEFAULT_MEDAL_NAME
        result["date"] = self.__now_text()
        result["purchase_time"] = result["date"] if result.get("status") == "success" else ""
        result["status_text"] = self.__status_text(result.get("status"))
        result["next_purchase_at"] = self.__next_action_time(state)
        if save_record:
            self.__save_record(result)
        if notify and self._notify and result.get("status") != "skipped":
            self.__send_notification(result)
        return result

    def __save_record(self, result: Dict[str, Any]):
        records = self.__get_records()
        records.insert(0, dict(result))
        self.save_data("records", records[:self.MAX_HISTORY])

    def __send_notification(self, result: Dict[str, Any]):
        title = "【GGPT勋章购买】"
        text = (
            f"站点：{result.get('site_name') or '-'}\n"
            f"勋章：{result.get('medal_name') or '-'}\n"
            f"勋章 ID：{result.get('medal_id') or '-'}\n"
            f"状态：{result.get('status_text') or '-'}\n"
            f"说明：{result.get('message') or '-'}\n"
            f"预计下次购买：{result.get('next_purchase_at') or '-'}"
        )
        logger.info(f"准备发送 GGPT 勋章购买通知：status={result.get('status')}")
        self.post_message(mtype=NotificationType.Plugin, title=title, text=text)

    def __is_due(self, state: Dict[str, Any]) -> bool:
        next_at = self.__next_purchase_datetime(state)
        if not next_at:
            logger.info("GGPT 勋章未解析到到期时间且无成功购买记录，将立即尝试购买一次")
            return True
        return datetime.now() >= next_at

    def __schedule_next_purchase_timer(self, state: Dict[str, Any], fallback_daily: bool = False):
        if not self._enabled:
            self.__cancel_purchase_timer()
            return
        next_at = self.__next_purchase_datetime(state)
        if not next_at:
            next_at = self.__next_daily_refresh_time() if fallback_daily else datetime.now() + timedelta(seconds=10)
        delay = max(1, int((next_at - datetime.now()).total_seconds()))
        next_at_text = next_at.strftime("%Y-%m-%d %H:%M:%S")
        with self._timer_lock:
            if self._purchase_timer and self._purchase_timer.is_alive() and self._purchase_timer_at == next_at_text:
                return
            if self._purchase_timer:
                self._purchase_timer.cancel()
            self._purchase_timer_at = next_at_text
            self._purchase_timer = threading.Timer(delay, self.__timer_purchase_task)
            self._purchase_timer.daemon = True
            self._purchase_timer.start()
        logger.info(f"已注册 GGPT 勋章到点购买定时器：run_at={next_at_text}，delay={delay}s")

    def __timer_purchase_task(self):
        logger.info("GGPT 勋章到点购买定时器触发")
        self.run_buy_task(force=False)

    def __cancel_purchase_timer(self):
        with self._timer_lock:
            if self._purchase_timer:
                self._purchase_timer.cancel()
            self._purchase_timer = None
            self._purchase_timer_at = ""

    def __next_purchase_time(self, state: Dict[str, Any]) -> str:
        next_at = self.__next_purchase_datetime(state)
        return next_at.strftime("%Y-%m-%d %H:%M:%S") if next_at else ""

    def __next_action_time(self, state: Dict[str, Any]) -> str:
        next_purchase_at = self.__next_purchase_time(state)
        if next_purchase_at:
            return next_purchase_at
        if self._purchase_timer_at:
            return self._purchase_timer_at
        return self.__next_daily_refresh_time().strftime("%Y-%m-%d %H:%M:%S")

    def __next_daily_refresh_time(self) -> datetime:
        now = datetime.now()
        next_at = now.replace(
            hour=self.DAILY_REFRESH_HOUR,
            minute=self.DAILY_REFRESH_MINUTE,
            second=0,
            microsecond=0
        )
        if next_at <= now:
            next_at += timedelta(days=1)
        return next_at

    def __next_purchase_datetime(self, state: Dict[str, Any]) -> Optional[datetime]:
        page_expire_at = state.get("page_expire_at")
        if page_expire_at:
            parsed_time = self.__parse_time_text(page_expire_at)
            if parsed_time:
                return parsed_time + timedelta(seconds=self._offset_seconds)
        last_success_at = state.get("last_success_at")
        if not last_success_at:
            return None
        last_at = self.__parse_time_text(last_success_at)
        if not last_at:
            return None
        valid_days = self.__safe_int(state.get("valid_days"), self.DEFAULT_VALID_DAYS, min_value=1)
        return last_at + timedelta(days=valid_days, seconds=self._offset_seconds)

    @staticmethod
    def __parse_time_text(value: Any) -> Optional[datetime]:
        if not value:
            return None
        text = str(value).strip()
        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"]:
            try:
                parsed_time = datetime.strptime(text, fmt)
                if fmt == "%Y-%m-%d":
                    return parsed_time.replace(hour=23, minute=59, second=59)
                return parsed_time
            except ValueError:
                continue
        return None

    def __get_ggpt_site(self):
        try:
            site = SiteOper().get_by_domain(self.SITE_DOMAIN)
            if site:
                return site
        except Exception as err:
            logger.debug(f"按域名读取 GGPT 站点失败：{err}")
        try:
            for site in SiteOper().list_active():
                name = (getattr(site, "name", "") or "").strip().lower()
                domain = (getattr(site, "domain", "") or "").strip().lower()
                if name == self.SITE_NAME.lower() or domain == self.SITE_DOMAIN:
                    return site
        except Exception as err:
            logger.debug(f"遍历 MoviePilot 站点读取 GGPT 失败：{err}")
        return None

    def __site_status_text(self, site) -> str:
        if not site:
            return "未找到 MoviePilot 站点管理中的 GGPT/gamegamept.com"
        cookie_status = "已读取 Cookie" if (site.cookie or "").strip() else "缺少 Cookie"
        return f"{site.name or self.SITE_NAME}（{site.domain or self.SITE_DOMAIN}）：{cookie_status}"

    def __medal_url(self, site) -> str:
        return urljoin(self.__base_url(site) + "/", self.MEDAL_PATH.lstrip("/"))

    def __userdetails_url(self, site, user_id: str) -> str:
        return f"{urljoin(self.__base_url(site) + '/', self.USERDETAILS_PATH.lstrip('/'))}?id={user_id}"

    def __parse_user_id_from_cookie(self, cookie: str) -> str:
        match = re.search(r"(?:^|;\s*)c_secure_pass=([^;]+)", cookie or "")
        if not match:
            return ""
        token = unquote(match.group(1)).strip()
        for payload in self.__cookie_payload_candidates(token):
            try:
                data = json.loads(payload)
                user_id = data.get("user_id")
                if user_id:
                    logger.info("已从 GGPT Cookie 解析到用户 ID")
                    return str(user_id)
            except Exception:
                continue
        logger.debug("解析 GGPT Cookie user_id 失败：未找到可用 payload")
        return ""

    def __cookie_payload_candidates(self, token: str) -> List[str]:
        candidates = []
        decoded = self.__base64_decode_text(token)
        if decoded:
            candidates.extend([decoded, decoded.split(".", 1)[0]])
        if "." in token:
            decoded_head = self.__base64_decode_text(token.split(".", 1)[0])
            if decoded_head:
                candidates.append(decoded_head)
        return [item.strip() for item in candidates if item and item.strip().startswith("{")]

    @staticmethod
    def __base64_decode_text(value: str) -> str:
        try:
            padded = value + "=" * (-len(value) % 4)
            return base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        except Exception:
            return ""

    @staticmethod
    def __base_url(site) -> str:
        return str(getattr(site, "url", "") or "https://www.gamegamept.com/").strip().rstrip("/")

    def __config_snapshot(self, run_once: bool = False) -> Dict[str, Any]:
        return {
            "enabled": self._enabled,
            "notify": self._notify,
            "run_once": run_once,
            "medal_id": self._medal_id,
            "offset_seconds": self._offset_seconds
        }

    @staticmethod
    def __html_to_text(content: str) -> str:
        text = re.sub(r"<(script|style).*?</\1>", " ", content or "", flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = unescape(text)
        return re.sub(r"\s+", " ", text).strip()

    def __extract_datetimes(self, text: str) -> List[datetime]:
        result: List[datetime] = []
        seen = set()
        for match in re.findall(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(?::\d{2})?", text or ""):
            if match in seen:
                continue
            seen.add(match)
            parsed_time = self.__parse_time_text(match)
            if parsed_time:
                result.append(parsed_time)
        for match in re.findall(r"\d{4}-\d{2}-\d{2}(?!\s+\d{2}:\d{2}(?::\d{2})?)", text or ""):
            if match in seen:
                continue
            seen.add(match)
            try:
                result.append(datetime.strptime(f"{match} 23:59:59", "%Y-%m-%d %H:%M:%S"))
            except ValueError:
                continue
        return result

    @staticmethod
    def __to_log_text(value: Any, max_length: int = 1000) -> str:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        if len(text) > max_length:
            return f"{text[:max_length]}...（已截断，原始长度 {len(text)}）"
        return text

    def __get_records(self) -> List[Dict[str, Any]]:
        records = self.get_data("records") or []
        return records if isinstance(records, list) else []

    def __get_state_data(self) -> Dict[str, Any]:
        state = self.get_data("state") or {}
        return state if isinstance(state, dict) else {}

    @staticmethod
    def __result(status: str, message: str, success: bool = False) -> Dict[str, Any]:
        return {
            "success": success,
            "status": status,
            "message": message
        }

    @staticmethod
    def __status_text(status: str) -> str:
        return {
            "success": "购买成功",
            "failed": "购买失败",
            "auth_failed": "Cookie 失效",
            "config_error": "配置错误",
            "skipped": "未到时间"
        }.get(status or "", status or "未知")

    @staticmethod
    def __now_text() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def __safe_int(value: Any, default: int, min_value: Optional[int] = None) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = default
        if min_value is not None:
            number = max(number, min_value)
        return number
