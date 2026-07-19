import base64
import json
import random
import re
import threading
import time
from datetime import datetime, timezone
from html import unescape
from typing import Any, Dict, List, Optional, Tuple

import requests
from apscheduler.triggers.cron import CronTrigger

from app.log import logger
from app.plugins import _PluginBase
from app.schemas import NotificationType


class AuthFailedError(RuntimeError):
    """rousi.pro Token 失效或登录已过期。"""


class RousiCheckin(_PluginBase):
    plugin_name = "肉丝自动签到"
    plugin_desc = "rousi.pro JWT Token 自动签到、站内信增量推送与过期提醒"
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/signin.png"
    plugin_version = "1.0.3"
    plugin_author = "wuyaos"
    author_url = "https://github.com/wuyaos"
    plugin_config_prefix = "rousicheckin_"
    plugin_order = 36
    auth_level = 2

    BASE_URL = "https://rousi.pro"
    API_ME = f"{BASE_URL}/api/me"
    API_ATTENDANCE_STATS = f"{BASE_URL}/api/points/attendance/stats"
    API_ATTENDANCE = f"{BASE_URL}/api/points/attendance"
    API_MESSAGES = f"{BASE_URL}/api/messages"
    MAX_HISTORY = 100
    MAX_PUSH_MESSAGES = 5

    _enabled = False
    _notify = True
    _message_notify = True
    _token = ""
    _cron = "7 9 * * *"
    _expire_threshold_days = 5
    _random_delay_minutes = 3
    _onlyonce = False

    def init_plugin(self, config: dict = None):
        # 停止现有任务，避免重载时定时任务残留/丢失（参考 moviepilotupdatenotify）
        self.stop_service()
        if not hasattr(self, '_lock'):
            self._lock = threading.Lock()
        config = config or {}
        self._enabled = bool(config.get("enabled", False))
        self._notify = bool(config.get("notify", True))
        self._message_notify = bool(config.get("message_notify", True))
        self._token = self.__safe_str(config.get("token"), "")
        self._cron = self.__safe_str(config.get("cron"), "7 9 * * *")
        self._expire_threshold_days = self.__safe_int(config.get("expire_threshold_days"), 5, 0)
        self._random_delay_minutes = self.__safe_int(config.get("random_delay_minutes"), 3, 0)
        self._onlyonce = bool(config.get("onlyonce", False))
        logger.info(
            f"肉丝自动签到初始化完成：enabled={self._enabled}, notify={self._notify}, "
            f"message_notify={self._message_notify}, cron={repr(self._cron)}, "
            f"expire_threshold_days={self._expire_threshold_days}, random_delay_minutes={self._random_delay_minutes}"
        )
        if self._onlyonce:
            self._onlyonce = False
            cur = self.get_config() or {}
            cur.update({
                "enabled": self._enabled,
                "notify": self._notify,
                "message_notify": self._message_notify,
                "token": self._token,
                "cron": self._cron,
                "expire_threshold_days": self._expire_threshold_days,
                "random_delay_minutes": self._random_delay_minutes,
                "onlyonce": False
            })
            self.update_config(cur)
            logger.info("收到配置页立即运行请求，后台启动肉丝签到任务")
            threading.Thread(target=self.__signin, kwargs={"manual": True}, daemon=True).start()

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        return [{
            "path": "/RousiCheckin/run",
            "endpoint": self.run_once_api,
            "methods": ["POST"],
            "auth": "bear",
            "summary": "立即执行肉丝签到",
            "description": "按当前插件配置立即执行一次肉丝签到任务。"
        }]

    def get_service(self) -> List[Dict[str, Any]]:
        if not self._enabled:
            logger.info("肉丝自动签到定时服务未注册：插件未启用")
            return []
        if not self._cron:
            logger.warning("肉丝自动签到定时服务未注册：Cron 为空")
            return []
        try:
            trigger = CronTrigger.from_crontab(self._cron)
        except Exception as err:
            logger.warning(f"肉丝自动签到 Cron 配置无效：cron={repr(self._cron)}，error={err}")
            return []
        return [{
            "id": "RousiCheckin",
            "name": "肉丝自动签到服务",
            "trigger": trigger,
            "func": self.signin,
            "kwargs": {}
        }]

    def signin(self) -> Dict[str, Any]:
        return self.__signin(manual=False)

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [{
            "component": "VForm",
            "content": [
                {"component": "VAlert", "props": {"type": "info", "variant": "tonal", "class": "mb-3"}, "text": "前端手动触发 API：POST /RousiCheckin/run（bear 鉴权），保存后也可勾选立即运行一次。"},
                self.__form_card("mdi-cog-outline", "通用设置", "#E91E63", [
                    {"component": "VRow", "content": [
                        self.__form_col({"component": "VSwitch", "props": {"model": "enabled", "label": "启用插件", "color": "primary"}}, 3),
                        self.__form_col({"component": "VSwitch", "props": {"model": "notify", "label": "签到结果通知", "color": "info"}}, 3),
                        self.__form_col({"component": "VSwitch", "props": {"model": "message_notify", "label": "站内信增量推送", "color": "success"}}, 3),
                        self.__form_col({"component": "VSwitch", "props": {"model": "onlyonce", "label": "立即运行一次", "color": "warning"}}, 3)
                    ]}
                ]),
                self.__form_card("mdi-key-variant", "Token 设置", "#AD1457", [
                    {"component": "VRow", "content": [
                        self.__form_col({
                            "component": "VTextField",
                            "props": {
                                "model": "token",
                                "label": "rousi.pro JWT Token",
                                "type": "password",
                                "placeholder": "从浏览器 localStorage 手动复制 token",
                                "autocomplete": "new-password",
                                "clearable": True
                            }
                        }, 12)
                    ]}
                ]),
                self.__form_card("mdi-clock-outline", "调度提醒", "#8E24AA", [
                    {"component": "VRow", "content": [
                        self.__form_col({"component": "VCronField", "props": {"model": "cron", "label": "签到周期", "placeholder": "7 9 * * *", "hint": "默认每天09:07执行，避开整点"}}, 4),
                        self.__form_col({"component": "VTextField", "props": {"model": "random_delay_minutes", "label": "随机抖动(分钟)", "type": "number", "min": 0, "placeholder": "3"}}, 4),
                        self.__form_col({"component": "VTextField", "props": {"model": "expire_threshold_days", "label": "Token过期提醒阈值(天)", "type": "number", "min": 0, "placeholder": "5"}}, 4)
                    ]}
                ]),
                self.__form_card("mdi-information-outline", "使用说明", "#1976D2", [
                    {"component": "VList", "props": {"density": "comfortable", "lines": "two"}, "content": [
                        self.__list_item("mdi-login-variant", "Token 获取", "登录 rousi.pro 时建议勾选30天免登录，然后从浏览器 localStorage 复制 JWT Token 填入本插件。"),
                        self.__list_item("mdi-calendar-check", "签到逻辑", "定时触发后先读取 attendance stats 判断今日是否已签，已签则跳过 POST，未签才提交 fixed 模式签到。"),
                        self.__list_item("mdi-message-text-clock", "站内信推送", "首次运行只记录当前最大消息ID不推送；之后仅推送新增站内信，最多展示5条并汇总超出数量。"),
                        self.__list_item("mdi-shield-alert", "失效处理", "Token 过期或接口返回401时会当日通知一次、写入历史；插件保持启用并在下次定时周期自动重试，刷新 token 后无需手动重开。")
                    ]}
                ])
            ]
        }], {
            "enabled": False,
            "notify": True,
            "message_notify": True,
            "token": "",
            "cron": "7 9 * * *",
            "expire_threshold_days": 5,
            "random_delay_minutes": 3,
            "onlyonce": False
        }

    def get_page(self) -> List[dict]:
        try:
            token_status = self.__token_status(self._token)
            user_info = self.get_data("user_info") or {}
            last_run = self.get_data("last_run") or {}
            history = self.__get_history()
            status_meta = self.__token_status_meta(token_status)
            return [
                {"component": "VRow", "props": {"class": "mb-4"}, "content": [
                    self.__token_card(token_status, status_meta),
                    self.__user_card(user_info),
                    self.__last_run_card(last_run)
                ]},
                self.__history_card(history)
            ]
        except Exception as err:
            logger.error(f"肉丝签到详情页渲染失败：{err}")
            return [{
                "component": "VAlert",
                "props": {"type": "error", "variant": "tonal"},
                "text": f"详情页加载失败：{err}"
            }]

    def stop_service(self):
        logger.info("肉丝自动签到插件正在停止，调度任务将由框架清理")

    def run_once_api(self) -> Dict[str, Any]:
        if self._lock.locked():
            logger.warning("立即执行请求被忽略：已有肉丝签到任务正在执行")
            return {"success": False, "message": "已有肉丝签到任务正在执行"}
        logger.info("收到 API 立即执行请求，后台启动肉丝签到任务")
        threading.Thread(target=self.__signin, kwargs={"manual": True}, daemon=True).start()
        return {"success": True, "message": "任务已开始，完成后会写入历史记录并按配置发送通知"}

    def __signin(self, manual: bool = False) -> Dict[str, Any]:
        if not self._lock.acquire(blocking=False):
            logger.warning("肉丝签到任务启动失败：已有任务正在执行")
            result = self.__new_result(manual=manual)
            result.update({"status_code": "running", "status": "任务已在执行中", "message": "前次任务未完成，跳过本次触发"})
            self.__save_run_result(result)
            return result
        result = self.__new_result(manual=manual)
        try:
            token = (self._token or "").strip()
            if not token:
                result.update({"status_code": "failed", "status": "签到失败", "message": "缺少 rousi.pro JWT Token"})
                self.__save_run_result(result)
                if self._notify:
                    self.__send_signin_notification(result)
                return result

            if not manual and self._random_delay_minutes > 0:
                delay = random.randint(0, self._random_delay_minutes * 60)
                if delay > 0:
                    logger.info(f"肉丝签到定时任务随机抖动 {delay} 秒后执行")
                    time.sleep(delay)

            token_status = self.__token_status(token)
            logger.info(
                f"肉丝 Token 状态：valid_format={token_status.get('valid_format')}，"
                f"expired={token_status.get('expired')}，remaining_days={token_status.get('remaining_days')}"
            )
            self.__check_expire_reminder(token_status)
            if token_status.get("expired"):
                logger.warning("肉丝 Token 本地判定已过期，但仍将尝试 API 调用（禁用决策交由 API 实际返回 401）")

            session = requests.Session()
            session.headers.update({
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "User-Agent": "MoviePilot-RousiCheckin/1.0.0"
            })

            me = self.__request_json(session, "GET", self.API_ME)
            if self.__is_auth_failed(me):
                result.update({"message": self.__auth_message(me)})
                self.__handle_auth_failed(result.get("message"), result)
                return result
            if me.get("code") != 0:
                raise RuntimeError(me.get("message") or f"获取用户信息失败：{me}")
            user_info = self.__extract_user_info(me)
            self.save_data("user_info", user_info)
            logger.info(f"肉丝用户信息获取成功：username={user_info.get('username')}")

            stats = self.__request_json(session, "GET", self.API_ATTENDANCE_STATS)
            if self.__is_auth_failed(stats):
                result.update({"message": self.__auth_message(stats)})
                self.__handle_auth_failed(result.get("message"), result)
                return result
            if stats.get("code") != 0:
                raise RuntimeError(stats.get("message") or f"获取签到统计失败：{stats}")

            today = self.__today_str()
            stats_data = stats.get("data") or {}
            attended_dates = (stats_data.get("attended_dates") or []) if isinstance(stats_data, dict) else []
            current_streak = stats_data.get("current_streak") if isinstance(stats_data, dict) else None
            if today in attended_dates:
                result.update({
                    "status_code": "success_already",
                    "status": "今日已签",
                    "message": "今日已签到，跳过提交",
                    "current_streak": current_streak
                })
            else:
                attendance = self.__request_json(session, "POST", self.API_ATTENDANCE, json={"mode": "fixed"})
                if self.__is_auth_failed(attendance):
                    result.update({"message": self.__auth_message(attendance)})
                    self.__handle_auth_failed(result.get("message"), result)
                    return result
                if attendance.get("code") != 0:
                    raise RuntimeError(attendance.get("message") or f"签到失败：{attendance}")
                data = attendance.get("data") or {}
                current_streak = data.get("current_streak") if isinstance(data, dict) else None
                result.update({
                    "status_code": "success_new",
                    "status": "签到成功",
                    "message": "签到成功",
                    "current_streak": current_streak
                })

            new_message_count = 0
            if self._message_notify:
                messages_result = self.__fetch_messages(session)
                new_message_count = messages_result.get("new_count", 0)
                result["message"] = f"{result.get('message')}；新增站内信 {new_message_count} 条"
            result.update({
                "username": user_info.get("username"),
                "uploaded": user_info.get("uploaded"),
                "downloaded": user_info.get("downloaded"),
                "new_message_count": new_message_count,
                "token_remaining_days": token_status.get("remaining_days")
            })
            self.__save_run_result(result)
            if self._notify:
                self.__send_signin_notification(result)
            logger.info(f"肉丝签到任务结束：status={result.get('status_code')} username={user_info.get('username')} new_messages={new_message_count}")
            return result
        except AuthFailedError as err:
            result.update({"message": str(err)})
            return self.__handle_auth_failed(result.get("message"), result)
        except Exception as err:
            logger.error(f"肉丝签到任务异常：{err}")
            result.update({"status_code": "failed", "status": "签到失败", "message": str(err)})
            self.__save_run_result(result)
            if self._notify:
                self.__send_signin_notification(result)
            return result
        finally:
            self._lock.release()

    def __fetch_messages(self, session: requests.Session) -> Dict[str, Any]:
        body = self.__request_json(session, "GET", self.API_MESSAGES)
        if self.__is_auth_failed(body):
            raise AuthFailedError(self.__auth_message(body))
        if body.get("code") != 0:
            raise RuntimeError(body.get("message") or f"获取站内信失败：{body}")
        data = body.get("data") or {}
        messages = data.get("messages") or [] if isinstance(data, dict) else []
        ids = [self.__safe_int(item.get("id"), 0, 0) for item in messages if isinstance(item, dict)]
        max_id = max(ids) if ids else self.__safe_int(self.get_data("last_message_id"), 0, 0)
        initialized = bool(self.get_data("messages_initialized"))
        last_message_id = self.__safe_int(self.get_data("last_message_id"), 0, 0)
        if not initialized:
            self.save_data("messages_initialized", True)
            self.save_data("last_message_id", max_id)
            logger.info(f"肉丝站内信首次初始化：last_message_id={max_id}")
            return {"new_count": 0, "initialized": False}

        new_messages = []
        for item in messages:
            if not isinstance(item, dict):
                continue
            message_id = self.__safe_int(item.get("id"), 0, 0)
            if message_id > last_message_id:
                new_messages.append(item)
        new_messages.sort(key=lambda item: self.__safe_int(item.get("id"), 0, 0))
        if max_id > last_message_id:
            self.save_data("last_message_id", max_id)
        if new_messages and self._message_notify:
            self.__send_messages_notification(new_messages)
        return {"new_count": len(new_messages), "initialized": True}

    def __token_status(self, token: str) -> Dict[str, Any]:
        result = {
            "valid_format": False,
            "expired": False,
            "exp": None,
            "expire_time": "-",
            "remaining_days": None,
            "message": "未填写 Token"
        }
        token = (token or "").strip()
        if not token:
            return result
        try:
            parts = token.split(".")
            if len(parts) < 2:
                result["message"] = "Token 格式不正确"
                return result
            payload = parts[1]
            payload += "=" * (-len(payload) % 4)
            data = json.loads(base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8"))
            exp = data.get("exp")
            if exp is None:
                result["message"] = "Token 缺少 exp 字段"
                return result
            exp_int = int(exp)
            now = int(time.time())
            remaining_seconds = exp_int - now
            expire_dt = datetime.fromtimestamp(exp_int, tz=timezone.utc).astimezone()
            result.update({
                "valid_format": True,
                "expired": remaining_seconds <= 0,
                "exp": exp_int,
                "expire_time": expire_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "remaining_days": max(0, remaining_seconds // 86400),
                "message": "Token 已过期" if remaining_seconds <= 0 else "Token 有效"
            })
            return result
        except Exception as err:
            result["message"] = f"Token 解析失败：{err}"
            return result

    def __handle_auth_failed(self, message: str, result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        today = self.__today_str()
        record = result or self.__new_result(manual=False)
        record.update({"status_code": "auth_failed", "status": "Token失效", "message": message or "登录已过期，请重新登录"})
        try:
            self.__save_run_result(record)
        except Exception as err:
            logger.warning(f"肉丝认证失败历史写入失败：{err}")
        try:
            if self._notify and self.get_data("last_auth_failed_notify_date") != today:
                self.__safe_post_message(
                    mtype=NotificationType.Plugin,
                    title="【肉丝自动签到】Token 已失效",
                    text=(
                        f"肉丝签到认证失败：{record.get('message')}\n\n"
                        "插件保持启用，将在下次定时周期自动重试。请尽快登录 rousi.pro 勾选30天免登录刷新 token 并更新插件配置。"
                    )
                )
                self.save_data("last_auth_failed_notify_date", today)
        except Exception as err:
            logger.warning(f"肉丝认证失败通知处理失败：{err}")
        # 不再自动停用插件：Token 失效是临时状态，停用会导致 get_service 注销 cron，
        # 用户更新 token 后还需手动重开，且下一周期无法自动恢复。保留启用态让 cron 自动重试。
        logger.warning("肉丝 Token 认证失败，保留插件启用态，等待下次定时周期自动重试")
        return record

    def __safe_post_message(self, **kwargs):
        try:
            getattr(self, "post_message")(**kwargs)
        except Exception as err:
            logger.warning(f"肉丝通知发送失败：{err}")

    def __check_expire_reminder(self, token_status: Dict[str, Any]):
        if not self._notify or not token_status.get("valid_format") or token_status.get("expired"):
            return
        remaining_days = token_status.get("remaining_days")
        if remaining_days is None or remaining_days >= self._expire_threshold_days:
            return
        today = self.__today_str()
        if self.get_data("last_expire_notify_date") == today:
            return
        self.__safe_post_message(
            mtype=NotificationType.Plugin,
            title="【肉丝自动签到】Token 即将过期",
            text=(
                f"rousi.pro Token 剩余约 {remaining_days} 天，过期时间：{token_status.get('expire_time')}。\n\n"
                "请登录 rousi.pro 勾选30天免登录刷新 token，手动填入插件配置。"
            )
        )
        self.save_data("last_expire_notify_date", today)

    def __request_json(self, session: requests.Session, method: str, url: str, **kwargs) -> Dict[str, Any]:
        response = session.request(method, url, timeout=20, **kwargs)
        try:
            body = response.json()
        except ValueError:
            body = {"code": -1, "message": f"非 JSON 响应 HTTP {response.status_code}: {(response.text or '')[:120]}"}
        if isinstance(body, dict):
            body["_http"] = response.status_code
            return body
        return {"code": -1, "message": f"响应格式异常 HTTP {response.status_code}", "_http": response.status_code}

    @staticmethod
    def __is_auth_failed(body: Dict[str, Any]) -> bool:
        # 仅 HTTP 401 视为认证失败；code==100 可能是限流/维护等临时故障，
        # 需同时伴随 401 才算，避免把临时错误误判为 Token 失效。
        return body.get("_http") == 401

    @staticmethod
    def __auth_message(body: Dict[str, Any]) -> str:
        return str(body.get("message") or "登录已过期，请重新登录")

    @staticmethod
    def __extract_user_info(body: Dict[str, Any]) -> Dict[str, Any]:
        data = body.get("data") or {}
        stats = data.get("stats") or {} if isinstance(data, dict) else {}
        return {
            "username": stats.get("username") or "-",
            "uploaded": stats.get("uploaded") or "-",
            "downloaded": stats.get("downloaded") or "-",
            "updated_at": RousiCheckin.__local_time_text()
        }

    def __save_run_result(self, result: Dict[str, Any]):
        result.setdefault("date", self.__today_str())
        result.setdefault("time", self.__local_time_text())
        self.save_data("last_run", result)
        self.__save_history_record(result)

    def __save_history_record(self, record: Dict[str, Any]):
        history = self.__get_history()
        record_date = str(record.get("date") or self.__today_str())
        existing_index = -1
        for index, item in enumerate(history):
            if str(item.get("date") or "") == record_date:
                existing_index = index
                break
        new_success = record.get("status_code") in ("success_new", "success_already")
        if existing_index >= 0:
            old_success = history[existing_index].get("status_code") in ("success_new", "success_already")
            if new_success or not old_success:
                history[existing_index] = record.copy()
        else:
            history.append(record.copy())
        history = sorted(history, key=lambda item: str(item.get("time") or ""), reverse=True)[:self.MAX_HISTORY]
        self.save_data("history", history)

    def __get_history(self) -> List[Dict[str, Any]]:
        history = self.get_data("history") or []
        return history if isinstance(history, list) else []

    def __send_signin_notification(self, result: Dict[str, Any]):
        status = result.get("status") or "-"
        text = (
            f"执行时间：{result.get('time')}\n"
            f"状态：{status}\n"
            f"用户：{result.get('username') or '-'}\n"
            f"连续天数：{result.get('current_streak') if result.get('current_streak') not in (None, '') else '-'}\n"
            f"新增站内信：{result.get('new_message_count', 0)} 条\n"
            f"说明：{result.get('message') or '-'}"
        )
        self.__safe_post_message(mtype=NotificationType.Plugin, title="【肉丝自动签到】", text=text)

    def __send_messages_notification(self, messages: List[Dict[str, Any]]):
        lines = []
        for item in messages[:self.MAX_PUSH_MESSAGES]:
            title = self.__clean_text(item.get("title"), 60) or "无标题"
            content = self.__clean_text(item.get("content"), 80) or "无内容"
            lines.append(f"• {title}\n  {content}")
        if len(messages) > self.MAX_PUSH_MESSAGES:
            lines.append(f"其余 {len(messages) - self.MAX_PUSH_MESSAGES} 条请到 rousi.pro 查看")
        self.__safe_post_message(
            mtype=NotificationType.Plugin,
            title=f"【肉丝站内信】新增 {len(messages)} 条",
            text="\n\n".join(lines)
        )

    @staticmethod
    def __clean_text(value: Any, limit: int) -> str:
        text = unescape(re.sub(r"<[^>]+>", "", str(value or "")))
        text = " ".join(text.split())
        if len(text) > limit:
            return text[:limit] + "..."
        return text

    @staticmethod
    def __today_str() -> str:
        return datetime.now().strftime("%Y-%m-%d")

    @staticmethod
    def __local_time_text() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def __new_result(manual: bool = False) -> Dict[str, Any]:
        now = RousiCheckin.__local_time_text()
        return {
            "date": now[:10],
            "time": now,
            "manual": manual,
            "status_code": "running",
            "status": "执行中",
            "current_streak": None,
            "new_message_count": 0,
            "message": ""
        }

    @staticmethod
    def __safe_str(value: Any, default: str = "") -> str:
        if isinstance(value, str):
            return value.strip() or default
        if value is None:
            return default
        return str(value).strip() or default

    @staticmethod
    def __safe_int(value: Any, default: int = 0, min_value: Optional[int] = None) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = default
        if min_value is not None:
            number = max(number, min_value)
        return number

    @staticmethod
    def __form_card(icon: str, title: str, color: str, content: List[dict]) -> Dict[str, Any]:
        return {
            "component": "VCard",
            "props": {"variant": "outlined", "class": "mt-3"},
            "content": [
                {"component": "VCardTitle", "props": {"class": "d-flex align-center"}, "content": [
                    {"component": "VIcon", "props": {"style": f"color: {color};", "class": "mr-2"}, "text": icon},
                    {"component": "span", "text": title}
                ]},
                {"component": "VDivider"},
                {"component": "VCardText", "content": content}
            ]
        }

    @staticmethod
    def __form_col(component: Dict[str, Any], md: int) -> Dict[str, Any]:
        return {"component": "VCol", "props": {"cols": 12, "md": md}, "content": [component]}

    @staticmethod
    def __list_item(icon: str, title: str, subtitle: str) -> Dict[str, Any]:
        return {"component": "VListItem", "content": [
            {"component": "template", "props": {"v-slot:prepend": ""}, "content": [{"component": "VIcon", "props": {"color": "primary"}, "text": icon}]},
            {"component": "VListItemTitle", "text": title},
            {"component": "VListItemSubtitle", "text": subtitle}
        ]}

    @staticmethod
    def __token_status_meta(token_status: Dict[str, Any]) -> Dict[str, str]:
        if not token_status.get("valid_format"):
            return {"label": "未配置/格式错误", "color": "#9E9E9E", "icon": "mdi-alert-circle"}
        if token_status.get("expired"):
            return {"label": "已过期", "color": "#F44336", "icon": "mdi-close-circle"}
        remaining = token_status.get("remaining_days")
        if remaining is not None and remaining < 5:
            return {"label": "即将过期", "color": "#FB8C00", "icon": "mdi-clock-alert"}
        return {"label": "有效", "color": "#4CAF50", "icon": "mdi-check-circle"}

    def __token_card(self, token_status: Dict[str, Any], meta: Dict[str, str]) -> Dict[str, Any]:
        return {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [{
            "component": "VCard", "props": {"variant": "outlined", "class": "h-100"}, "content": [
                {"component": "VCardTitle", "props": {"class": "d-flex align-center"}, "content": [
                    {"component": "VIcon", "props": {"style": "color: #E91E63;", "class": "mr-2"}, "text": "mdi-key-variant"},
                    {"component": "span", "text": "Token 状态"},
                    {"component": "VSpacer"},
                    {"component": "VChip", "props": {"style": f"background-color: {meta['color']}; color: white;", "size": "small"}, "content": [
                        {"component": "VIcon", "props": {"start": True, "size": "small", "style": "color: white;"}, "text": meta["icon"]},
                        {"component": "span", "text": meta["label"]}
                    ]}
                ]},
                {"component": "VDivider"},
                {"component": "VCardText", "content": [
                    self.__info_line("剩余天数", token_status.get("remaining_days") if token_status.get("remaining_days") is not None else "-"),
                    self.__info_line("过期时间", token_status.get("expire_time") or "-"),
                    self.__info_line("说明", token_status.get("message") or "-")
                ]}
            ]
        }]}

    def __user_card(self, user_info: Dict[str, Any]) -> Dict[str, Any]:
        return {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [{
            "component": "VCard", "props": {"variant": "outlined", "class": "h-100"}, "content": [
                {"component": "VCardTitle", "props": {"class": "d-flex align-center"}, "content": [
                    {"component": "VIcon", "props": {"style": "color: #AD1457;", "class": "mr-2"}, "text": "mdi-account-circle"},
                    {"component": "span", "text": "用户信息"}
                ]},
                {"component": "VDivider"},
                {"component": "VCardText", "content": [
                    self.__info_line("用户名", user_info.get("username") or "-"),
                    self.__info_line("上传量", user_info.get("uploaded") or "-"),
                    self.__info_line("下载量", user_info.get("downloaded") or "-"),
                    self.__info_line("更新时间", user_info.get("updated_at") or "-")
                ]}
            ]
        }]}

    def __last_run_card(self, last_run: Dict[str, Any]) -> Dict[str, Any]:
        return {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [{
            "component": "VCard", "props": {"variant": "outlined", "class": "h-100"}, "content": [
                {"component": "VCardTitle", "props": {"class": "d-flex align-center"}, "content": [
                    {"component": "VIcon", "props": {"style": "color: #8E24AA;", "class": "mr-2"}, "text": "mdi-history"},
                    {"component": "span", "text": "最近运行"}
                ]},
                {"component": "VDivider"},
                {"component": "VCardText", "content": [
                    self.__info_line("运行时间", last_run.get("time") or "-"),
                    self.__info_line("状态", last_run.get("status") or "-"),
                    self.__info_line("连续天数", last_run.get("current_streak") if last_run.get("current_streak") not in (None, "") else "-"),
                    self.__info_line("新消息数", last_run.get("new_message_count", 0)),
                    self.__info_line("说明", last_run.get("message") or "-")
                ]}
            ]
        }]}

    @staticmethod
    def __info_line(label: str, value: Any) -> Dict[str, Any]:
        return {"component": "div", "props": {"class": "d-flex justify-space-between py-1"}, "content": [
            {"component": "span", "props": {"class": "text-medium-emphasis"}, "text": label},
            {"component": "span", "props": {"class": "font-weight-medium text-right ml-2"}, "text": str(value)}
        ]}

    def __history_card(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        rows = []
        for record in history:
            meta = self.__history_status_meta(record.get("status_code"))
            rows.append({"component": "tr", "content": [
                {"component": "td", "props": {"class": "text-caption text-no-wrap"}, "text": record.get("date") or "-"},
                {"component": "td", "props": {"class": "text-caption text-no-wrap"}, "text": record.get("time") or "-"},
                {"component": "td", "content": [{"component": "VChip", "props": {"style": f"background-color: {meta['color']}; color: white;", "size": "small"}, "content": [
                    {"component": "VIcon", "props": {"start": True, "size": "small", "style": "color: white;"}, "text": meta["icon"]},
                    {"component": "span", "text": meta["label"]}
                ]}]},
                {"component": "td", "props": {"class": "text-caption"}, "text": record.get("current_streak") if record.get("current_streak") not in (None, "") else "-"},
                {"component": "td", "props": {"class": "text-caption"}, "text": record.get("new_message_count", 0)},
                {"component": "td", "props": {"class": "text-caption", "style": "white-space: normal; min-width: 220px;"}, "text": record.get("message") or "-"}
            ]})
        table_content = [{"component": "VAlert", "props": {"type": "info", "variant": "tonal", "class": "ma-2"}, "text": "暂无签到历史"}] if not rows else [{
            "component": "VResponsive", "content": [{
                "component": "VTable", "props": {"hover": True, "density": "comfortable"}, "content": [
                    {"component": "thead", "content": [{"component": "tr", "content": [
                        {"component": "th", "text": "日期"},
                        {"component": "th", "text": "时间"},
                        {"component": "th", "text": "状态"},
                        {"component": "th", "text": "连续天数"},
                        {"component": "th", "text": "新消息数"},
                        {"component": "th", "text": "说明"}
                    ]}]},
                    {"component": "tbody", "content": rows}
                ]
            }]
        }]
        return {"component": "VCard", "props": {"variant": "outlined", "class": "mb-4"}, "content": [
            {"component": "VCardTitle", "props": {"class": "d-flex align-center"}, "content": [
                {"component": "VIcon", "props": {"style": "color: #E91E63;", "class": "mr-2"}, "text": "mdi-table-clock"},
                {"component": "span", "props": {"class": "text-h6 font-weight-bold"}, "text": "签到历史"}
            ]},
            {"component": "VDivider"},
            {"component": "VCardText", "props": {"class": "pa-0 pa-md-2"}, "content": table_content}
        ]}

    @staticmethod
    def __history_status_meta(status_code: Any) -> Dict[str, str]:
        metas = {
            "success_new": {"label": "签到成功", "color": "#4CAF50", "icon": "mdi-check-circle"},
            "success_already": {"label": "今日已签", "color": "#2196F3", "icon": "mdi-check-decagram"},
            "auth_failed": {"label": "Token失效", "color": "#F44336", "icon": "mdi-close-circle"},
            "failed": {"label": "签到失败", "color": "#FB8C00", "icon": "mdi-alert-circle"},
            "running": {"label": "执行中", "color": "#9E9E9E", "icon": "mdi-progress-clock"}
        }
        return metas.get(status_code, {"label": "未知", "color": "#9E9E9E", "icon": "mdi-help-circle"})
