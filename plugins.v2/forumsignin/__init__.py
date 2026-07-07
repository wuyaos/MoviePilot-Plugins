import random
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import NotificationType

from .fengchao import FengchaoService
from .invites import InvitesService
from .models import ForumSigninConfig, PluginCallbacks
from .ui import build_form, build_page, get_status_meta


class ForumSignin(_PluginBase):
    # 插件名称
    plugin_name = "论坛签到"
    # 插件描述
    plugin_desc = "论坛站点签到（蜂巢 pting.club + 药丸 invites.fun），单插件双站调度，支持 Cookie/账号登录、失败重试与历史记录。"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/signin.png"
    # 插件版本
    plugin_version = "1.0.5"
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
    _scheduler: Optional[BackgroundScheduler] = None
    _active_enabled = None
    _active_cron = None
    _active_timed_update_enabled = None
    _active_timed_update_cron = None

    def init_plugin(self, config: dict = None):
        """插件初始化"""
        self.config = ForumSigninConfig.from_config(config, self.get_data)
        self._sync_attrs_from_config()
        self._init_services()

        if not self._scheduler or not self._scheduler.running:
            self.stop_service()
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            logger.info("双站签到调度器未运行，已创建新的实例。")
            self._active_enabled = not self._enabled

        signin_job_id = "forumsignin_dual_signin_cron"
        signin_config_changed = self._enabled != self._active_enabled or self.config.cron != self._active_cron
        if signin_config_changed:
            logger.info("检测到双站签到任务配置变更，正在更新...")
            if self._scheduler.get_job(signin_job_id):
                self._scheduler.remove_job(signin_job_id)
                logger.info("已移除旧的双站签到周期任务。")
            if self._enabled and self.config.cron:
                self._scheduler.add_job(
                    func=self.__signin,
                    trigger=CronTrigger.from_crontab(self.config.cron),
                    name="蜂巢药丸双站签到",
                    id=signin_job_id
                )
                logger.info(f"已添加新的双站签到周期任务，周期：{self.config.cron}")

        info_update_job_id = "forumsignin_fengchao_info_update_cron"
        info_update_config_changed = (
            self._enabled != self._active_enabled or
            self.config.timed_update_enabled != self._active_timed_update_enabled or
            self.config.timed_update_cron != self._active_timed_update_cron
        )
        if info_update_config_changed:
            logger.info("检测到蜂巢个人信息更新任务配置变更，正在更新...")
            if self._scheduler.get_job(info_update_job_id):
                self._scheduler.remove_job(info_update_job_id)
                logger.info("已移除旧的蜂巢个人信息更新周期任务。")
            if self._enabled and self.config.timed_update_enabled:
                cron_to_use = self.config.timed_update_cron if self.config.timed_update_cron else "0 */2 * * *"
                self._scheduler.add_job(
                    func=self.__update_user_info,
                    kwargs={'is_scheduled_run': True},
                    trigger=CronTrigger.from_crontab(cron_to_use),
                    name="蜂巢个人信息定时更新",
                    id=info_update_job_id
                )
                logger.info(f"已添加新的蜂巢个人信息更新周期任务，周期：{cron_to_use}")

        if self.config.update_info_now:
            logger.info("立即更新蜂巢个人信息")
            self._scheduler.add_job(
                func=self.__update_user_info,
                trigger='date',
                run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3),
                name="蜂巢个人信息更新"
            )
            self.config.update_info_now = False
            self.update_config(self.get_config_dict())

        if self.config.onlyonce:
            logger.info("双站签到插件启动，立即运行一次")
            self._scheduler.add_job(
                func=self.__signin,
                trigger='date',
                run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3),
                name="蜂巢药丸双站签到（单次）"
            )
            self.config.onlyonce = False
            self.update_config(self.get_config_dict())

        if self._scheduler and not self._scheduler.running and self._scheduler.get_jobs():
            self._scheduler.print_jobs()
            self._scheduler.start()

        self._active_enabled = self._enabled
        self._active_cron = self.config.cron
        self._active_timed_update_enabled = self.config.timed_update_enabled
        self._active_timed_update_cron = self.config.timed_update_cron
        self._sync_attrs_from_config()

    def _sync_attrs_from_config(self):
        self._enabled = self.config.enabled
        self._notify = self.config.notify
        self._cron = self.config.cron
        self._onlyonce = self.config.onlyonce
        self._update_info_now = self.config.update_info_now
        self._history_days = self.config.history_days
        self._retry_count = self.config.retry_count
        self._retry_interval = self.config.retry_interval
        self._use_proxy = self.config.use_proxy
        self._fengchao_enabled = self.config.fengchao_enabled
        self._invites_enabled = self.config.invites_enabled

    def _init_services(self):
        callbacks = PluginCallbacks(
            save_data=self.save_data,
            get_data=self.get_data,
            update_config=self.update_config,
            post_message=self.post_message,
            save_history=self._save_history,
            schedule_retry=self._schedule_retry,
            get_proxy_url=self._get_proxy_url,
            send_notification=self._send_notification,
            send_signin_failure_notification=self._send_signin_failure_notification,
            schedule_info_update_retry=self._schedule_info_update_retry,
            send_info_update_failure_notification=self._send_info_update_failure_notification,
            persist_config=lambda: self.update_config(self.get_config_dict())
        )
        self._fengchao_service = FengchaoService(self.config, callbacks)
        self._invites_service = InvitesService(self.config, callbacks)

    def get_config_dict(self):
        """获取当前配置字典，用于更新"""
        return self.config.to_config_dict()

    def _send_notification(self, title, text):
        """发送通知"""
        if self.config.notify:
            self.post_message(mtype=NotificationType.SiteMessage, title=title, text=text)

    def _get_proxy_url(self):
        """获取代理设置"""
        if not self.config.use_proxy:
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

    def _schedule_retry(self, site: str = "invites", minutes=None):
        """安排分钟级签到重试任务，并添加随机抖动避免重试集中在整点。"""
        if not self._scheduler:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
        retry_interval = minutes if minutes is not None else self.config.retry_interval
        jitter_seconds = random.randint(30, 180)
        next_run_time = datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(
            minutes=retry_interval,
            seconds=jitter_seconds
        )
        current = self.config.fengchao_current_retry if site == "fengchao" else self.config.invites_current_retry
        site_name = "蜂巢" if site == "fengchao" else "药丸"
        func = self.__fengchao_signin if site == "fengchao" else self.__invites_signin
        self._scheduler.add_job(
            func=func,
            trigger='date',
            run_date=next_run_time,
            name=f"{site_name}签到重试 ({current}/{self.config.retry_count})"
        )
        logger.info(
            f"{site_name}签到失败，将在{retry_interval}分钟后重试，随机抖动{jitter_seconds}秒，"
            f"当前重试次数: {current}/{self.config.retry_count}"
        )
        if not self._scheduler.running:
            self._scheduler.start()

    def _send_signin_failure_notification(self, reason: str, attempt: int, site: str = "fengchao"):
        """发送签到失败通知"""
        if not self.config.notify:
            return
        current = self.config.fengchao_current_retry if site == "fengchao" else self.config.invites_current_retry
        site_name = "蜂巢" if site == "fengchao" else "药丸"
        remaining_retries = self.config.retry_count - current
        retry_info = ""
        if self.config.retry_count > 0 and remaining_retries > 0:
            retry_info = (
                f"🔄 重试信息\n"
                f"• 将在 {self.config.retry_interval} 分钟后进行下一次定时重试（含随机抖动）\n"
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
        retry_interval_hours = self.config.timed_update_retry_interval
        if retry_interval_hours <= 0:
            logger.warning("信息更新重试间隔配置为0或负数，不安排重试")
            return
        next_run_time = datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(hours=retry_interval_hours)
        self._scheduler.add_job(
            func=self.__update_user_info,
            kwargs={'is_scheduled_run': True},
            trigger='date',
            run_date=next_run_time,
            name=f"蜂巢信息更新重试 ({self.config.timed_update_current_retry}/{self.config.timed_update_retry_count})"
        )
        logger.info(
            f"蜂巢信息更新失败，将在{retry_interval_hours}小时后重试，"
            f"当前重试次数: {self.config.timed_update_current_retry}/{self.config.timed_update_retry_count}"
        )
        if not self._scheduler.running:
            self._scheduler.start()

    def _send_info_update_failure_notification(self, reason: str):
        """发送蜂巢信息更新失败通知"""
        if not self.config.notify:
            return
        remaining_retries = self.config.timed_update_retry_count - self.config.timed_update_current_retry
        retry_info = ""
        if self.config.timed_update_retry_count > 0 and remaining_retries > 0:
            retry_info = (
                f"🔄 重试信息\n"
                f"• 将在 {self.config.timed_update_retry_interval} 小时后进行下一次定时重试\n"
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
            if not self.config.fengchao_enabled:
                logger.info("蜂巢签到未启用，跳过")
                results["fengchao"] = True
            else:
                try:
                    logger.info("开始执行蜂巢签到")
                    results["fengchao"] = self.__fengchao_signin(retry_count=retry_count, max_retries=max_retries)
                except Exception as e:
                    logger.error(f"蜂巢签到异常已隔离，不影响药丸签到: {e}")
                    results["fengchao"] = False

            if not self.config.invites_enabled:
                logger.info("药丸签到未启用，跳过")
                results["invites"] = True
            else:
                try:
                    logger.info("开始执行药丸签到")
                    results["invites"] = self.__invites_signin(retry_count=retry_count, max_retries=max_retries)
                except Exception as e:
                    logger.error(f"药丸签到异常已隔离: {e}")
                    results["invites"] = False
            return bool(results.get("fengchao") or results.get("invites"))
        finally:
            self._dual_signing_in = False

    def __fengchao_signin(self, retry_count=0, max_retries=3):
        return self._fengchao_service.signin(retry_count=retry_count, max_retries=max_retries)

    def __invites_signin(self, retry_count=0, max_retries=3):
        return self._invites_service.signin(retry_count=retry_count, max_retries=max_retries)

    def __update_user_info(self, is_scheduled_run: bool = False):
        return self._fengchao_service.update_user_info(is_scheduled_run=is_scheduled_run)

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

        is_new_success = get_status_meta(record).get("code") in ("success_new", "success_already")
        if existing_index != -1:
            last_record = history[existing_index]
            is_last_success = get_status_meta(last_record).get("code") in ("success_new", "success_already")
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

        if get_status_meta(record).get("code") == "failed":
            current = self.config.fengchao_current_retry if site == "fengchao" else self.config.invites_current_retry
            record["retry"] = {
                "enabled": self.config.retry_count > 0,
                "current": current,
                "max": self.config.retry_count,
                "interval": self.config.retry_interval,
                "unit": "分钟"
            }

        if self.config.history_days:
            try:
                expired_time = time.time() - int(self.config.history_days) * 24 * 60 * 60
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
        if self._enabled and self.config.cron:
            services.append({
                "id": "ForumSignin",
                "name": "蜂巢药丸双站签到服务",
                "trigger": CronTrigger.from_crontab(self.config.cron),
                "func": self.__signin,
                "kwargs": {}
            })
        if self._enabled and self.config.timed_update_enabled:
            services.append({
                "id": "ForumSigninInfoUpdate",
                "name": "蜂巢个人信息定时更新服务",
                "trigger": CronTrigger.from_crontab(self.config.timed_update_cron or "0 */2 * * *"),
                "func": self.__update_user_info,
                "kwargs": {"is_scheduled_run": True}
            })
        return services

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return build_form()

    def get_page(self) -> List[dict]:
        return build_page(self.get_data, self.config)

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
