import random
import re
import threading
import time
from datetime import datetime
from html import unescape
from typing import Any, Dict, List, Optional, Tuple

from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import NotificationType

from .client import PeerGoAuthError, PeerGoClient, PeerGoError
from .ui import build_form, build_page


class RousiCheckin(_PluginBase):
    plugin_name = "肉丝自动签到"
    plugin_desc = "rousi.pro（PeerGo）账号登录、Session Cookie 自动续期、签到与站内消息推送"
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/signin.png"
    plugin_version = "1.1.0"
    plugin_author = "wuyaos"
    author_url = "https://github.com/wuyaos"
    plugin_config_prefix = "rousicheckin_"
    plugin_order = 36
    auth_level = 2

    MAX_HISTORY = 100
    MAX_PUSH_MESSAGES = 5
    MAX_NOTIFICATION_PAGES = 5
    NOTIFICATION_PAGE_SIZE = 20
    MAX_SEEN_NOTIFICATIONS = 500

    _enabled = False
    _notify = True
    _message_notify = True
    _username = ""
    _password = ""
    _cookie = ""
    _cron = "7 9 * * *"
    _random_delay_minutes = 3
    _onlyonce = False

    def init_plugin(self, config: dict = None):
        if not hasattr(self, "_lock"):
            self._lock = threading.Lock()
        config = config or {}
        self._enabled = bool(config.get("enabled", False))
        self._notify = bool(config.get("notify", True))
        self._message_notify = bool(config.get("message_notify", True))
        self._username = self.__safe_str(config.get("username"))
        self._password = self.__safe_str(config.get("password"))
        self._cookie = PeerGoClient.normalize_cookie(self.__safe_str(config.get("cookie")))
        self._cron = self.__safe_str(config.get("cron"), "7 9 * * *")
        self._random_delay_minutes = self.__safe_int(config.get("random_delay_minutes"), 3, 0)
        self._onlyonce = bool(config.get("onlyonce", False))

        logger.info(
            f"肉丝自动签到初始化完成：enabled={self._enabled}，notify={self._notify}，"
            f"message_notify={self._message_notify}，cron={self._cron!r}，"
            f"username_configured={bool(self._username)}，password_configured={bool(self._password)}，"
            f"cookie_configured={bool(self._cookie)}，random_delay_minutes={self._random_delay_minutes}"
        )

        if "token" in config or "expire_threshold_days" in config:
            self.update_config(self.__current_config(onlyonce=False))
            logger.info("已移除旧版 JWT Token 配置，迁移为 PeerGo Session 登录配置")

        if self._onlyonce:
            self._onlyonce = False
            self.update_config(self.__current_config(onlyonce=False))
            logger.info("收到配置页立即运行请求，后台启动肉丝签到任务")
            threading.Thread(target=self.__signin, kwargs={"manual": True}, daemon=True).start()

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        return [{
            "path": "/run",
            "endpoint": self.run_once_api,
            "methods": ["POST"],
            "auth": "bear",
            "summary": "立即执行肉丝签到",
            "description": "按当前插件配置立即执行一次肉丝签到任务。",
        }]

    def get_service(self) -> List[Dict[str, Any]]:
        if not self._enabled:
            logger.info("肉丝自动签到定时服务未注册：插件未启用")
            return []
        if not self._cron:
            logger.warning("肉丝自动签到定时服务未注册：Cron 为空")
            return []
        try:
            trigger = CronTrigger.from_crontab(self._cron, timezone=settings.TZ)
        except Exception as error:
            logger.warning(f"肉丝自动签到 Cron 配置无效：cron={self._cron!r}，error={error}")
            return []
        return [{
            "id": "RousiCheckin",
            "name": "肉丝自动签到服务",
            "trigger": trigger,
            "func": self.scheduled_run,
            "kwargs": {},
        }]

    def scheduled_run(self) -> Dict[str, Any]:
        return self.signin()

    def signin(self) -> Dict[str, Any]:
        return self.__signin(manual=False)

    @staticmethod
    def get_form() -> Tuple[List[dict], Dict[str, Any]]:
        return build_form()

    def get_page(self) -> List[dict]:
        try:
            return build_page(
                self.get_data("auth_state") or {},
                self.get_data("user_info") or {},
                self.get_data("last_run") or {},
                self.__get_history(),
            )
        except Exception as error:
            logger.error(f"肉丝签到详情页渲染失败：{error}")
            return [{
                "component": "VAlert",
                "props": {"type": "error", "variant": "tonal"},
                "text": f"详情页加载失败：{error}",
            }]

    def stop_service(self):
        logger.info("肉丝自动签到插件正在停止，调度任务将由框架清理")

    def run_once_api(self) -> Dict[str, Any]:
        if self._lock.locked():
            logger.warning("立即执行请求被忽略：已有肉丝签到任务正在执行")
            return {"success": False, "message": "已有肉丝签到任务正在执行"}
        logger.info("收到 API 立即执行请求，后台启动肉丝签到任务")
        threading.Thread(target=self.__signin, kwargs={"manual": True}, daemon=True).start()
        return {"success": True, "message": "任务已开始，完成后会写入签到历史"}

    def __signin(self, manual: bool = False) -> Dict[str, Any]:
        if not self._lock.acquire(blocking=False):
            logger.warning("肉丝签到任务启动失败：已有任务正在执行")
            result = self.__new_result(manual)
            result.update({
                "status_code": "running",
                "status": "任务已在执行中",
                "message": "前次任务未完成，跳过本次触发",
            })
            self.__save_run_result(result)
            return result

        result = self.__new_result(manual)
        try:
            if not self._cookie and not (self._username and self._password):
                raise PeerGoAuthError("请至少配置 Cookie，或同时配置账号和密码")

            if not manual and self._random_delay_minutes > 0:
                delay = random.randint(0, self._random_delay_minutes * 60)
                if delay:
                    logger.info(f"肉丝签到定时任务随机抖动 {delay} 秒后执行")
                    time.sleep(delay)

            client = PeerGoClient(cookie=self._cookie)
            session_info, cookie, refreshed = client.ensure_session(self._username, self._password)
            username = self.__safe_str((session_info.get("user") or {}).get("username"), self._username or "-")
            auth_state = {
                "status": "refreshed" if refreshed else "valid",
                "username": username,
                "expires_at": self.__format_time(session_info.get("expires_at")),
                "updated_at": self.__local_time_text(),
                "message": "Cookie 失效后已使用账号密码重新登录" if refreshed else "Cookie Session 有效",
            }
            self.save_data("auth_state", auth_state)
            if refreshed and cookie:
                self.__persist_cookie(cookie)
                logger.info(f"肉丝 Session Cookie 已自动刷新并回写插件配置：username={username}")
            else:
                logger.info(f"肉丝 Session Cookie 验证成功：username={username}")

            user_info = self.__load_user_info(client, session_info)
            self.save_data("user_info", user_info)
            logger.info(f"肉丝用户信息获取成功：username={username}")

            overview = client.get_attendance()
            current_streak = overview.get("current_streak")
            if overview.get("claimed_today"):
                today_record = overview.get("today_record") or {}
                reward = today_record.get("total_reward")
                message = "今日已签到，跳过提交"
                if reward not in (None, ""):
                    message += f"；今日奖励 {reward} 魔力值"
                result.update({
                    "status_code": "success_already",
                    "status": "今日已签",
                    "message": message,
                    "current_streak": current_streak,
                })
            else:
                attendance_settings = ((overview.get("policy") or {}).get("settings") or {})
                if attendance_settings and not attendance_settings.get("enabled", False):
                    raise PeerGoError("站点签到活动当前未开放")
                if attendance_settings.get("fixed_enabled", True):
                    attendance_mode = "fixed"
                elif attendance_settings.get("random_enabled"):
                    attendance_mode = "random"
                else:
                    raise PeerGoError("站点当前没有可用的签到奖励模式")
                client.claim_attendance(session_info["csrf_token"], mode=attendance_mode)
                verified = client.get_attendance()
                if not verified.get("claimed_today"):
                    raise PeerGoError("签到提交后状态仍为未签到")
                today_record = verified.get("today_record") or {}
                current_streak = verified.get("current_streak")
                reward = today_record.get("total_reward")
                message = "签到成功"
                if reward not in (None, ""):
                    message += f"；获得 {reward} 魔力值"
                result.update({
                    "status_code": "success_new",
                    "status": "签到成功",
                    "message": message,
                    "current_streak": current_streak,
                })

            new_message_count = 0
            if self._message_notify:
                messages_result = self.__fetch_notifications(client)
                new_message_count = messages_result["new_count"]
                result["message"] = f"{result['message']}；新增站内消息 {new_message_count} 条"
            result.update({
                "username": username,
                "new_message_count": new_message_count,
            })
            self.__save_run_result(result)
            if self._notify:
                self.__send_signin_notification(result)
            logger.info(
                f"肉丝签到任务结束：status={result.get('status_code')}，"
                f"username={username}，new_messages={new_message_count}"
            )
            return result
        except PeerGoAuthError as error:
            return self.__handle_auth_failed(str(error), result)
        except Exception as error:
            logger.error(f"肉丝签到任务异常：{error}")
            result.update({"status_code": "failed", "status": "签到失败", "message": str(error)})
            self.__save_run_result(result)
            if self._notify:
                self.__send_signin_notification(result)
            return result
        finally:
            self._lock.release()

    def __load_user_info(self, client: PeerGoClient, session_info: Dict[str, Any]) -> Dict[str, Any]:
        user = session_info.get("user") or {}
        info = {
            "username": user.get("username") or self._username or "-",
            "display_name": user.get("display_name") or "-",
            "uploaded": "-",
            "downloaded": "-",
            "level": None,
            "magic": None,
            "updated_at": self.__local_time_text(),
        }
        try:
            totals = (client.get_traffic().get("totals") or {})
            info["uploaded"] = self.__format_bytes(totals.get("credited_uploaded_bytes"))
            info["downloaded"] = self.__format_bytes(totals.get("charged_downloaded_bytes"))
        except Exception as error:
            logger.warning(f"肉丝流量信息读取失败：{error}")
        try:
            economy = client.get_economy()
            info["magic"] = economy.get("magic_balance")
            info["level"] = (economy.get("progress") or {}).get("level")
        except Exception as error:
            logger.warning(f"肉丝经济信息读取失败：{error}")
        return info

    def __fetch_notifications(self, client: PeerGoClient) -> Dict[str, Any]:
        initialized = bool(self.get_data("notifications_initialized"))
        seen = [str(value) for value in (self.get_data("seen_notification_ids") or []) if value]
        seen_set = set(seen)
        notifications = []
        for page in range(self.MAX_NOTIFICATION_PAGES):
            body = client.get_notifications(
                limit=self.NOTIFICATION_PAGE_SIZE,
                offset=page * self.NOTIFICATION_PAGE_SIZE,
            )
            items = body.get("items") or []
            if not isinstance(items, list):
                raise PeerGoError("站内消息响应 items 格式异常")
            notifications.extend(item for item in items if isinstance(item, dict))
            if len(items) < self.NOTIFICATION_PAGE_SIZE:
                break
            if initialized and any(str(item.get("id") or "") in seen_set for item in items):
                break

        current_ids = [str(item.get("id")) for item in notifications if item.get("id") is not None]
        if not initialized:
            self.save_data("notifications_initialized", True)
            self.save_data("seen_notification_ids", current_ids[-self.MAX_SEEN_NOTIFICATIONS:])
            logger.info(f"肉丝站内消息首次初始化：baseline_count={len(current_ids)}")
            return {"new_count": 0, "initialized": False}

        new_items = [
            item for item in notifications
            if item.get("id") is not None and str(item.get("id")) not in seen_set
        ]
        merged_ids = list(dict.fromkeys(current_ids + seen))[:self.MAX_SEEN_NOTIFICATIONS]
        self.save_data("seen_notification_ids", merged_ids)
        new_items.sort(key=lambda item: str(item.get("created_at") or ""))
        if new_items:
            self.__send_messages_notification(new_items)
        return {"new_count": len(new_items), "initialized": True}

    def __handle_auth_failed(self, message: str, result: Dict[str, Any]) -> Dict[str, Any]:
        record = result or self.__new_result(False)
        record.update({
            "status_code": "auth_failed",
            "status": "登录失效",
            "message": message or "Cookie 已失效且账号密码登录失败",
        })
        self.save_data("auth_state", {
            "status": "failed",
            "username": self._username or "-",
            "expires_at": "-",
            "updated_at": self.__local_time_text(),
            "message": record["message"],
        })
        self.__save_run_result(record)
        today = self.__today_str()
        if self._notify and self.get_data("last_auth_failed_notify_date") != today:
            self.__safe_post_message(
                mtype=NotificationType.Plugin,
                title="【肉丝自动签到】登录失效",
                text=(
                    f"认证失败：{record['message']}\n\n"
                    "插件保持启用并在下个周期重试。请检查 Cookie，或更新账号密码。"
                ),
            )
            self.save_data("last_auth_failed_notify_date", today)
        logger.warning(f"肉丝登录失败，保留插件启用态等待下次重试：{record['message']}")
        return record

    def __persist_cookie(self, cookie: str):
        normalized = PeerGoClient.normalize_cookie(cookie)
        if not normalized:
            return
        self._cookie = normalized
        self.update_config(self.__current_config(onlyonce=False))

    def __current_config(self, onlyonce: bool = False) -> Dict[str, Any]:
        return {
            "enabled": self._enabled,
            "notify": self._notify,
            "message_notify": self._message_notify,
            "username": self._username,
            "password": self._password,
            "cookie": self._cookie,
            "cron": self._cron,
            "random_delay_minutes": self._random_delay_minutes,
            "onlyonce": onlyonce,
        }

    def __save_run_result(self, result: Dict[str, Any]):
        result.setdefault("date", self.__today_str())
        result.setdefault("time", self.__local_time_text())
        self.save_data("last_run", result)
        self.__save_history_record(result)

    def __save_history_record(self, record: Dict[str, Any]):
        history = self.__get_history()
        record_date = str(record.get("date") or self.__today_str())
        existing_index = next(
            (index for index, item in enumerate(history) if str(item.get("date") or "") == record_date),
            -1,
        )
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
        self.__safe_post_message(
            mtype=NotificationType.Plugin,
            title="【肉丝自动签到】",
            text=(
                f"执行时间：{result.get('time')}\n"
                f"状态：{result.get('status') or '-'}\n"
                f"用户：{result.get('username') or '-'}\n"
                f"连续天数：{result.get('current_streak') if result.get('current_streak') not in (None, '') else '-'}\n"
                f"新增站内消息：{result.get('new_message_count', 0)} 条\n"
                f"说明：{result.get('message') or '-'}"
            ),
        )

    def __send_messages_notification(self, messages: List[Dict[str, Any]]):
        lines = []
        for item in messages[:self.MAX_PUSH_MESSAGES]:
            title = self.__notification_title(item)
            content = self.__clean_text(
                item.get("reason") or item.get("content") or item.get("message"), 100
            )
            lines.append(f"• {title}" + (f"\n  {content}" if content else ""))
        if len(messages) > self.MAX_PUSH_MESSAGES:
            lines.append(f"其余 {len(messages) - self.MAX_PUSH_MESSAGES} 条请到 rousi.pro 查看")
        self.__safe_post_message(
            mtype=NotificationType.Plugin,
            title=f"【肉丝站内消息】新增 {len(messages)} 条",
            text="\n\n".join(lines),
        )

    @staticmethod
    def __notification_title(item: Dict[str, Any]) -> str:
        kind = str(item.get("kind") or "")
        if kind == "content_tip":
            sender = item.get("content_tip_sender_display_name") or item.get("content_tip_sender_username") or "站点成员"
            amount = item.get("content_tip_net_amount") or "-"
            return f"收到 {sender} 打赏的 {amount} 魔力值"
        if kind == "member_gift":
            sender = item.get("member_gift_sender_display_name") or item.get("member_gift_sender_username") or "站点成员"
            amount = item.get("member_gift_net_amount") or "-"
            return f"收到 {sender} 赠送的 {amount} 魔力值"
        if kind == "workgroup_contribution":
            return "工作组贡献进度提醒"
        if kind == "ratio_watch":
            return "分享率状态更新"
        if kind in ("hnr", "hnr_appeal"):
            return f"H&R 状态更新：{item.get('torrent_title') or '种子'}"
        title = item.get("title") or item.get("torrent_title") or kind or "系统消息"
        return RousiCheckin.__clean_text(title, 80) or "系统消息"

    def __safe_post_message(self, **kwargs):
        try:
            self.post_message(**kwargs)
        except Exception as error:
            logger.warning(f"肉丝通知发送失败：{error}")

    @staticmethod
    def __clean_text(value: Any, limit: int) -> str:
        text = unescape(re.sub(r"<[^>]+>", "", str(value or "")))
        text = " ".join(text.split())
        return text[:limit] + "..." if len(text) > limit else text

    @staticmethod
    def __format_bytes(value: Any) -> str:
        try:
            size = float(value or 0)
        except (TypeError, ValueError):
            return "-"
        units = ("B", "KB", "MB", "GB", "TB", "PB")
        for unit in units:
            if abs(size) < 1024 or unit == units[-1]:
                return f"{size:.2f} {unit}"
            size /= 1024
        return "-"

    @staticmethod
    def __format_time(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return "-"
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
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
            "message": "",
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
        return max(number, min_value) if min_value is not None else number
