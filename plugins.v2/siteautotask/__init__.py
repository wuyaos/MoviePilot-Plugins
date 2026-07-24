import json
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.db.site_oper import SiteOper
from app.helper.sites import SitesHelper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import NotificationType
from app.schemas.types import EventType
from app.utils.timer import TimerUtils

from .sites import load_site_classes, get_site_handler
from .utils.feedback import NotificationIcons, detect_reward_type, build_feedback

try:
    from ruamel.yaml import CommentedMap
except Exception:
    CommentedMap = None


class SiteAutoTask(_PluginBase):
    # 插件名称
    plugin_name = "站点自动任务"
    # 插件描述
    plugin_desc = "站点周期任务合集：签到、喊话、领勋章、抽奖、兑换、任务申领，并解析喊话反馈奖励。合并自 ptautotask 与 groupchatzone。"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/ptautotask.png"
    # 插件版本
    plugin_version = "1.0.0"
    # 插件作者
    plugin_author = "wuyaos"
    # 作者主页
    author_url = "https://github.com/wuyaos"
    # 插件配置项 ID 前缀
    plugin_config_prefix = "siteautotask_"
    # 加载顺序
    plugin_order = 24
    # 可使用的用户级别
    auth_level = 2

    # —— 私有属性 ——
    _enabled = False
    _cron = None
    _onlyonce = False
    _notify = False
    _history_days = 30
    _use_proxy = False
    _get_feedback = True
    _feedback_timeout = 5
    _retry_count = 2
    _retry_interval = 10
    _retry_notify = False
    _chat_sites: List[str] = []
    _task_switches: Dict[str, bool] = {}
    _interval_cnt = 2
    _start_time: Optional[int] = None
    _end_time: Optional[int] = None

    # —— 织梦独立调度 ——
    _zm_mail_time: Optional[str] = None
    _last_zm_execution_time: Optional[datetime] = None
    _zm_execution_cooldown = 600
    _zm_interval = 60

    # —— 精细重试 ——
    _failed_messages: List[Dict] = []
    _current_retry_count = 0
    _next_retry_time: Optional[datetime] = None
    _failed_messages_max = 100

    # —— 运行态 ——
    _scheduler: Optional[BackgroundScheduler] = None
    _lock: Optional[threading.Lock] = None
    _zm_lock: Optional[threading.Lock] = None
    _retry_lock: Optional[threading.Lock] = None
    _running = False
    _auto_task_in = False

    # —— 站点信息缓存 ——
    _site_classes: List[dict] = []
    _handler_classes: List[type] = []

    # —— 站点助手 ——
    sites: SitesHelper = None
    siteoper: SiteOper = None

    # 数据页 key
    _data_key = "history"

    def init_plugin(self, config: Optional[dict] = None):
        self._lock = threading.Lock()
        self._zm_lock = threading.Lock()
        self._retry_lock = threading.Lock()
        self.sites = SitesHelper()
        self.siteoper = SiteOper()

        # 加载站点类（缓存）
        if not self._site_classes:
            self._site_classes = load_site_classes()
            self._handler_classes = [s["handler_cls"] for s in self._site_classes if s.get("handler_cls")]

        # 停止现有任务
        self.stop_service()

        if config:
            self._enabled = config.get("enabled", False)
            self._cron = config.get("cron", "30 9,21 * * *")
            self._onlyonce = config.get("onlyonce", False)
            self._notify = config.get("notify", False)
            self._history_days = config.get("history_days", 30)
            self._use_proxy = config.get("use_proxy", False)
            self._get_feedback = config.get("get_feedback", True)
            self._feedback_timeout = int(config.get("feedback_timeout", 5))
            self._retry_count = int(config.get("retry_count", 2))
            self._retry_interval = int(config.get("retry_interval", 10))
            self._retry_notify = config.get("retry_notify", False)
            self._chat_sites = config.get("chat_sites", [])
            self._task_switches = config.get("task_switches", {}) or {}
            self._interval_cnt = int(config.get("interval_cnt", 2))

            # 织梦状态恢复
            self._zm_mail_time = config.get("zm_mail_time")
            last_zm = config.get("last_zm_execution_time")
            if last_zm and isinstance(last_zm, str):
                try:
                    self._last_zm_execution_time = datetime.fromisoformat(last_zm)
                except ValueError:
                    self._last_zm_execution_time = None
            self._zm_execution_cooldown = int(config.get("zm_execution_cooldown", 600))
            self._zm_interval = int(config.get("zm_interval", 60))

            # 重试状态恢复
            self._failed_messages = config.get("failed_messages", []) or []
            self._prune_failed_messages()
            self._current_retry_count = int(config.get("current_retry_count", 0))
            next_retry = config.get("next_retry_time")
            if next_retry:
                try:
                    tz = pytz.timezone(settings.TZ)
                    parsed = datetime.fromisoformat(next_retry)
                    self._next_retry_time = parsed if parsed.tzinfo else tz.localize(parsed)
                except (ValueError, TypeError):
                    self._next_retry_time = None
            else:
                self._next_retry_time = None

            # 过滤已删除的站点
            all_site_ids = [s.id for s in self.siteoper.list_order_by_pri()] + [
                s.get("id") for s in self._custom_sites()
            ]
            self._chat_sites = [sid for sid in self._chat_sites if sid in all_site_ids]

            self.__update_config()

        # 加载定时服务
        if self._enabled or self._onlyonce:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)

            if self._onlyonce:
                logger.info("站点自动任务服务启动，立即运行一次")
                # 织梦先执行
                if self._has_selected_zm_site():
                    self._scheduler.add_job(
                        func=self.send_zm_site_messages, trigger="date",
                        run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3),
                        name="SiteAutoTask_ZM",
                    )
                # 其他站点任务
                self._scheduler.add_job(
                    func=self.__do_tasks, trigger="date",
                    run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=30),
                    name="SiteAutoTask",
                )
                self._onlyonce = False
                self.__update_config()
                # 清除重试状态
                if self._failed_messages:
                    self._failed_messages = []
                    self._current_retry_count = 0
                    self.__update_config()
            else:
                services = self.get_service()
                for svc in services:
                    self._scheduler.add_job(
                        func=svc["func"], trigger=svc["trigger"],
                        name=svc.get("name", "SiteAutoTask"), **svc.get("kwargs", {}),
                    )

            if self._scheduler.get_jobs():
                self._scheduler.print_jobs()
                self._scheduler.start()

    # —— 配置读写 ——
    def get_state(self) -> bool:
        return self._enabled

    def __update_config(self):
        self.update_config({
            "enabled": self._enabled,
            "cron": self._cron,
            "onlyonce": self._onlyonce,
            "notify": self._notify,
            "history_days": self._history_days,
            "use_proxy": self._use_proxy,
            "get_feedback": self._get_feedback,
            "feedback_timeout": self._feedback_timeout,
            "retry_count": self._retry_count,
            "retry_interval": self._retry_interval,
            "retry_notify": self._retry_notify,
            "chat_sites": self._chat_sites,
            "task_switches": self._task_switches,
            "interval_cnt": self._interval_cnt,
            "zm_mail_time": self._zm_mail_time,
            "last_zm_execution_time": self._last_zm_execution_time.isoformat() if self._last_zm_execution_time else None,
            "zm_execution_cooldown": self._zm_execution_cooldown,
            "zm_interval": self._zm_interval,
            "failed_messages": self._failed_messages,
            "current_retry_count": self._current_retry_count,
            "next_retry_time": self._next_retry_time.isoformat() if self._next_retry_time else None,
        })

    def _prune_failed_messages(self):
        """失败消息内存清理。"""
        try:
            if isinstance(self._failed_messages, list):
                total = len(self._failed_messages)
                if total > self._failed_messages_max:
                    drop = total - self._failed_messages_max
                    self._failed_messages = self._failed_messages[-self._failed_messages_max:]
                    logger.warning(f"失败消息过多，已清理较早的 {drop} 条，仅保留最近 {self._failed_messages_max} 条")
        except Exception as e:
            logger.error(f"清理失败消息时发生异常: {e}")

    # —— 站点信息 ——
    def _custom_sites(self) -> List[Any]:
        custom = []
        cfg = self.get_config("CustomSites")
        if cfg and cfg.get("enabled"):
            custom = cfg.get("sites") or []
        return custom

    def _all_sites(self) -> List[Any]:
        return [s for s in self.sites.get_indexers() if not s.get("public")] + self._custom_sites()

    def _has_selected_zm_site(self) -> bool:
        """是否选中了织梦站点。"""
        try:
            if not self._chat_sites:
                return False
            for sid in self._chat_sites:
                site = self.siteoper.get(sid)
                if site and "织梦" in site.name:
                    return True
        except Exception as e:
            logger.error(f"检测织梦站点失败: {e}")
        return False

    def get_support_sites(self) -> List[dict]:
        """获取插件支持的所有站点列表（不含 cookie），供配置页动态生成任务卡片。"""
        return [{
            "name": s["site_name"],
            "domain": s["domain"],
            "tasks": s["tasks_meta"],
        } for s in self._site_classes]

    # —— 通知 ——
    def _send_notification(self, title: str, text: str):
        if self._notify:
            self.post_message(mtype=NotificationType.SiteMessage, title=title, text=text)

    # —— 执行引擎（核心）——
    def __do_tasks(self):
        """站点周期任务执行主循环。

        合并 ptautotask 的 __do_tasks（多任务合集）与 groupchatzone 的
        send_site_messages（喊话+反馈解析）。
        """
        if not self._lock:
            self._lock = threading.Lock()
        if not self._lock.acquire(blocking=False):
            logger.warning("已有任务在执行，跳过本次调度")
            return

        self._running = True
        self._auto_task_in = True
        try:
            if not self._chat_sites:
                logger.info("未配置需要执行的站点")
                return

            all_sites = self._all_sites()
            # 选中织梦时，普通任务中过滤织梦（由独立 send_zm 处理）
            has_zm = self._has_selected_zm_site()
            do_sites = [s for s in all_sites if s.get("id") in self._chat_sites
                        and not (has_zm and s.get("name", "").startswith("织梦"))]

            if not do_sites:
                logger.info("没有找到有效的站点")
                return

            run_records: List[Dict] = []
            any_failure = False
            tz = pytz.timezone(settings.TZ)

            for site in do_sites:
                site_name = site.get("name") or "未知站点"
                logger.info(f"开始处理站点: {site_name}")

                # 构造 site_info
                site_info = {
                    "id": site.get("id"),
                    "url": site.get("url") or "",
                    "name": site_name,
                    "cookie": site.get("cookie") or "",
                    "ua": site.get("ua") or "",
                    "render": site.get("render", False),
                    "use_proxy": self._use_proxy,
                    "feedback_timeout": self._feedback_timeout,
                }

                # 路由 Handler
                handler = get_site_handler(site_info, self._handler_classes)
                if not handler:
                    logger.warning(f"站点 {site_name} 无匹配处理器，跳过")
                    continue

                # 找到该站点的 Tasks 类
                site_meta = next((s for s in self._site_classes
                                  if s.get("handler_cls") == type(handler)), None)
                tasks_cls = site_meta.get("tasks_cls") if site_meta else None

                # 执行任务
                if tasks_cls:
                    try:
                        tasks_inst = tasks_cls(cookie=None)
                        tasks_inst.client = handler
                    except Exception as e:
                        logger.error(f"实例化 {site_name} 任务类失败: {e}")
                        continue

                    for task in tasks_inst.get_registered_tasks():
                        task_id = task["id"]
                        # 检查任务开关
                        if not self._task_switches.get(task_id, False):
                            logger.debug(f"任务 {task_id} 已禁用，跳过")
                            continue
                        rec, failed = self._run_single_task(handler, site_name, task)
                        if rec:
                            run_records.append(rec)
                            if failed:
                                any_failure = True

                # 喊话反馈（若开启且站点支持）
                if self._get_feedback and hasattr(handler, "get_feedback"):
                    try:
                        feedback = handler.get_feedback()
                        if feedback and run_records:
                            # 关联到最后一个喊话任务记录
                            for rec in reversed(run_records):
                                if rec.get("site") == site_name and "喊话" in (rec.get("task_label") or ""):
                                    rec["feedback"] = feedback
                                    break
                    except Exception as e:
                        logger.error(f"获取 {site_name} 反馈失败: {e}")

            # 保存历史
            self._save_history_run(run_records)

            # 发送通知
            if self._notify and run_records:
                self._send_summary_notification(run_records)

            # 失败重试
            if any_failure and self._retry_count > 0:
                self._schedule_retry()

        finally:
            self._running = False
            self._auto_task_in = False
            try:
                self._lock.release()
            except Exception:
                pass
            # 重新注册（更新下次执行时间）
            try:
                self.reregister_plugin()
            except Exception:
                pass

    def _run_single_task(self, handler, site_name: str, task: dict) -> Tuple[Optional[dict], bool]:
        """执行单个任务并返回 (record, failed)。"""
        now_str = datetime.now(tz=pytz.timezone(settings.TZ)).strftime("%Y-%m-%d %H:%M:%S")
        task_id = task.get("id")
        func = task.get("func")
        try:
            logger.info(f"开始执行任务 {task_id}（站点: {site_name}）")
            result = func()
            status_text = self._result_to_status(result)
            failed = self._is_fail(status_text)
            emoji = "❌" if failed else "✅"
            logger.info(f"{site_name} - {task_id}: {emoji} {status_text}")
            return {
                "date": now_str,
                "site": site_name,
                "domain": handler.domain,
                "task_id": task_id,
                "task_label": task.get("label"),
                "status": status_text,
            }, failed
        except Exception as e:
            logger.error(f"{site_name} - {task_id} 异常: {e}", exc_info=True)
            return {
                "date": now_str,
                "site": site_name,
                "domain": handler.domain,
                "task_id": task_id,
                "task_label": task.get("label"),
                "status": f"执行失败: {e}",
            }, True

    @staticmethod
    def _result_to_status(result) -> str:
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            return result.get("status") or result.get("message") or result.get("msg") or "执行完成"
        if isinstance(result, tuple) and len(result) >= 2:
            return str(result[1])
        if result is None:
            return "执行完成"
        return repr(result)

    @staticmethod
    def _is_fail(status: str) -> bool:
        if not status:
            return False
        st = status.lower()
        return ("失败" in status) or ("异常" in status) or ("error" in st) or ("false" == st)

    # —— 历史记录 ——
    def _save_history_run(self, records: List[dict]):
        history = self.get_data(self._data_key) or []
        now_str = datetime.now(tz=pytz.timezone(settings.TZ)).strftime("%Y-%m-%d %H:%M:%S")
        history.append({"date": now_str, "records": records})
        # 按天清理
        if self._history_days:
            try:
                cutoff = time.time() - int(self._history_days) * 24 * 60 * 60
                history = [h for h in history
                           if datetime.strptime(h["date"], "%Y-%m-%d %H:%M:%S").timestamp() >= cutoff]
            except Exception as e:
                logger.error(f"清理历史记录异常: {e}")
        self.save_data(self._data_key, history)

    # —— 通知 ——
    def _send_summary_notification(self, records: List[dict]):
        title = "站点自动任务执行汇总"
        _site_order: List[str] = []
        _site_map: Dict[str, List[str]] = {}
        for rec in records:
            site = rec.get("site") or "未知站点"
            if site not in _site_order:
                _site_order.append(site)
            emoji = "❌" if self._is_fail(rec.get("status", "")) else "✅"
            line = f"{emoji} {rec.get('task_label') or rec.get('task_id')}: {rec.get('status')}"
            # 反馈奖励
            fb = rec.get("feedback")
            if fb and fb.get("rewards"):
                for rw in fb["rewards"]:
                    icon = NotificationIcons.get(rw.get("type", ""))
                    line += f"\n  {icon} {rw.get('description', '')}"
            _site_map.setdefault(site, []).append(line)

        parts: List[str] = []
        for site in _site_order:
            parts.append(f"🔔 {site}")
            parts.extend(_site_map.get(site, []))
            parts.append("────────────────────")
        if parts and parts[-1].startswith("─"):
            parts = parts[:-1]
        self._send_notification(title, "\n".join(parts))

    # —— 失败重试 ——
    def _schedule_retry(self):
        """安排失败重试任务。"""
        try:
            run_date = datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(minutes=self._retry_interval)
            if self._scheduler:
                self._scheduler.add_job(func=self._execute_retry, trigger="date",
                                        run_date=run_date, name="SiteAutoTask_Retry")
                logger.info(f"已安排重试任务，{self._retry_interval} 分钟后执行")
        except Exception as e:
            logger.error(f"安排重试任务失败: {e}")

    def _execute_retry(self):
        """执行失败重试。"""
        if not self._retry_lock:
            self._retry_lock = threading.Lock()
        if not self._retry_lock.acquire(blocking=False):
            return
        try:
            if self._current_retry_count >= self._retry_count:
                logger.info("已达到最大重试次数，不再重试")
                return
            self._current_retry_count += 1
            logger.info(f"开始执行第 {self._current_retry_count} 次重试")
            # 重跑主任务
            self.__do_tasks()
        finally:
            try:
                self._retry_lock.release()
            except Exception:
                pass

    # —— 织梦独立调度 ——
    def send_zm_site_messages(self):
        """织梦站点独立任务（基于邮件时间检测的 24h 调度）。"""
        if not self._zm_lock:
            self._zm_lock = threading.Lock()
        if not self._zm_lock.acquire(blocking=False):
            logger.warning("已有织梦任务在执行，跳过")
            return
        try:
            all_sites = self._all_sites()
            zm_sites = [s for s in all_sites if s.get("id") in self._chat_sites
                        and s.get("name", "").startswith("织梦")]
            if not zm_sites:
                return
            # 获取邮件时间并计算下次
            for site in zm_sites:
                site_info = {
                    "url": site.get("url") or "",
                    "name": site.get("name"),
                    "cookie": site.get("cookie") or "",
                    "ua": site.get("ua") or "",
                    "render": site.get("render", False),
                    "use_proxy": self._use_proxy,
                    "feedback_timeout": self._feedback_timeout,
                }
                handler = get_site_handler(site_info, self._handler_classes)
                if not handler:
                    continue
                latest_time = handler.get_latest_message_time()
                if latest_time:
                    self._zm_mail_time = latest_time
                    logger.info(f"织梦最新邮件时间: {latest_time}")
            self.__update_config()
        finally:
            try:
                self._zm_lock.release()
            except Exception:
                pass
            try:
                self.reregister_plugin()
            except Exception:
                pass

    # —— 接口实现 ——
    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_service(self) -> List[Dict[str, Any]]:
        services = []
        if self._enabled and self._cron:
            services.append({
                "id": "SiteAutoTask",
                "name": "站点自动任务服务",
                "trigger": CronTrigger.from_crontab(str(self._cron)),
                "func": self.__do_tasks,
                "kwargs": {},
            })
        # 织梦独立调度
        if self._enabled and self._has_selected_zm_site() and self._zm_mail_time:
            try:
                tz = pytz.timezone(settings.TZ)
                mail_time = datetime.strptime(self._zm_mail_time, "%Y-%m-%d %H:%M:%S")
                if mail_time.tzinfo is None:
                    mail_time = tz.localize(mail_time)
                next_time = mail_time + timedelta(hours=24)
                now = datetime.now(tz=tz)
                if (next_time - now).total_seconds() <= 0:
                    next_time = now + timedelta(seconds=3)
                services.append({
                    "id": "SiteAutoTask_ZM",
                    "name": "站点自动任务 - 织梦",
                    "trigger": "date",
                    "func": self.send_zm_site_messages,
                    "kwargs": {"run_date": next_time},
                })
            except Exception as e:
                logger.error(f"计算织梦调度时间失败: {e}")
        # 重试任务
        if self._next_retry_time and self._next_retry_time > datetime.now(tz=pytz.timezone(settings.TZ)):
            services.append({
                "id": "SiteAutoTask_Retry",
                "name": f"站点自动任务 - 重试(第{self._current_retry_count + 1}次)",
                "trigger": "date",
                "func": self._execute_retry,
                "kwargs": {"run_date": self._next_retry_time},
            })
        return services

    def stop_service(self):
        """停止定时服务。"""
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown(wait=False)
                self._scheduler = None
        except Exception as e:
            logger.error(f"停止服务异常: {e}")
