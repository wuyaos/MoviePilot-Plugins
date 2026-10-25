import re
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
    plugin_version = "3.2.2"
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
            self._user_id = None
            if self._history_rescue_enabled:
                self._user_id = self._resolve_user_id()
                if not self._user_id:
                    logger.warning("无法解析当前憨憨站用户 UID，跳过历史保种任务")
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
        try:
            if self._downloader and self._custom_tag:
                svc = self.downloader_helper.get_service(self._downloader)
                if svc and svc.instance:
                    reward_tag = self._reward_tag or ""
                    for t in self._get_scoped_torrents(self._downloader):
                        s = self._get_torrent_stats(t)
                        if not s or not s.get("hash"):
                            continue
                        if s["progress"] < 1:
                            status = "下载中"
                        elif reward_tag and reward_tag in s["tags"]:
                            status = "已达标"
                        else:
                            status = "做种中"
                        live[s["hash"].lower()] = {
                            "status": status,
                            "uploaded": s["uploaded"],
                            "seeding_time_hours": s["seeding_hours"],
                        }
                    aggregated = True
        except Exception as e:
            logger.warning(f"聚合下载器实时状态失败: {str(e)}")
        if aggregated:
            for r in records:
                info = live.get(str(r.get("torrent_hash") or "").lower())
                if info:
                    r.update(info)
                else:
                    # 下载器中已不存在该 hash（被删除或标签不符）
                    r["status"] = "已删除"
                    r["uploaded"] = 0
                    r["seeding_time_hours"] = 0
        return Response(success=True, data={
            "records": records,
            "auto_delete_enabled": bool(self._auto_delete_enabled),
            "disk_quota_gb": self._disk_quota_gb
        })

    @property
    def service_infos(self) -> Optional[Dict[str, ServiceInfo]]:
        """
        服务信息
        """
        if not self._downloader:
            logger.warning("尚未配置下载器，请检查配置")
            return None

        services = self.downloader_helper.get_services(name_filters=self._downloader)
        if not services:
            logger.warning("获取下载器实例失败，请检查配置")
            return None

        active_services = {}
        for service_name, service_info in services.items():
            if service_info.instance.is_inactive():
                logger.warning(f"下载器 {service_name} 未连接，请检查配置")
            else:
                active_services[service_name] = service_info

        if not active_services:
            logger.warning("没有已连接的下载器，请检查配置")
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
    def _check_seeding(self):
        try:
            if not self._enable:
                logger.info("憨憨保种区插件未启用，跳过检查")
                return
            if not self._downloader:
                logger.error("未配置下载器，无法执行保种任务")
                return
            records = self.get_data("download_records") or []
            candidates = []
            budget = {"used": 0, "limit": self.DETAIL_REQUEST_BUDGET}
            downloaded_count = 0
            success_count = 0
            failed_count = 0
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
                        record = self._prefilter_row(elem)
                        if record is not None:
                            candidates.append(record)
                    except Exception as exc:
                        logger.error(f"处理列表种子时出错: {exc}")
                if self._event.is_set():
                    break
            if not candidates:
                logger.debug("本轮无粗筛候选")
            refined = self._refine_by_detail(candidates, budget)
            for record in refined:
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
                link = record.get("download_link")
                if not link:
                    failed_count += 1
                    continue
                content, torrent_hash = self._download_torrent(link, self.site)
                if not content:
                    failed_count += 1
                    continue
                service_info = self.downloader_helper.get_service(self._downloader)
                if not service_info or not service_info.instance:
                    logger.error(f"下载器 {self._downloader} 未连接或不可用")
                    failed_count += 1
                    continue
                try:
                    kwargs = {"content": content, "cookie": self.site.cookie}
                    if self._save_path:
                        kwargs["download_dir"] = self._save_path
                    logger.debug(f"下载种子参数键: {sorted(kwargs.keys())}")
                    result = service_info.instance.add_torrent(**kwargs)
                    if not result:
                        failed_count += 1
                        logger.error("下载种子失败")
                        continue
                    downloaded_count += 1
                    success_count += 1
                    if self._custom_tag and torrent_hash:
                        self._add_torrent_tag(service_info, torrent_hash, self._custom_tag)
                    if self._force_resume and service_info.type == "qbittorrent" and torrent_hash:
                        service_info.instance.torrents_set_force_start(ids=torrent_hash)
                    records.append({
                        "title": record["title"], "zh_title": record["zh_title"],
                        "size": record["size"], "seeders": record["seeders"],
                        "download_link": link, "torrent_hash": torrent_hash,
                        "download_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    })
                    self.save_data(key="download_records", value=records[-500:])
                except Exception as exc:
                    failed_count += 1
                    logger.error(f"下载种子失败: {exc}")
            if self._enable_notification:
                if success_count:
                    text = f"本轮成功拯救 {success_count} 个种子"
                    if failed_count:
                        text += f"，失败 {failed_count} 个"
                    self.post_message(mtype=NotificationType.Plugin, title="【憨憨保种区获取】", text=text)
                elif failed_count:
                    self.post_message(mtype=NotificationType.Plugin, title="【憨憨保种区获取】", text=f"本轮下载全部失败（{failed_count} 个），请检查站点与下载器状态")
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
                        if self._connect_time_max_hours is not None:
                            raw_connected = peer.get("connected") if isinstance(peer, dict) else None
                            match = re.fullmatch(r"(?:(\d+)天)?(\d+):(\d+):(\d+)", str(raw_connected or "").strip())
                            if not match:
                                logger.debug("下载者连接时间解析失败: id=%s", candidate.get("torrent_id"))
                                result = ("unknown", None)
                                break
                            hours = int(match.group(1) or 0) * 24 + int(match.group(2)) + int(match.group(3)) / 60 + int(match.group(4)) / 3600
                            if hours >= self._connect_time_max_hours:
                                bad = True
                    else:
                        result = ("reject" if bad else "pass", None)
                    if result and result[0] == "unknown":
                        break
                except Exception as exc:
                    logger.debug("详情精筛请求失败 id=%s attempt=%s: %s", candidate.get("torrent_id"), attempt + 1, exc)
                    if attempt == 2:
                        result = ("unknown", None)
            if not result or result[0] == "unknown":
                unknown_ids.append(str(candidate.get("torrent_id")))
            elif result[0] == "pass":
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
            guard = service_info.instance.get_torrents(ids=torrent_hash, tags=self._custom_tag) or []
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


    def _maintenance(self):
        """
        种子监控任务：达标打标 → 配额删除 → 卡死清理
        仅依赖下载器状态，不访问保种区站点
        """
        try:
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
                torrents = [t for t in info.instance.get_torrents(tags=self._custom_tag) or []
                            if self._torrent_has_managed_tag(t)]
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
        for torrent in service.instance.get_torrents(tags=self._custom_tag) or []:
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
            progress = val("progress", "percent_done") or 0
            added = val("added_on", "date_added")
            tags = val("tags", "labels") or []
            if isinstance(tags, str):
                tags = [x.strip() for x in tags.split(",") if x.strip()]
            # 进度归一到 0-1：qb progress 为 0-1，transmission-rpc progress 为 0-100
            try:
                progress = float(progress)
            except (TypeError, ValueError):
                progress = 0.0
            if progress > 1:
                progress = progress / 100.0
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
                "seeding_hours": float(active_seconds) / 3600.0,
                "added_days": added_days,
                "tags": [str(x) for x in tags],
                "state": str(val("state", "status") or "")
            }
        except Exception as e:
            logger.warning(f"解析种子状态失败: {str(e)}")
            return None

    def _add_torrent_tag(self, service_info, torrent_hash: str, tag: str, org_tags: list = None) -> bool:
        """qb/tr 统一使用 MP set_torrent_tag，并保留原标签。"""
        if not torrent_hash or not tag:
            return False
        try:
            service_info.instance.set_torrent_tag(
                ids=[torrent_hash], tags=[tag], org_tags=list(org_tags or []))
            return True
        except Exception as e:
            logger.warning(f"添加标签失败 (hash: {torrent_hash}, tag: {tag}): {str(e)}")
            return False

    def _prefilter_row(self, elem) -> dict | None:
        """List-only coarse filter. Peer thresholds are handled by _refine_by_detail."""
        def text_num(nodes):
            if not nodes or nodes[0].text is None:
                return None
            try:
                return int(nodes[0].text.strip())
            except (ValueError, AttributeError):
                return None
        seeders = text_num(elem.xpath("div[3]/div/div[3]/a"))
        if seeders is None:
            logger.warning("未找到做种人数或格式错误，跳过该种子")
            return None
        seeding = str(self._seeding_count or "").strip()
        if seeding and not self._value_in_specs(seeders, seeding):
            return None
        free_tags = elem.xpath('div[2]/div/div[2]/div[contains(., "免费")]')
        if self._free and not free_tags:
            return None
        leechers = text_num(elem.xpath("div[3]/div/div[4]/a"))
        if self._min_downloaders is not None and leechers is not None and leechers < self._min_downloaders:
            return None
        if self._min_downloaders is not None and leechers is None and self._completion_ratio_max is None and self._connect_time_max_hours is None:
            logger.debug("列表下载数未知且未启用详情精筛，跳过")
            return None
        size_nodes = elem.xpath("div[3]/div/div[1]")
        size_text = size_nodes[0].text.strip() if size_nodes and size_nodes[0].text else None
        if self._torrent_size and size_text:
            size_gb = self._parse_size_to_gb(size_text)
            if size_gb is not None and not self._value_in_specs(size_gb, str(self._torrent_size), numeric=True):
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
                                            logger.info(f"获取到passkey: {passkey[:8]}...")
                                        else:
                                            logger.warning("无法从详情页获取passkey")
                                    else:
                                        logger.warning("在详情页未找到下载链接")
                                else:
                                    logger.warning("种子详情页解析失败")
                            else:
                                logger.warning("访问种子详情页失败")

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
                                logger.debug(f"下载种子参数键: {sorted(download_kwargs.keys())}")
                                # 下载种子文件
                                result = service_info.instance.add_torrent(**download_kwargs)
                                logger.debug(f"下载结果: {result}")
                                if result:
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
                                    # 保存更新后的列表（上限 500 条，裁最旧）
                                    download_records = download_records[-500:]
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
