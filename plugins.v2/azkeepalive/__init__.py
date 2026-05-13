# input: MoviePilot _PluginBase | output: AnimeZ 保活插件 | pos: 插件入口

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings as app_settings
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import NotificationType


from .core.page import build_page, v_col, v_cron, v_row, v_switch, v_text


class AzKeepAlive(_PluginBase):
    plugin_name = "AnimeZ保活"
    plugin_desc = "定时从 AnimeZ 私有 RSS 选种提交 qBittorrent，满足 90 天保活要求"
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/signin.png"
    plugin_version = "1.0.0"
    plugin_author = "wuyaos"
    author_url = "https://github.com/wuyaos"
    plugin_config_prefix = "azkeepalive_"
    plugin_order = 30
    auth_level = 2

    _enabled = False
    _notify = True
    _cron = "17 3 * * 0"
    _onlyonce = False
    _rss_url = ""
    _site_url = ""
    _qb_url = ""
    _qb_username = ""
    _qb_password = ""
    _qb_category = "AnimeZ"
    _qb_tags = "keepalive"
    _keepalive_days = 75
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
        self._cron = str(config.get("cron") or "17 3 * * 0").strip()
        self._onlyonce = bool(config.get("onlyonce"))
        self._rss_url = str(config.get("rss_url") or "").strip()
        self._site_url = str(config.get("site_url") or "").strip().rstrip("/")
        self._qb_url = str(config.get("qb_url") or "").strip().rstrip("/")
        self._qb_username = str(config.get("qb_username") or "")
        self._qb_password = str(config.get("qb_password") or "")
        self._qb_category = str(config.get("qb_category") or "AnimeZ")
        self._qb_tags = str(config.get("qb_tags") or "keepalive")
        self._keepalive_days = int(config.get("keepalive_days") or 75)
        self._min_seeders = int(config.get("min_seeders") or 5)
        self._max_items = int(config.get("max_items") or 50)
        self._timeout = int(config.get("timeout") or 30)
        self._use_proxy = bool(config.get("use_proxy"))

        if self._onlyonce:
            self._scheduler = BackgroundScheduler(timezone=app_settings.TZ)
            self._scheduler.add_job(self._run_task, "date",
                                    name="AnimeZ保活-立即执行")
            self._scheduler.start()
            self._onlyonce = False
            self._save_config()

    def get_state(self) -> bool:
        return self._enabled

    def _save_config(self):
        self.update_config({
            "enabled": self._enabled, "notify": self._notify,
            "cron": self._cron, "onlyonce": False, "rss_url": self._rss_url,
            "site_url": self._site_url, "qb_url": self._qb_url,
            "qb_password": self._qb_password, "qb_category": self._qb_category,
            "qb_tags": self._qb_tags, "keepalive_days": self._keepalive_days,
            "min_seeders": self._min_seeders, "max_items": self._max_items,
            "timeout": self._timeout, "use_proxy": self._use_proxy,
        })

    def _run_task(self):
        from .core.keepalive import run_keepalive
        from .core.models import QBSettings

        if not self._rss_url or not self._qb_url:
            logger.warning("AnimeZ保活: 缺少 RSS URL 或 qBittorrent URL")
            return

        state = self.get_data("state") or {}
        qb = QBSettings(
            url=self._qb_url, username=self._qb_username,
            password=self._qb_password, category=self._qb_category,
            tags=self._qb_tags,
        )
        status, message, state = run_keepalive(
            rss_url=self._rss_url, qb=qb,
            keepalive_days=self._keepalive_days, min_seeders=self._min_seeders,
            max_items=self._max_items, timeout=self._timeout,
            use_proxy=self._use_proxy, site_url=self._site_url, state=state,
        )
        self.save_data("state", state)
        logger.info(f"AnimeZ保活: [{status}] {message}")

        if self._notify and status != "skipped":
            self.post_message(
                title="【AnimeZ保活】",
                mtype=NotificationType.SiteMessage,
                text=message,
            )

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        return []

    def get_service(self) -> List[Dict[str, Any]]:
        if not self._enabled or not self._cron:
            return []
        try:
            return [{
                "id": "AzKeepAlive",
                "name": "AnimeZ保活定时任务",
                "trigger": CronTrigger.from_crontab(self._cron),
                "func": self._run_task,
                "kwargs": {},
            }]
        except Exception as e:
            logger.error(f"AnimeZ保活 cron 配置错误: {e}")
            return []

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [{"component": "VForm", "content": [
            v_row([
                v_col(3, v_switch("enabled", "启用插件")),
                v_col(3, v_switch("notify", "发送通知")),
                v_col(3, v_switch("onlyonce", "立即运行一次")),
                v_col(3, v_switch("use_proxy", "使用代理")),
            ]),
            v_row([
                v_col(6, v_text("rss_url", "AnimeZ RSS URL", "https://animez.to/your-private-rss")),
                v_col(6, v_text("site_url", "站点访问地址", "https://animez.to/")),
            ]),
            v_row([
                v_col(6, v_text("qb_url", "qBittorrent 地址", "http://127.0.0.1:8080")),
                v_col(3, v_text("qb_username", "qB 用户名", "留空=无认证")),
                v_col(3, v_text("qb_password", "qB 密码", "", "password")),
            ]),
            v_row([
                v_col(3, v_text("qb_category", "qB 分类")),
                v_col(3, v_text("qb_tags", "qB 标签")),
                v_col(3, v_cron("cron", "执行周期", "17 3 * * 0")),
                v_col(3, v_text("keepalive_days", "保活间隔(天)")),
            ]),
            v_row([
                v_col(4, v_text("min_seeders", "最小做种数")),
                v_col(4, v_text("max_items", "最大扫描条目")),
                v_col(4, v_text("timeout", "超时(秒)")),
            ]),
            v_row([v_col(12, {"component": "VAlert", "props": {
                "type": "info", "variant": "tonal",
                "text": "AnimeZ 要求 90 天内至少下载一个种子。插件按 cron 周期检查 RSS，"
                        "筛选做种数 >= 阈值且体积最小的种子，提交到 qBittorrent。"
                        "保活间隔建议 75 天，留 15 天容错。"
            }})]),
        ]}], {
            "enabled": False, "notify": True, "cron": "17 3 * * 0",
            "onlyonce": False, "rss_url": "", "site_url": "",
            "qb_url": "", "qb_username": "", "qb_password": "",
            "qb_category": "AnimeZ", "qb_tags": "keepalive",
            "keepalive_days": 75, "min_seeders": 5,
            "max_items": 50, "timeout": 30, "use_proxy": False,
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
