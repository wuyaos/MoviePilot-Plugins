import re
import json
import math
import datetime
import threading
import traceback

import pytz
from typing import List, Tuple, Dict, Any, Optional

import chardet
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from lxml import etree

from app.schemas import NotificationType, Response, ServiceInfo
from app.db.oper.site import SiteOper
from app.plugins import _PluginBase
from app.sdk.config import settings
from app.sdk.logging import logger
from app.sdk.network import RequestUtils
from app.sdk.services import DownloaderHelper, ServiceConfigHelper
from torrentool.torrent import Torrent


class Hhanclubrescueseed(_PluginBase):
    # 插件名称
    plugin_name = "憨憨保种区"
    # 插件描述
    plugin_desc = "拯救憨憨保种区"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/hhanclubrescueseed.png"
    # 插件版本
    plugin_version = "3.3.12"
    # 插件作者
    plugin_author = "Seed680, wuyaos"
    # 作者主页
    author_url = "https://github.com/wuyaos"
    # 插件配置项ID前缀
    plugin_config_prefix = "hhanclubrescueseed_"
    # 加载顺序
    plugin_order = 16
    # 可使用的用户级别
    auth_level = 2

    domain = "hhanclub.net"
    # —— 内置治理常数（不做成配置，改动需发版）——
    DISK_QUOTA_TARGET_RATIO = 0.9
    NO_UPLOAD_AVG_SPEED = 1024
    MAX_REMOVE_PER_RUN = 5
    DEFAULT_REWARD_HOURS = 18
    DEFAULT_STUCK_DAYS = 7
    DETAIL_REQUEST_BUDGET = 15
    CONFIG_KEYS = (
        "enable", "run_once", "history_rescue_enabled", "cron", "monitor_cron",
        "downloader", "save_path", "custom_tag", "reward_tag", "reward_hours",
        "enable_notification", "notify_on_zero_torrents", "force_resume",
        "auto_delete_enabled", "delete_files", "disk_quota_gb", "stuck_days",
        "seeding_count", "torrent_size", "download_limit", "max_downloading",
        "max_pages", "min_downloaders", "completion_ratio_max",
        "connect_time_max_hours", "free",
    )
    _event = threading.Event()
    _scheduler = None
    _enable = False
    _run_once = False
    _cron = "*/20 14-15 * * *"
    _monitor_cron = "*/10 * * * *"
    _downloader = None
    _seeding_count = "1-3"
    _torrent_size = None
    _download_limit = 5
    _save_path = None
    _custom_tag = "憨憨保种"
    _enable_notification = False
    _notify_on_zero_torrents = False
    _history_rescue_enabled = False
    _user_id = None
    _force_resume = False
    _max_pages = 5
    _reward_tag = None
    _reward_hours = 18
    _disk_quota_gb = None
    _stuck_days = 7
    _min_downloaders = 1
    _completion_ratio_max = 20.0
    _connect_time_max_hours = None
    _free = False
    _auto_delete_enabled = False
    _delete_files = True
    _max_downloading = 3
    # 推送评分常数（SCORE_VERSION=v1；改动需发版并同步文档）
    SCORE_VERSION = "v1"
    SCORE_SIZE_WEIGHT = 50.0       # 体积分满分（300GB 封顶）
    SCORE_DEMAND_WEIGHT = 40.0     # 需求分满分（人数热度×剩余比例）
    SCORE_SCARCITY_WEIGHT = 10.0   # 稀缺分满分（10/做种数）
    SCORE_SIZE_CAP_GB = 300.0      # 体积分封顶体积
    SCORE_LEECHER_CAP = 20         # 下载人数热度封顶（站点典型范围 0-20）
    SCORE_UNKNOWN_REMAINING = 0.5  # 完成率未知时的中性剩余比例

    def _normalize_config(self, config: dict) -> dict:
        """Normalize the 26 persisted keys without retaining stale instance values."""
        raw = dict(config or {})
        defaults = {
            "enable": False, "run_once": False, "history_rescue_enabled": False,
            "cron": "*/20 14-15 * * *", "monitor_cron": "*/10 * * * *",
            "downloader": None, "save_path": None, "custom_tag": "憨憨保种",
            "reward_tag": None, "reward_hours": 18, "enable_notification": False,
            "notify_on_zero_torrents": False, "force_resume": False,
            "auto_delete_enabled": False, "delete_files": True, "disk_quota_gb": None,
            "stuck_days": 7, "seeding_count": "1-3", "torrent_size": None,
            "download_limit": 5, "max_downloading": 3, "max_pages": 5,
            "min_downloaders": 1, "completion_ratio_max": 20.0,
            "connect_time_max_hours": None, "free": False,
        }
        result = {}
        bool_keys = {"enable", "run_once", "history_rescue_enabled", "enable_notification",
                     "notify_on_zero_torrents", "force_resume", "auto_delete_enabled", "delete_files", "free"}
        for key, default in defaults.items():
            value = raw[key] if key in raw else default
            if key in bool_keys:
                result[key] = value if isinstance(value, bool) else default
            elif key == "monitor_cron":
                result[key] = default if value is None else str(value).strip()
            elif key == "cron":
                result[key] = default if value in (None, "") else str(value).strip()
            elif key in {"downloader", "save_path", "custom_tag", "reward_tag"}:
                result[key] = None if value is None else str(value)
            elif key == "seeding_count":
                result[key] = default if value is None else str(value).strip()
            elif key == "torrent_size":
                result[key] = None if value in (None, "") else str(value).strip()
            elif key in {"disk_quota_gb", "min_downloaders", "completion_ratio_max", "connect_time_max_hours"}:
                result[key] = self._coerce_number(value, default, allow_none=True)
            elif key in {"reward_hours", "stuck_days", "download_limit", "max_downloading", "max_pages"}:
                result[key] = self._coerce_int(value, default)
            else:
                result[key] = value
        if result["disk_quota_gb"] is not None and result["disk_quota_gb"] < 0:
            result["disk_quota_gb"] = None
        if result["stuck_days"] is not None and result["stuck_days"] < 0:
            result["stuck_days"] = 7
        if result["completion_ratio_max"] is not None and not 0 <= result["completion_ratio_max"] <= 100:
            result["completion_ratio_max"] = None
        if result["connect_time_max_hours"] is not None and result["connect_time_max_hours"] < 0:
            result["connect_time_max_hours"] = None
        result["max_pages"] = max(1, result["max_pages"])
        return result

    @staticmethod
    def _coerce_number(value, default=None, allow_none=False):
        if value is None:
            return None if allow_none else default
        if value == "":
            return None if allow_none else default
        try:
            value = float(value)
            return value if value == value and value not in (float("inf"), float("-inf")) else default
        except (TypeError, ValueError):
            return default

    @classmethod
    def _coerce_int(cls, value, default=None):
        number = cls._coerce_number(value, default)
        try:
            return int(number)
        except (TypeError, ValueError):
            return default

    def _apply_config(self, config: dict):
        normalized = self._normalize_config(config)
        for key in self.CONFIG_KEYS:
            setattr(self, f"_{key}", normalized[key])
        self._full_config = dict(normalized)
        return normalized

    def init_plugin(self, config: dict = None):
        try:
            self.downloader_helper = DownloaderHelper()
            self.site = SiteOper().get_by_domain(self.domain)
            if not self.site:
                self.domain = "hhanclub.top"
                self.site = SiteOper().get_by_domain(self.domain)
            if not self.site:
                self.domain = "hhan.club"
                self.site = SiteOper().get_by_domain(self.domain)
            if not self.site:
                logger.error("憨憨站点未配置，请先在系统配置中添加站点")
                return
            normalized = self._apply_config(config)
            logger.info(f"【憨憨保种区】插件初始化 v{self.plugin_version}，状态：{'启用' if self._enable else '未启用'}，获取调度：{self._cron or '未设置'}，监控调度：{self._monitor_cron or '未设置'}")
            self._user_id = None
            if self._history_rescue_enabled:
                self._user_id = self._resolve_user_id()
                if not self._user_id:
                    logger.warning("无法解析当前憨憨站用户 UID（请检查站点 Cookie 是否有效），跳过历史保种任务")
                    if self._enable_notification:
                        self.post_message(mtype=NotificationType.Plugin, title="【憨憨保种区】", text="无法解析当前站点用户 UID，历史保种任务未执行")
            self.stop_service()
            self._event.clear()
            need_run_once = self._run_once or bool(self._history_rescue_enabled and self._user_id)
            if not need_run_once:
                return
            saved = dict(normalized)
            if self._run_once:
                saved["run_once"] = False
            if self._history_rescue_enabled:
                saved["history_rescue_enabled"] = False
            self.update_config(config=saved)
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            if self._run_once:
                self._run_once = False
                self._scheduler.add_job(self._check_seeding, "date", run_date=datetime.datetime.now(tz=pytz.timezone(settings.TZ)) + datetime.timedelta(seconds=3), name="拯救憨憨保种区")
            if self._history_rescue_enabled and self._user_id:
                self._history_rescue_enabled = False
                logger.info(f"立即运行历史保种任务，用户ID: {self._user_id}")
                self._scheduler.add_job(self._check_history_seeding, "date", run_date=datetime.datetime.now(tz=pytz.timezone(settings.TZ)) + datetime.timedelta(seconds=3), name="拯救憨憨保种区历史任务")
            if self._scheduler.get_jobs():
                self._scheduler.start()
        except Exception as e:
            logger.error(f"初始化失败：{str(e)}", exc_info=True)

    def _resolve_user_id(self):
        """Resolve the authenticated site's UID only for the history task."""
        def field(obj, name):
            try:
                value = obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)
            except Exception:
                value = None
            return str(value).strip() if value is not None else ""
        for name in ("userid", "user_id"):
            value = field(self.site, name)
            if value.isdigit() and int(value) > 0:
                return value
        source = self._get_page_source(f"https://{self.domain}/", self.site)
        candidates = set(re.findall(r"(?:[?&]uid=|userdetails\.php\?(?:[^'\"#]*&)?id=)(\d+)", source or "", re.I))
        if len(candidates) == 1:
            return candidates.pop()
        return None

    def get_form(self) -> Tuple[Optional[List[dict]], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
        return None, {key: getattr(self, f"_{key}") for key in self.CONFIG_KEYS} | {
            "all_downloaders": self._all_downloaders,
        }

    def load_config(self, config: dict):
        """加载配置"""
        self._apply_config(config)


    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        """
        获取插件渲染模式
        :return: 1、渲染模式，支持：vue/vuetify，默认vuetify
        :return: 2、组件路径，默认 dist/assets
        """
        return "vue", "dist/assets"

    # --- Instance methods for API endpoints ---
    def _get_config(self) -> Response:
        """API Endpoint: Returns current plugin configuration."""

        return Response(success=True, data={
            **{key: getattr(self, f"_{key}") for key in self.CONFIG_KEYS},
            "all_downloaders": self._all_downloaders,
        })


    def _get_download_records(self) -> Response:
        """API Endpoint: Returns download records with auto-delete switch state."""
        records = self.get_data("download_records") or []
        records.reverse()
        # 聚合下载器实时状态（状态/上传量/做种时长），按种子 hash 匹配记录
        aggregated = False
        live = {}
        live_source = {}
        try:
            if self._downloader and self._custom_tag:
                svc = self.downloader_helper.get_service(self._downloader)
                if svc and svc.instance:
                    reward_tag = self._reward_tag or ""
                    for t in self._get_scoped_torrents(self._downloader):
                        s = self._get_torrent_stats(t)
                        if not s or not s.get("hash"):
                            continue
                        state_l = (s.get("state") or "").lower()
                        if "queued" in state_l or "pending" in state_l or "排队" in state_l:
                            status = "排队"
                        elif s["progress"] < 1:
                            status = "下载中"
                        elif reward_tag and reward_tag in s["tags"]:
                            status = "已达标"
                        else:
                            status = "做种中"
                        live[s["hash"].lower()] = {
                            "status": status,
                            "uploaded": round(s["uploaded"] / (1024 ** 3), 3),
                            "seeding_time_hours": s["seeding_hours"],
                            "progress": s["progress"],
                        }
                        live_source[s["hash"].lower()] = s
                    aggregated = True
        except Exception as e:
            logger.warning(f"聚合下载器实时状态失败: {str(e)}")
        if aggregated:
            known = set()
            for r in records:
                info = live.get(str(r.get("torrent_hash") or "").lower())
                known.add(str(r.get("torrent_hash") or "").lower())
                if info:
                    r.update(info)
                else:
                    # 下载器中已不存在该 hash（被删除或标签不符）
                    r["status"] = "已删除"
                    r["uploaded"] = 0
                    r["seeding_time_hours"] = 0
            # 下载器中存在但本地无记录的历史种子（早期版本/手动下载），合成展示记录（不入库）
            known.discard("")
            now = datetime.datetime.now()
            for h, info in live.items():
                if h in known:
                    continue
                s = live_source.get(h)
                if not s:
                    continue
                added_dt = now - datetime.timedelta(days=s.get("added_days") or 0)
                records.append({
                    "title": s["name"], "zh_title": "", "score": None,
                    "size": f"{s['size_gb']:.2f} GB", "seeders": None,
                    "download_link": None, "torrent_hash": h,
                    "download_time": added_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "discovered": True, **info,
                })
        return Response(success=True, data={
            "records": records,
            "auto_delete_enabled": bool(self._auto_delete_enabled),
            "disk_quota_gb": self._disk_quota_gb
        })


    def _cleanup_stale_records(self) -> Response:
        """API Endpoint: 清理失效下载记录（下载器中已不存在对应种子的记录）。

        守卫：下载器状态聚合失败时不删除任何记录，避免误清。
        """
        records = self.get_data("download_records") or []
        if not records:
            return Response(success=True, data={"removed": 0, "total": 0})
        live_hashes = set()
        try:
            if self._downloader and self._custom_tag:
                svc = self.downloader_helper.get_service(self._downloader)
                if svc and svc.instance:
                    for t in self._get_scoped_torrents(self._downloader):
                        s = self._get_torrent_stats(t)
                        if s and s.get("hash"):
                            live_hashes.add(s["hash"].lower())
        except Exception as e:
            logger.warning(f"清理失效记录时聚合下载器状态失败: {str(e)}")
            return Response(success=False, message=f"聚合下载器状态失败，未删除任何记录：{str(e)}")
        kept = [r for r in records if str(r.get("torrent_hash") or "").lower() in live_hashes]
        removed = len(records) - len(kept)
        if removed:
            self.save_data(key="download_records", value=kept[-100:])
            logger.info(f"【憨憨保种区】清理失效下载记录 {removed} 条（剩余 {len(kept)} 条）")
        return Response(success=True, data={"removed": removed, "total": len(kept)})

    def _adopt_missing_records(self, scoped_torrents=None) -> int:
        """接管入库核心：把下载器中带插件标签但本地无记录的种子写入 download_records。

        scoped_torrents 为空时自行调用 _get_scoped_torrents(self._downloader) 拉取；
        调用方已持有同一下载器的 scoped 种子列表时可传入复用，避免重复请求下载器。
        不构造 Response；异常自行 log 并返回 0，由调用方决定如何呈现/是否通知。
        """
        if not (self._downloader and self._custom_tag):
            return 0
        try:
            torrents = scoped_torrents if scoped_torrents is not None else self._get_scoped_torrents(self._downloader)
            records = self.get_data("download_records") or []
            known = {str(r.get("torrent_hash") or "").lower() for r in records}
            known.discard("")
            adopted = 0
            now = datetime.datetime.now()
            for t in torrents:
                s = self._get_torrent_stats(t)
                if not s or not s.get("hash") or s["hash"].lower() in known:
                    continue
                h = s["hash"].lower()
                added_dt = now - datetime.timedelta(days=s.get("added_days") or 0)
                records.append({
                    "title": s["name"], "zh_title": "", "score": None,
                    "size": f"{s['size_gb']:.2f} GB", "seeders": None,
                    "download_link": None, "torrent_hash": h,
                    "download_time": added_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "adopted": True,
                })
                known.add(h)
                adopted += 1
            if adopted:
                self.save_data(key="download_records", value=records[-100:])
            return adopted
        except Exception as e:
            logger.warning(f"接管入库失败: {str(e)}")
            return 0

    def _adopt_torrents(self) -> Response:
        """API Endpoint: 刷新接管——把下载器中带插件标签但本地无记录的种子入库。

        入库后参与删除/清理管理；score/download_link 不可回补，显示为空。
        """
        if not (self._downloader and self._custom_tag):
            return Response(success=False, message="未配置下载器或自定义标签")
        try:
            svc = self.downloader_helper.get_service(self._downloader)
            if not svc or not svc.instance:
                return Response(success=False, message=f"下载器 {self._downloader} 未连接")
            adopted = self._adopt_missing_records()
        except Exception as e:
            logger.warning(f"刷新接管失败: {str(e)}")
            return Response(success=False, message=f"接管失败：{str(e)}")
        records = self.get_data("download_records") or []
        if adopted:
            logger.info(f"【憨憨保种区】刷新接管：入库 {adopted} 个历史种子（共 {len(records)} 条记录）")
        return Response(success=True, data={"adopted": adopted, "total": len(records)})

    @property
    def service_infos(self) -> Optional[Dict[str, ServiceInfo]]:
        """
        服务信息
        """
        if not self._downloader:
            logger.warning("尚未配置下载器（配置项「下载器实例」为空），无法执行下载与监控")
            return None

        services = self.downloader_helper.get_services(name_filters=[self._downloader])
        if not services:
            all_names = list(self.downloader_helper.get_services().keys())
            logger.warning(
                f"获取下载器实例失败：配置的「{self._downloader}」不存在或未启用，"
                f"当前可用：{all_names or '（无）'}，请检查配置")
            return None

        active_services = {}
        for service_name, service_info in services.items():
            if service_info.instance.is_inactive():
                logger.warning(f"下载器 {service_name} 未连接，请检查配置")
            else:
                active_services[service_name] = service_info

        if not active_services:
            logger.warning(f"配置的下载器「{self._downloader}」未连接，请检查下载器状态")
            return None

        return active_services

    @property
    def _all_downloaders(self) -> List[dict]:
        """
        获取全部下载器
        """
        return [
            {"title": config.name, "value": config.name}
            for config in ServiceConfigHelper.get_downloader_configs()
            if config.enabled
        ]

    def _parse_size_to_gb(self, size_str: str) -> Optional[float]:
        """
        解析种子大小字符串为GB数值
        支持格式: "1.5 GB", "500 MB", "2.3 TB", "100 KB"
        返回: GB数值，如果解析失败返回None
        """
        if not size_str:
            return None

        size_str = size_str.strip().upper()

        # 匹配数字和单位
        match = re.match(r'([\d.]+)\s*(KB|MB|GB|TB)', size_str)
        if not match:
            logger.warning(f"无法解析种子大小格式: {size_str}")
            return None

        try:
            value = float(match.group(1))
            unit = match.group(2)

            # 转换为GB
            if unit == 'KB':
                return value / (1024 * 1024)
            elif unit == 'MB':
                return value / 1024
            elif unit == 'GB':
                return value
            elif unit == 'TB':
                return value * 1024
            else:
                return None
        except Exception as e:
            logger.error(f"解析种子大小失败: {str(e)}")
            return None

    def get_state(self) -> bool:
        return self._enable

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/config",
                "endpoint": self._get_config,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取当前配置"
            },
            {
                "path": "/download_records",
                "endpoint": self._get_download_records,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取下载记录"
            },

            {
                "path": "/delete_torrents",
                "endpoint": self._delete_torrents,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "批量删除下载器中的种子"
            },
            {
                "path": "/delete_download_records",
                "endpoint": self._delete_download_records,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "批量删除下载记录"
            },
            {
                "path": "/cleanup_records",
                "endpoint": self._cleanup_stale_records,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "清理失效下载记录"
            },
            {
                "path": "/adopt_torrents",
                "endpoint": self._adopt_torrents,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "刷新接管下载器历史种子"
            }
        ]


    def _delete_torrents(self, torrent_hashes: List[str] = None):
        """
        API端点：批量删除指定hashes的种子
        """
        if not torrent_hashes:
            return Response(success=False, message="种子hash列表不能为空")

        results = []
        for torrent_hash in torrent_hashes:
            success = self._delete_torrent_by_hash(torrent_hash)
            results.append({
                "hash": torrent_hash,
                "success": success
            })

        # 统计成功和失败的数量
        success_count = sum(1 for r in results if r["success"])
        fail_count = len(results) - success_count

        return Response(
            success=True,
            message=f"批量删除完成: 成功 {success_count}, 失败 {fail_count}",
            data=results
        )

    def _delete_download_records(self, titles: List[str] = None):
        """
        API端点：批量删除指定标题的下载记录
        """
        if not titles:
            return Response(success=False, message="标题列表不能为空")

        try:
            # 获取所有下载记录
            download_records = self.get_data("download_records") or []

            # 过滤掉要删除的记录（基于标题）
            updated_records = [record for record in download_records if record.get("title") not in titles]

            # 保存更新后的记录
            self.save_data(key="download_records", value=updated_records)

            return Response(success=True, message=f"成功删除 {len(titles)} 条下载记录")
        except Exception as e:
            logger.error(f"批量删除下载记录失败: {str(e)}")
            return Response(success=False, message=f"批量删除下载记录失败: {str(e)}")

    def get_service(self) -> List[Dict[str, Any]]:
        """
        注册插件公共服务
        [{
            "id": "服务ID",
            "name": "服务名称",
            "trigger": "触发器：cron/interval/date/CronTrigger.from_crontab()",
            "func": self.xxx,
            "kwargs": {} # 定时器参数
        }]
        """
        services = []
        # 任务一：保种区获取（抓列表→粗筛→精筛→下载）
        if self._enable and self._cron:
            services.append({
                "id": "Hhanclubrescueseed",
                "name": "憨憨保种区获取",
                "trigger": CronTrigger.from_crontab(self._cron),
                "func": self._check_seeding,
                "kwargs": {}
            })
        # 任务二：种子监控（达标打标→配额删除→卡死清理）
        if self._enable and self._monitor_cron:
            services.append({
                "id": "HhanclubrescueseedMonitor",
                "name": "憨憨保种区监控",
                "trigger": CronTrigger.from_crontab(self._monitor_cron),
                "func": self._maintenance,
                "kwargs": {}
            })

        return services
    @staticmethod
    def _norm_title(value) -> str:
        """标题归一化：小写 + 分隔符折叠，用于种子去重比对"""
        return re.sub(r"[._\[\]\s]+", " ", str(value or "").strip().lower())

    def _check_seeding(self):
        try:
            logger.info("【憨憨保种区】开始执行保种区获取任务")
            if not self._enable:
                logger.info("憨憨保种区插件未启用，跳过检查")
                return
            if not self._downloader:
                logger.error("未配置下载器，无法执行保种任务")
                return
            # —— 容量前置：任务开始先算本轮候选上限（本轮固定），避免达上限仍抓取/精筛 ——
            max_downloading = self._max_downloading or 0
            download_limit = self._download_limit or 0
            unfinished = None
            if max_downloading > 0:
                try:
                    scoped = self._get_scoped_torrents(self._downloader)
                except Exception as exc:
                    logger.error(f"检查下载器未完成种子数失败，无法计算本轮容量，终止本轮: {exc}")
                    return
                unfinished = sum(1 for torrent in scoped if (self._get_torrent_stats(torrent) or {}).get("progress", 1) < 1)
                available_slots = max(0, max_downloading - unfinished)
            else:
                available_slots = math.inf
            round_capacity = min(available_slots, download_limit) if download_limit > 0 else available_slots
            if round_capacity <= 0:
                logger.info(f"【憨憨保种区】本轮容量为0：下载器未完成种子 {unfinished} 个，已达 max_downloading={max_downloading} 上限（download_limit={self._download_limit}），本轮不抓取列表，跳过精筛与下载")
            records = self.get_data("download_records") or []
            # 去重集合：历史记录标题 + 下载器现有带标签种子的名称（归一化后比对）
            existing_titles = set()
            if round_capacity > 0:
                existing_titles = {self._norm_title(r.get("title")) for r in records if r.get("title")}
                try:
                    for t in (self._get_scoped_torrents(self._downloader) or []):
                        s = self._get_torrent_stats(t)
                        if s and s.get("name"):
                            existing_titles.add(self._norm_title(s["name"]))
                except Exception:
                    pass
            skipped_dup_count = 0
            candidates = []
            stats = {}
            budget = {"used": 0, "limit": self.DETAIL_REQUEST_BUDGET}
            downloaded_count = 0
            success_count = 0
            failed_count = 0
            success_details = []
            failed_details = []
            refined = []
            if round_capacity > 0:
                for page in range(self._max_pages):
                    if self._event.is_set():
                        logger.info("检测到停止事件，终止本轮页面下载")
                        break
                    url = f"https://{self.domain}/rescue.php?page={page}"
                    logger.info(f"憨憨保种区第{page + 1}页: {url}")
                    source = self._get_page_source(url=url, site=self.site)
                    if not source:
                        logger.error(f"请求憨憨保种区第{page + 1}页失败")
                        break
                    html = etree.HTML(source)
                    if html is None:
                        logger.error(f"憨憨保种区第{page + 1}页页面解析失败")
                        break
                    elements = html.xpath('//*[@id="mainContent"]/div[1]/div[2]/div[3]/div')
                    logger.info(f"第{page + 1}页数据获取{len(elements)}条数据")
                    if not elements:
                        break
                    for elem in elements:
                        if self._event.is_set():
                            break
                        try:
                            record = self._prefilter_row(elem, stats)
                            if record is not None:
                                candidates.append(record)
                        except Exception as exc:
                            logger.error(f"处理列表种子时出错: {exc}")
                    if self._event.is_set():
                        break
                logger.info(f"【憨憨保种区】本轮粗筛淘汰分布: {json.dumps(stats, ensure_ascii=False)}")
                if not candidates:
                    logger.debug("本轮无粗筛候选")
                refined = self._refine_by_detail(candidates, budget)
                for record in refined:
                    record["score"] = round(self._compute_push_score(record), 2)
                refined.sort(key=lambda r: r.get("score") or 0, reverse=True)
                if refined:
                    board = ", ".join(f"{r['title'][:24]}={r['score']:.1f}" for r in refined[:20])
                    suffix = f" 等共{len(refined)}个" if len(refined) > 20 else ""
                    logger.info(f"【憨憨保种区】本轮候选得分({self.SCORE_VERSION}): {board}{suffix}")
                # 只取排序后前 N 个（N=本轮候选上限），上限为无穷时等同原有全量下载
                download_targets = refined if round_capacity == math.inf else refined[:int(round_capacity)]
                for record in download_targets:
                    if self._event.is_set():
                        logger.info("详情精筛后检测到停止事件，终止下载")
                        break
                    if self._download_limit > 0 and downloaded_count >= self._download_limit:
                        logger.info(f"已达到单次下载数量限制 ({self._download_limit})，停止下载")
                        break
                    if self._max_downloading:
                        try:
                            scoped = self._get_scoped_torrents(self._downloader)
                            unfinished = sum(1 for torrent in scoped if (self._get_torrent_stats(torrent) or {}).get("progress", 1) < 1)
                            if unfinished >= self._max_downloading:
                                logger.info(f"下载器未完成种子 {unfinished} 个，已达上限 {self._max_downloading}，停止本轮")
                                break
                        except Exception as exc:
                            logger.warning(f"检查未完成种子数失败: {exc}")
                    norm_title = self._norm_title(record.get("title"))
                    if norm_title and norm_title in existing_titles:
                        logger.info(f"跳过重复种子（已在下载器或历史记录中）: {record['title'][:40]}")
                        skipped_dup_count += 1
                        continue
                    link = record.get("download_link")
                    if not link:
                        failed_count += 1
                        failed_details.append(f"- {record['title'][:30]}（无下载链接）")
                        continue
                    content, torrent_hash = self._download_torrent(link, self.site)
                    if not content:
                        failed_count += 1
                        failed_details.append(f"- {record['title'][:30]}（种子下载失败）")
                        continue
                    service_info = self.downloader_helper.get_service(self._downloader)
                    if not service_info or not service_info.instance:
                        logger.error(f"下载器 {self._downloader} 未连接或不可用")
                        failed_count += 1
                        failed_details.append(f"- {record['title'][:30]}（下载器不可用）")
                        continue
                    try:
                        kwargs = {"content": content, "cookie": self.site.cookie}
                        if self._save_path:
                            kwargs["download_dir"] = self._save_path
                        # 添加前后对下载器做 hash 快照：torrentool 解析的是 v1 infohash，
                        # v1+v2 混合种子在下载器（libtorrent 2.x）中的真实 hash 可能是 v2，
                        # 唯一新增的 hash 才是可信的 torrent_hash。
                        try:
                            hashes_before = self._downloader_hashes()
                        except Exception:
                            hashes_before = set()
                        logger.debug(f"下载种子参数键: {sorted(kwargs.keys())}")
                        result = service_info.instance.add_torrent(**kwargs)
                        if not result:
                            failed_count += 1
                            failed_details.append(f"- {record['title'][:30]}（下载器拒绝）")
                            logger.error("下载种子失败")
                            continue
                        downloaded_count += 1
                        success_count += 1
                        # 差集修正：唯一新增的 hash 才是下载器中的真实 hash（v2 混合种子场景）
                        try:
                            new_hashes = self._downloader_hashes() - hashes_before
                            if len(new_hashes) == 1:
                                torrent_hash = new_hashes.pop()
                            elif len(new_hashes) > 1:
                                logger.warning(f"添加后发现 {len(new_hashes)} 个新种子，无法唯一确定 hash，保留解析值")
                        except Exception as exc:
                            logger.warning(f"下载器 hash 快照失败，保留解析值: {exc}")
                        success_details.append(f"{success_count}. [{record.get('score', 0):.1f}分] {record['size']} {record['title'][:30]}")
                        if norm_title:
                            existing_titles.add(norm_title)
                        if self._custom_tag and torrent_hash:
                            self._add_torrent_tag(service_info, torrent_hash, self._custom_tag)
                        if self._force_resume and service_info.type == "qbittorrent" and torrent_hash:
                            service_info.instance.torrents_set_force_start(ids=torrent_hash)
                        records.append({
                            "title": record["title"], "zh_title": record["zh_title"], "score": record.get("score"),
                            "size": record["size"], "seeders": record["seeders"],
                            "download_link": link, "torrent_hash": torrent_hash,
                            "download_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        })
                        self.save_data(key="download_records", value=records[-100:])
                    except Exception as exc:
                        failed_count += 1
                        logger.error(f"下载种子失败: {exc}")
                        failed_details.append(f"- {record.get('title', '?')[:30]}（异常）")
            logger.info(f"【憨憨保种区】获取任务完成：精筛通过 {len(refined)} 个，成功下载 {success_count} 个，失败 {failed_count} 个，重复跳过 {skipped_dup_count} 个")
            if self._enable_notification:
                if success_count or failed_count:
                    text = f"本轮成功拯救 {success_count} 个种子"
                    if skipped_dup_count:
                        text += f"，重复跳过 {skipped_dup_count} 个"
                    if failed_count:
                        text += f"，失败 {failed_count} 个"
                    if success_details:
                        text += "\n\n✅ 成功明细:\n" + self._fmt_details(success_details)
                    if failed_details:
                        text += "\n\n❌ 失败明细:\n" + self._fmt_details(failed_details)
                    self.post_message(mtype=NotificationType.Plugin, title="【憨憨保种区获取】", text=text)
                elif self._notify_on_zero_torrents:
                    self.post_message(mtype=NotificationType.Plugin, title="【憨憨保种区获取】", text="本轮未找到符合条件的新种子")
        except Exception as exc:
            logger.error(f"检查保种区异常: {exc}\\n{traceback.format_exc()}")
            if self._enable_notification:
                self.post_message(mtype=NotificationType.Plugin, title="【憨憨保种区获取】", text="保种任务执行异常，请查看日志了解详情")

    def _refine_by_detail(self, candidates, budget=None):
        """Apply peer-level thresholds once per candidate with one shared round budget."""
        if self._completion_ratio_max is None and self._connect_time_max_hours is None:
            logger.debug("详情精筛跳过: config_empty")
            return [c for c in candidates if self._min_downloaders is None or c.get("leechers") is not None and c["leechers"] >= self._min_downloaders]
        budget = budget or {"used": 0, "limit": self.DETAIL_REQUEST_BUDGET}
        passed, unknown_ids, structure_ids = [], [], []
        detail_requests = 0
        for candidate in candidates:
            if self._event.is_set():
                break
            if budget["used"] >= budget["limit"]:
                logger.debug("详情精筛预算耗尽，候选延期: %s", candidate.get("torrent_id"))
                continue
            result = None
            for attempt, backoff in enumerate((0, 2, 4)):
                if attempt and self._event.wait(backoff):
                    break
                if self._event.is_set() or budget["used"] >= budget["limit"]:
                    break
                if detail_requests and self._event.wait(2):
                    break
                budget["used"] += 1
                detail_requests += 1
                try:
                    response = RequestUtils(cookies=self.site.cookie, timeout=30).get_res(
                        f"https://{self.domain}/viewpeerlist.php?id={candidate['torrent_id']}&json=1",
                        allow_redirects=True)
                    status = getattr(response, "status_code", 200) if response is not None else 0
                    if status != 200 or response is None:
                        raise ValueError(f"HTTP {status}")
                    payload = response.json() if hasattr(response, "json") else None
                    if not isinstance(payload, dict) or "leechers" not in payload:
                        raise ValueError("缺少 leechers")
                    leechers = payload.get("leechers")
                    if not isinstance(leechers, dict) or not isinstance(leechers.get("data"), list):
                        structure_ids.append(str(candidate.get("torrent_id")))
                        result = ("unknown", None)
                        break
                    peers = leechers["data"]
                    count = payload.get("leecher_count", leechers.get("count", len(peers)))
                    try:
                        count = int(count)
                    except (TypeError, ValueError):
                        count = len(peers)
                    if self._min_downloaders is not None and count < self._min_downloaders:
                        result = ("reject", None)
                        break
                    if len(peers) < count:
                        logger.debug("详情数据可能 partial: id=%s returned=%s count=%s", candidate.get("torrent_id"), len(peers), count)
                    bad = False
                    complete_values = []
                    for peer in peers:
                        if self._completion_ratio_max is not None:
                            raw_complete = peer.get("complete") if isinstance(peer, dict) else None
                            try:
                                complete = float(str(raw_complete).strip().rstrip("%"))
                            except (TypeError, ValueError):
                                logger.debug("下载者完成率解析失败: id=%s", candidate.get("torrent_id"))
                                result = ("unknown", None)
                                break
                            if complete >= self._completion_ratio_max:
                                bad = True
                            complete_values.append(complete)
                        else:
                            # 未启用精筛阈值时也收集完成率，供评分使用；解析失败不影响准入
                            _raw = peer.get("complete") if isinstance(peer, dict) else None
                            try:
                                complete_values.append(float(str(_raw).strip().rstrip("%")))
                            except (TypeError, ValueError):
                                pass
                        if self._connect_time_max_hours is not None:
                            raw_connected = peer.get("connected") if isinstance(peer, dict) else None
                            text = str(raw_connected or "").strip()
                            # NexusPHP 递进格式（qnap 真实 peerlist 实证）：MM:SS（<1h）/ H:MM:SS（<1d）/ X天H:MM:SS
                            match = re.fullmatch(r"(?:(\d+)天)?(\d+):(\d+):(\d+)", text)
                            match_short = re.fullmatch(r"(\d+):(\d+)", text)
                            if not match and not match_short:
                                logger.debug("下载者连接时间解析失败: id=%s", candidate.get("torrent_id"))
                                result = ("unknown", None)
                                break
                            if match:
                                hours = int(match.group(1) or 0) * 24 + int(match.group(2)) + int(match.group(3)) / 60 + int(match.group(4)) / 3600
                            else:
                                hours = int(match_short.group(1)) / 60 + int(match_short.group(2)) / 3600
                            if hours >= self._connect_time_max_hours:
                                bad = True
                    else:
                        ratio = None
                        if complete_values and len(peers) >= count:
                        # 策略：准入不受坏行影响；评分对成功解析子集求均值（部分样本降级），partial 响应不外推
                            ratio = sum(complete_values) / len(complete_values) / 100.0
                        result = ("reject" if bad else "pass", ratio)
                    if result and result[0] == "unknown":
                        break
                except Exception as exc:
                    logger.debug("详情精筛请求失败 id=%s attempt=%s: %s", candidate.get("torrent_id"), attempt + 1, exc)
                    if attempt == 2:
                        result = ("unknown", None)
            if not result or result[0] == "unknown":
                unknown_ids.append(str(candidate.get("torrent_id")))
            elif result[0] == "pass":
                candidate["completion_ratio"] = result[1]
                passed.append(candidate)
        if unknown_ids or structure_ids:
            ids = (unknown_ids + structure_ids)[:5]
            if self._enable_notification:
                if structure_ids:
                    text = f"详情页表结构变化，需要适配，失败种子ID: {', '.join(ids)}"
                else:
                    text = f"详情页解析失败，本轮跳过下载，种子ID: {', '.join(ids)}"
                self.post_message(mtype=NotificationType.Plugin, title="【憨憨保种区获取】", text=text)
        return passed

    def _get_page_source(self, url: str, site):
        """
        获取页面资源
        """
        ret = RequestUtils(
            cookies=site.cookie,
            timeout=30,
        ).get_res(url, allow_redirects=True)
        if ret is not None:
            # 使用chardet检测字符编码
            raw_data = ret.content
            if raw_data:
                try:
                    result = chardet.detect(raw_data)
                    encoding = result['encoding']
                    # 解码为字符串
                    page_source = raw_data.decode(encoding)
                except Exception as e:
                    # 探测utf-8解码
                    if re.search(r"charset=\"?utf-8\"?", ret.text, re.IGNORECASE):
                        ret.encoding = "utf-8"
                    else:
                        ret.encoding = ret.apparent_encoding
                    page_source = ret.text
            else:
                page_source = ret.text
        else:
            page_source = ""
        return page_source

    def _fetch_torrents(self, instance, **kwargs) -> list:
        """统一解包下载器模块 get_torrents 返回值：qb 模块返回 (list, err) 元组，
        transmission 模块返回裸 list。此前直接迭代元组导致圈定恒 0、记录被误清。"""
        result = instance.get_torrents(**kwargs)
        if isinstance(result, tuple):
            torrents, _err = result
            return list(torrents or [])
        return list(result or [])

    def _downloader_hashes(self) -> set:
        """获取下载器中全部种子的 hash 集合（小写），不经标签过滤。"""
        service_info = self.downloader_helper.get_service(self._downloader)
        if not service_info or not service_info.instance:
            return set()
        hashes = set()
        for t in self._fetch_torrents(service_info.instance):
            h = getattr(t, "hash", None)
            if h:
                hashes.add(str(h).lower())
        return hashes

    def _download_torrent(self, url: str, site) -> Tuple[Optional[bytes], Optional[str]]:
        """
        根据url下载种子文件，返回种子内容bytes和种子对应的hash
        """
        ret = RequestUtils(
            cookies=site.cookie,
            timeout=30,
        ).get_res(url, allow_redirects=True)

        if ret is not None and ret.content:
            try:
                # 使用torrentool解析种子内容并计算info hash
                torrent = Torrent.from_string(ret.content)
                torrent_hash = torrent.info_hash
                return ret.content, torrent_hash
            except Exception as e:
                logger.error(f"解析种子文件失败: {str(e)}")
                # 如果解析失败，仍然返回内容但hash为None
                return ret.content, None
        else:
            logger.error("下载种子失败")
            return None, None

    def _delete_torrent_by_hash(self, torrent_hash: str) -> bool:
        """
        根据hash删除下载器中的种子
        """
        if not self._custom_tag:
            logger.error("未配置自定义标签，拒绝删除种子（防止误删非本插件种子）")
            return False
        if not self._downloader:
            logger.error("未配置下载器")
            return False

        service_info = self.downloader_helper.get_service(self._downloader)
        if not service_info or not service_info.instance:
            logger.error(f"下载器 {self._downloader} 未连接或不可用")
            return False

        try:
            # 应用层复核标签与 hash，不能信任下载器 tags 过滤参数。
            guard = self._fetch_torrents(service_info.instance, ids=torrent_hash, tags=self._custom_tag)
            expected_hash = str(torrent_hash).lower()
            matched = [t for t in guard if self._torrent_has_managed_tag(t)
                       and str((self._get_torrent_stats(t) or {}).get("hash", "")).lower() == expected_hash]
            if not matched:
                logger.warning(f"种子 {torrent_hash} 不带插件标签或 hash 不匹配，拒绝删除")
                return False
            # 根据下载器类型调用相应的删除方法
            if service_info.type == "qbittorrent":
                # Qbittorrent 删除种子
                result = service_info.instance.delete_torrents(ids=torrent_hash, delete_file=self._delete_files)
                return result
            elif service_info.type == "transmission":
                # Transmission 删除种子
                result = service_info.instance.remove_torrents(hashs=torrent_hash, delete_file=self._delete_files)
                return result
            else:
                logger.error(f"不支持的下载器类型: {service_info.type}")
                return False
        except Exception as e:
            logger.error(f"删除种子失败 (hash: {torrent_hash}): {str(e)}")
            return False


    def _retag_existing(self, info) -> None:
        """存量补标：下载记录中的种子若因历史打标失败缺本插件标签，补打（幂等）。
        老版 MP 的 qb 模块没有 set_torrent_tag，v3.2.8 前下载的种子会全部缺标签，
        导致监控圈定 0 个、max_downloading 失明、数据页状态聚合匹配不到。"""
        if not self._custom_tag:
            return
        try:
            records = self.get_data("download_records") or []
            if not records:
                return
            by_hash = {}
            for torrent in self._fetch_torrents(info.instance):
                h = (getattr(torrent, "hash", "") or "").lower()
                if h:
                    by_hash[h] = torrent
            retagged = 0
            for record in records:
                h = (record.get("hash") or "").lower()
                match = by_hash.get(h)
                if match is not None and not self._torrent_has_managed_tag(match):
                    if self._add_torrent_tag(info, h, self._custom_tag):
                        retagged += 1
            if retagged:
                logger.info(f"下载器 {info.name} 存量补标 {retagged} 个（历史打标失败补救）")
        except Exception as exc:
            logger.warning(f"存量补标检查失败: {exc}")

    def _maintenance(self):
        """
        种子监控任务：达标打标 → 配额删除 → 卡死清理
        仅依赖下载器状态，不访问保种区站点
        """
        try:
            logger.info("【憨憨保种区】开始执行种子监控")
            if not self._enable:
                logger.info("憨憨保种区插件未启用，跳过监控")
                return
            if not self._custom_tag:
                logger.warning("未配置下载标签，无法圈定监控范围，跳过监控")
                return

            infos = self.service_infos
            if not infos:
                return

            reward_tag = self._reward_tag or "憨憨保种达标"
            removed_names = []
            still_over_gb = 0.0
            quota_removed = 0
            stuck_removed = 0
            tagged_count = 0

            for name, info in infos.items():
                self._retag_existing(info)
                torrents = [t for t in self._fetch_torrents(info.instance, tags=self._custom_tag)
                            if self._torrent_has_managed_tag(t)]
                # 监控任务开头顺带接管：复用本轮已拉取的 scoped torrents，避免重复请求下载器
                if name == self._downloader:
                    adopted = self._adopt_missing_records(scoped_torrents=torrents)
                    if adopted:
                        logger.info(f"【憨憨保种区】监控接管：入库 {adopted} 个历史种子")
                stats = []
                for t in torrents:
                    s = self._get_torrent_stats(t)
                    if s:
                        stats.append((t, s))
                logger.info(f"下载器 {name} 圈定种子 {len(stats)} 个（标签 {self._custom_tag}）")

                # ① 达标打标：做种满 reward_hours 小时且下载完成
                for _, s in stats:
                    if s["progress"] >= 1 and s["seeding_hours"] >= self._reward_hours and reward_tag not in s["tags"]:
                        if self._add_torrent_tag(info, s["hash"], reward_tag, org_tags=s["tags"]):
                            tagged_count += 1
                            s["tags"].append(reward_tag)
                            logger.info(f"达标打标: {s['name']} 做种 {s['seeding_hours']:.1f}h")

                if not self._auto_delete_enabled:
                    continue

                # ② 配额删除：总体积超过配额触发，删回配额 * DISK_QUOTA_TARGET_RATIO
                if self._disk_quota_gb:
                    total_gb = sum(s["size_gb"] for _, s in stats)
                    quota = float(self._disk_quota_gb)
                    if total_gb > quota:
                        target_gb = quota * self.DISK_QUOTA_TARGET_RATIO
                        logger.info(f"保种总体积 {total_gb:.2f}GB 超过配额 {quota:.2f}GB，目标删至 {target_gb:.2f}GB")
                        # 排序：已达标（有奖励标签）优先删 → 平均上传低优先 → 做种久的优先
                        cands = sorted(stats, key=lambda x: (
                            reward_tag not in x[1]["tags"],
                            x[1]["avg_upspeed"] >= self.NO_UPLOAD_AVG_SPEED,
                            -x[1]["seeding_hours"]
                        ))
                        for _, s in cands:
                            if self._event.is_set() or total_gb <= target_gb or quota_removed >= self.MAX_REMOVE_PER_RUN:
                                break
                            if self._delete_torrent_by_hash(s["hash"]):
                                logger.info(f"配额清理删除: {s['name']}（{s['size_gb']:.2f}GB，平均上传 {s['avg_upspeed']:.0f}B/s）")
                                removed_names.append(s["name"])
                                quota_removed += 1
                                total_gb -= s["size_gb"]
                        still_over_gb = max(0.0, total_gb - target_gb)

                # ③ 卡死清理：超过 stuck_days 天仍未下载完成
                if self._stuck_days:
                    stuck = [(t, s) for t, s in stats
                             if s["progress"] < 1 and s["added_days"] >= self._stuck_days]
                    for _, s in stuck[:max(0, self.MAX_REMOVE_PER_RUN - stuck_removed)]:
                        if self._event.is_set() or stuck_removed >= self.MAX_REMOVE_PER_RUN:
                            break
                        if self._delete_torrent_by_hash(s["hash"]):
                            logger.info(f"卡死清理删除: {s['name']}（加入 {s['added_days']:.1f} 天未完成）")
                            removed_names.append(s["name"])
                            stuck_removed += 1

            logger.info(f"【憨憨保种区】监控完成：达标打标 {tagged_count} 个，配额清理 {quota_removed} 个，卡死清理 {stuck_removed} 个")
            # 通知：仅在发生删除时发送
            if self._enable_notification and removed_names:
                text = f"已清理做种 {len(removed_names)} 个:\n" + "\n".join(f"· {n}" for n in removed_names[:10])
                if still_over_gb > 0:
                    text += f"\n仍超出目标水位 {still_over_gb:.2f} GB，下轮监控继续清理"
                self.post_message(
                    mtype=NotificationType.Plugin,
                    title="【憨憨保种区监控】",
                    text=text
                )
        except Exception as e:
            logger.error(f"种子监控异常: {str(e)}\n{traceback.format_exc()}")

    def _torrent_has_managed_tag(self, torrent):
        stats = self._get_torrent_stats(torrent)
        expected = {tag.strip() for tag in str(self._custom_tag or "").split(",") if tag.strip()}
        return bool(stats and expected.intersection(set(stats["tags"])))

    def _get_scoped_torrents(self, downloader):
        """Downloader tag queries are only a hint; enforce exact application-layer tag matching."""
        if not self._custom_tag or not self.downloader_helper:
            return []
        service = self.downloader_helper.get_service(downloader)
        if not service or not service.instance:
            return []
        expected = {tag.strip() for tag in str(self._custom_tag).split(",") if tag.strip()}
        result = []
        for torrent in self._fetch_torrents(service.instance, tags=self._custom_tag):
            stats = self._get_torrent_stats(torrent)
            if stats and expected.intersection(set(stats["tags"])):
                result.append(torrent)
        return result

    def _get_torrent_stats(self, torrent) -> Optional[dict]:
        """
        把 qbittorrent(dict 风格)/transmission(属性风格) 的种子对象翻译成统一结构
        {
            name, hash, size_gb, uploaded, avg_upspeed, progress,
            seeding_hours, added_days, tags, state
        }
        解析失败返回 None
        """
        try:
            def val(*names):
                for n in names:
                    try:
                        v = torrent.get(n)
                    except Exception:
                        v = getattr(torrent, n, None)
                    if v is not None:
                        return v
                return None

            size = val("total_size", "size", "filesize") or 0
            uploaded = val("uploaded", "uploadedEver") or 0
            # 活动时长(秒)：qb time_active / tr secondsSeeding
            active_seconds = val("time_active", "secondsSeeding") or 0
            # 做种时长(秒)：仅做种阶段 qb seeding_time / tr secondsSeeding，下载中为 0
            seeding_seconds = val("seeding_time", "secondsSeeding") or 0
            progress = val("progress", "percent_done") or 0
            added = val("added_on", "date_added")
            tags = val("tags", "labels") or []
            if isinstance(tags, str):
                tags = [x.strip() for x in tags.split(",") if x.strip()]
            # 进度归一到 0-1：qb progress 0-1；tr percent_done 0-100（可能小于 1，按字段来源分支而非阈值猜测）
            pd = val("percent_done")
            try:
                if pd is not None:
                    progress = float(pd) / 100.0
                else:
                    progress = float(val("progress") or 0)
            except (TypeError, ValueError):
                progress = 0.0
            now = datetime.datetime.now()
            added_days = 0.0
            if added:
                try:
                    if isinstance(added, (int, float)):
                        added_dt = datetime.datetime.fromtimestamp(added)
                    elif isinstance(added, datetime.datetime):
                        added_dt = added
                    else:
                        added_dt = None
                    if added_dt:
                        added_days = max(0.0, (now - added_dt).total_seconds() / 86400.0)
                except Exception:
                    pass
            return {
                "name": val("name") or "未知名称",
                "hash": val("hash", "hashString") or "",
                "size_gb": float(size) / (1024 ** 3),
                "uploaded": float(uploaded),
                "avg_upspeed": (float(uploaded) / float(active_seconds)) if float(active_seconds) > 0 else 0.0,
                "progress": progress,
                "seeding_hours": float(seeding_seconds) / 3600.0,
                "added_days": added_days,
                "tags": [str(x) for x in tags],
                "state": str(val("state", "status") or "")
            }
        except Exception as e:
            logger.warning(f"解析种子状态失败: {str(e)}")
            return None

    def _add_torrent_tag(self, service_info, torrent_hash: str, tag: str, org_tags: list = None) -> bool:
        """打标兼容层：优先 MP 统一接口 set_torrent_tag（tr 及新版 qb 模块），
        回退 qbittorrent-api 底层 torrents_add_tags（老版 MP 的 qb 模块没有
        set_torrent_tag；该接口语义为追加标签，天然保留原标签）。"""
        if not torrent_hash or not tag:
            return False
        instance = service_info.instance
        try:
            if hasattr(instance, "set_torrent_tag"):
                instance.set_torrent_tag(
                    ids=[torrent_hash], tags=[tag], org_tags=list(org_tags or []))
            elif hasattr(instance, "set_torrents_tag"):
                # 老版 MP qb 模块接口（追加语义，保留原有标签）
                instance.set_torrents_tag(ids=[torrent_hash], tags=[tag])
            elif hasattr(instance, "torrents_add_tags"):
                instance.torrents_add_tags(tags=[tag], hashes=[torrent_hash])
            else:
                logger.warning(
                    f"添加标签失败 (hash: {torrent_hash}, tag: {tag}): "
                    f"下载器实例不支持标签接口（无 set_torrent_tag/torrents_add_tags）")
                return False
            return True
        except Exception as e:
            logger.warning(f"添加标签失败 (hash: {torrent_hash}, tag: {tag}): {str(e)}")
            return False

    def _compute_push_score(self, record: dict) -> float:
        """推送评分 v1：体积分(50) + 需求分(40) + 稀缺分(10)。

        量纲按站点经验校准：下载人数典型范围 0-20（SCORE_LEECHER_CAP 封顶），
        300GB 与 0.7GB 的体积分差(约 45 分)与需求+稀缺满分(50 分)接近，
        极端满热度小体积可逼近大体积；需求可反转 40 分以内的体积差(如 30GB vs 300GB)。
        """
        size_gb = record.get("size_gb")
        if size_gb is None:
            size_gb = self._parse_size_to_gb(record.get("size"))
        try:
            size_gb = float(size_gb) if size_gb is not None else None
        except (TypeError, ValueError):
            size_gb = None
        if size_gb is not None and size_gb > 0:
            size_score = self.SCORE_SIZE_WEIGHT * math.log2(1 + min(size_gb, self.SCORE_SIZE_CAP_GB)) / math.log2(1 + self.SCORE_SIZE_CAP_GB)
        else:
            size_score = 0.0
        remaining = record.get("completion_ratio")
        remaining = (1.0 - remaining) if remaining is not None else self.SCORE_UNKNOWN_REMAINING
        leechers = record.get("leechers")
        if isinstance(leechers, (int, float)) and not isinstance(leechers, bool) and leechers >= 0:
            heat = math.log2(1 + min(leechers, self.SCORE_LEECHER_CAP)) / math.log2(1 + self.SCORE_LEECHER_CAP)
            demand_score = self.SCORE_DEMAND_WEIGHT * heat * remaining
        else:
            demand_score = 0.0
        try:
            seeders = int(str(record.get("seeders") or 0))
            if seeders < 0:
                seeders = None
        except ValueError:
            seeders = None
        scarcity_score = self.SCORE_SCARCITY_WEIGHT / max(1, seeders) if seeders is not None else 0.0
        return size_score + demand_score + scarcity_score

    @staticmethod
    def _fmt_details(lines: List[str], limit: int = 10) -> str:
        """通知明细列表：超 limit 条折叠为摘要行。"""
        text = "\n".join(lines[:limit])
        if len(lines) > limit:
            text += f"\n...等 {len(lines)} 条"
        return text
    def _prefilter_row(self, elem, stats=None) -> dict | None:
        """List-only coarse filter. Peer thresholds are handled by _refine_by_detail."""
        def bump(key):
            if stats is not None:
                stats[key] = stats.get(key, 0) + 1

        def text_num(nodes):
            if not nodes:
                return None
            # itertext 递归取全部文本（数字可能在 <span>/<font> 子元素里），正则提取首个整数
            match = re.search(r"\d+", "".join(nodes[0].itertext()))
            return int(match.group()) if match else None
        seeders = text_num(elem.xpath("div[3]/div/div[3]/a"))
        if seeders is None:
            # '0' 等数字可能直接在单元格文本层而非 <a> 内（qnap 真实页面实证）
            seeders = text_num(elem.xpath("div[3]/div/div[3]"))
        if seeders is None:
            bump("做种数解析失败")
            logger.warning(f"未找到做种人数或格式错误，跳过该种子（单元格文本: {(elem.xpath('string(div[3]/div/div[3])') or '').strip()!r}）")
            return None
        seeding = str(self._seeding_count or "").strip()
        if seeding and not self._value_in_specs(seeders, seeding):
            bump("做种人数不在范围内")
            return None
        free_tags = elem.xpath('div[2]/div/div[2]/div[contains(., "免费")]')
        if self._free and not free_tags:
            bump("非免费种子")
            return None
        leechers = text_num(elem.xpath("div[3]/div/div[4]/a"))
        if leechers is None:
            leechers = text_num(elem.xpath("div[3]/div/div[4]"))
        if self._min_downloaders is not None and leechers is not None and leechers < self._min_downloaders:
            bump("下载数不在范围内")
            return None
        if self._min_downloaders is not None and leechers is None and self._completion_ratio_max is None and self._connect_time_max_hours is None:
            logger.debug("列表下载数未知且未启用详情精筛，跳过")
            bump("下载数未知")
            return None
        size_nodes = elem.xpath("div[3]/div/div[1]")
        size_text = size_nodes[0].text.strip() if size_nodes and size_nodes[0].text else None
        if self._torrent_size and size_text:
            size_gb = self._parse_size_to_gb(size_text)
            if size_gb is not None and not self._value_in_specs(size_gb, str(self._torrent_size), numeric=True):
                bump("种子大小不在范围内")
                return None
        title_nodes = elem.xpath("div[2]/div/a")
        zh_nodes = elem.xpath("div[2]/div/div[1]/div")
        detail_nodes = elem.xpath("div[2]/div/a/@href")
        download_nodes = elem.xpath("div[4]/div/a/@href")
        detail_link = detail_nodes[0] if detail_nodes else ""
        match = re.search(r"id=(\d+)", detail_link)
        download_link = ""
        if download_nodes:
            download_link = f"https://{self.domain}/{download_nodes[0].lstrip('/')}"
        return {
            "title": title_nodes[0].text.strip() if title_nodes and title_nodes[0].text else "未知标题",
            "zh_title": zh_nodes[0].text.strip() if zh_nodes and zh_nodes[0].text else "无中文标题",
            "size": size_text or "未知大小",
            "size_gb": self._parse_size_to_gb(size_text) if size_text else None,
            "seeders": str(seeders),
            "leechers": leechers,
            "torrent_id": match.group(1) if match else None,
            "download_link": download_link,
        }

    @staticmethod
    def _value_in_specs(value, spec, numeric=False):
        try:
            for item in str(spec).split(","):
                item = item.strip()
                if not item:
                    continue
                if "-" in item:
                    low, high = item.split("-", 1)
                    low, high = (float(low) if numeric else int(low), float(high) if numeric else int(high))
                    if low <= value <= high:
                        return True
                elif value <= (float(item) if numeric else int(item)):
                    return True
        except (TypeError, ValueError):
            logger.error(f"无效的筛选格式: {spec}")
            return False
        return False

    def get_page(self) -> List[dict]:
        return None

    def stop_service(self):
        """
        停止服务
        """
        try:
            self._event.set()
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown(wait=False)
                self._scheduler = None
            # 保持置位，直到下一次 init_plugin 明确开启新一轮
        except Exception as e:
            logger.error(f"停止服务异常: {str(e)}")

    def _check_history_seeding(self):
        """
        下载历史保种任务
        访问 /userdetails.php?id={用户id}&action=7&page={page} 页面，解析种子信息并下载
        """
        if not self._user_id:
            logger.error("用户ID未配置，无法执行下载历史保种任务")
            return

        try:
            # 初始化passkey变量
            passkey = ""
            downloaded_count = 0
            success_downloaded_count = 0
            failed_downloaded_count = 0

            # 遍历页面，从page=0开始
            page = 0
            while True:
                if self._event.is_set():
                    logger.info("检测到停止事件，终止历史保种任务")
                    break
                user_details_url = f"https://{self.domain}/userdetails.php?id={self._user_id}&action=7&page={page}"
                logger.debug(f"正在访问用户历史页面第{page + 1}页: {user_details_url}")

                page_content = self._get_page_source(url=user_details_url, site=self.site)
                if not page_content:
                    logger.error(f"访问用户历史页面第{page + 1}页失败: {user_details_url}")
                    break

                # 解析页面
                html = etree.HTML(page_content)
                if html is None:
                    logger.error(f"用户历史页面第{page + 1}页解析失败")
                    break

                # 通过xpath获取tr元素
                tables = html.xpath('//*[@id="mainContent"]/div/div[2]/table')
                if not tables:
                    logger.error(f"用户历史页面第{page + 1}页结构异常，未找到表格")
                    break
                tr_elements = tables[0].xpath('tr')

                # 检查tr数量
                if len(tr_elements) < 2:
                    logger.info(f"用户历史页面第{page + 1}页种子数量为0个，终止任务")
                    break

                logger.info(f"用户历史页面第{page + 1}页发现 {len(tr_elements)-1} 条种子记录，开始处理")

                # 从第2个tr开始遍历（跳过标题行）
                for i, tr in enumerate(tr_elements[1:], start=1):
                    try:
                        # 检查下载数量限制
                        if self._download_limit > 0 and success_downloaded_count >= self._download_limit:
                            logger.info(f"已达到单次下载数量限制 ({self._download_limit})，停止下载")
                            break
                        # 通过td[2]/a/@href获取种子详情页的地址
                        detail_link_elements = tr.xpath('td[2]/a/@href')
                        if not detail_link_elements:
                            logger.warning(f"第 {i} 条记录没有找到详情链接")
                            continue

                        detail_link = detail_link_elements[0]

                        # 通过正则匹配数字获取种子id
                        import re
                        torrent_id_match = re.search(r'id=(\d+)', detail_link)
                        if not torrent_id_match:
                            logger.warning(f"第 {i} 条记录无法解析种子ID")
                            continue

                        torrent_id = torrent_id_match.group(1)

                        # 通过td[2]/a/text()获取种子的标题
                        title_elements = tr.xpath('td[2]/a/text()')
                        title = title_elements[0].strip() if title_elements else f"未知标题-{torrent_id}"

                        # 通过td[3]获取种子大小
                        size_elements = tr.xpath('td[3]//text()')
                        size = "".join(size_elements).strip() if size_elements else "未知大小"

                        # 通过td[4]获取做种人数
                        seeders_elements = tr.xpath('td[4]//text()')
                        seeders_text = "".join(seeders_elements).strip() if seeders_elements else "0"

                        # 尝试解析做种人数
                        try:
                            seeders = int(re.search(r'\d+', seeders_text).group())
                        except (ValueError, AttributeError):
                            logger.warning(f"第 {i} 条记录无法解析做种人数: {seeders_text}")
                            continue

                        logger.info(f"种子 {torrent_id}: {title}, 大小: {size}, 做种人数: {seeders}")

                        # 检查做种人数是否在设定区间内
                        seeding_count_str = str(self._seeding_count or "").strip()
                        if seeding_count_str and not self._value_in_specs(seeders, seeding_count_str):
                            logger.info(f"种子 {torrent_id} 做种人数 {seeders} 不在设定范围内 {seeding_count_str}，跳过")
                            continue

                        # 检查种子大小是否在设定范围内
                        if self._torrent_size:
                            size_gb = self._parse_size_to_gb(size)
                            if size_gb is not None:
                                torrent_size_str = str(self._torrent_size)
                                size_in_range = False

                                if '-' in torrent_size_str:
                                    # 范围格式，如 1-5
                                    range_parts = torrent_size_str.split('-')
                                    if len(range_parts) == 2:
                                        try:
                                            lower_bound = float(range_parts[0])
                                            upper_bound = float(range_parts[1])
                                            if lower_bound <= size_gb <= upper_bound:
                                                size_in_range = True
                                        except ValueError:
                                            logger.error(f"无效的种子大小范围格式: {torrent_size_str}")
                                            continue
                                else:
                                    # 单个数字格式，检查种子大小是否小于该数字
                                    try:
                                        if size_gb <= float(torrent_size_str):
                                            size_in_range = True
                                    except ValueError:
                                        logger.error(f"无效的种子大小数字格式: {torrent_size_str}")
                                        continue

                                if not size_in_range:
                                    logger.info(f"种子 {torrent_id} 大小 {size_gb:.2f}GB 不在设定范围内 {torrent_size_str}GB，跳过")
                                    continue
                            else:
                                logger.warning(f"无法解析种子大小: {size}，跳过大小检查")

                        # 如果passkey为空，访问第一个种子的详情页获取passkey
                        if not passkey:
                            first_detail_url = f"https://{self.domain}/{detail_link}"
                            logger.info(f"正在访问第一个种子详情页获取passkey: {first_detail_url}")

                            detail_page_content = self._get_page_source(url=first_detail_url, site=self.site)
                            if detail_page_content:
                                detail_html = etree.HTML(detail_page_content)
                                if detail_html is not None:
                                    # 通过xpath获取下载链接
                                    download_link_elements = detail_html.xpath('//*[@id="mainContent"]/div/div/div[1]/span/a/@href')
                                    if download_link_elements:
                                        # 通过正则表达式获取passkey
                                        passkey_match = re.search(r'passkey=([^&]*)', download_link_elements[0])
                                        if passkey_match:
                                            passkey = passkey_match.group(1)
                                            logger.info("已从详情页获取 passkey")
                                        else:
                                            logger.warning(f"无法从详情页获取passkey: {first_detail_url}")
                                    else:
                                        logger.warning(f"在详情页未找到下载链接: {first_detail_url}")
                                else:
                                    logger.warning(f"种子详情页解析失败: {first_detail_url}")
                            else:
                                logger.warning(f"访问种子详情页失败: {first_detail_url}")

                            if not passkey:
                                logger.error("无法获取passkey，终止任务")
                                return

                        # 构造下载链接
                        download_link = f"https://{self.domain}/download.php?id={torrent_id}&passkey={passkey}"
                        logger.info(f"开始下载种子: id={torrent_id}")

                        # 下载种子文件
                        torrent_content, torrent_hash = self._download_torrent(download_link, self.site)
                        if not torrent_content:
                            logger.error(f"下载种子文件失败: id={torrent_id}")
                            failed_downloaded_count += 1
                            continue

                        # 调用下载器下载种子
                        downloader = self._downloader
                        service_info = self.downloader_helper.get_service(downloader)
                        if service_info and service_info.instance:
                            try:
                                logger.debug(f"获取下载器实例成功: {downloader}")
                                # 准备下载参数
                                download_kwargs = {"content": torrent_content, "cookie": self.site.cookie}
                                if self._save_path:
                                    download_kwargs["download_dir"] = self._save_path
                                # v2 混合种子 hash 修正：添加前快照
                                try:
                                    hashes_before = self._downloader_hashes()
                                except Exception:
                                    hashes_before = set()
                                logger.debug(f"下载种子参数键: {sorted(download_kwargs.keys())}")
                                # 下载种子文件
                                result = service_info.instance.add_torrent(**download_kwargs)
                                logger.debug(f"下载结果: {result}")
                                if result:
                                    # 差集修正：唯一新增的 hash 才是下载器真实 hash
                                    try:
                                        new_hashes = self._downloader_hashes() - hashes_before
                                        if len(new_hashes) == 1:
                                            torrent_hash = new_hashes.pop()
                                        elif len(new_hashes) > 1:
                                            logger.warning(f"添加后发现 {len(new_hashes)} 个新种子，无法唯一确定 hash，保留解析值")
                                    except Exception as exc:
                                        logger.warning(f"下载器 hash 快照失败，保留解析值: {exc}")
                                    logger.info(f"成功下载种子: id={torrent_id}")
                                    if self._custom_tag and torrent_hash:
                                        self._add_torrent_tag(service_info, torrent_hash, self._custom_tag)
                                    downloaded_count += 1
                                    success_downloaded_count += 1

                                    # 如果启用了强制继续且是qbittorrent，设置强制作种
                                    if self._force_resume and service_info.type == "qbittorrent":
                                        try:
                                            # 等待一下让种子添加到下载器
                                            import time
                                            time.sleep(1)
                                            service_info.instance.torrents_set_force_start(ids=torrent_hash)
                                            logger.info(f"已设置种子强制作种: {torrent_hash}")
                                        except Exception as e:
                                            logger.error(f"设置强制作种失败: {str(e)}")

                                    # 获取种子信息
                                    zh_title = "历史种子"  # 历史种子可能没有中文标题
                                    seed_count = str(seeders)

                                    # 保存下载记录
                                    download_record = {
                                        "title": title,
                                        "zh_title": zh_title,
                                        "size": size,
                                        "seeders": seed_count,
                                        "download_link": download_link,
                                        "torrent_hash": torrent_hash,  # 使用下载时计算的种子hash
                                        "download_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    }

                                    # 获取现有下载记录
                                    download_records = self.get_data("download_records") or []
                                    # 将新记录添加到列表中
                                    download_records.append(download_record)
                                    # 保存更新后的列表（上限 100 条，裁最旧）
                                    download_records = download_records[-100:]
                                    self.save_data(key="download_records", value=download_records)

                                else:
                                    logger.error(f"下载种子失败: {download_link}")
                                    failed_downloaded_count += 1

                            except Exception as e:
                                logger.error(f"下载种子失败: {str(e)}")
                                failed_downloaded_count += 1
                        else:
                            logger.error(f"下载器 {downloader} 未连接或不可用")
                            failed_downloaded_count += 1

                    except Exception as e:
                        logger.error(f"处理第 {i} 条记录时出错: {str(e)}")
                        continue
                # 检查是否达到下载限制，如果是则跳出外层循环
                if self._download_limit > 0 and success_downloaded_count >= self._download_limit:
                    break
                page += 1

            # 发送通知
            if self._enable_notification:
                self.post_message(
                    mtype=NotificationType.Plugin,
                    title="【憨憨保种区-历史任务】",
                    text=f"历史保种任务完成: 成功 {success_downloaded_count}, 失败 {failed_downloaded_count}"
                )

        except Exception as e:
            logger.error(f"下载历史保种任务执行异常: {str(e)}", exc_info=True)
            # 发送异常通知
            if self._enable_notification:
                self.post_message(
                    mtype=NotificationType.Plugin,
                    title="【憨憨保种区-历史任务】",
                    text=f"历史保种任务执行异常，请查看日志了解详情"
                )

        # 任务完成后将history_rescue_enabled设为false（用 init_plugin 保存的完整配置，避免覆盖丢配置）
        config = dict(getattr(self, "_full_config", {}) or {})
        config["history_rescue_enabled"] = False
        self.update_config(config=config)
