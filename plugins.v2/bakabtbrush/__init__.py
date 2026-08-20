"""MoviePilot V2 BakaBT Freeleech 刷流插件入口。"""

from __future__ import annotations

import threading
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings as app_settings
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import NotificationType

from .core.config import BrushConfig, ConfigError
from .core.cookie import resolve_cookie
from .core.downloader import DownloaderError, get_qb_instance
from .core.form import build_form
from .core.notification import build_notification
from .core.page import build_page
from .core.runner import RunResult, run_once
from .core.scraper import BROWSE_URL
from .core.state import normalize_state, record_run


class BakaBTBrush(_PluginBase):
    """按发布时间和体积选择 BakaBT Freeleech，并提交到 MoviePilot 配置的 qB。"""

    plugin_name = "BakaBT 刷流"
    plugin_desc = "定时筛选 BakaBT Freeleech 种子并提交到 qBittorrent"
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/bakabtbrush.png"
    plugin_version = "0.1.4"
    plugin_author = "wuyaos"
    author_url = "https://github.com/wuyaos"
    plugin_config_prefix = "bakabtbrush_"
    plugin_order = 30
    auth_level = 2

    _enabled = False
    _notify = True
    _onlyonce = False
    _dry_run = False
    _cron = "*/10 * * * *"
    _cookie = ""
    _timeout = 20
    _detail_request_retries = 3

    _scheduler: BackgroundScheduler | None = None
    _run_lock = threading.Lock()
    _runtime_config: BrushConfig | None = None
    _pending_cookie_write = ""

    def init_plugin(self, config: dict | None = None) -> None:
        """加载 MoviePilot 配置；立即运行仅在用户显式勾选时触发一次。"""
        self.stop_service()
        self._ensure_plugin_log_file()
        raw_config = config or {}
        try:
            self._runtime_config = BrushConfig.from_mapping(raw_config)
        except ConfigError as err:
            self._enabled = False
            self._runtime_config = None
            logger.error(f"BakaBT 刷流配置无效：{err}")
            return
        self._apply_config(self._runtime_config)
        self._onlyonce = bool(raw_config.get("onlyonce", False))

        if self._onlyonce or self._dry_run:
            # 两个开关同时开启时，试运行优先，确保本次绝不推送 qB。
            run_dry_run = self._consume_dry_run()
            self._onlyonce = False
            # 两种一次性操作都在任务创建前关闭，reload 不会重复执行。
            self._save_config()
            self._scheduler = BackgroundScheduler(timezone=app_settings.TZ)
            self._scheduler.add_job(
                self._safe_run_task,
                "date",
                run_date=datetime.now(tz=pytz.timezone(app_settings.TZ)) + timedelta(seconds=3),
                kwargs={"dry_run": run_dry_run},
                name="BakaBT 刷流立即试运行" if run_dry_run else "BakaBT 刷流立即运行",
            )
            self._scheduler.start()

    def _apply_config(self, config: BrushConfig) -> None:
        self._enabled = config.enabled
        self._notify = config.notify
        self._dry_run = config.dry_run
        self._cron = config.cron
        self._cookie = config.cookie
        self._timeout = config.timeout
        self._detail_request_retries = config.detail_request_retries

    def _consume_dry_run(self) -> bool:
        """取走一次性试运行标记；任务创建前即关闭，reload 不会重复执行。"""
        if not self._dry_run:
            return False
        self._dry_run = False
        return True

    def _save_config(self) -> None:
        """完整回写配置，供 CookieCloud 补取 Cookie 等场景复用。"""
        if not self._runtime_config:
            return
        config = replace(
            self._runtime_config,
            enabled=self._enabled,
            notify=self._notify,
            dry_run=self._dry_run,
            cron=self._cron,
            cookie=self._cookie,
            timeout=self._timeout,
            detail_request_retries=self._detail_request_retries,
        )
        self._runtime_config = config
        self.update_config(config.to_mapping(onlyonce=False))

    def _resolve_cookie(self) -> str:
        """Cookie 为空时从 CookieCloud 获取；回写延后到运行锁释放后执行。"""
        cookie, should_save = resolve_cookie(self._cookie, BROWSE_URL)
        if should_save:
            self._cookie = cookie
            self._pending_cookie_write = cookie
        return cookie

    def _flush_pending_cookie_writeback(self) -> None:
        """在运行锁外写回 CookieCloud 结果，且保留用户最新保存的其它配置。"""
        cookie = self._pending_cookie_write
        self._pending_cookie_write = ""
        if not cookie:
            return
        try:
            base = self._runtime_config.to_mapping(onlyonce=False) if self._runtime_config else {}
            current = self.get_config()
            if isinstance(current, dict):
                # 以刚从 MoviePilot 读到的值覆盖运行时快照，避免丢失用户并发保存的字段。
                base.update(current)
            if base.get("cookie") == cookie:
                return
            base["cookie"] = cookie
            self.update_config(base)
            logger.info("BakaBT 刷流：已从 CookieCloud 获取 Cookie 并写回插件配置")
        except Exception as err:
            logger.warning(f"BakaBT 刷流 CookieCloud 回写失败：{type(err).__name__}")

    def _safe_run_task(self, dry_run: bool = False) -> None:
        """防止定时服务和立即运行并发提交同一批种子。"""
        if not self._run_lock.acquire(blocking=False):
            logger.warning("BakaBT 刷流：已有任务运行中，跳过本次触发")
            return
        state: dict | None = None
        try:
            state = normalize_state(self.get_data("state"))
            config = self._runtime_config
            if not config:
                record_run(state, {
                    "status": "failed",
                    "torrent": "-",
                    "push": "未推送",
                    "detail": "插件配置无效，未执行任务",
                })
                self.save_data("state", state)
                return
            try:
                qb_instance = get_qb_instance(config.downloader)
                # 普通抓取仅在有空槽位后访问站点；启用促销过期清理时会先读取详情确认。
                result = run_once(
                    config,
                    self._resolve_cookie,
                    state,
                    qb_instance,
                    dry_run=dry_run,
                )
            except DownloaderError as err:
                record_run(state, {
                    "status": "failed",
                    "torrent": "-",
                    "push": "未推送",
                    "detail": str(err),
                })
                result = RunResult(
                    status="failed",
                    added=(),
                    failed_titles=(),
                    detail=str(err),
                    downloading_count=0,
                    max_downloading=config.max_bakabt_downloading,
                )
            self.save_data("state", state)
            self._log_result(result)
            self._notify_result(config, result)
        except Exception as err:
            # 最外层保护只记录错误类型，不泄漏 Cookie、qB 凭据或私密下载链接。
            if state is not None:
                record_run(state, {
                    "status": "failed",
                    "torrent": "-",
                    "push": "未推送",
                    "detail": f"任务异常：{type(err).__name__}",
                })
                self.save_data("state", state)
            logger.exception(f"BakaBT 刷流任务异常：{type(err).__name__}")
        finally:
            self._run_lock.release()
            self._flush_pending_cookie_writeback()

    @staticmethod
    def _log_result(result: RunResult) -> None:
        logger.info(
            f"BakaBT 刷流完成：status={result.status}，"
            f"added={len(result.added)}，deleted={len(result.deleted)}，detail={result.detail}"
        )

    def _notify_result(self, config: BrushConfig, result: RunResult) -> None:
        if not config.notify:
            return
        try:
            message = build_notification(config, result)
            if not message:
                return
            title, text = message
            self.post_message(title=title, mtype=NotificationType.SiteMessage, text=text)
        except Exception as err:
            logger.warning(f"BakaBT 刷流通知发送失败：{type(err).__name__}")

    def get_state(self) -> bool:
        return bool(self._enabled)

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        return []

    def get_service(self) -> List[Dict[str, Any]]:
        if not self._enabled:
            return []
        try:
            trigger = CronTrigger.from_crontab(self._cron, timezone=app_settings.TZ)
        except Exception as err:
            logger.error("BakaBT 刷流 Cron 配置无效：%r，%s", self._cron, err)
            return []
        return [{
            "id": "BakaBTBrush",
            "name": "BakaBT 刷流任务",
            "trigger": trigger,
            "func": self._safe_run_task,
            "kwargs": {},
        }]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        try:
            from app.helper.downloader import DownloaderHelper
            helper = DownloaderHelper()
            services = helper.get_services() or {}
            downloader_options = [
                {"title": name, "value": name}
                for name, service in services.items()
                if helper.is_downloader("qbittorrent", service=service)
            ]
        except Exception as err:
            logger.debug(f"BakaBT 刷流：读取 qB 下载器列表失败：{type(err).__name__}")
            downloader_options = []
        return build_form(downloader_options)

    def get_page(self) -> List[dict]:
        try:
            config = self._runtime_config or BrushConfig.from_mapping({})
            return build_page(
                normalize_state(self.get_data("state")),
                max_height=config.page_max_height,
                visible_items=config.page_visible_items,
            )
        except Exception as err:
            logger.error(f"BakaBT 刷流数据页加载失败：{type(err).__name__}")
            return [{
                "component": "VAlert",
                "props": {
                    "type": "error",
                    "variant": "tonal",
                    "text": "BakaBT 刷流数据页加载失败。",
                },
            }]

    def stop_service(self) -> None:
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown()
                self._scheduler = None
        except Exception as err:
            logger.warning("BakaBT 刷流停止立即运行任务失败：%s", err)

    @staticmethod
    def _ensure_plugin_log_file() -> None:
        """预创建日志文件，避免 MoviePilot 前端首次查看时返回 404。"""
        try:
            path = app_settings.LOG_PATH / "plugins" / "bakabtbrush.log"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)
        except Exception:
            pass
