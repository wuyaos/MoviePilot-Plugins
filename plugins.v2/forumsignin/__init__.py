import json
import random
import re
import time
from datetime import date, datetime, timedelta
from http.cookies import SimpleCookie
from typing import Any, Dict, List, Optional, Tuple

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import NotificationType
from app.utils.http import RequestUtils


class ForumSignin(_PluginBase):
    # 插件名称
    plugin_name = "论坛签到"
    # 插件描述
    plugin_desc = "论坛站点签到（蜂巢 pting.club + 药丸 invites.fun），单插件双站调度，支持 Cookie/账号登录、失败重试与历史记录。"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/signin.png"
    # 插件版本
    plugin_version = "1.0.0"
    # 插件作者
    plugin_author = "wuyaos"
    # 作者主页
    author_url = "https://github.com/wuyaos"
    # 插件配置项ID前缀
    plugin_config_prefix = "forumsignin_"
    # 加载顺序
    plugin_order = 35
    # 可使用的用户级别
    auth_level = 2

    _enabled = False
    _notify = False
    _cron = "7 9 * * *"
    _onlyonce = False
    _update_info_now = False
    _history_days = 30
    _retry_count = 0
    _retry_interval = 10
    _use_proxy = True

    _fengchao_username = None
    _fengchao_password = None
    _fengchao_cookie = None
    _fengchao_current_retry = 0

    _invites_username = None
    _invites_password = None
    _invites_cookie = None
    _invites_current_retry = 0

    _mp_push_enabled = False
    _mp_push_interval = 1
    _last_push_time = None

    _timed_update_enabled = False
    _timed_update_cron = "0 */2 * * *"
    _timed_update_retry_count = 0
    _timed_update_retry_interval = 0
    _timed_update_current_retry = 0

    _scheduler: Optional[BackgroundScheduler] = None
    _active_enabled = None
    _active_cron = None
    _active_timed_update_enabled = None
    _active_timed_update_cron = None

    _site_url = "https://invites.fun"
    _user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0"
    )
    _congestion_status_codes = {429, 502, 503, 504}

    def init_plugin(self, config: dict = None):
        """插件初始化"""
        config = config or {}
        self._enabled = config.get("enabled", False)
        self._notify = config.get("notify", False)
        self._cron = config.get("cron", "7 9 * * *")
        self._onlyonce = config.get("onlyonce", False)
        self._update_info_now = config.get("_update_info_now", config.get("update_info_now", False))
        self._history_days = int(config.get("history_days") or 30)
        self._retry_count = int(config.get("retry_count") or 0)
        self._retry_interval = int(config.get("retry_interval") or 10)
        self._use_proxy = config.get("use_proxy", True)

        self._fengchao_username = config.get("fengchao_username", "")
        self._fengchao_password = config.get("fengchao_password", "")
        self._fengchao_cookie = config.get("fengchao_cookie", "")
        self._invites_username = config.get("invites_username", "")
        self._invites_password = config.get("invites_password", "")
        self._invites_cookie = config.get("invites_cookie", "")

        self._mp_push_enabled = config.get("mp_push_enabled", False)
        self._mp_push_interval = int(config.get("mp_push_interval") or 1)
        self._last_push_time = self.get_data('last_push_time')
        self._timed_update_enabled = config.get("timed_update_enabled", False)
        self._timed_update_cron = config.get("timed_update_cron", "0 */2 * * *")
        self._timed_update_retry_count = int(config.get("timed_update_retry_count") or 0)
        self._timed_update_retry_interval = int(config.get("timed_update_retry_interval") or 0)

        self._fengchao_current_retry = 0
        self._invites_current_retry = 0
        self._timed_update_current_retry = 0

        if not self._scheduler or not self._scheduler.running:
            self.stop_service()
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            logger.info("双站签到调度器未运行，已创建新的实例。")
            self._active_enabled = not self._enabled

        signin_job_id = "forumsignin_dual_signin_cron"
        signin_config_changed = self._enabled != self._active_enabled or self._cron != self._active_cron
        if signin_config_changed:
            logger.info("检测到双站签到任务配置变更，正在更新...")
            if self._scheduler.get_job(signin_job_id):
                self._scheduler.remove_job(signin_job_id)
                logger.info("已移除旧的双站签到周期任务。")
            if self._enabled and self._cron:
                self._scheduler.add_job(
                    func=self.__signin,
                    trigger=CronTrigger.from_crontab(self._cron),
                    name="蜂巢药丸双站签到",
                    id=signin_job_id
                )
                logger.info(f"已添加新的双站签到周期任务，周期：{self._cron}")

        info_update_job_id = "forumsignin_fengchao_info_update_cron"
        info_update_config_changed = (
            self._enabled != self._active_enabled or
            self._timed_update_enabled != self._active_timed_update_enabled or
            self._timed_update_cron != self._active_timed_update_cron
        )
        if info_update_config_changed:
            logger.info("检测到蜂巢个人信息更新任务配置变更，正在更新...")
            if self._scheduler.get_job(info_update_job_id):
                self._scheduler.remove_job(info_update_job_id)
                logger.info("已移除旧的蜂巢个人信息更新周期任务。")
            if self._enabled and self._timed_update_enabled:
                cron_to_use = self._timed_update_cron if self._timed_update_cron else "0 */2 * * *"
                self._scheduler.add_job(
                    func=self.__update_user_info,
                    kwargs={'is_scheduled_run': True},
                    trigger=CronTrigger.from_crontab(cron_to_use),
                    name="蜂巢个人信息定时更新",
                    id=info_update_job_id
                )
                logger.info(f"已添加新的蜂巢个人信息更新周期任务，周期：{cron_to_use}")

        if self._update_info_now:
            logger.info("立即更新蜂巢个人信息")
            self._scheduler.add_job(
                func=self.__update_user_info,
                trigger='date',
                run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3),
                name="蜂巢个人信息更新"
            )
            self._update_info_now = False
            self.update_config(self.get_config_dict())

        if self._onlyonce:
            logger.info("双站签到插件启动，立即运行一次")
            self._scheduler.add_job(
                func=self.__signin,
                trigger='date',
                run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3),
                name="蜂巢药丸双站签到（单次）"
            )
            self._onlyonce = False
            self.update_config(self.get_config_dict())

        if self._scheduler and not self._scheduler.running and self._scheduler.get_jobs():
            self._scheduler.print_jobs()
            self._scheduler.start()

        self._active_enabled = self._enabled
        self._active_cron = self._cron
        self._active_timed_update_enabled = self._timed_update_enabled
        self._active_timed_update_cron = self._timed_update_cron

    def get_config_dict(self):
        """获取当前配置字典，用于更新"""
        return {
            "enabled": self._enabled,
            "notify": self._notify,
            "cron": self._cron,
            "onlyonce": self._onlyonce,
            "_update_info_now": self._update_info_now,
            "history_days": self._history_days,
            "retry_count": self._retry_count,
            "retry_interval": self._retry_interval,
            "use_proxy": self._use_proxy,
            "fengchao_username": self._fengchao_username,
            "fengchao_password": self._fengchao_password,
            "fengchao_cookie": self._fengchao_cookie,
            "invites_username": self._invites_username,
            "invites_password": self._invites_password,
            "invites_cookie": self._invites_cookie,
            "mp_push_enabled": self._mp_push_enabled,
            "mp_push_interval": self._mp_push_interval,
            "timed_update_enabled": self._timed_update_enabled,
            "timed_update_cron": self._timed_update_cron,
            "timed_update_retry_count": self._timed_update_retry_count,
            "timed_update_retry_interval": self._timed_update_retry_interval
        }

    def _send_notification(self, title, text):
        """发送通知"""
        if self._notify:
            self.post_message(mtype=NotificationType.SiteMessage, title=title, text=text)

    def _get_proxies(self):
        """获取代理设置"""
        if not self._use_proxy:
            logger.info("未启用代理")
            return None
        try:
            if hasattr(settings, 'PROXY') and settings.PROXY:
                logger.info(f"使用系统代理: {settings.PROXY}")
                return settings.PROXY
            logger.warning("系统代理未配置")
            return None
        except Exception as e:
            logger.error(f"获取代理设置出错: {str(e)}")
            return None

    @staticmethod
    def _format_money(value: Any) -> str:
        """格式化积分数量"""
        if value is None:
            return '—'
        try:
            num = float(value)
            if num == int(num):
                return str(int(num))
            return f'{round(num, 3):g}'
        except (ValueError, TypeError):
            return str(value)

    @staticmethod
    def __get_status_meta(record: dict) -> dict:
        """获取统一状态元数据，兼容旧版中文状态文本。"""
        status_code = (record or {}).get("status_code")
        status_text = (record or {}).get("status", "")
        if not status_code:
            if "失败" in status_text:
                status_code = "failed"
            elif "已签到" in status_text:
                status_code = "success_already"
            elif "成功" in status_text:
                status_code = "success_new"
            else:
                status_code = "unknown"
        metas = {
            "success_new": {"label": "签到成功", "color": "#4CAF50", "icon": "mdi-check-circle"},
            "success_already": {"label": "今日已签", "color": "#2196F3", "icon": "mdi-check-decagram"},
            "failed": {"label": "签到失败", "color": "#F44336", "icon": "mdi-close-circle"},
            "unknown": {"label": "未知", "color": "#9E9E9E", "icon": "mdi-help-circle"}
        }
        meta = metas.get(status_code, metas["unknown"]).copy()
        meta["code"] = status_code if status_code in metas else "unknown"
        return meta

    def _schedule_retry(self, site: str = "invites", minutes=None):
        """安排分钟级签到重试任务，并添加随机抖动避免重试集中在整点。"""
        if not self._scheduler:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
        retry_interval = minutes if minutes is not None else self._retry_interval
        jitter_seconds = random.randint(30, 180)
        next_run_time = datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(
            minutes=retry_interval,
            seconds=jitter_seconds
        )
        current = self._fengchao_current_retry if site == "fengchao" else self._invites_current_retry
        site_name = "蜂巢" if site == "fengchao" else "药丸"
        func = self.__fengchao_signin if site == "fengchao" else self.__invites_signin
        self._scheduler.add_job(
            func=func,
            trigger='date',
            run_date=next_run_time,
            name=f"{site_name}签到重试 ({current}/{self._retry_count})"
        )
        logger.info(
            f"{site_name}签到失败，将在{retry_interval}分钟后重试，随机抖动{jitter_seconds}秒，"
            f"当前重试次数: {current}/{self._retry_count}"
        )
        if not self._scheduler.running:
            self._scheduler.start()

    def _send_signin_failure_notification(self, reason: str, attempt: int, site: str = "fengchao"):
        """发送签到失败通知"""
        if not self._notify:
            return
        current = self._fengchao_current_retry if site == "fengchao" else self._invites_current_retry
        site_name = "蜂巢" if site == "fengchao" else "药丸"
        remaining_retries = self._retry_count - current
        retry_info = ""
        if self._retry_count > 0 and remaining_retries > 0:
            retry_info = (
                f"🔄 重试信息\n"
                f"• 将在 {self._retry_interval} 分钟后进行下一次定时重试（含随机抖动）\n"
                f"• 剩余定时重试次数: {remaining_retries}\n"
                f"━━━━━━━━━━\n"
            )
        self._send_notification(
            title=f"【❌ {site_name}签到失败】",
            text=(
                f"📢 执行结果\n"
                f"━━━━━━━━━━\n"
                f"🕐 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"❌ 状态：签到失败 (已完成 {attempt + 1} 次快速重试)\n"
                f"💬 原因：{reason}\n"
                f"━━━━━━━━━━\n"
                f"{retry_info}"
            )
        )

    def _schedule_info_update_retry(self):
        """安排蜂巢用户信息更新的重试任务"""
        if not self._scheduler:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
        retry_interval_hours = self._timed_update_retry_interval
        if retry_interval_hours <= 0:
            logger.warning("信息更新重试间隔配置为0或负数，不安排重试")
            return
        next_run_time = datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(hours=retry_interval_hours)
        self._scheduler.add_job(
            func=self.__update_user_info,
            kwargs={'is_scheduled_run': True},
            trigger='date',
            run_date=next_run_time,
            name=f"蜂巢信息更新重试 ({self._timed_update_current_retry}/{self._timed_update_retry_count})"
        )
        logger.info(
            f"蜂巢信息更新失败，将在{retry_interval_hours}小时后重试，"
            f"当前重试次数: {self._timed_update_current_retry}/{self._timed_update_retry_count}"
        )
        if not self._scheduler.running:
            self._scheduler.start()

    def _send_info_update_failure_notification(self, reason: str):
        """发送蜂巢信息更新失败通知"""
        if not self._notify:
            return
        remaining_retries = self._timed_update_retry_count - self._timed_update_current_retry
        retry_info = ""
        if self._timed_update_retry_count > 0 and remaining_retries > 0:
            retry_info = (
                f"🔄 重试信息\n"
                f"• 将在 {self._timed_update_retry_interval} 小时后进行下一次定时重试\n"
                f"• 剩余定时重试次数: {remaining_retries}\n"
                f"━━━━━━━━━━\n"
            )
        self._send_notification(
            title="【❌ 蜂巢信息定时更新失败】",
            text=(
                f"📢 执行结果\n"
                f"━━━━━━━━━━\n"
                f"🕐 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"❌ 状态：信息更新失败\n"
                f"💬 原因：{reason}\n"
                f"━━━━━━━━━━\n"
                f"{retry_info}"
            )
        )

    def __signin(self, retry_count=0, max_retries=3):
        """依次执行蜂巢和药丸双站签到，一站失败不影响另一站。"""
        if hasattr(self, '_dual_signing_in') and self._dual_signing_in:
            logger.info("已有双站签到任务在执行，跳过当前任务")
            return False
        self._dual_signing_in = True
        results = {}
        try:
            try:
                logger.info("开始执行蜂巢签到")
                results["fengchao"] = self.__fengchao_signin(retry_count=retry_count, max_retries=max_retries)
            except Exception as e:
                logger.error(f"蜂巢签到异常已隔离，不影响药丸签到: {e}")
                results["fengchao"] = False
            try:
                logger.info("开始执行药丸签到")
                results["invites"] = self.__invites_signin(retry_count=retry_count, max_retries=max_retries)
            except Exception as e:
                logger.error(f"药丸签到异常已隔离: {e}")
                results["invites"] = False
            return bool(results.get("fengchao") or results.get("invites"))
        finally:
            self._dual_signing_in = False

    def __update_user_info(self, is_scheduled_run: bool = False):
        """
        仅更新用户信息，不执行签到
        :param is_scheduled_run: 是否为定时任务调用，用于判断是否启用重试
        """
        logger.info("开始执行蜂巢用户信息更新任务...")
        try:
            if not self._fengchao_username or not self._fengchao_password:
                raise Exception("未配置用户名和密码")

            proxies = self._get_proxies()
            cookie = self._get_fengchao_auth_cookie(proxies)
            if not cookie:
                raise Exception("登录失败，无法获取Cookie")

            res_main = None
            try:
                res_main = RequestUtils(cookies=cookie, proxies=proxies, timeout=30).get_res(url="https://pting.club")
            except Exception as e:
                logger.error(f"访问主页时发生网络错误: {e}")
                raise Exception(f"访问主页失败: {e}")

            if not res_main or res_main.status_code != 200:
                raise Exception(f"访问主页失败，状态码: {res_main.status_code if res_main else 'N/A'}")

            match = re.search(r'"userId":(\d+)', res_main.text)
            if not match or match.group(1) == "0":
                raise Exception("无法从主页获取有效的用户ID")

            userId = match.group(1)

            res_api = None
            api_url = f"https://pting.club/api/users/{userId}"

            logger.info(f"正在使用API URL: {api_url}")
            try:
                res_api = RequestUtils(cookies=cookie, proxies=proxies, timeout=30).get_res(url=api_url)
            except Exception as e:
                logger.error(f"请求API时发生网络错误: {e}")
                raise Exception(f"API请求失败: {e}")

            if not res_api or res_api.status_code != 200:
                raise Exception(f"API请求失败，状态码: {res_api.status_code if res_api else 'N/A'}")

            user_info = res_api.json()
            self.save_data("fengchao_user_info", user_info)
            self.save_data("fengchao_user_info_updated_at", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

            # --- 同步签到历史记录 START ---
            try:
                attrs = user_info.get('data', {}).get('attributes', {})
                last_checkin_time = attrs.get('lastCheckinTime')
                if last_checkin_time:
                    # API返回的时间格式例如 "2025-12-01 07:35:15"
                    today_str = datetime.now().strftime('%Y-%m-%d')
                    # 检查是否是今天的签到
                    if last_checkin_time.startswith(today_str):
                        # 获取现有历史记录
                        history = self.get_data('history') or []
                        record_date = last_checkin_time.split(" ")[0]
                        skip_update = False
                        
                        # 检查今天是否已有“成功”或“已签到”的记录
                        for item in history:
                            if item.get("site", "fengchao") == "fengchao" and item.get("date", "").startswith(record_date):
                                current_status = item.get("status", "")
                                # 核心修复：如果已经是“成功”或“已签到”状态，则跳过覆盖，防止丢失详细奖励信息
                                if "成功" in current_status or "已签到" in current_status:
                                    skip_update = True
                                    logger.info(f"今日已存在有效签到记录({current_status})，跳过从用户信息同步签到状态")
                                break
                        
                        if not skip_update:
                            history_record = {
                                "site": "fengchao",
                                "date": last_checkin_time,
                                "status": "已签到",  # 标记为已签到
                                "status_code": "success_already",
                                "money": attrs.get('money', 0),
                                "totalContinuousCheckIn": attrs.get('totalContinuousCheckIn', 0),
                                "lastCheckinMoney": attrs.get('lastCheckinMoney', 0),
                                "failure_count": 0
                            }
                            # 保存到历史记录（_save_history 会处理覆盖逻辑）
                            self._save_history(history_record)
                            logger.info(f"同步个人信息时检测到今日已签到，已更新本地记录。奖励: {attrs.get('lastCheckinMoney', 0)}")
            except Exception as e:
                logger.warning(f"同步签到历史记录失败: {e}")
            # --- 同步签到历史记录 END ---

            logger.info("成功更新并保存了蜂巢用户信息。")

            try:
                user_attrs = user_info.get('data', {}).get('attributes', {})
                unread_notifications = user_attrs.get('unreadNotificationCount', 0)
                if unread_notifications > 0:
                    logger.info(f"检测到 {unread_notifications} 条未读消息，发送通知。")
                    self._send_notification(
                        title=f"【📢 蜂巢论坛消息提醒】",
                        text=f"您有 {unread_notifications} 条未读消息待处理，请及时访问蜂巢论坛查看。"
                    )
            except Exception as e:
                logger.warning(f"检查未读消息时发生错误: {e}")

            if is_scheduled_run:
                self._timed_update_current_retry = 0

            self._send_notification(
                title="【✅ 蜂巢信息更新成功】",
                text=f"已成功获取并刷新您的蜂巢论坛个人信息。\n"
                     f"🕐 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

        except Exception as e:
            logger.error(f"更新蜂巢用户信息失败: {e}")
            if is_scheduled_run:
                self._send_info_update_failure_notification(reason=str(e))
                if self._timed_update_retry_count > 0 and self._timed_update_current_retry < self._timed_update_retry_count:
                    self._timed_update_current_retry += 1
                    self._schedule_info_update_retry()
                else:
                    if self._timed_update_retry_count > 0:
                        logger.info("用户信息更新已达到最大定时重试次数，不再重试")
                    self._timed_update_current_retry = 0
            else:
                self._send_notification(
                    title="【❌ 蜂巢信息更新失败】",
                    text=f"在尝试刷新您的蜂巢论坛个人信息时发生错误。\n"
                         f"💬 原因：{e}\n"
                         f"🕐 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
        finally:
            if not is_scheduled_run:
                self._update_info_now = False
                self.update_config(self.get_config_dict())

    def __fengchao_signin(self, retry_count=0, max_retries=3):
        """
        蜂巢签到
        """
        # 增加任务锁，防止重复执行
        if hasattr(self, '_fengchao_signing_in') and self._fengchao_signing_in:
            logger.info("已有签到任务在执行，跳过当前任务")
            return

        self._fengchao_signing_in = True
        attempt = 0
        try:
            # 检查用户名密码是否配置
            if not self._fengchao_username or not self._fengchao_password:
                logger.error("未配置用户名密码，无法进行签到")
                if self._notify:
                    self._send_notification(
                        title="【❌ 蜂巢签到失败】",
                        text=(
                            f"📢 执行结果\n"
                            f"━━━━━━━━━━\n"
                            f"🕐 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                            f"❌ 状态：签到失败，未配置用户名密码\n"
                            f"━━━━━━━━━━\n"
                            f"💡 配置方法\n"
                            f"• 在插件设置中填写蜂巢论坛用户名和密码\n"
                            f"━━━━━━━━━━"
                        )
                    )
                return False

            # 使用循环而非递归实现重试
            for attempt in range(max_retries + 1):
                if attempt > 0:
                    logger.info(f"正在进行第 {attempt}/{max_retries} 次重试...")
                    time.sleep(3)  # 重试前等待3秒

                # 获取代理设置
                proxies = self._get_proxies()

                # 优先复用已配置 Cookie，失效时再登录获取
                logger.info(f"开始获取蜂巢论坛认证cookie...")
                cookie = self._get_fengchao_auth_cookie(proxies)
                if not cookie:
                    logger.error(f"登录失败，无法获取cookie")
                    if attempt < max_retries:
                        continue
                    raise Exception("登录失败，无法获取cookie")

                logger.info(f"成功获取有效cookie")

                # 使用获取的cookie访问蜂巢
                try:
                    res = RequestUtils(cookies=cookie, proxies=proxies, timeout=30).get_res(url="https://pting.club")
                except Exception as e:
                    logger.error(f"请求蜂巢出错: {str(e)}")
                    if attempt < max_retries:
                        continue
                    raise Exception("连接站点出错")

                if not res or res.status_code != 200:
                    logger.error(f"请求蜂巢返回错误状态码: {res.status_code if res else '无响应'}")
                    if attempt < max_retries:
                        continue
                    raise Exception("无法连接到站点")

                pre_money = None
                pre_days = None
                try:
                    pre_money_match = re.search(r'"money":\s*([\d.]+)', res.text)
                    if pre_money_match:
                        pre_money = float(pre_money_match.group(1))
                    pre_days_match = re.search(r'"totalContinuousCheckIn":\s*(\d+)', res.text)
                    if pre_days_match:
                        pre_days = int(pre_days_match.group(1))
                    logger.info(f"签到前状态检查：当前花粉 -> {pre_money}, 签到天数 -> {pre_days}")
                except Exception as e:
                    logger.warning(f"签到前解析用户状态失败，将依赖API原始判断: {e}")

                # 获取csrfToken
                pattern = r'"csrfToken":"(.*?)"'
                csrfToken = re.findall(pattern, res.text)
                if not csrfToken:
                    logger.error("请求csrfToken失败")
                    if attempt < max_retries:
                        continue
                    raise Exception("无法获取CSRF令牌")

                csrfToken = csrfToken[0]
                logger.info(f"获取csrfToken成功 {csrfToken}")

                # 获取userid
                pattern = r'"userId":(\d+)'
                match = re.search(pattern, res.text)

                if match and match.group(1) != "0":
                    userId = match.group(1)
                    logger.info(f"获取userid成功 {userId}")

                    # 如果开启了蜂巢论坛PT人生数据更新，尝试更新数据
                    if self._mp_push_enabled:
                        self.__push_mp_stats(user_id=userId, csrf_token=csrfToken, cookie=cookie)
                else:
                    logger.error("未找到userId")
                    if attempt < max_retries:
                        continue
                    raise Exception("无法获取用户ID")

                # 准备签到请求
                headers = {
                    "X-Csrf-Token": csrfToken,
                    "X-Http-Method-Override": "PATCH",
                    "Cookie": cookie
                }

                data = {
                    "data": {
                        "type": "users",
                        "attributes": {
                            "canCheckin": False,
                            "totalContinuousCheckIn": 2
                        },
                        "id": userId
                    }
                }

                # 开始签到
                try:
                    res = RequestUtils(headers=headers, proxies=proxies, timeout=30).post_res(
                        url=f"https://pting.club/api/users/{userId}",
                        json=data
                    )
                except Exception as e:
                    logger.error(f"签到请求出错: {str(e)}")
                    if attempt < max_retries:
                        continue
                    raise Exception("签到请求异常")

                if not res or res.status_code != 200:
                    logger.error(f"蜂巢签到失败，状态码: {res.status_code if res else '无响应'}")
                    if attempt < max_retries:
                        continue
                    raise Exception("API请求错误")

                # 签到成功
                sign_dict = json.loads(res.text)

                # 直接保存签到后的用户信息
                self.save_data("fengchao_user_info", sign_dict)
                self.save_data("fengchao_user_info_updated_at", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                logger.info("成功获取并保存用户信息。")

                # 新增：检查未读消息并通知
                try:
                    user_attrs_for_msg = sign_dict.get('data', {}).get('attributes', {})
                    unread_notifications = user_attrs_for_msg.get('unreadNotificationCount', 0)
                    if unread_notifications > 0:
                        logger.info(f"检测到 {unread_notifications} 条未读消息，发送通知。")
                        self._send_notification(
                            title=f"【📢 蜂巢论坛消息提醒】",
                            text=f"您有 {unread_notifications} 条未读消息待处理，请及时访问蜂巢论坛查看。"
                        )
                except Exception as e:
                    logger.warning(f"检查未读消息时发生错误: {e}")

                money = sign_dict['data']['attributes']['money']
                totalContinuousCheckIn = sign_dict['data']['attributes']['totalContinuousCheckIn']
                lastCheckinMoney = sign_dict['data']['attributes'].get('lastCheckinMoney', 0)

                formatted_money = self._format_pollen(money)
                formatted_last_checkin_money = self._format_pollen(lastCheckinMoney)

                is_successful_checkin = False
                if pre_money is not None and pre_days is not None:
                    if money > pre_money or totalContinuousCheckIn > pre_days:
                        is_successful_checkin = True
                else:
                    can_checkin_before = '"canCheckin":true' in res.text
                    logger.info(f"回退到API标志位判断: canCheckin -> {can_checkin_before}")
                    if can_checkin_before:
                        is_successful_checkin = True

                if is_successful_checkin:
                    status_text = "签到成功"
                    reward_text = f"获得{formatted_last_checkin_money}花粉奖励" if lastCheckinMoney > 0 else "获得奖励"
                    logger.info(
                        f"蜂巢签到成功，获得{formatted_last_checkin_money}花粉，当前花粉: {formatted_money}，累计签到: {totalContinuousCheckIn}")
                else:
                    status_text = "已签到"
                    reward_text = "今日已领取奖励"
                    logger.info(f"蜂巢已签到，当前花粉: {formatted_money}，累计签到: {totalContinuousCheckIn}")

                # 发送通知
                if self._notify:
                    self._send_notification(
                        title=f"【✅ 蜂巢{status_text}】",
                        text=(
                            f"📢 执行结果\n"
                            f"━━━━━━━━━━\n"
                            f"🕐 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                            f"✨ 状态：{status_text}\n"
                            f"🎁 奖励：{reward_text}\n"
                            f"━━━━━━━━━━\n"
                            f"📊 积分统计\n"
                            f"🌸 花粉：{formatted_money}\n"
                            f"📆 签到天数：{totalContinuousCheckIn}\n"
                            f"━━━━━━━━━━"
                        )
                    )

                # 准备历史记录
                history_record = {
                    "site": "fengchao",
                    "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "status": status_text,
                    "status_code": "success_new" if is_successful_checkin else "success_already",
                    "money": money,
                    "totalContinuousCheckIn": totalContinuousCheckIn,
                    "lastCheckinMoney": lastCheckinMoney if is_successful_checkin else 0,
                    "failure_count": 0
                }

                # 保存签到历史
                self._save_history(history_record)

                # 如果是重试后成功，重置重试计数
                if self._fengchao_current_retry > 0:
                    logger.info(f"蜂巢签到重试成功，重置重试计数")
                    self._fengchao_current_retry = 0

                # 签到成功，退出循环
                return True

        except Exception as e:
            logger.error(f"签到过程发生异常: {str(e)}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")

            # 保存失败记录
            failure_history_record = {
                "site": "fengchao",
                "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "status": "签到失败",
                "status_code": "failed",
                "reason": str(e),
                "failure_count": 1  # 初始失败次数为1
            }
            self._save_history(failure_history_record)

            # 所有重试失败，发送通知并退出
            self._send_signin_failure_notification(str(e), attempt, site='fengchao')

            # 设置下次定时重试
            if self._retry_count > 0 and self._fengchao_current_retry < self._retry_count:
                self._fengchao_current_retry += 1
                logger.info(f"安排第{self._fengchao_current_retry}次蜂巢定时重试，将在{self._retry_interval}分钟后重试")
                self._schedule_retry(site='fengchao', minutes=self._retry_interval)
            else:
                if self._retry_count > 0:
                    logger.info("已达到最大定时重试次数，不再重试")
                self._fengchao_current_retry = 0

            return False
        finally:
            # 释放锁
            self._fengchao_signing_in = False

    def _map_fa_to_mdi(self, icon_class: str) -> str:
        """
        Maps common Font Awesome icon names to MDI icon names.
        """
        if not icon_class or not isinstance(icon_class, str):
            return 'mdi-account-group'
        if icon_class.startswith('mdi-'):
            return icon_class

        mapping = {
            'fa-user-tie': 'mdi-account-tie', 'fa-crown': 'mdi-crown', 'fa-shield-alt': 'mdi-shield-outline',
            'fa-user-shield': 'mdi-account-shield', 'fa-user-cog': 'mdi-account-cog',
            'fa-user-check': 'mdi-account-check', 'fa-fan': 'mdi-fan', 'fa-user': 'mdi-account',
            'fa-users': 'mdi-account-group', 'fa-cogs': 'mdi-cog', 'fa-cog': 'mdi-cog', 'fa-star': 'mdi-star',
            'fa-gem': 'mdi-diamond'
        }
        match = re.search(r'fa-[\w-]+', icon_class)
        if match:
            core_icon = match.group(0)
            return mapping.get(core_icon, 'mdi-account-group')
        return 'mdi-account-group'

    def _format_pollen(self, value: Any) -> str:
        """
        Formats the pollen value.
        """
        if value is None:
            return '—'
        try:
            num = float(value)
            if num == int(num):
                return str(int(num))
            else:
                return f'{round(num, 3):g}'
        except (ValueError, TypeError):
            return str(value)

    def __check_and_push_mp_stats(self):
        """检查是否需要更新蜂巢论坛PT人生数据"""
        if hasattr(self, '_pushing_stats') and self._pushing_stats:
            logger.info("已有更新PT人生数据任务在执行，跳过当前任务")
            return
        self._pushing_stats = True
        try:
            if not self._mp_push_enabled: return
            if not self._fengchao_username or not self._fengchao_password:
                logger.error("未配置用户名密码，无法更新PT人生数据")
                return
            proxies = self._get_proxies()
            now = datetime.now()
            if self._last_push_time:
                last_push = datetime.strptime(self._last_push_time, '%Y-%m-%d %H:%M:%S')
                if (now - last_push).days < self._mp_push_interval:
                    logger.info(f"距离上次更新PT人生数据时间不足{self._mp_push_interval}天，跳过更新")
                    return
            logger.info(f"开始更新蜂巢论坛PT人生数据...")
            cookie = self._get_fengchao_auth_cookie(proxies)
            if not cookie:
                logger.error("登录失败，无法获取cookie进行PT人生数据更新")
                return
            try:
                res = RequestUtils(cookies=cookie, proxies=proxies, timeout=30).get_res(url="https://pting.club")
            except Exception as e:
                logger.error(f"请求蜂巢出错: {str(e)}")
                return
            if not res or res.status_code != 200:
                logger.error(f"请求蜂巢返回错误状态码: {res.status_code if res else '无响应'}")
                return
            csrf_matches = re.findall(r'"csrfToken":"(.*?)"', res.text)
            if not csrf_matches:
                logger.error("获取CSRF令牌失败，无法进行PT人生数据更新")
                return
            csrf_token = csrf_matches[0]
            user_matches = re.search(r'"userId":(\d+)', res.text)
            if not user_matches:
                logger.error("获取用户ID失败，无法进行PT人生数据更新")
                return
            user_id = user_matches.group(1)
            self.__push_mp_stats(user_id=user_id, csrf_token=csrf_token, cookie=cookie)
        finally:
            self._pushing_stats = False

    def __push_mp_stats(self, user_id=None, csrf_token=None, cookie=None, retry_count=0, max_retries=3):
        """更新蜂巢论坛PT人生数据"""
        if not self._mp_push_enabled: return
        if not all([user_id, csrf_token, cookie]):
            logger.error("用户ID、CSRF令牌或Cookie为空，无法更新PT人生数据")
            return
        for attempt in range(retry_count, max_retries + 1):
            if attempt > retry_count:
                logger.info(f"更新失败，正在进行第 {attempt - retry_count}/{max_retries - retry_count} 次重试...")
                time.sleep(3)
            try:
                now = datetime.now()
                logger.info(f"开始获取站点统计数据以更新蜂巢论坛PT人生数据 (用户ID: {user_id})")
                if not hasattr(self, '_cached_stats_data') or not self._cached_stats_data or not hasattr(self,
                                                                                                        '_cached_stats_time') or (
                        now - self._cached_stats_time).total_seconds() > 3600:
                    self._cached_stats_data = self._get_site_statistics()
                    self._cached_stats_time = now
                    logger.info("获取最新站点统计数据")
                else:
                    logger.info(f"使用缓存的站点统计数据（缓存时间：{self._cached_stats_time.strftime('%Y-%m-%d %H:%M:%S')}）")
                stats_data = self._cached_stats_data
                if not stats_data:
                    logger.error("获取站点统计数据失败，无法更新PT人生数据")
                    if attempt < max_retries: continue
                    return
                if not hasattr(self, '_cached_formatted_stats') or not self._cached_formatted_stats or not hasattr(
                        self,
                        '_cached_stats_time') or (
                        now - self._cached_stats_time).total_seconds() > 3600:
                    self._cached_formatted_stats = self._format_stats_data(stats_data)
                    logger.info("格式化最新站点统计数据")
                else:
                    logger.info("使用缓存的已格式化站点统计数据")
                formatted_stats = self._cached_formatted_stats
                if not formatted_stats:
                    logger.error("格式化站点统计数据失败，无法更新PT人生数据")
                    if attempt < max_retries: continue
                    return
                
                # 记录第一个站点的数据以便确认所有字段是否都被正确传递
                if formatted_stats.get("sites") and len(formatted_stats.get("sites")) > 0:
                    first_site = formatted_stats.get("sites")[0]
                    logger.info(f"推送数据示例：站点={first_site.get('name')}, 用户名={first_site.get('username')}, 等级={first_site.get('user_level')}, "
                                f"上传={first_site.get('upload')}, 下载={first_site.get('download')}, 分享率={first_site.get('ratio')}, "
                                f"魔力值={first_site.get('bonus')}, 做种数={first_site.get('seeding')}, 做种体积={first_site.get('seeding_size')}")

                sites = formatted_stats.get("sites", [])
                if len(sites) > 300:
                    logger.warning(f"站点数据过多({len(sites)}个)，将只推送做种数最多的前300个站点")
                    sites.sort(key=lambda x: x.get("seeding", 0), reverse=True)
                    formatted_stats["sites"] = sites[:300]
                headers = {"X-Csrf-Token": csrf_token, "X-Http-Method-Override": "PATCH",
                           "Content-Type": "application/json", "Cookie": cookie}
                data = {"data": {"type": "users", "attributes": {
                    "mpStatsSummary": json.dumps(formatted_stats.get("summary", {})),
                    "mpStatsSites": json.dumps(formatted_stats.get("sites", []))}, "id": user_id}}
                
                # 输出JSON数据片段以便确认
                json_data = json.dumps(formatted_stats.get("sites", []))
                if len(json_data) > 500:
                    logger.info(f"推送的JSON数据片段: {json_data[:500]}...")
                    logger.info(f"推送数据大小约为: {len(json_data)/1024:.2f} KB")
                else:
                    logger.info(f"推送的JSON数据: {json_data}")
                    logger.info(f"推送数据大小约为: {len(json_data)/1024:.2f} KB")

                proxies = self._get_proxies()
                url = f"https://pting.club/api/users/{user_id}"
                logger.info(f"准备更新蜂巢论坛PT人生数据: {len(formatted_stats.get('sites', []))} 个站点")
                try:
                    res = RequestUtils(headers=headers, proxies=proxies, timeout=60).post_res(url=url, json=data)
                except Exception as e:
                    logger.error(f"更新请求出错: {str(e)}")
                    if attempt < max_retries: continue
                    logger.error("所有重试都失败，放弃更新")
                    return
                if res and res.status_code == 200:
                    logger.info(
                        f"成功更新蜂巢论坛PT人生数据: 总上传 {round(formatted_stats['summary']['total_upload'] / (1024 ** 3), 2)} GB, 总下载 {round(formatted_stats['summary']['total_download'] / (1024 ** 3), 2)} GB")
                    self._last_push_time = now.strftime('%Y-%m-%d %H:%M:%S')
                    self.save_data('last_push_time', self._last_push_time)
                    if hasattr(self, '_cached_stats_data'): self._cached_stats_data = None
                    if hasattr(self, '_cached_formatted_stats'): self._cached_formatted_stats = None
                    if hasattr(self, '_cached_stats_time'): delattr(self, '_cached_stats_time')
                    logger.info("已清除站点数据缓存，下次将获取最新数据")
                    if self._notify:
                        self._send_notification(
                            title="【✅ 蜂巢论坛PT人生数据更新成功】",
                            text=(
                                f"📢 执行结果\n"
                                f"━━━━━━━━━━\n"
                                f"🕐 时间：{now.strftime('%Y-%m-%d %H:%M:%S')}\n"
                                f"✨ 状态：成功更新蜂巢论坛PT人生数据\n"
                                f"📊 站点数：{len(formatted_stats.get('sites', []))} 个\n"
                                f"━━━━━━━━━━"
                            )
                        )
                    return True
                else:
                    logger.error(f"更新蜂巢论坛PT人生数据失败：{res.status_code if res else '请求失败'}, 响应: {res.text[:100] if res and hasattr(res, 'text') else '无响应内容'}")
                    if attempt < max_retries:
                        continue

                    # 所有重试都失败，发送通知
                    if self._notify:
                        self._send_notification(
                            title="【❌ 蜂巢论坛PT人生数据更新失败】",
                            text=(
                                f"📢 执行结果\n"
                                f"━━━━━━━━━━\n"
                                f"🕐 时间：{now.strftime('%Y-%m-%d %H:%M:%S')}\n"
                                f"❌ 状态：更新蜂巢论坛PT人生数据失败（已重试{attempt - retry_count}次）\n"
                                f"━━━━━━━━━━\n"
                                f"💡 可能的解决方法\n"
                                f"• 检查Cookie是否有效\n"
                                f"• 确认站点是否可访问\n"
                                f"• 尝试手动登录网站\n"
                                f"━━━━━━━━━━"
                            )
                        )
                    return False
            except Exception as e:
                logger.error(f"更新过程发生异常: {str(e)}")
                import traceback
                logger.error(f"错误详情: {traceback.format_exc()}")

                if attempt < max_retries:
                    continue

                # 所有重试都失败
                if self._notify:
                    self._send_notification(
                        title="【❌ 蜂巢论坛PT人生数据更新失败】",
                        text=(
                            f"📢 执行结果\n"
                            f"━━━━━━━━━━\n"
                            f"🕐 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                            f"❌ 状态：更新蜂巢论坛PT人生数据失败（已重试{attempt - retry_count}次）\n"
                            f"━━━━━━━━━━\n"
                            f"💡 可能的解决方法\n"
                            f"• 检查系统网络连接\n"
                            f"• 确认站点是否可访问\n"
                            f"• 检查代码是否有错误\n"
                            f"━━━━━━━━━━"
                        )
                    )

    def _get_site_statistics(self):
        """获取站点统计数据（参考站点统计插件实现）"""
        try:
            # 导入SiteOper类和SitesHelper
            from app.db.site_oper import SiteOper
            from app.helper.sites import SitesHelper
            site_oper, sites_helper = SiteOper(), SitesHelper()
            managed_sites = sites_helper.get_indexers()
            managed_site_names = [s.get("name") for s in managed_sites if s.get("name")]
            raw_data_list = site_oper.get_userdata()
            if not raw_data_list:
                logger.error("未获取到站点数据")
                return None
            data_dict = {f"{d.updated_day}_{d.name}": d for d in raw_data_list}
            data_list = sorted(list(data_dict.values()), key=lambda x: x.updated_day, reverse=True)
            site_names = set()
            latest_site_data = []
            for data in data_list:
                if data.name not in site_names and data.name in managed_site_names:
                    site_names.add(data.name)
                    latest_site_data.append(data)
            sites = []
            for site_data in latest_site_data:
                site_dict = site_data.to_dict() if hasattr(site_data, "to_dict") else site_data.__dict__
                if "_sa_instance_state" in site_dict: site_dict.pop("_sa_instance_state")
                sites.append(site_dict)
            return {"sites": sites}
        except Exception as e:
            logger.error(f"获取站点统计数据出错: {str(e)}")
            return self._get_site_statistics_via_api()

    def _get_site_statistics_via_api(self):
        """通过API获取站点统计数据（备用）"""
        try:
            from app.helper.sites import SitesHelper
            sites_helper = SitesHelper()
            managed_sites = sites_helper.get_indexers()
            managed_site_names = [s.get("name") for s in managed_sites if s.get("name")]
            api_url = f"{settings.HOST}/api/v1/site/statistics"
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {settings.API_TOKEN}"}
            res = RequestUtils(headers=headers).get_res(url=api_url)
            if res and res.status_code == 200:
                data = res.json()
                all_sites = data.get("sites", [])
                sites = [s for s in all_sites if s.get("name") in managed_site_names]
                data["sites"] = sites
                return data
            else:
                logger.error(f"获取站点统计数据失败: {res.status_code if res else '连接失败'}")
                return None
        except Exception as e:
            logger.error(f"获取站点统计数据出错: {str(e)}")
            return None

    def _format_stats_data(self, stats_data):
        """格式化站点统计数据"""
        try:
            if not stats_data or not stats_data.get("sites"): return None
            sites = stats_data.get("sites", [])
            summary = {"total_upload": 0, "total_download": 0, "total_seed": 0, "total_seed_size": 0}
            site_details = []
            for site in sites:
                if not site.get("name") or site.get("error"): continue
                upload = float(site.get("upload", 0))
                download = float(site.get("download", 0))
                summary["total_upload"] += upload
                summary["total_download"] += download
                summary["total_seed"] += int(site.get("seeding", 0))
                summary["total_seed_size"] += float(site.get("seeding_size", 0))
                site_details.append({
                    "name": site.get("name"), "username": site.get("username", ""),
                    "user_level": site.get("user_level", ""),
                    "upload": upload, "download": download,
                    "ratio": round(upload / download, 2) if download > 0 else float('inf'),
                    "bonus": site.get("bonus", 0), "seeding": site.get("seeding", 0),
                    "seeding_size": site.get("seeding_size", 0)
                })
            summary["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return {"summary": summary, "sites": site_details}
        except Exception as e:
            logger.error(f"格式化站点统计数据出错: {str(e)}")
            return None

    def _login_and_get_cookie(self, proxies=None):
        """使用用户名密码登录获取cookie"""
        try:
            logger.info(f"开始使用用户名'{self._fengchao_username}'登录蜂巢论坛...")
            cookie = self._login_postman_method(proxies=proxies)
            if cookie:
                self._update_fengchao_cookie_if_changed(cookie)
            return cookie
        except Exception as e:
            logger.error(f"登录过程出错: {str(e)}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return None

    def _update_fengchao_cookie_if_changed(self, cookie_str: str):
        """蜂巢登录成功后持久化 Cookie。"""
        if cookie_str and cookie_str != (self._fengchao_cookie or ""):
            self._fengchao_cookie = cookie_str
            logger.info("蜂巢 Cookie 已更新，保存新配置")
            self.update_config(self.get_config_dict())

    def _get_fengchao_auth_cookie(self, proxies=None):
        """优先复用已配置蜂巢 Cookie，失效时再登录刷新。"""
        if self._fengchao_cookie:
            req = RequestUtils(proxies=proxies, timeout=30)
            verified = self._verify_cookie(req, self._fengchao_cookie, "代理" if proxies else "直接连接")
            if verified:
                logger.info("蜂巢 Cookie 验证有效，直接复用")
                return verified
            logger.warning("蜂巢 Cookie 验证失效，回退账号密码登录")
        return self._login_and_get_cookie(proxies)

    def _login_postman_method(self, proxies=None):
        """使用Postman方式登录"""
        try:
            req = RequestUtils(proxies=proxies, timeout=30)
            proxy_info = "代理" if proxies else "直接连接"
            logger.info(f"使用Postman方式登录 (使用{proxy_info})...")
            headers = {"Accept": "*/*",
                       "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                       "Cache-Control": "no-cache"}
            try:
                res = req.get_res("https://pting.club", headers=headers)
                if not res or res.status_code != 200:
                    logger.error(f"GET请求失败，状态码: {res.status_code if res else '无响应'} (使用{proxy_info})")
                    return None
            except Exception as e:
                logger.error(f"GET请求异常 (使用{proxy_info}): {str(e)}")
                return None
            csrf_token = res.headers.get('x-csrf-token') or (re.findall(r'"csrfToken":"(.*?)"', res.text) or [None])[
                0]
            if not csrf_token:
                logger.error(f"无法获取CSRF令牌 (使用{proxy_info})")
                return None
            set_cookie_header = res.headers.get('set-cookie')
            if not set_cookie_header or not (
                    session_match := re.search(r'flarum_session=([^;]+)', set_cookie_header)):
                logger.error(f"无法从set-cookie中提取session cookie (使用{proxy_info})")
                return None
            session_cookie = session_match.group(1)
            login_data = {"identification": self._fengchao_username, "password": self._fengchao_password, "remember": True}
            login_headers = {"Content-Type": "application/json", "X-CSRF-Token": csrf_token,
                             "Cookie": f"flarum_session={session_cookie}", **headers}
            try:
                login_res = req.post_res(url="https://pting.club/login", json=login_data, headers=login_headers)
                if not login_res or login_res.status_code != 200:
                    logger.error(
                        f"登录请求失败，状态码: {login_res.status_code if login_res else '无响应'} (使用{proxy_info})")
                    return None
            except Exception as e:
                logger.error(f"登录请求异常 (使用{proxy_info}): {str(e)}")
                return None
            cookie_dict = {}
            if set_cookie_header := login_res.headers.get('set-cookie'):
                if session_match := re.search(r'flarum_session=([^;]+)', set_cookie_header):
                    cookie_dict['flarum_session'] = session_match.group(1)
                if remember_match := re.search(r'flarum_remember=([^;]+)', set_cookie_header):
                    cookie_dict['flarum_remember'] = remember_match.group(1)
            if 'flarum_session' not in cookie_dict: cookie_dict['flarum_session'] = session_cookie
            cookie_str = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])
            return self._verify_cookie(req, cookie_str, proxy_info)
        except Exception as e:
            logger.error(f"Postman方式登录失败 (使用{proxy_info if proxies else '直接连接'}): {str(e)}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return None

    def _verify_cookie(self, req, cookie_str, proxy_info):
        """验证cookie是否有效"""
        if not cookie_str: return None
        logger.info(f"验证cookie有效性 (使用{proxy_info})...")
        headers = {"Cookie": cookie_str,
                   "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                   "Accept": "*/*", "Cache-Control": "no-cache"}
        for attempt in range(3):
            try:
                if attempt > 0:
                    logger.info(f"验证Cookie重试 {attempt}/2...")
                    time.sleep(2)
                verify_res = req.get_res("https://pting.club", headers=headers)
                if verify_res and verify_res.status_code == 200:
                    if user_matches := re.search(r'"userId":(\d+)', verify_res.text):
                        if (user_id := user_matches.group(1)) != "0":
                            logger.info(f"登录成功！获取到有效cookie，用户ID: {user_id} (使用{proxy_info})")
                            return cookie_str
                if verify_res and verify_res.status_code in self._congestion_status_codes and attempt < 2:
                    self.__backoff_sleep(attempt, response=verify_res)
                    continue
                logger.warning(f"第{attempt + 1}次验证cookie失败 (使用{proxy_info})")
            except Exception as e:
                logger.warning(f"第{attempt + 1}次验证cookie请求异常 (使用{proxy_info}): {str(e)}")
        logger.error("所有 3 次cookie验证尝试均失败。")
        return None

    def __backoff_sleep(self, attempt: int, response=None, base_seconds: int = 3, max_seconds: int = 90):
        """
        对拥塞/限流响应进行指数退避，并添加随机抖动。
        """
        retry_after = None
        try:
            if response is not None:
                retry_after_header = response.headers.get('Retry-After')
                if retry_after_header and str(retry_after_header).isdigit():
                    retry_after = int(retry_after_header)
        except Exception:
            retry_after = None

        if retry_after is None:
            retry_after = min(max_seconds, base_seconds * (2 ** attempt))
        jitter = random.uniform(0.5, 3.0)
        sleep_seconds = retry_after + jitter
        logger.info(f"药丸站点拥塞或限流，退避 {sleep_seconds:.1f} 秒后重试")
        time.sleep(sleep_seconds)

    def __get_remember_value(self, cookie: str) -> Optional[str]:
        """从cookie字符串中提取flarum_remember值"""
        remember_match = re.search(r'flarum_remember=([^;]+)', cookie or "")
        if remember_match:
            return remember_match.group(1)
        return None

    def __parse_cookie_string(self, cookie_str: str) -> dict:
        """安全地解析cookie字符串，返回cookie字典"""
        try:
            cookie = SimpleCookie()
            cookie.load(cookie_str or "")
            cookies = {}
            if 'flarum_remember' in cookie:
                cookies['flarum_remember'] = cookie['flarum_remember'].value
            if 'flarum_session' in cookie:
                cookies['flarum_session'] = cookie['flarum_session'].value
            return cookies
        except Exception as e:
            logger.error(f"解析cookie字符串失败: {e}")
            return {}

    def __build_api_headers(self, csrf_token: str, referer: str = "https://invites.fun/") -> dict:
        """
        构建药丸 API 请求头，贴近前端真实签到请求。
        """
        return {
            'accept': '*/*',
            'accept-language': 'zh-CN,zh-Hans;q=0.9',
            'origin': self._site_url,
            'referer': referer,
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'x-csrf-token': csrf_token,
            'user-agent': self._user_agent
        }

    @staticmethod

    def __extract_checkin_state(payload: dict) -> dict:
        """
        从药丸 JSON:API 用户响应中提取签到状态字段。
        """
        if not isinstance(payload, dict):
            return {}

        data = payload.get('data')
        if not isinstance(data, dict):
            return {}

        attrs = data.get('attributes')
        if not isinstance(attrs, dict):
            return {}

        return {
            "user_id": str(data.get('id') or ""),
            "username": attrs.get('username') or "",
            "displayName": attrs.get('displayName') or attrs.get('username') or "",
            "avatarUrl": attrs.get('avatarUrl') or "",
            "discussionCount": attrs.get('discussionCount'),
            "commentCount": attrs.get('commentCount'),
            "joinTime": attrs.get('joinTime') or "",
            "lastSeenAt": attrs.get('lastSeenAt') or "",
            "unreadNotificationCount": attrs.get('unreadNotificationCount'),
            "followerCount": attrs.get('followerCount'),
            "canCheckin": attrs.get('canCheckin'),
            "lastCheckinTime": attrs.get('lastCheckinTime') or "",
            "totalContinuousCheckIn": attrs.get('totalContinuousCheckIn'),
            "lastCheckinMoney": attrs.get('lastCheckinMoney', 0),
            "money": attrs.get('money')
        }

    def __request_invites_with_backoff(self, method: str, url: str, **kwargs):
        """药丸请求统一退避包装，覆盖限流与拥塞状态码。"""
        max_attempts = kwargs.pop("max_attempts", 4)
        request_kwargs = kwargs.copy()
        for attempt in range(max_attempts):
            try:
                if attempt > 0:
                    logger.info(f"正在重试药丸请求 {method.upper()} ({attempt}/{max_attempts - 1})")
                call_kwargs = request_kwargs.copy()
                request = RequestUtils(
                    proxies=call_kwargs.pop("proxies", self._get_proxies()),
                    timeout=call_kwargs.pop("timeout", 30),
                    **{key: call_kwargs.pop(key) for key in list(call_kwargs.keys()) if key in ("headers", "cookies")}
                )
                if method.lower() == "post":
                    response = request.post_res(url=url, **call_kwargs)
                else:
                    response = request.get_res(url=url, **call_kwargs)
            except Exception as e:
                logger.error(f"药丸请求 {method.upper()} {url} 异常: {e}")
                if attempt < max_attempts - 1:
                    self.__backoff_sleep(attempt)
                    continue
                return None

            if response is None:
                logger.error(f"药丸请求 {method.upper()} {url} 失败：无响应")
                if attempt < max_attempts - 1:
                    self.__backoff_sleep(attempt)
                    continue
                return None

            if response.status_code in self._congestion_status_codes and attempt < max_attempts - 1:
                logger.warning(f"药丸请求 {method.upper()} {url} 遇到拥塞状态码: {response.status_code}")
                self.__backoff_sleep(attempt, response=response)
                continue
            return response
        return None

    def __fetch_checkin_state(self, user_id: str, cookies: dict, csrf_token: str) -> dict:
        """
        查询用户当前签到状态，用于签到前判断和签到后复核。
        """
        try:
            response = self.__request_invites_with_backoff(
                "get",
                f'{self._site_url}/api/users/{user_id}',
                cookies=cookies,
                headers=self.__build_api_headers(csrf_token),
                timeout=30
            )
            if response is None:
                logger.error("查询药丸签到状态失败：无响应")
                return {}
            if response.status_code != 200:
                logger.error(f"查询药丸签到状态失败，状态码: {response.status_code}")
                return {}
            return self.__extract_checkin_state(response.json())
        except Exception as e:
            logger.error(f"查询药丸签到状态异常: {e}")
            return {}

    @staticmethod

    def __is_today_checkin(state: dict) -> bool:
        """
        判断签到状态是否已经落到当天。
        """
        last_checkin_time = str((state or {}).get("lastCheckinTime") or "")
        return bool(last_checkin_time and last_checkin_time.startswith(datetime.now().strftime('%Y-%m-%d')))

    @staticmethod

    def __get_response_error_message(response) -> str:
        """
        从药丸接口错误响应中提取可读提示。
        """
        if response is None:
            return "无响应"

        try:
            payload = response.json()
            errors = payload.get("errors") if isinstance(payload, dict) else None
            if errors:
                messages = []
                for error in errors:
                    if not isinstance(error, dict):
                        continue
                    message = error.get("detail") or error.get("title") or error.get("code")
                    if message:
                        messages.append(str(message))
                if messages:
                    return "；".join(messages)
        except Exception:
            pass

        text = getattr(response, "text", "") or ""
        return text[:200] if text else f"HTTP {response.status_code}"

    def __get_new_session(self, flarum_remember: str) -> Optional[dict]:
        """使用长期 flarum_remember 一次请求刷新 session 并解析首页状态。"""
        headers = {
            "Cookie": f"flarum_remember={flarum_remember}",
            "User-Agent": self._user_agent,
            "Upgrade-Insecure-Requests": "1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
        }
        response = self.__request_invites_with_backoff(
            "get",
            self._site_url,
            headers=headers,
            timeout=30,
            allow_redirects=False
        )
        if response is None or response.status_code != 200:
            logger.error(f"刷新药丸 session 失败，状态码: {response.status_code if response else '无响应'}")
            return None

        flarum_session = response.cookies.get('flarum_session')
        if not flarum_session:
            cookies = response.headers.get('Set-Cookie', '') or response.headers.get('set-cookie', '')
            session_match = re.search(r'flarum_session=([^;]+)', cookies)
            flarum_session = session_match.group(1) if session_match else None

        csrf_match = re.search(r'"csrfToken":"(.*?)"', response.text or "")
        user_match = re.search(r'"userId":(\d+)', response.text or "")
        if not flarum_session or not csrf_match or not user_match or user_match.group(1) == "0":
            logger.error("刷新药丸 session 失败：remember 可能失效，未获取到有效 session/csrfToken/userId")
            return None

        return {"flarum_session": flarum_session, "csrf_token": csrf_match.group(1), "user_id": user_match.group(1)}

    def __get_homepage_state(self, cookie_str: str) -> Optional[dict]:
        """使用新 Cookie 获取首页中的 csrfToken 和 userId"""
        headers = {
            "Cookie": cookie_str,
            "User-Agent": self._user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1"
        }
        response = self.__request_invites_with_backoff(
            "get",
            self._site_url,
            headers=headers,
            timeout=30
        )

        if not response or response.status_code != 200:
            logger.error(f"请求药丸首页失败，状态码: {response.status_code if response else '无响应'}")
            return None

        csrf_match = re.search(r'"csrfToken":"(.*?)"', response.text or "")
        if not csrf_match:
            logger.error("请求药丸 csrfToken 失败")
            return None

        user_match = re.search(r'"userId":(\d+)', response.text or "")
        if not user_match or user_match.group(1) == "0":
            logger.error("未找到有效的药丸 userId")
            return None

        csrf_token = csrf_match.group(1)
        user_id = user_match.group(1)
        logger.info(f"获取药丸 csrfToken 和 userId 成功，userId: {user_id}")
        return {"csrf_token": csrf_token, "user_id": user_id}

    def __login_with_credentials(self) -> dict:
        """使用用户名和密码登录药丸"""
        if not self._invites_username or not self._invites_password:
            return {"success": False, "error": "未配置用户名或密码"}

        headers_get = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'User-Agent': self._user_agent,
            'Upgrade-Insecure-Requests': '1'
        }
        proxies = self._get_proxies()
        response_get = self.__request_invites_with_backoff(
            "get",
            f'{self._site_url}/',
            headers=headers_get,
            proxies=proxies,
            timeout=30
        )

        if not response_get or response_get.status_code != 200:
            return {"success": False, "error": "获取初始session失败"}

        flarum_session = response_get.cookies.get('flarum_session')
        csrf_token = response_get.headers.get('x-csrf-token') or (
            re.findall(r'"csrfToken":"(.*?)"', response_get.text or "") or [None]
        )[0]

        if not flarum_session:
            return {"success": False, "error": "未获取到flarum_session"}
        if not csrf_token:
            return {"success": False, "error": "未获取到csrf token"}

        cookies_login = {'flarum_session': flarum_session}
        headers_login = {
            'Accept': '*/*',
            'Content-Type': 'application/json; charset=UTF-8',
            'Origin': self._site_url,
            'Referer': f'{self._site_url}/',
            'x-csrf-token': csrf_token,
            'User-Agent': self._user_agent
        }
        json_data_login = {
            'identification': self._invites_username,
            'password': self._invites_password,
            'remember': True,
        }

        login_response = self.__request_invites_with_backoff(
            "post",
            f'{self._site_url}/login',
            cookies=cookies_login,
            headers=headers_login,
            proxies=proxies,
            timeout=30,
            json=json_data_login
        )

        if not login_response or login_response.status_code != 200:
            status = login_response.status_code if login_response else '无响应'
            reason = self.__get_response_error_message(login_response) if login_response else '无响应'
            return {"success": False, "error": f"登录失败：HTTP {status} {reason}"}

        flarum_remember = login_response.cookies.get('flarum_remember')
        flarum_session_new = login_response.cookies.get('flarum_session')
        csrf_token_new = login_response.headers.get('X-CSRF-Token') or login_response.headers.get('x-csrf-token') or csrf_token

        if not flarum_remember or not flarum_session_new:
            return {"success": False, "error": "登录后未获取到有效Cookie"}

        try:
            login_data = login_response.json()
            user_id = login_data.get('userId')
        except Exception as e:
            logger.error(f"解析药丸登录响应失败: {e}")
            user_id = None

        if not user_id:
            cookie_str = f"flarum_remember={flarum_remember}; flarum_session={flarum_session_new}"
            homepage_state = self.__get_homepage_state(cookie_str)
            user_id = homepage_state.get("user_id") if homepage_state else None
            csrf_token_new = homepage_state.get("csrf_token") if homepage_state else csrf_token_new

        if not user_id:
            return {"success": False, "error": "登录后未获取到用户ID"}

        logger.info(f"药丸登录成功，用户ID: {user_id}")
        return {
            "success": True,
            "flarum_remember": flarum_remember,
            "flarum_session": flarum_session_new,
            "csrf_token": csrf_token_new,
            "user_id": str(user_id)
        }

    def __update_cookie_if_changed(self, new_cookie_str: str):
        """
        检查Cookie是否发生变化，如果有变化则更新配置。
        """
        try:
            if not new_cookie_str:
                return

            new_cookies = self.__parse_cookie_string(new_cookie_str)
            new_remember = new_cookies.get('flarum_remember')
            new_session = new_cookies.get('flarum_session')
            if not new_remember or not new_session:
                return

            old_cookies = self.__parse_cookie_string(self._invites_cookie or "")
            old_remember = old_cookies.get('flarum_remember')
            old_session = old_cookies.get('flarum_session')

            if new_remember != old_remember or new_session != old_session:
                self._invites_cookie = f"flarum_remember={new_remember}; flarum_session={new_session}"
                logger.info("药丸 Cookie 已更新，保存新配置")
                self.update_config(self.get_config_dict())
            else:
                logger.debug("药丸 Cookie 未发生变化，无需更新")
        except Exception as e:
            logger.error(f"更新药丸 Cookie 配置失败: {e}")

    def __save_success(self, state: dict, already_signed: bool = False):
        """保存成功签到状态并发送通知"""
        checkin_time = str((state or {}).get("lastCheckinTime") or "") or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        status_text = "已签到" if already_signed else "签到成功"
        record = {
            "site": "invites",
            "date": checkin_time,
            "status": status_text,
            "status_code": "success_already" if already_signed else "success_new",
            "money": (state or {}).get("money"),
            "totalContinuousCheckIn": (state or {}).get("totalContinuousCheckIn"),
            "lastCheckinMoney": (state or {}).get("lastCheckinMoney", 0) if not already_signed else 0,
            "failure_count": 0
        }
        self._save_history(record)
        self.save_data("invites_user_info", {"data": {"id": (state or {}).get("user_id"), "attributes": state or {}}})
        self.save_data("invites_user_info_updated_at", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

        if self._notify:
            money = self._format_money(record.get("money"))
            reward = self._format_money(record.get("lastCheckinMoney"))
            reward_text = "今日已领取奖励" if already_signed else f"获得 {reward} 个药丸奖励"
            self._send_notification(
                title=f"【✅ 药丸{status_text}】",
                text=(
                    f"📢 执行结果\n"
                    f"━━━━━━━━━━\n"
                    f"🕐 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"✨ 状态：{status_text}\n"
                    f"🎁 奖励：{reward_text}\n"
                    f"━━━━━━━━━━\n"
                    f"📊 积分统计\n"
                    f"💊 药丸：{money}\n"
                    f"📆 签到天数：{record.get('totalContinuousCheckIn')}\n"
                    f"━━━━━━━━━━"
                )
            )

    def __perform_checkin(self, user_id: str, cookie_str: str, csrf_token: str) -> bool:
        """执行实际的签到操作"""
        try:
            headers = self.__build_api_headers(csrf_token)
            cookies = self.__parse_cookie_string(cookie_str)
            if not cookies.get('flarum_remember') or not cookies.get('flarum_session'):
                logger.error("药丸 Cookie 中缺少 flarum_remember 或 flarum_session")
                return False

            before_state = self.__fetch_checkin_state(user_id, cookies, csrf_token)
            if before_state and before_state.get("canCheckin") is False and self.__is_today_checkin(before_state):
                logger.info("药丸今日已签到，跳过重复签到")
                self.__save_success(before_state, already_signed=True)
                return True

            checkin_url = f'{self._site_url}/api/checkin'
            response = self.__request_invites_with_backoff(
                "post",
                checkin_url,
                cookies=cookies,
                headers=headers,
                timeout=30
            )

            if response is None:
                return False

            if response.status_code != 200:
                error_message = self.__get_response_error_message(response)
                logger.error(f"药丸签到请求失败，状态码: {response.status_code}，原因: {error_message}")
                after_state = self.__fetch_checkin_state(user_id, cookies, csrf_token)
                if after_state and after_state.get("canCheckin") is False and self.__is_today_checkin(after_state):
                    logger.info("药丸站点状态显示今日已签到")
                    self.__save_success(after_state, already_signed=True)
                    return True
                return False

            try:
                checkin_data = response.json()
                checkin_state = self.__extract_checkin_state(checkin_data)
                if not checkin_state:
                    logger.error("药丸签到响应缺少用户状态数据")
                    return False
                if checkin_state.get("canCheckin") is not False or not self.__is_today_checkin(checkin_state):
                    logger.error(f"药丸签到响应未确认今日已签到: {checkin_state}")
                    after_state = self.__fetch_checkin_state(user_id, cookies, csrf_token)
                    if after_state and after_state.get("canCheckin") is False and self.__is_today_checkin(after_state):
                        self.__save_success(after_state, already_signed=True)
                        return True
                    return False

                logger.info("药丸签到成功")
                self.__save_success(checkin_state)
                return True
            except Exception as e:
                logger.error(f"解析药丸签到响应失败: {e}")
                logger.error(f"药丸签到响应内容: {response.text if response else 'None'}")
                after_state = self.__fetch_checkin_state(user_id, cookies, csrf_token)
                if after_state and after_state.get("canCheckin") is False and self.__is_today_checkin(after_state):
                    self.__save_success(after_state, already_signed=True)
                    return True
                return False
        except Exception as e:
            logger.error(f"执行药丸签到过程中发生异常: {e}")
            return False

    def __get_invites_auth_context(self) -> dict:
        """获取药丸统一认证上下文。"""
        if self._invites_cookie and self._invites_cookie.strip():
            flarum_remember = self.__get_remember_value(self._invites_cookie)
            if flarum_remember:
                session_state = self.__get_new_session(flarum_remember)
                if session_state:
                    cookie_str = f"flarum_remember={flarum_remember}; flarum_session={session_state['flarum_session']}"
                    cookies = self.__parse_cookie_string(cookie_str)
                    return {
                        "cookie_str": cookie_str,
                        "cookies": cookies,
                        "csrf_token": session_state["csrf_token"],
                        "user_id": session_state["user_id"],
                        "source": "remember_refresh",
                        "remember_valid": True,
                        "should_persist_cookie": True
                    }
                logger.warning("药丸 flarum_remember 已失效或无法刷新 session")
            else:
                cookies = self.__parse_cookie_string(self._invites_cookie)
                if cookies.get('flarum_session'):
                    homepage_state = self.__get_homepage_state(self._invites_cookie)
                    if homepage_state:
                        return {
                            "cookie_str": self._invites_cookie,
                            "cookies": cookies,
                            "csrf_token": homepage_state["csrf_token"],
                            "user_id": homepage_state["user_id"],
                            "source": "session_cookie",
                            "remember_valid": False,
                            "should_persist_cookie": False
                        }

        login_result = self.__login_with_credentials()
        if not login_result.get("success"):
            return {"success": False, "error": login_result.get("error", "登录失败"), "remember_valid": False}

        cookie_str = f"flarum_remember={login_result['flarum_remember']}; flarum_session={login_result['flarum_session']}"
        return {
            "cookie_str": cookie_str,
            "cookies": self.__parse_cookie_string(cookie_str),
            "csrf_token": login_result["csrf_token"],
            "user_id": login_result["user_id"],
            "source": "credentials",
            "remember_valid": True,
            "should_persist_cookie": True
        }

    def __invites_signin(self, retry_count=0, max_retries=3):
        """
        药丸签到
        """
        if hasattr(self, '_invites_signing_in') and self._invites_signing_in:
            logger.info("已有药丸签到任务在执行，跳过当前任务")
            return False

        self._invites_signing_in = True
        attempt = 0
        last_reason = "未知错误"
        try:
            if not self._invites_cookie and (not self._invites_username or not self._invites_password):
                last_reason = "未配置 Cookie，也未配置用户名密码"
                logger.error(last_reason)
                self._send_signin_failure_notification(last_reason, 0, site='invites')
                return False

            for attempt in range(max_retries + 1):
                if attempt > 0:
                    wait_seconds = 3 + random.uniform(0, 2)
                    logger.info(f"正在进行第 {attempt}/{max_retries} 次快速重试，等待 {wait_seconds:.1f} 秒...")
                    time.sleep(wait_seconds)

                auth_context = self.__get_invites_auth_context()
                if not auth_context.get("user_id"):
                    last_reason = auth_context.get("error", "药丸认证失败")
                    if "未配置" in last_reason or "登录失败" in last_reason or "403" in last_reason:
                        break
                    continue

                if auth_context.get("should_persist_cookie"):
                    self.__update_cookie_if_changed(auth_context["cookie_str"])

                logger.info(f"开始执行药丸签到，认证来源: {auth_context.get('source')}")
                if self.__perform_checkin(auth_context["user_id"], auth_context["cookie_str"], auth_context["csrf_token"]):
                    if self._invites_current_retry > 0:
                        logger.info("药丸签到重试成功，重置重试计数")
                        self._invites_current_retry = 0
                    return True

                last_reason = "药丸签到失败"

            raise Exception(last_reason)
        except Exception as e:
            reason = str(e)
            logger.error(f"药丸签到过程发生异常: {reason}")

            failure_history_record = {
                "site": "invites",
                "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "status": "签到失败",
                "status_code": "failed",
                "reason": reason,
                "failure_count": 1
            }
            self._save_history(failure_history_record)
            self._send_signin_failure_notification(reason, attempt, site='invites')

            if self._retry_count > 0 and self._invites_current_retry < self._retry_count:
                self._invites_current_retry += 1
                logger.info(f"安排第{self._invites_current_retry}次药丸定时重试，将在{self._retry_interval}分钟后重试")
                self._schedule_retry(site='invites', minutes=self._retry_interval)
            else:
                if self._retry_count > 0:
                    logger.info("药丸签到已达到最大定时重试次数，不再重试")
                self._invites_current_retry = 0
            return False
        finally:
            self._invites_signing_in = False

    def _save_history(self, record: Dict[str, Any]):
        """保存签到历史记录，确保同站点同一天只有一条记录。"""
        history = self.get_data('history') or []
        if not isinstance(history, list):
            history = [history]
        record.setdefault("site", "fengchao")
        site = record.get("site", "fengchao")
        try:
            record_date = record.get("date", "").split(" ")[0]
        except Exception:
            record_date = date.today().strftime('%Y-%m-%d')

        existing_index = -1
        for i, item in enumerate(history):
            if item.get("site", "fengchao") == site and item.get("date", "").startswith(record_date):
                existing_index = i
                break

        is_new_success = self.__get_status_meta(record).get("code") in ("success_new", "success_already")
        if existing_index != -1:
            last_record = history[existing_index]
            is_last_success = self.__get_status_meta(last_record).get("code") in ("success_new", "success_already")
            if is_new_success:
                if not is_last_success:
                    record['failure_count'] = last_record.get('failure_count', 0)
                history[existing_index] = record
                logger.info(f"更新站点 {site} 日期 {record_date} 的签到记录 (状态: {record.get('status')})")
            else:
                if not is_last_success:
                    last_record["failure_count"] = last_record.get("failure_count", 0) + 1
                    last_record["date"] = record["date"]
                    last_record["reason"] = record.get("reason", "")
                    logger.info(f"更新站点 {site} 日期 {record_date} 的失败记录，累计次数: {last_record['failure_count']}")
                else:
                    logger.info(f"站点 {site} 日期 {record_date} 已有成功记录，忽略新的失败记录")
        else:
            history.append(record)

        if self.__get_status_meta(record).get("code") == "failed":
            current = self._fengchao_current_retry if site == "fengchao" else self._invites_current_retry
            record["retry"] = {
                "enabled": self._retry_count > 0,
                "current": current,
                "max": self._retry_count,
                "interval": self._retry_interval,
                "unit": "分钟"
            }

        if self._history_days:
            try:
                expired_time = time.time() - int(self._history_days) * 24 * 60 * 60
                cleaned = []
                for item in history:
                    try:
                        if datetime.strptime(item["date"], '%Y-%m-%d %H:%M:%S').timestamp() >= expired_time:
                            cleaned.append(item)
                    except Exception:
                        cleaned.append(item)
                history = cleaned
            except Exception as e:
                logger.error(f"清理签到历史记录异常: {str(e)}")
        self.save_data("history", history)

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_service(self) -> List[Dict[str, Any]]:
        """注册插件公共服务。"""
        services = []
        if self._enabled and self._cron:
            services.append({
                "id": "ForumSignin",
                "name": "蜂巢药丸双站签到服务",
                "trigger": CronTrigger.from_crontab(self._cron),
                "func": self.__signin,
                "kwargs": {}
            })
        if self._enabled and self._timed_update_enabled:
            services.append({
                "id": "ForumSigninInfoUpdate",
                "name": "蜂巢个人信息定时更新服务",
                "trigger": CronTrigger.from_crontab(self._timed_update_cron or "0 */2 * * *"),
                "func": self.__update_user_info,
                "kwargs": {"is_scheduled_run": True}
            })
        return services

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """拼装插件配置页面。"""
        version = getattr(settings, "VERSION_FLAG", "v1")
        cron_field_component = "VCronField" if version == "v2" else "VTextField"
        return [
            {
                'component': 'VForm',
                'content': [
                    {'component': 'VCard', 'props': {'variant': 'outlined', 'class': 'mt-3'}, 'content': [
                        {'component': 'VCardTitle', 'props': {'class': 'd-flex align-center'}, 'content': [
                            {'component': 'VIcon', 'props': {'style': 'color: #1976D2;', 'class': 'mr-2'}, 'text': 'mdi-clipboard-check'},
                            {'component': 'span', 'text': '通用设置'}
                        ]},
                        {'component': 'VDivider'},
                        {'component': 'VCardText', 'content': [
                            {'component': 'VRow', 'content': [
                                {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': 'VSwitch', 'props': {'model': 'enabled', 'label': '启用插件', 'color': 'primary'}}]},
                                {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': 'VSwitch', 'props': {'model': 'notify', 'label': '开启通知', 'color': 'info'}}]},
                                {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': 'VSwitch', 'props': {'model': 'use_proxy', 'label': '使用代理', 'color': 'primary'}}]},
                                {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': 'VSwitch', 'props': {'model': 'onlyonce', 'label': '立即运行一次', 'color': 'warning'}}]}
                            ]},
                            {'component': 'VRow', 'content': [
                                {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': cron_field_component, 'props': {'model': 'cron', 'label': '签到周期', 'placeholder': '7 9 * * *', 'hint': '默认每天09:07执行，建议避开整点以降低拥塞/429概率'}}]},
                                {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': 'VTextField', 'props': {'model': 'history_days', 'label': '历史保留天数', 'type': 'number', 'placeholder': '30'}}]},
                                {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': 'VTextField', 'props': {'model': 'retry_count', 'label': '失败重试次数', 'type': 'number', 'placeholder': '0'}}]},
                                {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': 'VTextField', 'props': {'model': 'retry_interval', 'label': '重试间隔(分钟)', 'type': 'number', 'placeholder': '10', 'hint': '分钟级重试并自动加入随机抖动'}}]}
                            ]},
                            {'component': 'VRow', 'content': [
                                {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': 'VSwitch', 'props': {'model': '_update_info_now', 'label': '立即更新蜂巢个人信息', 'color': 'info'}}]}
                            ]}
                        ]}
                    ]},
                    {'component': 'VCard', 'props': {'variant': 'outlined', 'class': 'mt-3'}, 'content': [
                        {'component': 'VCardTitle', 'props': {'class': 'd-flex align-center'}, 'content': [
                            {'component': 'VIcon', 'props': {'style': 'color: #FF9800;', 'class': 'mr-2'}, 'text': 'mdi-flower'},
                            {'component': 'span', 'text': '蜂巢账号设置'}
                        ]},
                        {'component': 'VDivider'},
                        {'component': 'VCardText', 'content': [
                            {'component': 'VRow', 'content': [
                                {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [{'component': 'VTextField', 'props': {'model': 'fengchao_username', 'label': '蜂巢用户名', 'placeholder': 'pting.club 用户名', 'autocomplete': 'new-username', 'clearable': True}}]},
                                {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [{'component': 'VTextField', 'props': {'model': 'fengchao_password', 'label': '蜂巢密码', 'type': 'password', 'autocomplete': 'new-password', 'clearable': True}}]},
                                {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [{'component': 'VTextField', 'props': {'model': 'fengchao_cookie', 'label': '蜂巢Cookie(可选)', 'type': 'password', 'clearable': True}}]}
                            ]}
                        ]}
                    ]},
                    {'component': 'VCard', 'props': {'variant': 'outlined', 'class': 'mt-3'}, 'content': [
                        {'component': 'VCardTitle', 'props': {'class': 'd-flex align-center'}, 'content': [
                            {'component': 'VIcon', 'props': {'style': 'color: #9C27B0;', 'class': 'mr-2'}, 'text': 'mdi-pill'},
                            {'component': 'span', 'text': '药丸账号设置'}
                        ]},
                        {'component': 'VDivider'},
                        {'component': 'VCardText', 'content': [
                            {'component': 'VRow', 'content': [
                                {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [{'component': 'VTextField', 'props': {'model': 'invites_username', 'label': '药丸用户名', 'autocomplete': 'new-username', 'clearable': True}}]},
                                {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [{'component': 'VTextField', 'props': {'model': 'invites_password', 'label': '药丸密码', 'type': 'password', 'autocomplete': 'new-password', 'clearable': True}}]},
                                {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [{'component': 'VTextField', 'props': {'model': 'invites_cookie', 'label': '药丸Cookie', 'placeholder': '需要包含 flarum_remember，可自动刷新 flarum_session', 'type': 'password', 'autocomplete': 'new-cookie', 'clearable': True}}]}
                            ]}
                        ]}
                    ]},
                    {'component': 'VCard', 'props': {'variant': 'outlined', 'class': 'mt-3'}, 'content': [
                        {'component': 'VCardTitle', 'props': {'class': 'd-flex align-center'}, 'content': [
                            {'component': 'VIcon', 'props': {'style': 'color: #1976D2;', 'class': 'mr-2'}, 'text': 'mdi-chart-box'},
                            {'component': 'span', 'text': '蜂巢高级功能'}
                        ]},
                        {'component': 'VDivider'},
                        {'component': 'VCardText', 'content': [
                            {'component': 'VRow', 'content': [
                                {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': 'VSwitch', 'props': {'model': 'mp_push_enabled', 'label': '启用PT人生数据更新', 'color': 'primary'}}]},
                                {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': 'VTextField', 'props': {'model': 'mp_push_interval', 'label': 'PT人生推送间隔(天)', 'type': 'number', 'placeholder': '1'}}]},
                                {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': 'VSwitch', 'props': {'model': 'timed_update_enabled', 'label': '启用定时更新个人信息', 'color': 'primary'}}]},
                                {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': cron_field_component, 'props': {'model': 'timed_update_cron', 'label': '蜂巢信息更新周期', 'placeholder': '0 */2 * * *'}}]}
                            ]},
                            {'component': 'VRow', 'content': [
                                {'component': 'VCol', 'props': {'cols': 12, 'md': 6}, 'content': [{'component': 'VTextField', 'props': {'model': 'timed_update_retry_count', 'label': '信息更新失败重试次数', 'type': 'number', 'placeholder': '0'}}]},
                                {'component': 'VCol', 'props': {'cols': 12, 'md': 6}, 'content': [{'component': 'VTextField', 'props': {'model': 'timed_update_retry_interval', 'label': '信息更新重试间隔(小时)', 'type': 'number', 'placeholder': '0'}}]}
                            ]}
                        ]}
                    ]},
                    {'component': 'VCard', 'props': {'variant': 'outlined', 'class': 'mt-3'}, 'content': [
                        {'component': 'VCardTitle', 'props': {'class': 'd-flex align-center'}, 'content': [
                            {'component': 'VIcon', 'props': {'style': 'color: #1976D2;', 'class': 'mr-2'}, 'text': 'mdi-information-outline'},
                            {'component': 'span', 'text': '使用说明'}
                        ]},
                        {'component': 'VDivider'},
                        {'component': 'VCardText', 'content': [
                            {'component': 'VList', 'props': {'density': 'comfortable', 'lines': 'two'}, 'content': [
                                {'component': 'VListItem', 'content': [
                                    {'component': 'template', 'props': {'v-slot:prepend': ''}, 'content': [{'component': 'VIcon', 'props': {'color': 'primary'}, 'text': 'mdi-clock-check-outline'}]},
                                    {'component': 'VListItemTitle', 'text': '签到周期'},
                                    {'component': 'VListItemSubtitle', 'text': '支持标准cron表达式，建议避开整点（如 7 9 * * *）以降低药丸站点整点拥塞与429限流概率。默认09:07执行。'}
                                ]},
                                {'component': 'VListItem', 'content': [
                                    {'component': 'template', 'props': {'v-slot:prepend': ''}, 'content': [{'component': 'VIcon', 'props': {'color': 'info'}, 'text': 'mdi-sync'}]},
                                    {'component': 'VListItemTitle', 'text': '双站调度'},
                                    {'component': 'VListItemSubtitle', 'text': '一次定时触发依次执行蜂巢与药丸签到，两站异常隔离互不影响，各自独立重试与历史记录。'}
                                ]},
                                {'component': 'VListItem', 'content': [
                                    {'component': 'template', 'props': {'v-slot:prepend': ''}, 'content': [{'component': 'VIcon', 'props': {'color': 'warning'}, 'text': 'mdi-flower'}]},
                                    {'component': 'VListItemTitle', 'text': '蜂巢账号'},
                                    {'component': 'VListItemSubtitle', 'text': '填写 pting.club 用户名和密码，登录后自动获取Cookie；可选填Cookie优先复用。'}
                                ]},
                                {'component': 'VListItem', 'content': [
                                    {'component': 'template', 'props': {'v-slot:prepend': ''}, 'content': [{'component': 'VIcon', 'props': {'style': 'color: #9C27B0;'}, 'text': 'mdi-pill'}]},
                                    {'component': 'VListItemTitle', 'text': '药丸账号'},
                                    {'component': 'VListItemSubtitle', 'text': '填写 invites.fun 用户名和密码；Cookie选填（需含 flarum_remember，会自动刷新 flarum_session 并持久化）。Cookie优先，失败回退账号登录。'}
                                ]},
                                {'component': 'VListItem', 'content': [
                                    {'component': 'template', 'props': {'v-slot:prepend': ''}, 'content': [{'component': 'VIcon', 'props': {'color': 'success'}, 'text': 'mdi-refresh'}]},
                                    {'component': 'VListItemTitle', 'text': '失败重试'},
                                    {'component': 'VListItemSubtitle', 'text': '重试间隔为分钟级并自动加入随机抖动，避免重试集中在整点；药丸站点对429/拥塞状态码单独指数退避。'}
                                ]},
                                {'component': 'VListItem', 'content': [
                                    {'component': 'template', 'props': {'v-slot:prepend': ''}, 'content': [{'component': 'VIcon', 'props': {'color': 'primary'}, 'text': 'mdi-chart-box'}]},
                                    {'component': 'VListItemTitle', 'text': '蜂巢高级功能'},
                                    {'component': 'VListItemSubtitle', 'text': 'PT人生数据推送与定时更新个人信息仅服务蜂巢站；药丸站无对应接口。'}
                                ]}
                            ]}
                        ]}
                    ]}
                ]
            }
        ], {
            "enabled": False,
            "notify": True,
            "cron": "7 9 * * *",
            "onlyonce": False,
            "history_days": 30,
            "retry_count": 0,
            "retry_interval": 10,
            "use_proxy": True,
            "_update_info_now": False,
            "fengchao_username": "",
            "fengchao_password": "",
            "fengchao_cookie": "",
            "invites_username": "",
            "invites_password": "",
            "invites_cookie": "",
            "mp_push_enabled": False,
            "mp_push_interval": 1,
            "timed_update_enabled": False,
            "timed_update_cron": "0 */2 * * *",
            "timed_update_retry_count": 0,
            "timed_update_retry_interval": 0
        }

    def get_page(self) -> List[dict]:
        """构建插件详情页面，展示双站概览与签到历史。"""
        history = self.get_data('history') or []
        if not isinstance(history, list):
            history = [history]
        history = sorted(history, key=lambda x: x.get("date", ""), reverse=True)[:int(self._history_days or 30)]

        fengchao_user_info = self.get_data("fengchao_user_info") or {}
        invites_user_info = self.get_data("invites_user_info") or self.get_data("user_info") or {}
        updated_at = {
            "fengchao": self.get_data("fengchao_user_info_updated_at") or "—",
            "invites": self.get_data("invites_user_info_updated_at") or "—"
        }
        site_names = {"fengchao": "蜂巢", "invites": "药丸"}
        site_icons = {"fengchao": "mdi-flower", "invites": "mdi-pill"}
        site_colors = {"fengchao": "#FF9800", "invites": "#9C27B0"}
        site_points = {"fengchao": "花粉", "invites": "药丸"}
        site_history = {
            "fengchao": [item for item in history if item.get("site", "fengchao") == "fengchao"],
            "invites": [item for item in history if item.get("site") == "invites"]
        }
        today_str = datetime.now().strftime('%Y-%m-%d')
        frost_style = 'background-color: rgba(var(--v-theme-surface), 0.75); backdrop-filter: blur(5px); -webkit-backdrop-filter: blur(5px); border: 1px solid rgba(var(--v-theme-on-surface), 0.12); border-radius: 8px; box-sizing: border-box;'

        def user_attrs(user_info: dict) -> dict:
            if not isinstance(user_info, dict):
                return {}
            attrs = user_info.get("data", {}).get("attributes", {}) or {}
            return attrs if isinstance(attrs, dict) and attrs else user_info

        def user_id(user_info: dict) -> str:
            if not isinstance(user_info, dict):
                return "—"
            return str(user_info.get("data", {}).get("id") or user_info.get("user_id") or user_info.get("id") or "—")

        def stat_block(icon: str, color: str, value: Any, label: str) -> dict:
            value_text = str(value) if value not in (None, "") else "—"
            # 用 outline 替代 border，outline 不占盒模型空间，彻底避免溢出
            stat_style = 'background-color: rgba(var(--v-theme-surface), 0.75); backdrop-filter: blur(5px); -webkit-backdrop-filter: blur(5px); outline: 1px solid rgba(var(--v-theme-on-surface), 0.12); border-radius: 8px; box-sizing: border-box;'
            return {'component': 'VCol', 'props': {'cols': 6, 'md': 6, 'class': 'pa-2'}, 'content': [
                {'component': 'div', 'props': {'class': 'text-center pa-1 d-flex flex-column justify-center', 'style': stat_style}, 'content': [
                    {'component': 'div', 'props': {'class': 'd-flex justify-center align-center mb-1'}, 'content': [
                        {'component': 'VIcon', 'props': {'size': 'large', 'style': f'color: {color};', 'class': 'mr-1'}, 'text': icon},
                        {'component': 'span', 'props': {'class': 'text-h5 font-weight-bold'}, 'text': value_text}
                    ]},
                    {'component': 'div', 'props': {'class': 'text-caption text-medium-emphasis'}, 'text': label}
                ]}
            ]}

        def overview_card(site: str, title: str, user_info: dict) -> dict:
            attrs = user_attrs(user_info)
            records = site_history.get(site, [])
            latest_record = records[0] if records else {}
            today_record = next((item for item in records if item.get("date", "").startswith(today_str)), {})
            status_meta = self.__get_status_meta(today_record) if today_record else {"code": "unknown", "label": "今日未签", "color": "#9E9E9E", "icon": "mdi-help-circle"}
            last_reward = latest_record.get("lastCheckinMoney", attrs.get("lastCheckinMoney", 0)) if latest_record else attrs.get("lastCheckinMoney", 0)
            display_name = attrs.get('displayName') or attrs.get('username') or attrs.get('nickname') or '—'
            avatar_url = attrs.get('avatarUrl') or ""
            unread_count = attrs.get('unreadNotificationCount') or 0
            try:
                unread_count = int(unread_count)
            except (TypeError, ValueError):
                unread_count = 0
            can_checkin = attrs.get('canCheckin')
            if can_checkin is False:
                checkin_chip = {"label": "今日已签", "color": "#4CAF50", "icon": "mdi-check-circle"}
            elif can_checkin is True:
                checkin_chip = {"label": "待签到", "color": "#FB8C00", "icon": "mdi-calendar-clock"}
            else:
                checkin_chip = {"label": "签到状态 —", "color": "#9E9E9E", "icon": "mdi-help-circle"}
            follower_count = attrs.get('followerCount') or 0
            try:
                follower_count = int(follower_count)
            except (TypeError, ValueError):
                follower_count = 0
            return {'component': 'VCol', 'props': {'cols': 12, 'md': 4, 'class': 'd-flex'}, 'content': [
                {'component': 'VCard', 'props': {'variant': 'outlined', 'class': 'h-100 w-100 pa-0', 'style': frost_style}, 'content': [
                    {'component': 'VCardTitle', 'props': {'class': 'd-flex align-center py-1 px-2'}, 'content': [
                        {'component': 'VIcon', 'props': {'style': f'color: {site_colors[site]};', 'class': 'mr-2'}, 'text': site_icons[site]},
                        {'component': 'span', 'props': {'class': 'text-subtitle-1 font-weight-bold'}, 'text': title},
                        {'component': 'VSpacer'},
                        {'component': 'VChip', 'props': {'style': f"background-color: {status_meta['color']}; color: white;", 'size': 'small', 'variant': 'elevated'}, 'content': [
                            {'component': 'VIcon', 'props': {'start': True, 'style': 'color: white;', 'size': 'small'}, 'text': status_meta['icon']},
                            {'component': 'span', 'text': status_meta['label']}
                        ]}
                    ]},
                    {'component': 'VDivider'},
                    {'component': 'VCardText', 'props': {'class': 'pa-1', 'style': 'box-sizing: border-box;'}, 'content': [
                        {'component': 'div', 'props': {'class': 'd-flex align-center pa-2', 'style': frost_style}, 'content': [
                            {'component': 'VAvatar', 'props': {'size': 40, 'class': 'mr-2'}, 'content': [
                                {'component': 'VImg', 'props': {'src': avatar_url, 'alt': display_name}}
                            ]} if avatar_url else {'component': 'VAvatar', 'props': {'size': 40, 'color': '#ECEFF1', 'class': 'mr-2'}, 'content': [
                                {'component': 'VIcon', 'props': {'color': '#90A4AE', 'size': 'small'}, 'text': 'mdi-account'}
                            ]},
                            {'component': 'div', 'props': {'class': 'flex-grow-1'}, 'content': [
                                {'component': 'div', 'props': {'class': 'd-flex align-center'}, 'content': [
                                    {'component': 'span', 'props': {'class': 'text-h6 font-weight-bold'}, 'text': display_name},
                                    {'component': 'VBadge', 'props': {'content': unread_count, 'color': 'error', 'inline': True, 'class': 'ml-2'}, 'content': [
                                        {'component': 'VIcon', 'props': {'size': 'small', 'color': 'error'}, 'text': 'mdi-bell'}
                                    ]} if unread_count > 0 else {'component': 'span', 'text': ''}
                                ]},
                                {'component': 'div', 'props': {'class': 'text-body-1 text-medium-emphasis'}, 'text': f"UID：{user_id(user_info)} · 更新：{updated_at.get(site, '—')}"}
                            ]}
                        ]},
                        {'component': 'VRow', 'props': {'no-gutters': True}, 'content': [
                            stat_block(site_icons[site], site_colors[site], self._format_money(attrs.get('money', latest_record.get('money'))), f"当前{site_points[site]}"),
                            stat_block('mdi-clipboard-check', '#1976D2', attrs.get('totalContinuousCheckIn', latest_record.get('totalContinuousCheckIn', '—')), '连续签到'),
                            stat_block('mdi-gift', '#FF8F00', self._format_money(last_reward), '最近奖励'),
                            stat_block('mdi-comment-text-outline', '#26A69A', attrs.get('discussionCount', '—'), '主题数')
                        ]}
                    ]}
                ]}
            ]}

        def day_status(day_str: str) -> dict:
            """返回某天双站签到状态 {fengchao: code, invites: code}，code 取 success_new/success_already/failed/None。"""
            result = {"fengchao": None, "invites": None}
            for item in history:
                if not item.get("date", "").startswith(day_str):
                    continue
                site = item.get("site", "fengchao")
                if site in result and result[site] is None:
                    meta = self.__get_status_meta(item)
                    # 失败记录不覆盖当天已有成功记录
                    if meta["code"] != "failed" or result[site] is None:
                        if meta["code"] != "failed":
                            result[site] = meta["code"]
                        elif result[site] is None:
                            result[site] = "failed"
            return result

        def day_color(statuses: dict) -> str:
            fc, iv = statuses["fengchao"], statuses["invites"]
            fc_ok = fc in ("success_new", "success_already")
            iv_ok = iv in ("success_new", "success_already")
            fc_fail = fc == "failed"
            iv_fail = iv == "failed"
            if fc_ok and iv_ok:
                return "#2E7D32"  # 双站都成功 深绿
            if fc_ok and iv is None:
                return "#FF9800"  # 仅蜂巢 橙
            if iv_ok and fc is None:
                return "#9C27B0"  # 仅药丸 紫
            if fc_ok and iv_fail:
                return "#FF8F00"  # 蜂巢成药丸败 琥珀
            if iv_ok and fc_fail:
                return "#7E57C2"  # 药丸成蜂巢败 浅紫
            if fc_fail and iv_fail:
                return "#F44336"  # 双站失败 红
            if fc_fail or iv_fail:
                return "#EF5350"  # 单站失败 浅红
            return "transparent"  # 无数据

        today = datetime.now()
        year, month = today.year, today.month
        import calendar as _calendar
        cal_days = _calendar.monthcalendar(year, month)
        weekdays = ["一", "二", "三", "四", "五", "六", "日"]
        cal_rows = [{'component': 'tr', 'content': [{'component': 'th', 'props': {'class': 'text-center text-caption font-weight-bold pa-1'}, 'text': w} for w in weekdays]}]
        for week in cal_days:
            cells = []
            for idx, day in enumerate(week):
                if day == 0:
                    cells.append({'component': 'td', 'props': {'class': 'text-center pa-0', 'style': 'height: 24px;'}, 'text': ''})
                else:
                    day_str = f"{year:04d}-{month:02d}-{day:02d}"
                    statuses = day_status(day_str)
                    fc_ok = statuses["fengchao"] in ("success_new", "success_already")
                    iv_ok = statuses["invites"] in ("success_new", "success_already")
                    is_today = day_str == today.strftime("%Y-%m-%d")
                    border = "border: 2px solid #1976D2;" if is_today else ""
                    day_icons = []
                    if fc_ok:
                        day_icons.append({'component': 'VIcon', 'props': {'size': 12, 'color': '#FF9800'}, 'text': 'mdi-flower'})
                    if iv_ok:
                        day_icons.append({'component': 'VIcon', 'props': {'size': 12, 'color': '#9C27B0'}, 'text': 'mdi-pill'})
                    cells.append({'component': 'td', 'props': {'class': 'text-center pa-0', 'style': f"height: 24px; {border} border-radius: 4px;"}, 'content': [
                        {'component': 'div', 'props': {'class': 'text-caption font-weight-bold'}, 'text': str(day)},
                        {'component': 'div', 'props': {'class': 'd-flex justify-center ga-1', 'style': 'height: 14px; margin-top: 1px;'}, 'content': day_icons}
                    ]})
            cal_rows.append({'component': 'tr', 'content': cells})

        calendar_card = {'component': 'VCard', 'props': {'variant': 'outlined', 'class': 'h-100 w-100 pa-0', 'style': frost_style}, 'content': [
            {'component': 'VCardTitle', 'props': {'class': 'd-flex align-center'}, 'content': [
                {'component': 'VIcon', 'props': {'color': 'primary', 'class': 'mr-2'}, 'text': 'mdi-calendar-month'},
                {'component': 'span', 'props': {'class': 'text-h6 font-weight-bold'}, 'text': f"签到日历（{year}/{month:02d}）"}
            ]},
            {'component': 'VDivider'},
            {'component': 'VCardText', 'props': {'class': 'pa-1'}, 'content': [
                {'component': 'VTable', 'props': {'density': 'compact', 'class': 'text-center'}, 'content': [
                    {'component': 'tbody', 'content': cal_rows}
                ]}
            ]}
        ]}

        components = [
            {'component': 'VRow', 'props': {'class': 'mb-4', 'align': 'stretch'}, 'content': [
                overview_card("fengchao", "蜂巢站", fengchao_user_info),
                overview_card("invites", "药丸站", invites_user_info),
                {'component': 'VCol', 'props': {'cols': 12, 'md': 4, 'class': 'd-flex'}, 'content': [
                    calendar_card
                ]}
            ]}
        ]

        rows = []
        for record in history:
            site = record.get("site", "fengchao")
            status_meta = self.__get_status_meta(record)
            failure_count = record.get('failure_count', 0)
            retry = record.get('retry', {})
            retry_text = ""
            if status_meta["code"] == "failed" and retry.get('enabled') and retry.get('current', 0) > 0:
                retry_text = f"将在{retry.get('interval', self._retry_interval)}{retry.get('unit', '分钟')}后重试 ({retry.get('current', 0)}/{retry.get('max', self._retry_count)})"
            point_name = site_points.get(site, "积分")
            point_icon = site_icons.get(site, "mdi-web")
            reward_text = '—'
            if status_meta["code"] == "success_new" and record.get('lastCheckinMoney', 0):
                reward_text = f"{self._format_money(record.get('lastCheckinMoney', 0))}{point_name}"
            elif status_meta["code"] == "success_already":
                reward_text = "已领取"
            rows.append({
                'component': 'tr',
                'content': [
                    {'component': 'td', 'content': [{'component': 'VChip', 'props': {'size': 'small', 'variant': 'tonal'}, 'content': [
                        {'component': 'VIcon', 'props': {'start': True, 'size': 'small', 'style': f"color: {site_colors.get(site, '#607D8B')};"}, 'text': point_icon},
                        {'component': 'span', 'text': site_names.get(site, site)}
                    ]}]},
                    {'component': 'td', 'props': {'class': 'text-caption'}, 'text': record.get("date", "")},
                    {'component': 'td', 'content': [{'component': 'VChip', 'props': {'style': f"background-color: {status_meta['color']}; color: white;", 'size': 'small', 'variant': 'elevated'}, 'content': [
                        {'component': 'VIcon', 'props': {'start': True, 'style': 'color: white;', 'size': 'small'}, 'text': status_meta['icon']},
                        {'component': 'span', 'text': status_meta['label']}
                    ]}]},
                    {'component': 'td', 'text': str(failure_count) if failure_count > 0 else '—'},
                    {'component': 'td', 'content': [{'component': 'div', 'props': {'class': 'd-flex align-center'}, 'content': [
                        {'component': 'VIcon', 'props': {'style': f"color: {site_colors.get(site, '#607D8B')};", 'class': 'mr-1'}, 'text': point_icon},
                        {'component': 'span', 'text': self._format_money(record.get('money'))}
                    ]}]},
                    {'component': 'td', 'content': [{'component': 'div', 'props': {'class': 'd-flex align-center'}, 'content': [
                        {'component': 'VIcon', 'props': {'style': 'color: #1976D2;', 'class': 'mr-1'}, 'text': 'mdi-clipboard-check'},
                        {'component': 'span', 'text': record.get('totalContinuousCheckIn', '—')}
                    ]}]},
                    {'component': 'td', 'content': [{'component': 'div', 'props': {'class': 'd-flex align-center'}, 'content': [
                        {'component': 'VIcon', 'props': {'style': 'color: #FF8F00;', 'class': 'mr-1'}, 'text': 'mdi-gift'},
                        {'component': 'span', 'text': reward_text}
                    ]}]},
                    {'component': 'td', 'props': {'class': 'text-caption'}, 'text': record.get('reason') or retry_text or '—'}
                ]
            })

        if not rows:
            components.append({'component': 'VAlert', 'props': {'type': 'info', 'variant': 'tonal', 'text': '暂无双站签到记录，请先配置蜂巢/药丸账号并启用插件', 'class': 'mb-2', 'prepend-icon': 'mdi-information'}})
            return components

        components.extend([
            {'component': 'VCard', 'props': {'variant': 'outlined', 'class': 'mb-4'}, 'content': [
                {'component': 'VCardTitle', 'props': {'class': 'd-flex align-center'}, 'content': [
                    {'component': 'VIcon', 'props': {'style': 'color: #9C27B0;', 'class': 'mr-2'}, 'text': 'mdi-history'},
                    {'component': 'span', 'props': {'class': 'text-h6 font-weight-bold'}, 'text': '签到历史'}
                ]},
                {'component': 'VDivider'},
                {'component': 'VCardText', 'props': {'class': 'pa-0 pa-md-2'}, 'content': [
                    {'component': 'VResponsive', 'content': [
                        {'component': 'VTable', 'props': {'hover': True, 'density': 'comfortable'}, 'content': [
                            {'component': 'thead', 'content': [{'component': 'tr', 'content': [
                                {'component': 'th', 'text': '站点'},
                                {'component': 'th', 'text': '时间'},
                                {'component': 'th', 'text': '状态'},
                                {'component': 'th', 'text': '失败次数'},
                                {'component': 'th', 'text': '当前积分'},
                                {'component': 'th', 'text': '签到天数'},
                                {'component': 'th', 'text': '奖励'},
                                {'component': 'th', 'text': '说明'}
                            ]}]},
                            {'component': 'tbody', 'content': rows}
                        ]}
                    ]}
                ]}
            ]},
            {'component': 'style', 'text': ".v-table { border-radius: 8px; overflow: hidden; } .v-table th { background-color: rgba(var(--v-theme-primary), 0.05); color: rgb(var(--v-theme-primary)); font-weight: 600; }"}
        ])
        return components

    def stop_service(self):
        """退出插件。"""
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown()
                self._scheduler = None
        except Exception as e:
            logger.error("退出插件失败：%s" % str(e))
