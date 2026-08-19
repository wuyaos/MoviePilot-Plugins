"""MoviePilot V2 BakaBT Freeleech 刷流插件入口。"""

from __future__ import annotations

import threading
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
from .core.page import build_page
from .core.runner import RunResult, run_once
from .core.scraper import BROWSE_URL
from .core.state import normalize_state, record_run


class BakaBTBrush(_PluginBase):
    """按发布时间和体积选择 BakaBT Freeleech，并提交到 MoviePilot 配置的 qB。"""

    plugin_name = "BakaBT 刷流"
    plugin_desc = "定时筛选 BakaBT Freeleech 种子并提交到 qBittorrent"
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/bakabtbrush.png"
    plugin_version = "0.1.0"
    plugin_author = "wuyaos"
    author_url = "https://github.com/wuyaos"
    plugin_config_prefix = "bakabtbrush_"
    plugin_order = 30
    auth_level = 2

    _enabled = False
    _notify = True
    _onlyonce = False
    _cron = "*/10 * * * *"
    _cookie = ""
    _timeout = 20
    _detail_request_retries = 3
    _min_publish_age_minutes = 0
    _max_publish_age_minutes = 0
    _min_size_mb = 0
    _max_size_mb = 0
    _downloader = ""
    _qb_category = "刷流"
    _qb_tags = "bakabt,刷流"
    _save_path = ""
    _max_bakabt_downloading = 2

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

        if self._onlyonce:
            self._onlyonce = False
            self._save_config()
            self._scheduler = BackgroundScheduler(timezone=app_settings.TZ)
            self._scheduler.add_job(
                self._safe_run_task,
                "date",
                run_date=datetime.now(tz=pytz.timezone(app_settings.TZ)) + timedelta(seconds=3),
                name="BakaBT 刷流立即运行",
            )
            self._scheduler.start()

    def _apply_config(self, config: BrushConfig) -> None:
        self._enabled = config.enabled
        self._notify = config.notify
        self._cron = config.cron
        self._cookie = config.cookie
        self._timeout = config.timeout
        self._detail_request_retries = config.detail_request_retries
        self._min_publish_age_minutes = config.min_publish_age_minutes
        self._max_publish_age_minutes = config.max_publish_age_minutes
        self._min_size_mb = config.min_size_mb
        self._max_size_mb = config.max_size_mb
        self._downloader = config.downloader
        self._qb_category = config.qb_category
        self._qb_tags = ",".join(config.qb_tags)
        self._save_path = config.save_path
        self._max_bakabt_downloading = config.max_bakabt_downloading

    def _save_config(self) -> None:
        """完整回写配置，供 CookieCloud 补取 Cookie 等场景复用。"""
        config = BrushConfig(
            enabled=self._enabled,
            notify=self._notify,
            cron=self._cron,
            cookie=self._cookie,
            timeout=self._timeout,
            detail_request_retries=self._detail_request_retries,
            min_publish_age_minutes=self._min_publish_age_minutes,
            max_publish_age_minutes=self._max_publish_age_minutes,
            min_size_mb=self._min_size_mb,
            max_size_mb=self._max_size_mb,
            downloader=self._downloader,
            qb_category=self._qb_category,
            qb_tags=tuple(tag.strip() for tag in self._qb_tags.split(",") if tag.strip()),
            save_path=self._save_path,
            max_bakabt_downloading=self._max_bakabt_downloading,
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

    def _safe_run_task(self) -> None:
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
                # run_once 在确认 qB 有空槽位后才会按需获取 Cookie、请求 BakaBT。
                result = run_once(config, self._resolve_cookie, state, qb_instance)
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
            f"added={len(result.added)}，detail={result.detail}"
        )

    def _notify_result(self, config: BrushConfig, result: RunResult) -> None:
        if not config.notify:
            return
        try:
            if result.should_notify_success:
                lines = [
                    "✅ **BakaBT 刷流任务完成**",
                    "",
                    f"**已推送**：{len(result.added)} 个",
                    "**种子**：",
                ]
                for item in result.added:
                    published = item.published_at.isoformat().replace("+00:00", "Z") if item.published_at else "未知"
                    lines.extend([
                        f"- {item.title}（{item.size_mb:.2f} MB）",
                        f"  发种时间：{published}",
                        f"  详情：{item.detail_url}",
                    ])
                slot_text = (
                    "不限制" if result.max_downloading == 0
                    else f"{result.downloading_count}/{result.max_downloading}"
                )
                lines.extend([
                    "",
                    f"**qB 下载槽位**：{slot_text}",
                    f"**分类**：{config.qb_category}",
                    f"**标签**：{', '.join(config.qb_tags)}",
                ])
                self.post_message(
                    title="【BakaBT 刷流已加入 qB】",
                    mtype=NotificationType.SiteMessage,
                    text="\n".join(lines),
                )
            elif result.should_notify_failure:
                titles = "、".join(result.failed_titles) or "-"
                self.post_message(
                    title="【BakaBT 刷流任务异常】",
                    mtype=NotificationType.SiteMessage,
                    text="\n".join([
                        "❌ **BakaBT 刷流添加失败**",
                        "",
                        f"**失败种子**：{titles}",
                        f"**原因**：{result.detail}",
                    ]),
                )
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

        return [{
            "component": "VForm",
            "content": [
                {
                    "component": "VRow",
                    "content": [
                        self._col(3, self._switch("enabled", "启用插件")),
                        self._col(3, self._switch("notify", "发送通知")),
                        self._col(3, self._switch("onlyonce", "立即运行一次")),
                        self._col(3, self._cron_field()),
                    ],
                },
                self._section("BakaBT"),
                {
                    "component": "VRow",
                    "content": [
                        self._col(12, {
                            "component": "VTextField",
                            "props": {
                                "model": "cookie",
                                "label": "BakaBT Cookie",
                                "type": "password",
                                "autocomplete": "off",
                                "hint": "留空时从 CookieCloud 获取，并写回插件配置。",
                                "persistent-hint": True,
                            },
                        }),
                        self._col(4, self._number("timeout", "请求超时（秒）")),
                        self._col(4, self._number("detail_request_retries", "详情页重试次数")),
                    ],
                },
                self._section("筛选条件（0 表示不限制，体积统一为 MB）"),
                {
                    "component": "VRow",
                    "content": [
                        self._col(3, self._number("min_publish_age_minutes", "最小发种时间（分钟）")),
                        self._col(3, self._number("max_publish_age_minutes", "最大发种时间（分钟）")),
                        self._col(3, self._number("min_size_mb", "最小体积（MB）")),
                        self._col(3, self._number("max_size_mb", "最大体积（MB）")),
                    ],
                },
                self._section("qBittorrent"),
                {
                    "component": "VRow",
                    "content": [
                        self._col(4, {
                            "component": "VSelect",
                            "props": {
                                "model": "downloader",
                                "label": "下载器",
                                "items": downloader_options,
                                "hint": "请选择 MoviePilot 已配置的 qBittorrent 下载器。",
                                "persistent-hint": True,
                            },
                        }),
                        self._col(2, self._text("qb_category", "分类")),
                        self._col(2, self._text("qb_tags", "标签（逗号分隔）")),
                        self._col(2, self._text("save_path", "保存路径")),
                        self._col(2, self._number("max_bakabt_downloading", "最大下载流程数")),
                    ],
                },
            ],
        }], {
            "enabled": False,
            "notify": True,
            "onlyonce": False,
            "cron": "*/10 * * * *",
            "cookie": "",
            "timeout": 20,
            "detail_request_retries": 3,
            "min_publish_age_minutes": 0,
            "max_publish_age_minutes": 0,
            "min_size_mb": 0,
            "max_size_mb": 0,
            "downloader": "",
            "qb_category": "刷流",
            "qb_tags": "bakabt,刷流",
            "save_path": "",
            "max_bakabt_downloading": 2,
        }

    @staticmethod
    def _section(title: str) -> dict:
        return {
            "component": "VRow",
            "content": [{
                "component": "VCol",
                "props": {"cols": 12},
                "content": [{
                    "component": "div",
                    "props": {
                        "class": "text-subtitle-2 font-weight-medium text-medium-emphasis pt-2 pb-1",
                    },
                    "text": title,
                }],
            }],
        }

    @staticmethod
    def _col(md: int, content: dict) -> dict:
        return {"component": "VCol", "props": {"cols": 12, "md": md}, "content": [content]}

    @staticmethod
    def _switch(model: str, label: str) -> dict:
        return {"component": "VSwitch", "props": {"model": model, "label": label}}

    @staticmethod
    def _text(model: str, label: str) -> dict:
        return {"component": "VTextField", "props": {"model": model, "label": label}}

    @staticmethod
    def _number(model: str, label: str) -> dict:
        return {
            "component": "VTextField",
            "props": {"model": model, "label": label, "type": "number", "min": 0},
        }

    @staticmethod
    def _cron_field() -> dict:
        return {
            "component": "VCronField",
            "props": {"model": "cron", "label": "执行周期", "placeholder": "*/10 * * * *"},
        }

    def get_page(self) -> List[dict]:
        try:
            return build_page(normalize_state(self.get_data("state")))
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
