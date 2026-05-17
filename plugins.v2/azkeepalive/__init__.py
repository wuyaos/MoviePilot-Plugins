# input: MoviePilot _PluginBase | output: AnimeZ 保活插件 | pos: 插件入口
from __future__ import annotations
import threading
from typing import Any, Dict, List, Optional, Tuple

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.core.config import settings as app_settings
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import NotificationType
from app.utils.timer import TimerUtils

from .core.form_utils import v_col, v_cron, v_row, v_select, v_switch, v_text
from .core.page import build_page


class AzKeepAlive(_PluginBase):
    plugin_name = "AnimeZ保活"
    plugin_desc = "定时访问AnimeZ站点并从种子页选种提交下载器，满足保活要求"
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/refresh.png"
    plugin_version = "2.4.5"
    plugin_author = "wuyaos"
    author_url = "https://github.com/wuyaos"
    plugin_config_prefix = "azkeepalive_"
    plugin_order = 30
    auth_level = 2

    _enabled = False
    _notify = True
    _cron = ""
    _onlyonce = False
    _force_keepalive = False
    _site_url = "https://animez.to/"
    _downloader = ""
    _qb_category = "AnimeZ"
    _qb_tags = "keepalive"
    _keepalive_days = 30
    _min_seeders = 5
    _max_size_gb = 10.0
    _require_free = True
    _timeout = 30
    _use_proxy = False
    _auto_delete_hnr = False
    _scheduler: Optional[BackgroundScheduler] = None
    _run_lock = threading.Lock()

    def init_plugin(self, config: dict = None):
        self.stop_service()
        self._ensure_plugin_log_file()
        config = config or {}
        self._enabled = bool(config.get("enabled"))
        self._notify = bool(config.get("notify", True))
        self._cron = str(config.get("cron") or "").strip()
        self._onlyonce = bool(config.get("onlyonce"))
        self._force_keepalive = bool(config.get("force_keepalive"))
        self._site_url = str(config.get("site_url") or "https://animez.to/").strip().rstrip("/")
        self._downloader = str(config.get("downloader") or "")
        self._qb_category = str(config.get("qb_category") or "AnimeZ")
        self._qb_tags = str(config.get("qb_tags") or "keepalive")
        self._keepalive_days = int(config.get("keepalive_days") or 30)
        self._min_seeders = int(config.get("min_seeders") or 5)
        self._max_size_gb = float(config.get("max_size_gb") or 10.0)
        self._require_free = bool(config.get("require_free", True))
        self._timeout = int(config.get("timeout") or 30)
        self._use_proxy = bool(config.get("use_proxy"))
        self._auto_delete_hnr = bool(config.get("auto_delete_hnr"))
        if self._onlyonce or self._force_keepalive:
            force = self._force_keepalive
            self._scheduler = BackgroundScheduler(timezone=app_settings.TZ)
            self._scheduler.add_job(lambda: self._run_task(force=force), "date",
                                    name="AnimeZ保活-立即执行")
            self._scheduler.start()
            self._onlyonce = False
            self._force_keepalive = False
            self._save_config()

    def get_state(self) -> bool:
        return self._enabled

    def _ensure_plugin_log_file(self):
        """确保插件日志文件存在，避免前端日志页 404"""
        try:
            from app.core.config import settings
            path = settings.LOG_PATH / "plugins" / "azkeepalive.log"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)
        except Exception:
            pass

    def _save_config(self):
        self.update_config({
            "enabled": self._enabled, "notify": self._notify,
            "cron": self._cron, "onlyonce": False, "force_keepalive": False,
            "site_url": self._site_url, "downloader": self._downloader,
            "qb_category": self._qb_category, "qb_tags": self._qb_tags,
            "keepalive_days": self._keepalive_days, "min_seeders": self._min_seeders,
            "max_size_gb": self._max_size_gb, "require_free": self._require_free,
            "timeout": self._timeout, "use_proxy": self._use_proxy,
            "auto_delete_hnr": self._auto_delete_hnr,
        })

    def _run_task(self, force: bool = False):
        if not self._run_lock.acquire(blocking=False):
            logger.warning("AnimeZ保活: 已有任务运行中，跳过本次触发")
            return
        try:
            self._run_task_locked(force=force)
        finally:
            self._run_lock.release()

    def _run_task_locked(self, force: bool = False):
        from .core.keepalive import run_keepalive
        from .core.downloader import get_downloader_instance
        from .core.scraper import get_site_cookie
        if not self._site_url:
            logger.warning("AnimeZ保活: 缺少站点地址"); return
        dl_instance = get_downloader_instance(self._downloader)
        if not dl_instance:
            logger.warning("AnimeZ保活: 下载器未配置或不可用，仅执行站点访问保活")
        state = self.get_data("state") or {}
        cookie = get_site_cookie(self._site_url)
        status, message, state = run_keepalive(
            site_url=self._site_url, downloader_instance=dl_instance,
            category=self._qb_category, tags=self._qb_tags,
            keepalive_days=self._keepalive_days, min_seeders=self._min_seeders,
            max_size_gb=self._max_size_gb, require_free=self._require_free,
            timeout=self._timeout, use_proxy=self._use_proxy,
            cookie=cookie, state=state, force=force,
            auto_delete_hnr=self._auto_delete_hnr,
        )
        self.save_data("state", state)
        logger.info(f"AnimeZ保活: [{status}] {message}")
        if self._notify and status != "skipped":
            self.post_message(title="【AnimeZ保活】",
                              mtype=NotificationType.SiteMessage, text=message)

    def _run_force_task(self):
        self._run_task(force=True)

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        return []

    def get_service(self) -> List[Dict[str, Any]]:
        if not self._enabled:
            return []
        services = []
        if self._cron:
            try:
                if self._cron.count(" ") != 4:
                    logger.error("AnimeZ保活 cron 错误: 需要 5 位 cron 表达式")
                    return []
                services.append({"id": "AzKeepAlive", "name": "AnimeZ保活定时任务",
                                 "trigger": CronTrigger.from_crontab(self._cron),
                                 "func": self._run_task, "kwargs": {}})
            except Exception as e:
                logger.error(f"AnimeZ保活 cron 错误: {e}")
                return []
        else:
            # 无 cron 时每天随机执行一次（9-23点间）
            triggers = TimerUtils.random_scheduler(
                num_executions=1, begin_hour=9, end_hour=23, min_interval=60, max_interval=120)
            if not triggers:
                logger.error("AnimeZ保活未生成有效随机定时任务")
                return []
            logger.info("AnimeZ保活随机触发时间：%s" %
                        ", ".join([f"{t.hour:02d}:{t.minute:02d}" for t in triggers]))
            for t in triggers:
                services.append({"id": f"AzKeepAlive.{t.hour:02d}{t.minute:02d}",
                                 "name": f"AnimeZ保活定时任务 {t.hour:02d}:{t.minute:02d}",
                                 "trigger": CronTrigger(hour=t.hour, minute=t.minute),
                                 "func": self._run_task, "kwargs": {}})
        services.extend([
            {"id": "AzKeepAliveRunNow", "name": "AnimeZ保活-立即运行",
             "trigger": None, "func": self._run_task, "kwargs": {}},
            {"id": "AzKeepAliveForceRun", "name": "AnimeZ保活-强制保活",
             "trigger": None, "func": self._run_force_task, "kwargs": {}},
        ])
        return services

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        try:
            from app.helper.downloader import DownloaderHelper
            services = DownloaderHelper().get_services() or {}
            dl_options = [{"title": n, "value": n} for n in services.keys()]
        except Exception as e:
            logger.debug(f"获取下载器列表失败: {e}")
            dl_options = []

        def _sec(text: str) -> dict:
            return {"component": "VRow", "content": [{"component": "VCol", "props": {"cols": 12},
                "content": [{"component": "div", "props": {
                    "class": "text-subtitle-2 font-weight-medium text-medium-emphasis pt-2 pb-1"
                }, "text": text}]}]}

        return [{"component": "VForm", "content": [
            # ── 基本控制 ───────────────────────────
            v_row([
                v_col(3, v_switch("enabled", "启用插件")),
                v_col(3, v_switch("notify", "发送通知")),
                v_col(3, v_switch("onlyonce", "立即运行一次")),
                v_col(3, v_switch("force_keepalive", "强制保活")),
            ]),
            # ── 站点与下载器 ───────────────────────
            _sec("🌐 站点与下载器"),
            v_row([
                v_col(5, v_text("site_url", "站点地址", "https://animez.to/")),
                v_col(4, v_select("downloader", "下载器", dl_options)),
                v_col(3, v_switch("use_proxy", "使用代理")),
            ]),
            v_row([
                v_col(3, v_text("qb_category", "分类(qB)/标签(TR)", "AnimeZ")),
                v_col(3, v_text("qb_tags", "额外标签(仅qB)", "keepalive")),
                v_col(6, v_cron("cron", "执行周期", "留空=每天随机一次")),
            ]),
            # ── 筛选参数 ───────────────────────────
            _sec("🔍 筛选参数"),
            v_row([
                v_col(3, v_text("keepalive_days", "插件保活间隔(天)")),
                v_col(3, v_text("min_seeders", "最小做种数")),
                v_col(3, v_text("max_size_gb", "最大体积(GB)")),
                v_col(3, v_text("timeout", "超时(秒)")),
            ]),
            # ── H&R 控制 ──────────────────────────
            _sec("⏱ H&R 控制"),
            v_row([
                v_col(3, v_switch("require_free", "仅Free种子")),
                v_col(3, v_switch("auto_delete_hnr", "H&R到期自动删除")),
                v_col(6, {"component": "VAlert", "props": {
                    "type": "warning", "variant": "tonal", "density": "compact",
                    "text": "开启后，满足做种时限的H&R种子将被自动删除（保留文件）",
                }}),
            ]),
            # ── 说明 ──────────────────────────────
            v_row([v_col(12, {"component": "VAlert", "props": {
                "type": "info", "variant": "tonal",
                "text": "AZ保活策略：① 每 60 天至少登录一次，否则账号删除；"
                        "② 每 90 天至少下载 1 个种子，否则账号禁用。"
                        "插件按保活间隔执行访问和下载，默认30天冗余保活；"
                        "种子自动打 H&R 标签，到期后自动移除（可选删除）。"
            }})]),
        ]}], {
            "enabled": False, "notify": True, "cron": "", "onlyonce": False, "force_keepalive": False,
            "site_url": "https://animez.to/",
            "downloader": "", "qb_category": "AnimeZ", "qb_tags": "keepalive",
            "require_free": True, "auto_delete_hnr": False,
            "keepalive_days": 30, "min_seeders": 5,
            "max_size_gb": 10.0, "timeout": 30, "use_proxy": False,
        }

    def get_page(self) -> List[dict]:
        try:
            state = self.get_data("state") or {}
            dl_torrents = []
            try:
                from .core.downloader import get_downloader_instance, dl_list_category
                inst = get_downloader_instance(self._downloader)
                if inst:
                    dl_torrents = dl_list_category(inst, self._qb_category)
            except Exception as e:
                logger.debug(f"查询下载器种子失败: {e}")
            return build_page(state, self._keepalive_days, dl_torrents, dl_name=self._downloader)
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
