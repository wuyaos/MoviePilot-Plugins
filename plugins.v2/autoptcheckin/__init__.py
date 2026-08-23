# input: MoviePilot 配置、站点数据、签到/登录任务参数与 TimerUtils 调度能力
# output: AutoPtCheckin 插件入口、调度注册与站点自动签到执行逻辑
# pos: MoviePilot V2 PT 站点自动签到的入口与编排层
import re
import time
from datetime import datetime, timedelta
from functools import partial
from multiprocessing.dummy import Pool as ThreadPool
from threading import Lock
from typing import Any, List, Dict, Tuple, Optional
from urllib.parse import urljoin

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from ruamel.yaml import CommentedMap

from app import schemas
from app.chain.site import SiteChain
from app.core.config import settings
from app.core.event import EventManager, eventmanager, Event
from app.db.site_oper import SiteOper
from app.helper.browser import PlaywrightHelper
from app.helper.cloudflare import under_challenge
from app.helper.module import ModuleHelper
from app.helper.sites import SitesHelper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType, NotificationType
from app.utils.http import RequestUtils
from app.utils.site import SiteUtils
from app.utils.string import StringUtils
from app.utils.timer import TimerUtils

from .ui_helper import build_history_panels
from .form_builder import build_form
from .helper.signin_status import SigninStatus, SUCCESS_STATUSES, infer_signin_status


class AutoPtCheckin(_PluginBase):
    # 插件名称
    plugin_name = "PT站点自动签到"
    # 插件描述
    plugin_desc = "PT 站点自动签到与模拟登录，支持验证码"
    # 插件图标
    plugin_icon = "signin.png"
    # 插件版本
    plugin_version = "1.5.12"
    # 插件作者
    plugin_author = "wuyaos"
    # 作者主页
    author_url = "https://github.com/wuyaos"
    # 插件配置项ID前缀
    plugin_config_prefix = "autoptcheckin_"
    # 加载顺序
    plugin_order = 0
    # 可使用的用户级别
    auth_level = 2
    # 站点异常关键词（服务器繁忙/维护/403/网关错误等，命中时不报 Cookie 失效）
    _SITE_ERROR_KEYWORDS = [
        "服务器负载过高", "正在重试，请稍后", "服务器繁忙", "系统维护", "网站维护",
        "暂停服务", "访问被拒绝", "访问受限", "forbidden", "access denied",
        "server is busy", "overloaded", "temporarily unavailable",
        "under maintenance", "Bad Gateway", "Service Unavailable", "Gateway Timeout",
    ]

    # 私有属性
    sites: SitesHelper = None
    siteoper: SiteOper = None
    sitechain: SiteChain = None
    # 事件管理器
    event: EventManager = None
    # 定时器
    _scheduler: Optional[BackgroundScheduler] = None
    # 加载的模块
    _site_schema: list = []

    # 运行时状态
    _enabled = False

    # 自定义站点属性（合并自 CustomSites 插件）
    _custom_site_urls: str = ""
    _custom_sites_data: list = []
    _site_id_base: int = 60000
    _cron: str = ""
    _onlyonce: bool = False
    _notify: bool = False
    _queue_cnt: int = 5
    _sign_sites: list = []
    _login_sites: list = []
    _retry_keyword = None
    _clean: bool = False
    _start_time: Optional[int] = None
    _end_time: Optional[int] = None
    _auto_cf: int = 0
    _cron_mode: str = "interval"        # cron / interval
    _interval_hours: float = 2.0
    _begin_hour: int = 9
    _end_hour: int = 23
    _schedule_crons: list = []
    _schedule_signature: str = ""
    # CookieCloud init 同步冷却秒数；时间戳持久化，避免模块重载后冷却失效
    _cookie_cloud_sync_cooldown: int = 600

    def init_plugin(self, config: dict = None):
        self.sites = SitesHelper()
        self.siteoper = SiteOper()
        self.event = EventManager()
        self.sitechain = SiteChain()

        # 停止现有任务
        self.stop_service()

        # 配置：每次初始化都重建运行态，避免空配置热重载沿用旧字段。
        config = config or {}
        self._enabled = bool(config.get("enabled", False))
        self._cron = str(config.get("cron") or "").strip()
        self._cron_mode = config.get("cron_mode") or "interval"
        self._interval_hours = self.__safe_float(config.get("interval_hours"), 2.0, min_value=0.5)
        self._begin_hour = self.__safe_int(config.get("begin_hour"), 9, min_value=0, max_value=23)
        self._end_hour = self.__safe_int(config.get("end_hour"), 23, min_value=0, max_value=23)
        self._start_time = self._begin_hour if self._cron_mode == "interval" else None
        self._end_time = self._end_hour if self._cron_mode == "interval" else None
        self._onlyonce = bool(config.get("onlyonce", False))
        self._notify = bool(config.get("notify", False))
        self._queue_cnt = self.__safe_int(config.get("queue_cnt"), 5, min_value=1)
        self._sign_sites = config.get("sign_sites") or []
        self._login_sites = config.get("login_sites") or []
        self._retry_keyword = config.get("retry_keyword")
        self._auto_cf = self.__safe_int(config.get("auto_cf"), 0, min_value=0)
        self._clean = bool(config.get("clean", False))
        self._custom_site_urls = config.get("custom_site_urls") or ""
        self._custom_sites_data = config.get("custom_sites_data") or []
        self._schedule_crons = [
            str(value).strip() for value in (config.get("schedule_crons") or [])
            if len(str(value).strip().split()) == 5
        ]
        self._schedule_signature = str(config.get("schedule_signature") or "")
        expected_signature = self.__schedule_signature()
        if self._cron_mode != "cron" and (
            self._schedule_signature != expected_signature or not self._schedule_crons
        ):
            self._schedule_crons = self.__generate_schedule_crons()
            self._schedule_signature = expected_signature

        if config:
            self.__parse_custom_sites()
            self.__sync_cookie_cloud()
            all_sites = [site.id for site in self.siteoper.list_order_by_pri()] + [site.get("id") for site in
                                                                                   self.__custom_sites()]
            self._sign_sites = [site_id for site_id in all_sites if site_id in self._sign_sites]
            self._login_sites = [site_id for site_id in all_sites if site_id in self._login_sites]
            self.__update_config()

        # 加载模块
        if self._enabled or self._onlyonce:

            self._site_schema = ModuleHelper.load('app.plugins.autoptcheckin.sites',
                                                  filter_func=lambda _, obj: hasattr(obj, 'match'))

            # 立即运行一次
            if self._onlyonce:
                # 定时服务
                self._scheduler = BackgroundScheduler(timezone=settings.TZ)
                logger.info("站点自动签到服务启动，立即运行一次")
                self._scheduler.add_job(func=self.sign_in, trigger='date',
                                        run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3),
                                        name="站点自动签到")

                # 关闭一次性开关
                self._onlyonce = False
                # 保存配置
                self.__update_config()

                # 启动任务
                if self._scheduler.get_jobs():
                    self._scheduler.print_jobs()
                    self._scheduler.start()

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def __safe_float(value, default: float, min_value: float = None, max_value: float = None) -> float:
        try:
            ret = float(value)
        except (TypeError, ValueError):
            ret = default
        if min_value is not None:
            ret = max(min_value, ret)
        if max_value is not None:
            ret = min(max_value, ret)
        return ret

    @staticmethod
    def __safe_int(value, default: int, min_value: int = None, max_value: int = None) -> int:
        try:
            ret = int(value)
        except (TypeError, ValueError):
            ret = default
        if min_value is not None:
            ret = max(min_value, ret)
        if max_value is not None:
            ret = min(max_value, ret)
        return ret

    def __schedule_signature(self) -> str:
        return (
            f"{self._cron_mode}:{self._interval_hours}:"
            f"{self._begin_hour}:{self._end_hour}"
        )

    def __generate_schedule_crons(self) -> list:
        if self._cron_mode == "interval":
            window = self._end_hour - self._begin_hour
            if window <= 0:
                logger.error("触发时间范围无效，end_hour 必须大于 begin_hour")
                return []
            hours_f = max(0.5, self._interval_hours)
            triggers = TimerUtils.random_scheduler(
                num_executions=max(1, int(window / hours_f)),
                begin_hour=self._begin_hour,
                end_hour=self._end_hour,
                max_interval=int(hours_f * 60),
                min_interval=max(30, int(hours_f * 60 * 0.5)),
            )
        else:
            triggers = TimerUtils.random_scheduler(
                num_executions=2,
                begin_hour=9,
                end_hour=23,
                max_interval=6 * 60,
                min_interval=2 * 60,
            )
        crons = [f"{trigger.minute} {trigger.hour} * * *" for trigger in triggers]
        if crons:
            logger.info(f"站点自动签到已生成并持久化随机时间：{', '.join(crons)}")
        else:
            logger.error("站点自动签到未生成有效随机时间")
        return crons

    def __update_config(self):
        # 保存配置
        self.update_config(
            {
                "enabled": self._enabled,
                "notify": self._notify,
                "cron": self._cron,
                "cron_mode": self._cron_mode,
                "interval_hours": self._interval_hours,
                "begin_hour": self._begin_hour,
                "end_hour": self._end_hour,
                "onlyonce": self._onlyonce,
                "queue_cnt": self._queue_cnt,
                "sign_sites": self._sign_sites,
                "login_sites": self._login_sites,
                "retry_keyword": self._retry_keyword,
                "auto_cf": self._auto_cf,
                "clean": self._clean,
                "custom_site_urls": self._custom_site_urls,
                "custom_sites_data": self._custom_sites_data,
                "schedule_crons": self._schedule_crons,
                "schedule_signature": self._schedule_signature,
            }
        )

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """
        定义远程控制命令
        :return: 命令关键字、事件、描述、附带数据
        """
        return [
            {"cmd": "/checkin_now", "event": EventType.PluginAction,
             "desc": "立即对所有站点执行一次签到/模拟登录", "category": "签到",
             "data": {"action": "checkin_now"}},
            {"cmd": "/checkin_force", "event": EventType.PluginAction,
             "desc": "强制重新签到/模拟登录（清理本日缓存）", "category": "签到",
             "data": {"action": "checkin_force"}},
        ]

    def get_api(self) -> List[Dict[str, Any]]:
        """
        获取插件API
        [{
            "path": "/xx",
            "endpoint": self.xxx,
            "methods": ["GET", "POST"],
            "summary": "API说明"
        }]
        """
        return [{
            "path": "/signin_by_domain",
            "endpoint": self.signin_by_domain,
            "methods": ["GET"],
            "auth": "apikey",
            "summary": "站点签到",
            "description": "使用站点域名签到站点",
        }]

    def get_service(self) -> List[Dict[str, Any]]:
        """
        注册插件公共服务。
        cron 模式：5 位 cron 表达式
        interval 模式：在 begin_hour~end_hour 范围内按 interval_hours 随机调度
        """
        if not self._enabled:
            return []

        if self._cron_mode == "cron" and self._cron:
            try:
                cron_str = str(self._cron).strip()
                if cron_str.count(" ") == 4:
                    return [{
                        "id": "AutoSignIn",
                        "name": "站点自动签到服务",
                        "trigger": CronTrigger.from_crontab(cron_str, timezone=settings.TZ),
                        "func": self.sign_in,
                        "kwargs": {}
                    }]
                else:
                    logger.error("站点自动签到服务启动失败，cron 格式错误，需要 5 位 cron 表达式")
                    return []
            except Exception as err:
                logger.error(f"定时任务配置错误：{err}")
                return []

        if not self._schedule_crons:
            logger.error("站点自动签到没有已持久化的随机触发时间")
            return []
        ret_jobs = []
        for index, cron_str in enumerate(self._schedule_crons):
            try:
                trigger = CronTrigger.from_crontab(cron_str, timezone=settings.TZ)
            except Exception as err:
                logger.error(f"站点自动签到随机 Cron 无效：cron={cron_str!r}，error={err}")
                continue
            minute, hour, *_ = cron_str.split()
            ret_jobs.append({
                "id": f"AutoSignIn.{index}",
                "name": f"站点自动签到服务 {int(hour):02d}:{int(minute):02d}",
                "trigger": trigger,
                "func": self.sign_in,
                "kwargs": {},
            })
        return ret_jobs

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
        # 站点的可选项（内置站点 + 自定义站点）
        customSites = self.__custom_sites()

        try:
            site_options = ([{"title": site.name, "value": site.id}
                             for site in self.siteoper.list_order_by_pri()]
                            + [{"title": site.get("name"), "value": site.get("id")}
                               for site in customSites])
        except Exception as e:
            logger.warning(f"获取站点列表失败: {e}")
            site_options = [{"title": site.get("name"), "value": site.get("id")}
                            for site in customSites]
        return build_form(site_options)

    def __custom_sites(self) -> List[Any]:
        """返回内置自定义站点列表（不再依赖外部 CustomSites 插件）"""
        return self._custom_sites_data or []

    def __parse_custom_sites(self):
        """解析自定义站点文本 → self._custom_sites_data"""
        if not self._custom_site_urls:
            return
        try:
            from urllib.parse import urlparse
            site_urls = [line.strip() for line in self._custom_site_urls.splitlines() if line.strip()]
            new_urls = {line.split("|")[1].strip() for line in site_urls if "|" in line and len(line.split("|")) >= 3}

            # 保留已有站点（URL 匹配）
            kept = [s for s in self._custom_sites_data if s.get("url") in new_urls]
            kept_urls = {s.get("url") for s in kept}

            # 分配 ID
            alloc_ids = [s.get("id", self._site_id_base) for s in self._custom_sites_data] + [self._site_id_base]
            next_id = max(alloc_ids) + 1

            # 新增站点
            for line in site_urls:
                parts = line.split("|")
                if len(parts) < 3:
                    continue
                name, url, render = parts[0].strip(), parts[1].strip(), parts[2].strip()
                if url in kept_urls:
                    continue
                kept.append({
                    "id": next_id,
                    "name": name,
                    "url": url,
                    "render": render.upper() == 'Y',
                    "cookie": "",
                })
                next_id += 1

            # 删除移除的站点
            del_sites = [s for s in self._custom_sites_data if s.get("url") not in new_urls]
            for site in del_sites:
                try:
                    EventManager().send_event(EventType.SiteDeleted, {"site_id": site.get("id")})
                    logger.info(f"删除自定义站点 {site.get('name')}")
                except Exception:
                    pass

            self._custom_sites_data = kept
        except Exception as e:
            logger.error(f"解析自定义站点失败: {e}")

    def __sync_cookie_cloud(self):
        """通过 CookieCloudHelper 同步 cookie 到自定义站点。

        init_plugin 每次热重载都会触发；加冷却避免频繁全量下载，
        签到时 _fetch_cookie_cloud 仍会按需补取空 Cookie，不影响正确性。
        """
        if not self._custom_sites_data:
            return
        now = time.time()
        try:
            synced_at = float(self.get_data("cookie_cloud_synced_at") or 0)
        except (TypeError, ValueError):
            synced_at = 0
        if now - synced_at < self._cookie_cloud_sync_cooldown:
            logger.debug("CookieCloud 同步冷却中，跳过本次 init 同步")
            return
        try:
            from urllib.parse import urlparse
            from app.helper.cookiecloud import CookieCloudHelper
            cookies, msg = CookieCloudHelper().download()
            if not cookies:
                logger.debug(f"CookieCloud 同步跳过: {msg}")
                return
            count = 0
            for domain, cookie in cookies.items():
                for site in self._custom_sites_data:
                    site_domain = urlparse(site.get("url", "")).netloc
                    if site_domain and site_domain.endswith(domain):
                        site["cookie"] = cookie
                        count += 1
            if count:
                logger.info(f"CookieCloud 同步了 {count} 个自定义站点的 Cookie")
            self.save_data("cookie_cloud_synced_at", now)
        except Exception as e:
            logger.debug(f"CookieCloud 同步失败: {e}")

    def get_page(self) -> List[dict]:
        """
        拼装插件详情页面，需要返回页面配置，同时附带数据
        """
        try:
            return self._build_page()
        except Exception as e:
            logger.error(f"构建详情页失败: {e}")
            return [{
                'component': 'VAlert',
                'props': {
                    'type': 'error',
                    'text': f'详情页加载失败: {e}',
                    'variant': 'tonal',
                }
            }]

    def _build_page(self) -> List[dict]:
        # 获取最近14天的日期数组
        date_list = [(datetime.now() - timedelta(days=i)).date() for i in range(14)]

        # 获取所有数据，包括签到和登录历史
        all_data = {
            "signin": [],  # 签到数据
            "login": []  # 登录数据
        }
        sign_dates = set()
        sites_info = self._build_sites_info()

        # 获取常规日期格式数据
        for day in date_list:
            day_str = f"{day.month}月{day.day}日"
            day_formatted = day.strftime('%Y-%m-%d')

            # 获取"月日"格式数据
            day_data = self.get_data(day_str)
            if day_data:
                # 添加日期信息到每条记录
                if isinstance(day_data, list):
                    for record in day_data:
                        if isinstance(record, dict):
                            # 页面临时字段使用副本，避免修改读取到的历史记录。
                            page_record = {
                                **record,
                                "date": day_str,
                                "day_obj": day,
                            }
                            # 区分签到和登录数据
                            if "登录" in page_record.get("status", ""):
                                all_data["login"].append(page_record)
                            else:
                                all_data["signin"].append(page_record)
                    sign_dates.add(day_str)

            # 获取"签到-yyyy-mm-dd"和"登录-yyyy-mm-dd"格式数据
            signin_history = self.get_data(key="签到-" + day_formatted)
            if signin_history:
                if isinstance(signin_history, dict):
                    # 获取完成签到的站点ID列表
                    done_sites = signin_history.get("do", [])
                    retry_sites = signin_history.get("retry", [])

                    # 为所有已完成签到的站点创建记录
                    for site_id in done_sites:
                        site_name = self._get_site_display_name(site_id=site_id, sites_info=sites_info)
                        if not site_name:
                            continue

                        # 跳过需要重试的站点
                        if site_id in retry_sites:
                            # 为需要重试的站点添加记录
                            status_text = "需要重试"
                            all_data["signin"].append({
                                "site": site_name,
                                "status": status_text,
                                "date": day_str,
                                "day_obj": day,
                                "site_id": site_id
                            })
                        else:
                            # 为已完成的站点添加记录
                            status_text = "已签到"
                            all_data["signin"].append({
                                "site": site_name,
                                "status": status_text,
                                "date": day_str,
                                "day_obj": day,
                                "site_id": site_id
                            })

                    sign_dates.add(day_str)

            # 获取登录历史数据
            login_history = self.get_data(key="登录-" + day_formatted)
            if login_history:
                if isinstance(login_history, dict):
                    # 获取完成登录的站点ID列表
                    done_sites = login_history.get("do", [])
                    retry_sites = login_history.get("retry", [])

                    # 为所有已完成登录的站点创建记录
                    for site_id in done_sites:
                        site_name = self._get_site_display_name(site_id=site_id, sites_info=sites_info)
                        if not site_name:
                            continue

                        # 跳过需要重试的站点
                        if site_id in retry_sites:
                            # 为需要重试的站点添加记录
                            status_text = "登录需要重试"
                            all_data["login"].append({
                                "site": site_name,
                                "status": status_text,
                                "date": day_str,
                                "day_obj": day,
                                "site_id": site_id
                            })
                        else:
                            # 为已完成的站点添加记录
                            status_text = "登录成功"
                            all_data["login"].append({
                                "site": site_name,
                                "status": status_text,
                                "date": day_str,
                                "day_obj": day,
                                "site_id": site_id
                            })

                    sign_dates.add(day_str)

        # 如果没有数据，显示提示信息
        if not all_data["signin"] and not all_data["login"]:
            return [{
                'component': 'VAlert',
                'props': {
                    'type': 'info',
                    'text': '暂无签到数据',
                    'variant': 'tonal',
                    'class': 'mt-4',
                    'prepend-icon': 'mdi-information'
                }
            }]

        # 确保签到数据中至少有所有日期的记录
        if sign_dates:
            sign_dates_list = list(sign_dates)
            sign_dates_list.sort(reverse=True)  # 最新日期优先
        else:
            sign_dates_list = [f"{date_list[0].month}月{date_list[0].day}日"]

        # 签到和登录均按原始追加顺序去重；同站点同日的汇总状态在后追加，
        # 因而继续覆盖详细执行文案。
        signin_site_data, signin_panels = build_history_panels(all_data["signin"])
        login_site_data, login_panels = build_history_panels(all_data["login"])

        # 添加样式
        return [
            {
                'component': 'style',
                'text': """
                .v-expansion-panel-title {
                    min-height: 48px !important;
                    padding: 0 16px !important;
                }
                .v-expansion-panel-text__wrapper {
                    padding: 0 !important;
                }
                .v-expansion-panel {

                    margin-bottom: 10px !important;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
                    border-radius: 16px !important;
                    overflow: hidden !important;
                    border: 1px solid rgba(var(--v-theme-on-surface), .08);
                    transition: all 0.3s ease;
                }
                .v-expansion-panel:hover {

                    box-shadow: 0 4px 12px rgba(0,0,0,0.08) !important;
                    transform: translateY(-2px);
                }
                html[data-theme="transparent"] .v-expansion-panel,
                html[data-theme="transparent"] .signin-card,
                html[data-theme="transparent"] .login-card,
                .v-theme--transparent .v-expansion-panel,
                .v-theme--transparent .signin-card,
                .v-theme--transparent .login-card {
                    backdrop-filter: blur(var(--transparent-blur, 10px));
                    background-color: rgba(var(--v-theme-surface), 0) !important;
                }
                html[data-theme="transparent"] .v-expansion-panel-title,
                html[data-theme="transparent"] .v-expansion-panel-text,
                html[data-theme="transparent"] .v-expansion-panel-text__wrapper,
                html[data-theme="transparent"] .v-list,
                html[data-theme="transparent"] .v-list-item,
                .v-theme--transparent .v-expansion-panel-title,
                .v-theme--transparent .v-expansion-panel-text,
                .v-theme--transparent .v-expansion-panel-text__wrapper,
                .v-theme--transparent .v-list,
                .v-theme--transparent .v-list-item {
                    background-color: transparent !important;
                }
                .site-item {
                    border-radius: 10px;
                    transition: all 0.3s ease;
                    margin: 5px 0;

                }
                .site-item:hover {

                    transform: scale(1.01);
                    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
                }
                .text-teal-lighten-3 {
                    color: #80CBC4 !important;
                }
                .text-deep-orange-lighten-3 {
                    color: #FFAB91 !important;
                }
                .text-pink-lighten-3 {
                    color: #F8BBD0 !important;
                }
                .text-amber-lighten-3 {
                    color: #FFE082 !important;
                }
                .text-light-blue-lighten-3 {
                    color: #81D4FA !important;
                }
                .status-icon {
                    width: 24px;
                    height: 24px;
                    line-height: 24px;
                    text-align: center;
                    border-radius: 50%;
                    margin-right: 8px;
                }
                .signin-card, .login-card {
                    transition: all 0.3s ease;
                    border-radius: 20px !important;
                    overflow: hidden;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.03) !important;
                    border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
                }
                .signin-card:hover, .login-card:hover {
                    transform: translateY(-3px);
                    box-shadow: 0 6px 20px rgba(0,0,0,0.05) !important;
                }
                .v-card-title.gradient-title {
                    margin-bottom: 0 !important;
                    border-bottom: 1px solid rgba(0,0,0,0.03);
                }
                .signin-card .v-card-title.gradient-title {
                    background: linear-gradient(135deg, rgba(128, 203, 196, 0.15) 0%, rgba(165, 214, 167, 0.15) 100%);
                }
                .login-card .v-card-title.gradient-title {
                    background: linear-gradient(135deg, rgba(129, 212, 250, 0.15) 0%, rgba(159, 168, 218, 0.15) 100%);
                }
                .date-chip {
                    margin: 2px !important;
                    border-radius: 14px !important;
                    font-size: 0.75rem !important;
                }
                .status-chip {
                    padding: 0 8px;
                    border-radius: 14px !important;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.03);
                }
                .site-icon {
                    background: linear-gradient(45deg, #80CBC4, #81D4FA);
                    color: white !important;
                    border-radius: 12px;
                    width: 32px;
                    height: 32px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin-right: 10px;
                    font-weight: bold;
                    font-size: 15px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.06);
                }
                .page-title {
                    font-size: 1.5rem;
                    font-weight: 600;
                    background: -webkit-linear-gradient(45deg, #80CBC4, #81D4FA);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                }
                """
            },
            {
                'component': 'VRow',
                'props': {
                    'class': 'mt-2'
                },
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'class': 'pb-0'
                        },
                        'content': [
                            {
                                'component': 'div',
                                'props': {
                                    'class': 'd-flex align-center mb-4'
                                },
                                'content': [
                                    {
                                        'component': 'VIcon',
                                        'props': {
                                            'color': 'light-blue-lighten-3',
                                            'class': 'mr-2',
                                            'size': 'large'
                                        },
                                        'text': 'mdi-cat'
                                    },
                                    {
                                        'component': 'h2',
                                        'props': {
                                            'class': 'page-title m-0'
                                        },
                                        'text': '站点签到小助手'
                                    },
                                    {
                                        'component': 'VSpacer'
                                    },
                                    {
                                        'component': 'VChip',
                                        'props': {
                                            'color': 'light-blue-lighten-5',
                                            'size': 'small',
                                            'variant': 'elevated',
                                            'class': 'ml-2',
                                            'prepend-icon': 'mdi-paw'
                                        },
                                        'text': f'显示 {len(sign_dates_list)} 天数据'
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
            {
                'component': 'VRow',
                'content': [
                    # 左侧 - 签到数据
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VCard',
                                'props': {
                                    'variant': 'flat',
                                    'class': 'mb-4 signin-card'
                                },
                                'content': [
                                    {
                                        'component': 'VCardTitle',
                                        'props': {
                                            'class': 'gradient-title d-flex align-center pa-4'
                                        },
                                        'content': [
                                            {
                                                'component': 'VIcon',
                                                'props': {
                                                    'class': 'mr-2',
                                                    'color': 'teal-lighten-3',
                                                    'size': 'small'
                                                },
                                                'text': 'mdi-duck'
                                            },
                                            {
                                                'component': 'span',
                                                'props': {
                                                    'class': 'font-weight-medium'
                                                },
                                                'text': '签到打卡记录'
                                            },
                                            {
                                                'component': 'VSpacer'
                                            },
                                            {
                                                'component': 'VChip',
                                                'props': {
                                                    'color': 'teal-lighten-5',
                                                    'size': 'x-small',
                                                    'variant': 'elevated',
                                                    'class': 'ml-2',
                                                    'prepend-icon': 'mdi-rabbit'
                                                },
                                                'text': f'{len(signin_site_data)} 个站点'
                                            }
                                        ]
                                    },
                                    {
                                        'component': 'VCardText',
                                        'props': {
                                            'class': 'pa-3'
                                        },
                                        'content': [
                                            {
                                                'component': 'VExpansionPanels',
                                                'props': {
                                                    'variant': 'accordion',
                                                    'class': 'mt-2'
                                                },
                                                'content': signin_panels or [{
                                                    'component': 'VAlert',
                                                    'props': {
                                                        'type': 'info',
                                                        'text': '暂无签到数据',
                                                        'variant': 'tonal',
                                                        'class': 'mt-2',
                                                        'density': 'compact',
                                                        'prepend-icon': 'mdi-penguin'
                                                    }
                                                }]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    },
                    # 右侧 - 登录数据
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VCard',
                                'props': {
                                    'variant': 'flat',
                                    'class': 'mb-4 login-card'
                                },
                                'content': [
                                    {
                                        'component': 'VCardTitle',
                                        'props': {
                                            'class': 'gradient-title d-flex align-center pa-4'
                                        },
                                        'content': [
                                            {
                                                'component': 'VIcon',
                                                'props': {
                                                    'class': 'mr-2',
                                                    'color': 'light-blue-accent-3',
                                                    'size': 'small'
                                                },
                                                'text': 'mdi-dog'
                                            },
                                            {
                                                'component': 'span',
                                                'props': {
                                                    'class': 'font-weight-medium'
                                                },
                                                'text': '登录记录'
                                            },
                                            {
                                                'component': 'VSpacer'
                                            },
                                            {
                                                'component': 'VChip',
                                                'props': {
                                                    'color': 'light-blue-lighten-4',
                                                    'size': 'x-small',
                                                    'variant': 'elevated',
                                                    'class': 'ml-2',
                                                    'prepend-icon': 'mdi-panda'
                                                },
                                                'text': f'{len(login_site_data)} 个站点'
                                            }
                                        ]
                                    },
                                    {
                                        'component': 'VCardText',
                                        'props': {
                                            'class': 'pa-3'
                                        },
                                        'content': [
                                            {
                                                'component': 'VExpansionPanels',
                                                'props': {
                                                    'variant': 'accordion',
                                                    'class': 'mt-2'
                                                },
                                                'content': login_panels or [{
                                                    'component': 'VAlert',
                                                    'props': {
                                                        'type': 'info',
                                                        'text': '暂无登录数据',
                                                        'variant': 'tonal',
                                                        'class': 'mt-2',
                                                        'density': 'compact',
                                                        'prepend-icon': 'mdi-cat'
                                                    }
                                                }]
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
    @staticmethod
    def _add_site_info(sites_info: dict, site_id: Any, site_name: Any) -> None:
        """记录站点ID到名称的映射，兼容历史记录中ID类型不一致的情况。"""
        if site_id is None or not site_name:
            return
        sites_info[site_id] = site_name
        sites_info[str(site_id)] = site_name

    def _build_sites_info(self) -> dict:
        """汇总站点名称，供详情页历史记录反查。"""
        sites_info = {}
        for site in self.sites.get_indexers():
            if not site.get("public"):
                self._add_site_info(sites_info, site.get("id"), site.get("name"))
        for site in self.siteoper.list_order_by_pri():
            self._add_site_info(sites_info, getattr(site, "id", None), getattr(site, "name", None))
        for site in self.__custom_sites():
            self._add_site_info(sites_info, site.get("id"), site.get("name"))
        return sites_info

    @staticmethod
    def _get_site_display_name(site_id, sites_info: dict) -> Optional[str]:
        """根据站点ID获取详情页中展示的站点名称，查不到时返回空值便于跳过。"""
        site_id_str = str(site_id)
        return sites_info.get(site_id_str) or sites_info.get(site_id)


    @eventmanager.register(EventType.PluginAction)
    def sign_in(self, event: Event = None):
        """
        自动签到|模拟登录
        """
        if event:
            event_data = event.event_data
            action = (event_data or {}).get("action")
            if action not in ("checkin_now", "checkin_force"):
                return
            if action == "checkin_force":
                self._clean = True
        # 日期
        today = datetime.today()
        if self._start_time is not None and self._end_time is not None:
            if int(datetime.today().hour) < self._start_time or int(datetime.today().hour) > self._end_time:
                logger.error(
                    f"当前时间 {int(datetime.today().hour)} 不在 {self._start_time}-{self._end_time} 范围内，暂不执行任务")
                self._clean = False
                return
        if event:
            logger.info("收到命令，开始站点签到 ...")
            self.post_message(channel=event.event_data.get("channel"),
                              title="开始站点签到 ...",
                              userid=event.event_data.get("user"))

        _force = self._clean
        refresh_triggered_site_ids = set()
        failed_sites = []
        task_context = self.__build_task_context()
        if self._sign_sites:
            self._clean = _force
            self.__do(today=today, type_str="签到", do_sites=self._sign_sites, event=event,
                      refresh_triggered_site_ids=refresh_triggered_site_ids, failed_sites=failed_sites,
                      task_context=task_context)
        if self._login_sites:
            self._clean = _force
            self.__do(today=today, type_str="登录", do_sites=self._login_sites, event=event,
                      refresh_triggered_site_ids=refresh_triggered_site_ids, failed_sites=failed_sites,
                      task_context=task_context)
        if failed_sites:
            refreshed_site_ids = set()
            for site in failed_sites:
                site_id = site.get("site_id")
                if site_id in refreshed_site_ids:
                    continue
                refreshed_site_ids.add(site_id)
            if refreshed_site_ids:
                self.eventmanager.send_event(EventType.PluginAction, {
                    "site_ids": list(refreshed_site_ids),
                    "action": "site_refresh"
                })
                logger.info(f"共 {len(refreshed_site_ids)} 个站点 Cookie 失效，批量触发 site_refresh: {refreshed_site_ids}")

    def __do(self, today: datetime, type_str: str, do_sites: list, event: Event = None,
             refresh_triggered_site_ids: set = None, failed_sites: list = None, task_context: dict = None):
        """
        签到逻辑
        """
        if refresh_triggered_site_ids is None:
            refresh_triggered_site_ids = set()
        if failed_sites is None:
            failed_sites = []
        expired_day = today - timedelta(days=14)
        expired_day_str = expired_day.strftime('%Y-%m-%d')
        # 删除详情页 14 天展示窗口之外的同日历史。
        # 正常每日执行时，每天恰好清理一个过期日期，无需枚举全部 PluginData。
        self.del_data(key=type_str + "-" + expired_day_str)
        self.del_data(key=f"{expired_day.month}月{expired_day.day}日")

        # 查看今天有没有签到|登录历史

        today_str = today.strftime('%Y-%m-%d')
        today_history = self.get_data(key=type_str + "-" + today_str)

        # sign_in() 的签到/登录共用同一站点快照；单站 API 则按本次调用创建快照。
        task_context = task_context or self.__build_task_context()
        all_sites = task_context["all_sites"]
        # 过滤掉没有选中的站点
        if do_sites:
            do_sites = [site for site in all_sites if site.get("id") in do_sites]
        else:
            do_sites = all_sites

        # 今日没数据
        if not today_history or self._clean:
            logger.info(f"今日 {today_str} 未{type_str}，开始{type_str}已选站点")
            if self._clean:
                # 关闭开关
                self._clean = False
        else:
            # 需要重试站点
            retry_sites = today_history.get("retry") or []
            # 今天已签到|登录站点
            already_sites = today_history.get("do") or []

            # 今日未签|登录站点
            no_sites = [site for site in do_sites if
                        site.get("id") not in already_sites or site.get("id") in retry_sites]

            if not no_sites:
                logger.info(f"今日 {today_str} 已{type_str}，无重新{type_str}站点，本次任务结束")
                return

            # 任务站点 = 需要重试+今日未do
            do_sites = no_sites
            logger.info(f"今日 {today_str} 已{type_str}，开始重试命中关键词站点")

        if not do_sites:
            logger.info(f"没有需要{type_str}的站点")
            return

        # 执行签到
        logger.info(f"开始执行{type_str}任务 ...")
        if type_str == "签到":
            action = partial(self.signin_site, cookie_cache=task_context["cookie_cache"])
        else:
            action = partial(self.login_site, cookie_cache=task_context["cookie_cache"])
        with ThreadPool(min(len(do_sites), int(self._queue_cnt))) as p:
            status = p.map(action, do_sites)

        if status:
            logger.info(f"站点{type_str}任务完成！")
            # 获取今天的日期
            key = f"{datetime.now().month}月{datetime.now().day}日"
            today_data = self.get_data(key)
            if today_data:
                if not isinstance(today_data, list):
                    today_data = [today_data]
                for s in status:
                    today_data.append({
                        "site": s[0],
                        "status": s[1]
                    })
            else:
                today_data = [{
                    "site": s[0],
                    "status": s[1]
                } for s in status]
            # 保存数据
            self.save_data(key, today_data)

            # 命中重试词的站点id
            retry_sites = []
            # 本轮成功站点id，存入历史 do 字段
            success_site_ids = []
            # 命中重试词的站点签到msg
            retry_msg = []
            # 登录成功
            login_success_msg = []
            # 签到成功
            sign_success_msg = []
            # 已签到
            already_sign_msg = []
            # 仿真签到成功
            fz_sign_msg = []
            # 失败｜错误
            failed_msg = []

            ordinary_site_ids = task_context["ordinary_site_ids"]
            # ThreadPool.map 保持输入顺序，结果与实际执行的站点记录一一对应。
            for site_info, result in zip(do_sites, status):
                site_id = site_info.get("id")
                site_name, message, signin_status = result

                if 'Cookie已失效' in str(message):
                    if site_id in ordinary_site_ids:
                        if site_id not in refresh_triggered_site_ids:
                            refresh_triggered_site_ids.add(site_id)
                            failed_sites.append({"site_id": site_id, "site_name": site_name})
                            logger.info(f"站点 {site_name} Cookie 失效，待汇总触发 site_refresh")
                        else:
                            logger.info(f"站点 {site_name} 本轮已加入 site_refresh 汇总，跳过重复加入")
                    else:
                        logger.info(f"自定义站点 {site_name} Cookie已失效，但不在 MoviePilot 站点表，SiteRefresh 无法回写 Cookie/UA")
                is_success = signin_status in SUCCESS_STATUSES

                # 成功站记入 do，失败站下轮自动重试；命中重试关键词的单独列入 retry_msg 通知
                if is_success:
                    if site_id:
                        success_site_ids.append(site_id)
                else:
                    if site_id:
                        retry_sites.append(site_id)
                    if self._retry_keyword and re.search(self._retry_keyword, message):
                        logger.debug(f"站点 {site_name} 命中重试关键词 {self._retry_keyword}")
                        retry_msg.append((site_name, message))
                        continue

                if signin_status == SigninStatus.LOGIN:
                    login_success_msg.append((site_name, message))
                elif signin_status == SigninStatus.SIM_SIGNIN:
                    fz_sign_msg.append((site_name, message))
                elif signin_status == SigninStatus.SUCCESS:
                    sign_success_msg.append((site_name, message))
                elif signin_status == SigninStatus.ALREADY:
                    already_sign_msg.append((site_name, message))
                else:
                    failed_msg.append((site_name, message))
            logger.debug(f"下次{type_str}重试站点 {retry_sites}")

            # 存入历史：合并今日已成功站点，避免部分重试轮次覆盖丢失已签到站点
            # （else 分支只重试失败站点，直接覆盖会丢掉上一轮已成功的 do）
            prior_do = []
            if isinstance(today_history, dict):
                prior_do = list(today_history.get("do") or [])
            saved_do = list(dict.fromkeys(prior_do + success_site_ids))
            self.save_data(key=type_str + "-" + today_str,
                           value={
                               "do": saved_do,
                               "retry": retry_sites
                           })

            # 自动Cloudflare IP优选
            if self._auto_cf and int(self._auto_cf) > 0 and retry_msg and len(retry_msg) >= int(self._auto_cf):
                self.eventmanager.send_event(EventType.PluginAction, {
                    "action": "cloudflare_speedtest"
                })

            # 发送通知
            if self._notify:
                # 签到详细信息 登录成功、签到成功、已签到、仿真签到成功、失败--命中重试
                signin_message = login_success_msg + sign_success_msg + already_sign_msg + fz_sign_msg + failed_msg
                if len(retry_msg) > 0:
                    signin_message += retry_msg

                signin_message = "\n".join([f'【{s[0]}】{s[1]}' for s in signin_message if s])
                self.post_message(title=f"【站点自动{type_str}】",
                                  mtype=NotificationType.SiteMessage,
                                  text=f"全部{type_str}数量: {len(self._sign_sites if type_str == '签到' else self._login_sites)} \n"
                                       f"本次{type_str}数量: {len(do_sites)} \n"
                                       f"下次{type_str}数量: {len(retry_sites)} \n"
                                       f"{signin_message}"
                                  )
            if event:
                self.post_message(channel=event.event_data.get("channel"),
                                  title=f"站点{type_str}完成！", userid=event.event_data.get("user"))
        else:
            logger.error(f"站点{type_str}任务失败！")
            if event:
                self.post_message(channel=event.event_data.get("channel"),
                                  title=f"站点{type_str}任务失败！", userid=event.event_data.get("user"))
        # 保存配置
        self.__update_config()

    def __build_class(self, url) -> Any:
        for site_schema in self._site_schema:
            try:
                if site_schema.match(url):
                    return site_schema
            except Exception as e:
                logger.error("站点模块加载失败：%s" % str(e))
        return None

    def signin_by_domain(self, url: str, apikey: str) -> schemas.Response:
        """签到指定站点的调试 API，支持普通站点和本插件自定义站点。

        ``url`` 可传完整站点 URL 或域名。该入口仅执行匹配到的一站，
        不修改插件配置、定时任务或当日批量签到历史。
        """
        if apikey != settings.API_TOKEN:
            return schemas.Response(success=False, message="API密钥错误")
        if not url or not str(url).strip():
            return schemas.Response(success=False, message="缺少站点URL或域名")

        target = str(url).strip()
        if "://" not in target:
            target = f"https://{target}"
        target_domain = StringUtils.get_url_domain(target)
        all_sites = [site for site in self.sites.get_indexers() if not site.get("public")]
        all_sites.extend(self.__custom_sites())
        site_info = next((site for site in all_sites
                          if StringUtils.url_equal(site.get("url", ""), target)
                          or StringUtils.get_url_domain(site.get("url", "")) == target_domain), None)
        if not site_info:
            return schemas.Response(
                success=False,
                message=f"站点【{target_domain or url}】不存在或未配置"
            )

        site_name, message, status = self.signin_site(site_info, cookie_cache=self.__new_cookie_cache())
        return schemas.Response(
            success=status in SUCCESS_STATUSES,
            message=f"站点【{site_name}】{message}"
        )

    def __build_task_context(self) -> dict:
        """创建一次批量任务共享的站点快照和 CookieCloud 缓存。"""
        ordinary_sites = [site for site in self.sites.get_indexers() if not site.get("public")]
        custom_sites = self.__custom_sites()
        return {
            "all_sites": ordinary_sites + custom_sites,
            # 保持原有语义：仅 MoviePilot 内置站点可触发 SiteRefresh 写回。
            "ordinary_site_ids": {site.get("id") for site in ordinary_sites if site.get("id") is not None},
            "cookie_cache": self.__new_cookie_cache(),
        }

    @staticmethod
    def __new_cookie_cache() -> dict:
        """CookieCloud 下载结果仅在单次任务内复用，避免跨任务使用旧 Cookie。"""
        return {"loaded": False, "cookies": {}, "lock": Lock()}

    @staticmethod
    def _fetch_cookie_cloud(site_url: str, cookie_cache: dict = None) -> str:
        """Cookie 为空时从 CookieCloud 按域名补取，支持单次任务缓存。"""
        try:
            from urllib.parse import urlparse
            from app.helper.cookiecloud import CookieCloudHelper
            cookie_cache = cookie_cache or AutoPtCheckin.__new_cookie_cache()
            with cookie_cache["lock"]:
                if not cookie_cache["loaded"]:
                    cookies, _ = CookieCloudHelper().download()
                    cookie_cache["cookies"] = cookies or {}
                    cookie_cache["loaded"] = True
            cookies = cookie_cache["cookies"]
            if not cookies:
                logger.info(f"CookieCloud 未配置或无数据，跳过补取（{site_url}）")
                return ""
            site_domain = urlparse(site_url).netloc
            for domain, cookie in cookies.items():
                if site_domain and site_domain.endswith(domain):
                    return cookie
            logger.info(f"CookieCloud 未匹配到 {site_domain} 的 Cookie")
        except Exception as e:
            logger.info(f"CookieCloud 补取失败（可能未配置）：{e}")
        return ""

    def _execute_site_action(self, site_info: CommentedMap, cookie_cache: dict,
                             action_name: str, execute, normalize_message=None, prepare=None) -> Tuple[str, str, SigninStatus]:
        """执行站点动作，统一处理 CookieCloud 补取、失效重试和站点统计。"""
        if not site_info.get("cookie"):
            cookie = self._fetch_cookie_cloud(site_info.get("url", ""), cookie_cache=cookie_cache)
            if cookie:
                logger.info(f"{site_info.get('name')} Cookie 为空，已从 CookieCloud 补取")
                site_info["cookie"] = cookie

        if prepare:
            prepare()
        start_time = datetime.now()
        state, message, status = self._unpack_execute(execute())
        if normalize_message:
            message = normalize_message(state, message)

        if "Cookie已失效" in str(message):
            old_cookie = site_info.get("cookie") or ""
            cookie = self._fetch_cookie_cloud(site_info.get("url", ""), cookie_cache=cookie_cache)
            if cookie and cookie != old_cookie:
                logger.info(f"{site_info.get('name')} Cookie已失效，已从 CookieCloud 补取并重试{action_name}")
                site_info["cookie"] = cookie
                site_id = site_info.get("id")
                if site_id and self.siteoper.get(site_id):
                    self.siteoper.update(site_id, {"cookie": cookie})
                state, message, status = self._unpack_execute(execute())
                if normalize_message:
                    message = normalize_message(state, message)

        seconds = (datetime.now() - start_time).seconds
        domain = StringUtils.get_url_domain(site_info.get('url'))
        if state:
            self.siteoper.success(domain=domain, seconds=seconds)
        else:
            self.siteoper.fail(domain)
        return site_info.get("name"), message, status

    @staticmethod
    def _unpack_execute(result) -> Tuple[bool, str, SigninStatus]:
        """兼容适配器二元组与通用处理器三元组返回，统一补齐结构化状态。"""
        if len(result) >= 3:
            return result[0], result[1], result[2]
        ok, msg = result[0], result[1]
        return ok, msg, infer_signin_status(ok, msg)

    @staticmethod
    def _describe_http_failure(status_code: int) -> str:
        """把传输层哨兵值和明确限流状态转换为可操作的失败原因。"""
        if status_code == 0:
            return "网络请求失败或超时"
        if status_code == 429:
            return "站点请求过于频繁（HTTP 429），请稍后重试"
        return f"状态码：{status_code}"

    def signin_site(self, site_info: CommentedMap, cookie_cache: dict = None) -> Tuple[str, str, SigninStatus]:
        """
        签到一个站点
        """
        site_module = None

        def prepare_signin():
            """在 Cookie 补取后按原顺序选择签到处理器。"""
            nonlocal site_module
            site_module = self.__build_class(site_info.get("url"))

        def do_signin() -> Tuple[bool, str, SigninStatus]:
            if site_module and hasattr(site_module, "signin"):
                try:
                    ok, msg = site_module().signin(site_info)
                    return ok, msg, infer_signin_status(ok, msg)
                except Exception as e:
                    logger.exception(f"{site_info.get('name')} 签到处理器异常：{e}")
                    return False, f"签到失败：{str(e)}", SigninStatus.FAILED
            return self.__signin_base(site_info)

        return self._execute_site_action(
            site_info=site_info,
            cookie_cache=cookie_cache,
            action_name="签到",
            execute=do_signin,
            normalize_message=lambda state, message: message or ("签到成功" if state else "签到失败"),
            prepare=prepare_signin,
        )

    @staticmethod
    def __signin_base(site_info: CommentedMap) -> Tuple[bool, str, SigninStatus]:
        """
        通用签到处理
        :param site_info: 站点信息
        :return: 签到结果信息
        """
        if not site_info:
            return False, "", SigninStatus.FAILED
        from app.plugins.autoptcheckin.helper.attendance_post_helper import (
            _AttendancePostHandler, ATTENDANCE_SIGNED, ATTENDANCE_FORM,
            ATTENDANCE_CAPTCHA, ATTENDANCE_NOT_FOUND,
        )
        site = site_info.get("name")
        site_url = site_info.get("url")
        site_cookie = site_info.get("cookie")
        ua = site_info.get("ua")
        render = site_info.get("render")
        timeout = site_info.get("timeout")
        proxies = settings.PROXY if site_info.get("proxy") else None
        proxy_server = settings.PROXY_SERVER if site_info.get("proxy") else None
        if not site_url or not site_cookie:
            logger.warning(f"未配置 {site} 的站点地址或Cookie，无法签到")
            return False, "签到失败，未配置站点地址或Cookie", SigninStatus.FAILED
        # 模拟登录
        try:
            # 访问链接
            checkin_url = site_url
            if site_url.find("attendance.php") == -1:
                # 拼登签到地址
                checkin_url = urljoin(site_url, "attendance.php")
            logger.info(f"开始站点签到：{site}，地址：{checkin_url}...")
            if render:
                page_source = PlaywrightHelper().get_page_source(url=checkin_url,
                                                                 cookies=site_cookie,
                                                                 ua=ua,
                                                                 proxies=proxy_server)
                if not SiteUtils.is_logged_in(page_source):
                    if under_challenge(page_source):
                        return False, f"无法通过Cloudflare！", SigninStatus.FAILED
                    elif any(kw in (page_source or "").lower() for kw in AutoPtCheckin._SITE_ERROR_KEYWORDS):
                        return False, f"仿真签到失败，站点服务器异常，稍后重试！", SigninStatus.FAILED
                    return False, f"仿真签到失败，Cookie已失效！", SigninStatus.FAILED
                else:
                    # 仿真模式下也必须确认签到状态，避免"登录即成功"误报
                    state = _AttendancePostHandler.detect_attendance_state(page_source)
                    if state == ATTENDANCE_SIGNED:
                        logger.info(f"{site} 仿真签到成功")
                        return True, "仿真签到成功", SigninStatus.SIM_SIGNIN
                    if state == ATTENDANCE_FORM:
                        logger.warning(f"{site} 仿真签到失败，站点需要 POST 签到适配器")
                        return False, "仿真签到失败：站点需要 POST 签到适配器", SigninStatus.NEEDS_ADAPTER
                    if state == ATTENDANCE_CAPTCHA:
                        logger.warning(f"{site} 仿真签到失败，站点需要验证码签到适配器")
                        return False, "仿真签到失败：站点需要验证码签到适配器", SigninStatus.NEEDS_ADAPTER
                    if state == ATTENDANCE_NOT_FOUND:
                        logger.warning(f"{site} 签到页不存在，站点可能已改版或下线签到")
                        return False, "签到失败：签到页不存在，站点可能已改版", SigninStatus.FAILED
                    logger.info(f"{site} 仿真登录成功")
                    return True, "仿真登录成功", SigninStatus.LOGIN
            else:
                request_timeout = timeout or 20
                res = RequestUtils(cookies=site_cookie,
                                   ua=ua,
                                   proxies=proxies,
                                   timeout=request_timeout
                                   ).get_res(url=checkin_url)
                if res is None or not (res.text or "").strip():
                    verify_timeout = max(request_timeout + 15, 30)
                    logger.info(f"{site} 签到请求无响应，重新读取签到页确认结果...")
                    res = RequestUtils(cookies=site_cookie,
                                       ua=ua,
                                       proxies=proxies,
                                       timeout=verify_timeout
                                       ).get_res(url=checkin_url)
                if res is not None and res.status_code == 200 and not (res.text or "").strip():
                    logger.warning(f"{site} 签到失败，站点返回空响应，无法确认签到结果")
                    return False, "签到失败，站点返回空响应，无法确认签到结果！", SigninStatus.FAILED
                if res is not None and res.status_code in [200, 500, 403]:
                    if not SiteUtils.is_logged_in(res.text):
                        if under_challenge(res.text):
                            msg = "站点被Cloudflare防护，请打开站点浏览器仿真"
                        elif any(kw in res.text.lower() for kw in AutoPtCheckin._SITE_ERROR_KEYWORDS):
                            msg = "站点服务器异常，稍后重试"
                        elif res.status_code == 200:
                            msg = "Cookie已失效"
                        else:
                            msg = AutoPtCheckin._describe_http_failure(res.status_code)
                        logger.warning(f"{site} 签到失败，{msg}")
                        return False, f"签到失败，{msg}！", SigninStatus.FAILED

                    # 已登录：必须确认签到状态，避免"GET 见登录即成功"误报
                    state = _AttendancePostHandler.detect_attendance_state(res.text)
                    if state == ATTENDANCE_SIGNED:
                        logger.info(f"{site} 今日已签到")
                        return True, "今日已签到", SigninStatus.ALREADY
                    if state == ATTENDANCE_FORM:
                        logger.warning(f"{site} 签到失败，站点需要 POST 签到适配器")
                        return False, "签到失败：站点需要 POST 签到适配器", SigninStatus.NEEDS_ADAPTER
                    if state == ATTENDANCE_CAPTCHA:
                        logger.warning(f"{site} 签到失败，站点需要验证码签到适配器")
                        return False, "签到失败：站点需要验证码签到适配器", SigninStatus.NEEDS_ADAPTER
                    if state == ATTENDANCE_NOT_FOUND:
                        logger.warning(f"{site} 签到页不存在，站点可能已改版或下线签到")
                        return False, "签到失败：签到页不存在，站点可能已改版", SigninStatus.FAILED
                    logger.warning(f"{site} 签到结果未确认，签到页可能改版")
                    return False, "签到失败：签到结果未确认，签到页可能改版", SigninStatus.FAILED
                if res is not None:
                    msg = AutoPtCheckin._describe_http_failure(res.status_code)
                    logger.warning(f"{site} 签到失败，{msg}")
                    return False, f"签到失败，{msg}！", SigninStatus.FAILED

                logger.warning(f"{site} 签到失败，网络请求失败或超时，无法确认签到结果")
                return False, "签到失败，网络请求失败或超时，无法确认签到结果！", SigninStatus.FAILED
        except Exception as e:
            logger.exception("%s 签到失败：%s" % (site, str(e)))
            return False, f"签到失败：{str(e)}！", SigninStatus.FAILED

    def login_site(self, site_info: CommentedMap, cookie_cache: dict = None) -> Tuple[str, str, SigninStatus]:
        """
        模拟登录一个站点
        """
        site_module = None

        def prepare_login():
            """在 Cookie 补取后按原顺序选择登录处理器。"""
            nonlocal site_module
            site_module = self.__build_class(site_info.get("url"))

        def do_login() -> Tuple[bool, str, SigninStatus]:
            if site_module and hasattr(site_module, "login"):
                try:
                    ok, msg = site_module().login(site_info)
                    return ok, msg, infer_signin_status(ok, msg)
                except Exception as e:
                    logger.exception(f"{site_info.get('name')} 模拟登录处理器异常：{e}")
                    return False, f"模拟登录失败：{str(e)}", SigninStatus.FAILED
            return self.__login_base(site_info)

        # 保持现有语义：模拟登录的空消息不补默认文案。
        return self._execute_site_action(
            site_info=site_info,
            cookie_cache=cookie_cache,
            action_name="登录",
            execute=do_login,
            prepare=prepare_login,
        )

    @staticmethod
    def __login_base(site_info: CommentedMap) -> Tuple[bool, str, SigninStatus]:
        """
        模拟登录通用处理
        :param site_info: 站点信息
        :return: 签到结果信息
        """
        if not site_info:
            return False, "", SigninStatus.FAILED
        site = site_info.get("name")
        site_url = site_info.get("url")
        site_cookie = site_info.get("cookie")
        ua = site_info.get("ua")
        render = site_info.get("render")
        timeout = site_info.get("timeout")
        proxies = settings.PROXY if site_info.get("proxy") else None
        proxy_server = settings.PROXY_SERVER if site_info.get("proxy") else None
        if not site_url or not site_cookie:
            logger.warning(f"未配置 {site} 的站点地址或Cookie，无法登录")
            return False, "模拟登录失败，未配置站点地址或Cookie", SigninStatus.FAILED
        # 模拟登录
        try:
            # 访问链接
            site_url = str(site_url).replace("attendance.php", "")
            logger.info(f"开始站点模拟登录：{site}，地址：{site_url}...")
            if render:
                page_source = PlaywrightHelper().get_page_source(url=site_url,
                                                                 cookies=site_cookie,
                                                                 ua=ua,
                                                                 proxies=proxy_server)
                if not SiteUtils.is_logged_in(page_source):
                    if under_challenge(page_source):
                        return False, f"无法通过Cloudflare！", SigninStatus.FAILED
                    elif any(kw in (page_source or "").lower() for kw in AutoPtCheckin._SITE_ERROR_KEYWORDS):
                        return False, f"仿真登录失败，站点服务器异常，稍后重试！", SigninStatus.FAILED
                    return False, f"仿真登录失败，Cookie已失效！", SigninStatus.FAILED
                else:
                    return True, "模拟登录成功", SigninStatus.LOGIN
            else:
                page_text = None
                try:
                    res = RequestUtils(cookies=site_cookie,
                                       ua=ua,
                                       proxies=proxies,
                                       timeout=timeout or 20
                                       ).get_res(url=site_url)
                    if res is not None and res.status_code == 200:
                        page_text = res.text or None
                    elif res is not None and res.status_code not in [200, 500, 403]:
                        msg = AutoPtCheckin._describe_http_failure(res.status_code)
                        logger.warning(f"{site} 模拟登录失败，{msg}")
                        return False, f"模拟登录失败，{msg}！", SigninStatus.FAILED
                except Exception as req_err:
                    logger.warning(f"{site} RequestUtils 请求失败，尝试 CffiClient 回退：{req_err}")

                # CffiClient 回退（WAF / gzip 异常等场景）
                if page_text is None:
                    try:
                        from app.plugins.autoptcheckin.helper.http_helper import CffiClient
                        status, page_text = CffiClient(
                            cookie=site_cookie or "",
                            ua=ua,
                            proxy=proxy_server,
                        ).get(site_url, timeout=timeout or 60)
                        if status not in [200, 500, 403]:
                            msg = AutoPtCheckin._describe_http_failure(status)
                            logger.warning(f"{site} 模拟登录失败，{msg}")
                            return False, f"模拟登录失败，{msg}！", SigninStatus.FAILED
                    except Exception as cffi_err:
                        logger.warning(f"{site} 模拟登录失败，无法打开网站：{cffi_err}")
                        return False, f"模拟登录失败，无法打开网站！", SigninStatus.FAILED

                # 判断登录状态
                if not page_text:
                    logger.warning(f"{site} 模拟登录失败，无法打开网站")
                    return False, f"模拟登录失败，无法打开网站！", SigninStatus.FAILED
                if not SiteUtils.is_logged_in(page_text):
                    if under_challenge(page_text):
                        msg = "站点被Cloudflare防护，请打开站点浏览器仿真"
                    elif any(kw in page_text.lower() for kw in AutoPtCheckin._SITE_ERROR_KEYWORDS):
                        msg = "站点服务器异常，稍后重试"
                    else:
                        msg = "Cookie已失效"
                    logger.warning(f"{site} 模拟登录失败，{msg}")
                    return False, f"模拟登录失败，{msg}！", SigninStatus.FAILED
                else:
                    logger.info(f"{site} 模拟登录成功")
                    return True, f"模拟登录成功", SigninStatus.LOGIN
        except Exception as e:
            logger.exception("%s 模拟登录失败：%s" % (site, str(e)))
            return False, f"模拟登录失败：{str(e)}！", SigninStatus.FAILED

    def stop_service(self):
        """
        退出插件
        """
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown()
                self._scheduler = None
        except Exception as e:
            logger.error("退出插件失败：%s" % str(e))

    @eventmanager.register(EventType.SiteDeleted)
    def site_deleted(self, event):
        """
        删除对应站点选中
        """
        site_id = event.event_data.get("site_id")
        config = self.get_config()
        if config:
            self._sign_sites = self.__remove_site_id(config.get("sign_sites") or [], site_id)
            self._login_sites = self.__remove_site_id(config.get("login_sites") or [], site_id)
            # 保存配置
            self.__update_config()

    def __remove_site_id(self, do_sites, site_id):
        if do_sites:
            if isinstance(do_sites, str):
                do_sites = [do_sites]

            # 删除对应站点
            if site_id is not None:
                do_sites = [site for site in do_sites if str(site) != str(site_id)]
            else:
                # 清空
                do_sites = []

            # 若无站点，则停止
            if len(do_sites) == 0:
                self._enabled = False

        return do_sites
