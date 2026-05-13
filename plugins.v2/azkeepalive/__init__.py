# input: MoviePilot _PluginBase | output: AnimeZ 保活插件 | pos: 插件入口

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings as app_settings
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import NotificationType
from app.utils.timer import TimerUtils

from .core.page import build_page, v_col, v_cron, v_row, v_select, v_switch, v_text


class AzKeepAlive(_PluginBase):
    plugin_name = "AnimeZ保活"
    plugin_desc = "定时访问 AnimeZ 站点并从 RSS 选种提交下载器，满足保活要求"
    plugin_icon = "https://raw.githubusercontent.com/jxxghp/MoviePilot-Plugins/main/icons/refresh.png"
    plugin_version = "1.1.0"
    plugin_author = "wuyaos"
    author_url = "https://github.com/wuyaos"
    plugin_config_prefix = "azkeepalive_"
    plugin_order = 30
    auth_level = 2

    _enabled = False
    _notify = True
    _cron = ""
    _onlyonce = False
    _rss_url = ""
    _site_url = "https://animez.to/"
    _downloader = ""
    _qb_category = "AnimeZ"
    _qb_tags = "keepalive"
    _keepalive_days = 30
    _min_seeders = 5
    _max_items = 50
    _timeout = 30
    _use_proxy = False
    _scheduler: Optional[BackgroundScheduler] = None

    def init_plugin(self, config: dict = None):
        self.stop_service()
        config = config or {}
        self._enabled = bool(config.get("enabled"))
        self._notify = bool(config.get("notify", True))
        self._cron = str(config.get("cron") or "").strip()
        self._onlyonce = bool(config.get("onlyonce"))
        self._rss_url = str(config.get("rss_url") or "").strip()
        self._site_url = str(config.get("site_url") or "https://animez.to/").strip().rstrip("/")
        self._downloader = str(config.get("downloader") or "")
        self._qb_category = str(config.get("qb_category") or "AnimeZ")
        self._qb_tags = str(config.get("qb_tags") or "keepalive")
        self._keepalive_days = int(config.get("keepalive_days") or 30)
        self._min_seeders = int(config.get("min_seeders") or 5)
        self._max_items = int(config.get("max_items") or 50)
        self._timeout = int(config.get("timeout") or 30)
        self._use_proxy = bool(config.get("use_proxy"))
        if self._onlyonce:
            self._scheduler = BackgroundScheduler(timezone=app_settings.TZ)
            self._scheduler.add_job(self._run_task, "date", name="AnimeZ保活-立即执行")
            self._scheduler.start()
            self._onlyonce = False
            self._save_config()

    def get_state(self) -> bool:
        return self._enabled

    def _save_config(self):
        self.update_config({
            "enabled": self._enabled, "notify": self._notify,
            "cron": self._cron, "onlyonce": False,
            "rss_url": self._rss_url, "site_url": self._site_url,
            "downloader": self._downloader,
            "qb_category": self._qb_category, "qb_tags": self._qb_tags,
            "keepalive_days": self._keepalive_days, "min_seeders": self._min_seeders,
            "max_items": self._max_items, "timeout": self._timeout,
            "use_proxy": self._use_proxy,
        })

    def _run_task(self):
        from .core.keepalive import run_keepalive
        from .core.qb_client import get_downloader_instance
        from .core.rss import get_site_cookie
        if not self._rss_url:
            logger.warning("AnimeZ保活: 缺少 RSS URL"); return
        dl_instance = get_downloader_instance(self._downloader)
        if not dl_instance:
            logger.warning("AnimeZ保活: 下载器未配置或不可用"); return
        state = self.get_data("state") or {}
        cookie = get_site_cookie(self._site_url)
        status, message, state = run_keepalive(
            rss_url=self._rss_url, downloader_instance=dl_instance,
            category=self._qb_category, tags=self._qb_tags,
            keepalive_days=self._keepalive_days, min_seeders=self._min_seeders,
            max_items=self._max_items, timeout=self._timeout,
            use_proxy=self._use_proxy, site_url=self._site_url,
            cookie=cookie, state=state,
        )
        self.save_data("state", state)
        logger.info(f"AnimeZ保活: [{status}] {message}")
        if self._notify and status != "skipped":
            self.post_message(title="【AnimeZ保活】",
                              mtype=NotificationType.SiteMessage, text=message)

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        return []

    def get_service(self) -> List[Dict[str, Any]]:
        if not self._enabled:
            return []
        if self._cron:
            try:
                return [{"id": "AzKeepAlive", "name": "AnimeZ保活",
                         "trigger": CronTrigger.from_crontab(self._cron),
                         "func": self._run_task, "kwargs": {}}]
            except Exception as e:
                logger.error(f"AnimeZ保活 cron 错误: {e}")
        # 无 cron 时每天随机执行一次（9-23点间）
        triggers = TimerUtils.random_scheduler(
            num_executions=1, begin_hour=9, end_hour=23, min_interval=60, max_interval=120)
        return [{"id": f"AzKeepAlive|{t.hour}:{t.minute}", "name": "AnimeZ保活",
                 "trigger": "cron", "func": self._run_task,
                 "kwargs": {"hour": t.hour, "minute": t.minute}} for t in triggers]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        try:
            from app.helper.downloader import DownloaderHelper
            services = DownloaderHelper().get_services() or {}
            dl_options = [{"title": n, "value": n} for n in services.keys()]
        except Exception as e:
            logger.debug(f"获取下载器列表失败: {e}")
            dl_options = []
        return [{"component": "VForm", "content": [
            v_row([
                v_col(3, v_switch("enabled", "启用插件")),
                v_col(3, v_switch("notify", "发送通知")),
                v_col(3, v_switch("onlyonce", "立即运行一次")),
                v_col(3, v_switch("use_proxy", "使用代理")),
            ]),
            v_row([
                v_col(6, v_text("rss_url", "RSS 地址", "https://animez.to/your-private-rss")),
                v_col(6, v_text("site_url", "站点地址（定时访问）", "https://animez.to/")),
            ]),
            v_row([
                v_col(4, v_select("downloader", "下载器", dl_options)),
                v_col(4, v_text("qb_category", "下载分类")),
                v_col(4, v_text("qb_tags", "下载标签")),
            ]),
            v_row([
                v_col(4, v_cron("cron", "执行周期", "留空=每天随机一次")),
                v_col(4, v_text("keepalive_days", "保活间隔(天)")),
                v_col(4, v_text("min_seeders", "最小做种数")),
            ]),
            v_row([v_col(12, {"component": "VAlert", "props": {
                "type": "info", "variant": "tonal",
                "text": "AZ保活策略：① 每 60 天至少登录一次，否则账号删除；"
                        "② 每 90 天至少下载 1 个种子，否则账号禁用。"
                        "本插件每天定时访问站点满足登录要求，并在保活窗口到期前自动从 RSS "
                        "筛选体积最小、做种数达标的种子提交到下载器满足下载要求。"
                        "默认 30 天一次下载（留 60 天容错），执行周期留空则每天 9-23 点随机执行。"
            }})]),
        ]}], {
            "enabled": False, "notify": True, "cron": "", "onlyonce": False,
            "rss_url": "", "site_url": "https://animez.to/",
            "downloader": "", "qb_category": "AnimeZ", "qb_tags": "keepalive",
            "keepalive_days": 30, "min_seeders": 5, "max_items": 50,
            "timeout": 30, "use_proxy": False,
        }

    def get_page(self) -> List[dict]:
        try:
            state = self.get_data("state") or {}
            return build_page(state, self._keepalive_days)
        except Exception as e:
            logger.error(f"AnimeZ保活详情页失败: {e}")
            return [{"component": "VAlert", "props": {
                "type": "error", "variant": "tonal", "text": f"详情页加载失败: {e}"
            }}]

    def stop_service(self):
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown()
                self._scheduler = None
        except Exception as e:
            logger.error(f"AnimeZ保活停止失败: {e}")
