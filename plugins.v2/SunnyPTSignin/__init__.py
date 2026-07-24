# input: SunnyPT 用户名/密码、Cron 调度配置
# output: 自动登录获取 token 并签到，记录历史与通知
# pos: V2 站点任务插件，独立于 autoptcheckin（SunnyPT 用用户名密码登录换 token，非 cookie 鉴权）
import base64
import json
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
from apscheduler.triggers.cron import CronTrigger

from app.core.event import Event, eventmanager
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import NotificationType
from app.schemas.types import EventType


class SunnyPTSignin(_PluginBase):
    plugin_name = "SunnyPT 自动签到"
    plugin_desc = "通过用户名密码登录 SunnyPT 获取 token 自动签到，无需 Cookie。"
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/signin.png"
    plugin_version = "1.0.0"
    plugin_author = "wuyaos"
    author_url = "https://github.com/wuyaos/MoviePilot-Plugins"
    plugin_config_prefix = "sunnyptsignin_"
    plugin_order = 31
    auth_level = 1

    # 接口常量
    LOGIN_URL = "https://api.sunnypt.top/login"
    SIGNIN_URL = "https://api.sunnypt.top/api/v1/attendance/check-in"
    STATUS_URL = "https://api.sunnypt.top/api/v1/attendance/status"
    REFERER = "https://sunnypt.top/user/attendance"
    MAX_HISTORY = 30
    # token 提前 1 小时刷新，避免临界过期
    TOKEN_REFRESH_AHEAD = 3600

    _enabled = False
    _username = ""
    _password = ""
    _cron = "10 9 * * *"
    _notify = True
    _run_once = False
    _lock = threading.Lock()

    def init_plugin(self, config: dict = None):
        config = config or {}
        self._enabled = bool(config.get("enabled"))
        self._username = (config.get("username") or "").strip()
        self._password = config.get("password") or ""
        self._cron = self.__normalize_cron(config.get("cron"))
        self._notify = bool(config.get("notify", True))
        self._run_once = bool(config.get("run_once", False))

        if self._run_once and self._enabled and self._username and self._password:
            logger.info("SunnyPT 自动签到：立即运行一次")
            threading.Thread(target=self.__signin_task, daemon=True).start()
            # 自动关闭立即运行开关
            self._run_once = False
            self.__update_config()

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return [
            {
                "cmd": "sunnypt_signin",
                "title": "SunnyPT 签到",
                "desc": "立即执行一次 SunnyPT 签到",
                "category": "签到",
            }
        ]

    @eventmanager.register(EventType.PluginAction)
    def sunnypt_signin_action(self, event: Event):
        """
        响应 "sunnypt_signin" 命令，立即执行签到。
        """
        event_data = event.event_data or {}
        if event_data.get("action") != "sunnypt_signin":
            return
        if not self._enabled:
            logger.warning("SunnyPT 签到命令被忽略：插件未启用")
            return
        if self._lock.locked():
            logger.warning("SunnyPT 签到命令被忽略：已有任务正在执行")
            return
        logger.info("收到 SunnyPT 签到命令，后台启动签到任务")
        threading.Thread(target=self.__signin_task, daemon=True).start()

    def get_service(self) -> List[Dict[str, Any]]:
        if not self._enabled:
            return []
        if not self._cron:
            logger.warning("SunnyPT 签到定时服务未注册：Cron 为空")
            return []
        try:
            trigger = CronTrigger.from_crontab(self._cron)
        except Exception as err:
            logger.warning(f"SunnyPT 签到 Cron 配置无效：cron={repr(self._cron)}，error={err}")
            return []
        return [
            {
                "id": "SunnyPTSignin",
                "name": "SunnyPT 自动签到",
                "trigger": "cron",
                "func": self.__signin_task,
                "kwargs": {
                    "minute": str(trigger.fields[6]),
                    "hour": str(trigger.fields[5]),
                    "day": str(trigger.fields[2]),
                    "month": str(trigger.fields[1]),
                    "day_of_week": str(trigger.fields[4]),
                },
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
                                    {"component": "VSwitch", "props": {"model": "enabled", "label": "启用插件"}}
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {"component": "VSwitch", "props": {"model": "notify", "label": "发送通知"}}
                                ],
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
                                            "hint": "保存配置后执行，并自动关闭",
                                        },
                                    }
                                ],
                            },
                        ],
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
                                            "model": "username",
                                            "label": "用户名",
                                            "placeholder": "SunnyPT 用户名",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "password",
                                            "label": "密码",
                                            "type": "password",
                                            "placeholder": "SunnyPT 密码",
                                            "autocomplete": "new-password",
                                        },
                                    }
                                ],
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
                                            "placeholder": "10 9 * * *",
                                            "hint": "5位 Cron 表达式，例如 10 9 * * *",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VAlert",
                        "props": {
                            "type": "info",
                            "variant": "tonal",
                            "text": "SunnyPT 使用用户名密码登录获取 token 签到，token 缓存复用（24h 内无需重复登录）。与 autoptcheckin 的 cookie 鉴权体系独立。",
                        },
                    },
                ],
            }
        ], {
            "enabled": self._enabled,
            "username": self._username,
            "password": self._password,
            "cron": self._cron,
            "notify": self._notify,
            "run_once": False,
        }

    def get_page(self) -> List[dict]:
        records = self.__get_records()
        today = datetime.now().strftime("%Y-%m-%d")
        today_records = [r for r in records if r.get("date") == today]
        today_success = any(r.get("status") == "success" for r in today_records)
        today_status = "今日已签到" if today_success else ("今日签到失败" if today_records else "今日未签到")
        return [
            {
                "component": "VCard",
                "props": {"variant": "tonal", "class": "mb-4"},
                "content": [
                    {"component": "VCardTitle", "text": "SunnyPT 签到状态"},
                    {
                        "component": "VCardText",
                        "content": [
                            {
                                "component": "VRow",
                                "content": [
                                    self.__info_col("今日状态", today_status),
                                    self.__info_col("历史记录", str(len(records))),
                                    self.__info_col("执行周期", self._cron or "未配置"),
                                ],
                            }
                        ],
                    },
                ],
            },
            {
                "component": "VDataTable",
                "props": {
                    "headers": [
                        {"title": "日期", "key": "date"},
                        {"title": "时间", "key": "time"},
                        {"title": "状态", "key": "status_text"},
                        {"title": "连续签到", "key": "days"},
                        {"title": "累计签到", "key": "total_days"},
                        {"title": "魔力值", "key": "points"},
                        {"title": "消息", "key": "message"},
                    ],
                    "items": records,
                    "items-per-page": 10,
                },
            },
        ]

    @staticmethod
    def __info_col(label: str, value: Any) -> dict:
        return {
            "component": "VCol",
            "props": {"cols": 12, "md": 4},
            "content": [
                {
                    "component": "div",
                    "props": {"class": "text-caption text-medium-emphasis"},
                    "text": label,
                },
                {
                    "component": "div",
                    "props": {"class": "text-h6"},
                    "text": str(value) if value is not None else "-",
                },
            ],
        }

    def stop_service(self):
        pass

    # ===================== 核心签到逻辑 =====================

    def __signin_task(self):
        if not self._enabled:
            return
        if not self._username or not self._password:
            logger.error("SunnyPT 签到失败：未配置用户名或密码")
            return
        with self._lock:
            logger.info("开始执行 SunnyPT 签到任务")
            try:
                token = self.__get_token()
                if not token:
                    msg = "登录失败，无法获取 token"
                    self.__save_record("fail", msg)
                    self.__notify("SunnyPT 签到失败", msg)
                    return
                ok, msg, data = self.__do_signin(token)
                # token 失效则重新登录重试一次
                if not ok and "未登录" in msg:
                    logger.info("SunnyPT token 失效，重新登录后重试一次")
                    token = self.__get_token(force_refresh=True)
                    if token:
                        ok, msg, data = self.__do_signin(token)
                status = "success" if ok else "fail"
                self.__save_record(status, msg, data)
                title = "SunnyPT 签到成功" if ok else "SunnyPT 签到失败"
                self.__notify(title, msg)
            except Exception as e:
                logger.error(f"SunnyPT 签任务异常：{e}", exc_info=True)
                self.__save_record("fail", f"任务异常：{e}")
                self.__notify("SunnyPT 签到失败", f"任务异常：{e}")

    def __get_token(self, force_refresh: bool = False) -> Optional[str]:
        """
        获取 token：优先用缓存（未过期），否则登录拿新 token 并缓存。
        """
        cache = self.get_data("token_cache") or {}
        token = cache.get("token") if isinstance(cache, dict) else ""
        exp = cache.get("exp") if isinstance(cache, dict) else 0
        now = int(time.time())
        if not force_refresh and token and exp and now < exp - self.TOKEN_REFRESH_AHEAD:
            logger.info(f"SunnyPT token 缓存有效，距过期 {exp - now} 秒，复用")
            return token
        logger.info("SunnyPT token 缓存不存在或已过期，开始登录")
        new_token, new_exp = self.__login()
        if not new_token:
            logger.error("SunnyPT 登录失败，未获取到 token")
            return None
        self.save_data("token_cache", {"token": new_token, "exp": new_exp, "username": self._username})
        logger.info(f"SunnyPT 登录成功，token 已缓存，有效期至 {datetime.fromtimestamp(new_exp)}")
        return new_token

    def __login(self) -> Tuple[Optional[str], int]:
        """
        登录 SunnyPT，返回 (token, exp)。
        """
        try:
            res = requests.post(
                self.LOGIN_URL,
                json={"username": self._username, "password": self._password},
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0",
                    "Referer": self.REFERER,
                },
                timeout=15,
            )
            if res.status_code != 200:
                logger.error(f"SunnyPT 登录失败：HTTP {res.status_code} {res.text[:200]}")
                return None, 0
            ret = res.json()
        except Exception as e:
            logger.error(f"SunnyPT 登录请求异常：{e}")
            return None, 0
        code = ret.get("code")
        msg = ret.get("msg", "") or ""
        if code != 0:
            logger.error(f"SunnyPT 登录失败：code={code} msg={msg}")
            return None, 0
        data = ret.get("data") or {}
        token = data.get("token") or ""
        if not token:
            logger.error(f"SunnyPT 登录成功但未返回 token：{ret}")
            return None, 0
        exp = self.__decode_jwt_exp(token) or (int(time.time()) + 86400)
        return token, exp

    def __do_signin(self, token: str) -> Tuple[bool, str, dict]:
        """
        执行签到，返回 (是否成功, 消息, 附加数据)。
        """
        try:
            res = requests.post(
                self.SIGNIN_URL,
                json={},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0",
                    "Referer": self.REFERER,
                },
                timeout=15,
            )
            if res.status_code != 200:
                logger.error(f"SunnyPT 签到失败：HTTP {res.status_code} {res.text[:200]}")
                return False, f"HTTP {res.status_code}", {}
            ret = res.json()
        except Exception as e:
            logger.error(f"SunnyPT 签到请求异常：{e}")
            return False, f"请求异常：{e}", {}
        code = ret.get("code")
        msg = ret.get("msg", "") or ""
        data = ret.get("data") or {}
        if code == 0:
            logger.info(f"SunnyPT 签到成功：{msg}")
            status_data = self.__fetch_status(token)
            return True, msg or "签到成功", status_data or data
        if code == 400001:
            logger.info(f"SunnyPT 今日已签到：{msg}")
            status_data = self.__fetch_status(token)
            return True, "今日已签到", status_data or data
        if code == 400000 or "未登录" in msg:
            logger.warning(f"SunnyPT token 失效：code={code} msg={msg}")
            return False, "未登录，token 已失效", data
        logger.error(f"SunnyPT 签到失败：code={code} msg={msg}")
        return False, msg or f"签到失败 code={code}", data

    def __fetch_status(self, token: str) -> dict:
        """
        查询签到状态（连续天数、累计天数、魔力值），用于丰富历史记录。
        """
        try:
            res = requests.get(
                self.STATUS_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0",
                    "Referer": self.REFERER,
                },
                timeout=15,
            )
            if res.status_code != 200:
                return {}
            ret = res.json()
            if ret.get("code") == 0:
                return ret.get("data") or {}
        except Exception as e:
            logger.warning(f"SunnyPT 查询签到状态异常：{e}")
        return {}

    @staticmethod
    def __decode_jwt_exp(token: str) -> int:
        """
        解码 JWT payload 取 exp 字段。
        """
        try:
            parts = token.split(".")
            if len(parts) < 2:
                return 0
            payload = parts[1]
            payload += "=" * (-len(payload) % 4)
            data = json.loads(base64.urlsafe_b64decode(payload))
            return int(data.get("exp") or 0)
        except Exception:
            return 0

    # ===================== 历史记录与通知 =====================

    def __save_record(self, status: str, message: str, data: Optional[dict] = None):
        data = data or {}
        now = datetime.now()
        record = {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "status": status,
            "status_text": "签到成功" if status == "success" else "签到失败",
            "days": data.get("days"),
            "total_days": data.get("total_days"),
            "points": data.get("points"),
            "makeup_cards": data.get("makeup_cards"),
            "message": message,
        }
        records = self.__get_records()
        records.insert(0, record)
        self.save_data("records", records[: self.MAX_HISTORY])
        logger.info(f"SunnyPT 签到历史已保存：{record}")

    def __get_records(self) -> List[Dict[str, Any]]:
        records = self.get_data("records") or []
        return records if isinstance(records, list) else []

    def __notify(self, title: str, text: str):
        if not self._notify:
            return
        self.post_message(mtype=NotificationType.Plugin, title=title, text=text)

    # ===================== 工具方法 =====================

    def __update_config(self):
        self.update_config(
            {
                "enabled": self._enabled,
                "username": self._username,
                "password": self._password,
                "cron": self._cron,
                "notify": self._notify,
                "run_once": self._run_once,
            }
        )

    @staticmethod
    def __normalize_cron(cron: str) -> str:
        cron = (cron or "").strip()
        if not cron:
            return "10 9 * * *"
        parts = cron.split()
        if len(parts) == 5:
            return cron
        logger.warning(f"SunnyPT Cron 非标准 5 位，使用默认：{cron}")
        return "10 9 * * *"
