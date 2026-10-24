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
    plugin_version = "3.1.3"
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
    # 配额清理目标水位：触发删除后删回到 配额 * DISK_QUOTA_TARGET_RATIO
    DISK_QUOTA_TARGET_RATIO = 0.9
    # 平均上传速度低于此值(B/s)视为无贡献，配额删除时优先移除
    NO_UPLOAD_AVG_SPEED = 1024
    # 单轮每类清理（配额删除/卡死清理）最多删除的种子数
    MAX_REMOVE_PER_RUN = 5
    # 默认达标做种时长(小时) / 默认卡死判定天数
    DEFAULT_REWARD_HOURS = 18
    DEFAULT_STUCK_DAYS = 7
    # 私有属性
    downloader_helper = None
    _scheduler = None
    _enable = False
    _run_once = False
    _cron = None
    _downloader = None
    _seeding_count = None
    _torrent_size = None
    _download_limit = None
    _save_path = None
    _custom_tag = None
    _enable_notification = None
    _notify_on_zero_torrents = None
    _history_rescue_enabled = None
    _user_id = None
    _force_resume = None
    # 退出事件
    _event = threading.Event()
    _max_pages = 5
    _monitor_cron = None
    _reward_tag = None
    _reward_hours = 18
    _disk_quota_gb = None
    _stuck_days = 7
    _min_seeders = None
    _min_downloaders = None
    _max_torrent_size_gb = None
    _completion_ratio_max = None
    _connect_time_max_hours = None
    _free = False
    _auto_delete_enabled = False
    _delete_files = True
    _max_downloading = 3

    def init_plugin(self, config: dict = None):
        try:

            self.downloader_helper = DownloaderHelper()
            # 获取站点信息
            self.site = SiteOper().get_by_domain(self.domain)
            if not self.site:
                self.domain = "hhanclub.top"
                self.site = SiteOper().get_by_domain(self.domain)
                if not self.site:
                    self.domain = "hhan.club"
                    self.site = SiteOper().get_by_domain(self.domain)
                    if not self.site:
                        logger.error(f"憨憨站点未配置，请先在系统配置中添加站点")
                        return

            # 读取配置
            if config:
                logger.debug(f"读取配置：{config}")
                self._enable = config.get("enable", False)
                self._run_once = config.get("run_once", False)
                self._cron = config.get("cron")
                self._downloader = config.get("downloader", None)
                self._seeding_count = config.get("seeding_count", "1-3")
                self._torrent_size = config.get("torrent_size", "")
                self._download_limit = config.get("download_limit", 5)
                self._save_path = config.get("save_path")
                self._custom_tag = config.get("custom_tag")
                self._enable_notification = config.get("enable_notification", False)
                self._notify_on_zero_torrents = config.get("notify_on_zero_torrents", True)
                self._history_rescue_enabled = config.get("history_rescue_enabled", False)
                self._user_id = config.get("user_id", "")
                self._force_resume = config.get("force_resume", False)
                # 抓取页数，默认5页
                try:
                    self._max_pages = max(1, int(config.get("max_pages", 5)))
                except (TypeError, ValueError):
                    self._max_pages = 5
                # 监控任务
                self._monitor_cron = config.get("monitor_cron")
                # 奖励标签与达标时长
                self._reward_tag = config.get("reward_tag")
                self._reward_hours = self._cfg_float(config, "reward_hours", self.DEFAULT_REWARD_HOURS)
                # 配额与卡死清理
                self._disk_quota_gb = self._cfg_float(config, "disk_quota_gb", None)
                self._stuck_days = self._cfg_float(config, "stuck_days", self.DEFAULT_STUCK_DAYS)
                self._auto_delete_enabled = config.get("auto_delete_enabled", False)
                self._delete_files = config.get("delete_files", True)
                # 详情页精筛条件
                self._min_seeders = self._cfg_int(config, "min_seeders", None)
                self._min_downloaders = self._cfg_int(config, "min_downloaders", None)
                self._max_torrent_size_gb = self._cfg_float(config, "max_torrent_size_gb", None)
                self._completion_ratio_max = self._cfg_float(config, "completion_ratio_max", None)
                self._connect_time_max_hours = self._cfg_float(config, "connect_time_max_hours", None)
                self._max_downloading = self._cfg_int(config, "max_downloading", 3)
            # 停止现有任务
            self.stop_service()

            # 检查是否需要立即运行一次性任务
            need_run_once = self._run_once or (self._history_rescue_enabled and self._user_id)

            if need_run_once:
                # 更新配置，将run_once和history_rescue_enabled设为false
                updated = False
                if self._run_once:
                    config.update({"run_once": False})
                    updated = True
                if self._history_rescue_enabled:
                    config.update({"history_rescue_enabled": False})
                    updated = True

                if updated:
                    self.update_config(config=config)

                self._scheduler = BackgroundScheduler(timezone=settings.TZ)

                # 添加普通保种任务
                if self._run_once:
                    self._run_once = False
                    logger.info("立即运行拯救憨憨保种区")
                    self._scheduler.add_job(self._check_seeding, 'date',
                                            run_date=datetime.datetime.now(
                                                tz=pytz.timezone(settings.TZ)
                                            ) + datetime.timedelta(seconds=3),
                                            name="拯救憨憨保种区")

                # 添加历史保种任务
                if self._history_rescue_enabled and self._user_id:
                    self._history_rescue_enabled = False
                    logger.info(f"立即运行历史保种任务，用户ID: {self._user_id}")
                    self._scheduler.add_job(self._check_history_seeding, 'date',
                                            run_date=datetime.datetime.now(
                                                tz=pytz.timezone(settings.TZ)
                                            ) + datetime.timedelta(seconds=3),
                                            name="拯救憨憨保种区历史任务")

                if self._scheduler.get_jobs():
                    # 启动服务
                    self._scheduler.print_jobs()
                    self._scheduler.start()
        except Exception as e:
            logger.error(f"初始化失败：{str(e)}", exc_info=True)

    def get_form(self) -> Tuple[Optional[List[dict]], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
        return None, {
            "enable": self._enable,
            "run_once": self._run_once,
            "history_rescue_enabled": self._history_rescue_enabled,
            "cron": self._cron,
            "monitor_cron": self._monitor_cron,
            "downloader": self._downloader,
            "seeding_count": self._seeding_count,
            "torrent_size": self._torrent_size,
            "download_limit": self._download_limit,
            "max_downloading": self._max_downloading,
            "max_pages": self._max_pages,
            "min_seeders": self._min_seeders,
            "min_downloaders": self._min_downloaders,
            "max_torrent_size_gb": self._max_torrent_size_gb,
            "completion_ratio_max": self._completion_ratio_max,
            "connect_time_max_hours": self._connect_time_max_hours,
            "free": self._free,
            "all_downloaders": self._all_downloaders,
            "save_path": self._save_path,
            "custom_tag": self._custom_tag,
            "reward_tag": self._reward_tag,
            "reward_hours": self._reward_hours,
            "enable_notification": self._enable_notification,
            "notify_on_zero_torrents": self._notify_on_zero_torrents,
            "user_id": self._user_id,
            "force_resume": self._force_resume,
            "auto_delete_enabled": self._auto_delete_enabled,
            "delete_files": self._delete_files,
            "disk_quota_gb": self._disk_quota_gb,
            "stuck_days": self._stuck_days
        }

    def load_config(self, config: dict):
        """加载配置"""
        if config:
            # 遍历配置中的键并设置相应的属性
            for key in (
                    "enable",
                    "run_once",
                    "history_rescue_enabled",
                    "cron",
                    "monitor_cron",
                    "downloader",
                    "save_path",
                    "custom_tag",
                    "reward_tag",
                    "reward_hours",
                    "enable_notification",
                    "notify_on_zero_torrents",
                    "force_resume",
                    "user_id",
                    "auto_delete_enabled",
                    "delete_files",
                    "disk_quota_gb",
                    "stuck_days",
                    "seeding_count",
                    "torrent_size",
                    "download_limit",
                    "max_downloading",
                    "max_pages",
                    "min_seeders",
                    "min_downloaders",
                    "max_torrent_size_gb",
                    "completion_ratio_max",
                    "connect_time_max_hours",
                    "free"
                ):
                setattr(self, f"_{key}", config.get(key, getattr(self, f"_{key}")))


    @staticmethod
    def _cfg_float(config: dict, key: str, default=None):
        """读取 float 配置，空值/非法值回退 default"""
        try:
            value = config.get(key)
            return float(value) if value not in (None, "") else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _cfg_int(config: dict, key: str, default=None):
        """读取 int 配置，空值/非法值回退 default"""
        try:
            value = config.get(key)
            return int(float(value)) if value not in (None, "") else default
        except (TypeError, ValueError):
            return default
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
            "enable": self._enable,
            "run_once": self._run_once,
            "history_rescue_enabled": self._history_rescue_enabled,
            "cron": self._cron,
            "monitor_cron": self._monitor_cron,
            "downloader": self._downloader,
            "seeding_count": self._seeding_count,
            "torrent_size": self._torrent_size,
            "download_limit": self._download_limit,
            "max_downloading": self._max_downloading,
            "max_pages": self._max_pages,
            "min_seeders": self._min_seeders,
            "min_downloaders": self._min_downloaders,
            "max_torrent_size_gb": self._max_torrent_size_gb,
            "completion_ratio_max": self._completion_ratio_max,
            "connect_time_max_hours": self._connect_time_max_hours,
            "free": self._free,
            "all_downloaders": self._all_downloaders,
            "save_path": self._save_path,
            "custom_tag": self._custom_tag,
            "reward_tag": self._reward_tag,
            "reward_hours": self._reward_hours,
            "enable_notification": self._enable_notification,
            "notify_on_zero_torrents": self._notify_on_zero_torrents,
            "user_id": self._user_id,
            "force_resume": self._force_resume,
            "auto_delete_enabled": self._auto_delete_enabled,
            "delete_files": self._delete_files,
            "disk_quota_gb": self._disk_quota_gb,
            "stuck_days": self._stuck_days
        })


    def _get_download_records(self) -> Response:
        """API Endpoint: Returns download records with auto-delete switch state."""
        records = self.get_data("download_records") or []
        records.reverse()
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
            downloaded_count = 0
            success_downloaded_count = 0
            failed_downloaded_count = 0
            # 先获取现有的下载记录列表
            download_records = self.get_data("download_records") or []
            for page in range(0, self._max_pages):
                if self._event.is_set():
                    logger.info("检测到停止事件，终止本轮页面下载")
                    break
                url = "https://" + self.domain + f"/rescue.php?page={page}"
                logger.info(f"憨憨保种区第{page + 1}页:{url}")
                torrent_detail_source = self._get_page_source(url=url, site=self.site)
                if not torrent_detail_source:
                    logger.error(f"请求憨憨保种区第{page}页失败")
                    break
                # logger.debug(f"憨憨保种区第{page + 1}页详情：" +torrent_detail_source)
                html = etree.HTML(torrent_detail_source)
                if html is None:
                    logger.error(f"憨憨保种区第{page}页页面解析失败")
                    break
                elements = html.xpath('//*[@id="mainContent"]/div[1]/div[2]/div[3]/div')
                logger.info(f"第{page + 1}页数据获取{len(elements)}条数据")
                if len(elements) == 0:
                    break
                for elem in elements:
                    try:
                        # 列表页预筛：提取字段并按条件过滤（免费/做种/下载/大小/完成率/发布时间）
                        record = self._prefilter_row(elem)
                        if record is None:
                            continue
                        # 检查下载数量限制
                        if self._download_limit > 0 and downloaded_count >= self._download_limit:
                            logger.info(f"已达到单次下载数量限制 ({self._download_limit})，停止下载")
                            break
                        download_element = elem.xpath('div[4]/div/a')
                        if download_element:
                            # 下载链接
                            download_link = "https://" + self.domain + "/" + download_element[0].get('href')
                            if download_link:
                                logger.info(f"下载种子链接: {download_link}")
                                # 未完成种子数上限检查（max_downloading）
                                if self._max_downloading:
                                    try:
                                        svc = self.downloader_helper.get_service(self._downloader)
                                        unfinished = 0
                                        if svc and svc.instance:
                                            for t in (svc.instance.get_torrents(tags=self._custom_tag) or []):
                                                try:
                                                    p = t.get("progress")
                                                except Exception:
                                                    p = getattr(t, "percent_done", None)
                                                if p is not None and float(p) < 1:
                                                    unfinished += 1
                                        if unfinished >= int(self._max_downloading):
                                            logger.info(f"下载器未完成种子 {unfinished} 个，已达上限 {self._max_downloading}，停止本轮页面下载")
                                            break
                                    except Exception as e:
                                        logger.warning(f"检查未完成种子数失败: {str(e)}")
                                # 先下载种子文件获取hash
                                torrent_content, torrent_hash = self._download_torrent(download_link, self.site)
                                if not torrent_content:
                                    logger.error(f"下载种子文件失败: {download_link}")
                                    failed_downloaded_count += 1
                                    continue

                                # 调用下载器下载种子
                                downloader = self._downloader
                                service_info = self.downloader_helper.get_service(downloader)
                                if service_info and service_info.instance:
                                    try:
                                        logger.debug(f"获取下载器实例成功: {downloader}")
                                        # 准备下载参数
                                        download_kwargs = {
                                            "content": torrent_content,  # 使用下载的种子内容而不是URL
                                            "cookie": self.site.cookie
                                        }
                                        if self._save_path:
                                            download_kwargs["download_dir"] = self._save_path
                                        # 如果有自定义标签，则添加标签参数
                                        if self._custom_tag:
                                            if service_info.type == "qbittorrent":
                                                download_kwargs["tag"] = self._custom_tag.split(',')
                                            elif service_info.type == "transmission":
                                                download_kwargs["labels"] = self._custom_tag.split(',')
                                        logger.debug(f"下载种子参数: {download_kwargs}")
                                        # 下载种子文件
                                        result = service_info.instance.add_torrent(**download_kwargs)
                                        logger.debug(f"下载结果: {result}")
                                        if result:
                                            logger.info(f"成功下载种子: {download_link}")
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
                                            # 获取种子信息
                                            title_text = record["title"]
                                            zh_title_text = record["zh_title"]
                                            size_text = record["size"]
                                            seed_count = record["seeders"]
                                            # 保存下载记录
                                            download_record = {
                                                "title": title_text,
                                                "zh_title": zh_title_text,
                                                "size": size_text,
                                                "seeders": seed_count,
                                                "download_link": download_link,
                                                "torrent_hash": torrent_hash,  # 使用下载时计算的种子hash
                                                "download_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                            }

                                            # 使用self.save_data保存数据，以列表形式保存所有下载记录
                                            # 将新记录添加到列表中
                                            download_records.append(download_record)
                                            # 保存更新后的列表
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
                        logger.error(f"处理种子时出错: {str(e)}\n{traceback.format_exc()}")
                        continue

            # 发送通知
            # 发送通知（获取任务：有收获 / 全部失败 / 空白轮）
            if self._enable_notification:
                if success_downloaded_count > 0:
                    text = f"本轮成功拯救 {success_downloaded_count} 个种子"
                    if failed_downloaded_count > 0:
                        text += f"，失败 {failed_downloaded_count} 个"
                    self.post_message(
                        mtype=NotificationType.Plugin,
                        title="【憨憨保种区获取】",
                        text=text
                    )
                elif failed_downloaded_count > 0:
                    self.post_message(
                        mtype=NotificationType.Plugin,
                        title="【憨憨保种区获取】",
                        text=f"本轮下载全部失败（{failed_downloaded_count} 个），请检查站点与下载器状态"
                    )
                elif self._notify_on_zero_torrents:
                    self.post_message(
                        mtype=NotificationType.Plugin,
                        title="【憨憨保种区获取】",
                        text="本轮未找到符合条件的新种子"
                    )
        except Exception as e:
            logger.error(f"检查保种区异常: {str(e)}\n{traceback.format_exc()}")
            # 发送异常通知
            if self._enable_notification:
                self.post_message(
                    mtype=NotificationType.Plugin,
                    title="【憨憨保种区获取】",
                    text="保种任务执行异常，请查看日志了解详情"
                )

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
            logger.error(f"下载种子失败: {url}")
            return None, None

    def _delete_torrent_by_hash(self, torrent_hash: str) -> bool:
        """
        根据hash删除下载器中的种子
        """
        if not self._downloader:
            logger.error("未配置下载器")
            return False

        service_info = self.downloader_helper.get_service(self._downloader)
        if not service_info or not service_info.instance:
            logger.error(f"下载器 {self._downloader} 未连接或不可用")
            return False

        try:
            # 圈定复核：仅允许删除带本插件标签的种子（防止 API 绕过标签承诺误删用户种子）
            guard = service_info.instance.get_torrents(ids=torrent_hash, tags=self._custom_tag)
            if not guard:
                logger.warning(f"种子 {torrent_hash} 不带标签 {self._custom_tag}，拒绝删除")
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
                torrents = info.instance.get_torrents(tags=self._custom_tag) or []
                stats = []
                for t in torrents:
                    s = self._get_torrent_stats(t)
                    if s:
                        stats.append((t, s))
                logger.info(f"下载器 {name} 圈定种子 {len(stats)} 个（标签 {self._custom_tag}）")

                # ① 达标打标：做种满 reward_hours 小时且下载完成
                for _, s in stats:
                    if s["seeding_hours"] >= self._reward_hours and reward_tag not in s["tags"]:
                        if self._add_torrent_tag(info, s["hash"], reward_tag):
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
                "progress": float(progress),
                "seeding_hours": float(active_seconds) / 3600.0,
                "added_days": added_days,
                "tags": [str(x) for x in tags],
                "state": str(val("state", "status") or "")
            }
        except Exception as e:
            logger.warning(f"解析种子状态失败: {str(e)}")
            return None

    def _add_torrent_tag(self, service_info, torrent_hash: str, tag: str) -> bool:
        """为种子添加标签（qb 支持标签；tr 尝试 labels，失败仅记日志）"""
        if not torrent_hash or not tag:
            return False
        try:
            if service_info.type == "qbittorrent":
                service_info.instance.torrents_add_tags(ids=torrent_hash, tags=tag)
                return True
            elif service_info.type == "transmission":
                # tr 的标签接口按 MP 统一实例尽力而为
                service_info.instance.add_torrent_tag(ids=torrent_hash, tags=tag)
                return True
            else:
                logger.warning(f"不支持的下载器类型，无法打标: {service_info.type}")
                return False
        except Exception as e:
            logger.warning(f"添加标签失败 (hash: {torrent_hash}, tag: {tag}): {str(e)}")
            return False

    def _prefilter_row(self, elem) -> dict | None:
        """
        列表页预筛：从保种区行元素提取字段并按配置过滤。
        免费标签、做种/下载/完成人数、大小、发布精确时间均可从列表页直接获取，
        无需打开详情页。未配置的条件不判定；字段解析失败的条件自动放行（fail-open）；
        做种人数解析失败视为无效行。返回字段 dict 供下载段使用，None 表示该行被过滤。
        """
        def _num(nodes):
            if not nodes:
                return None
            try:
                return int(nodes[0].text.strip())
            except (ValueError, AttributeError, IndexError):
                return None

        seeders_count = _num(elem.xpath('div[3]/div/div[3]/a'))
        if seeders_count is None:
            logger.warning("未找到做种人数或格式错误，跳过该种子")
            return None

        # 做种人数区间（seeding_count 支持 "3-8" 或单值上限）
        seeding_count_str = str(self._seeding_count or "").strip()
        if seeding_count_str:
            try:
                if '-' in seeding_count_str:
                    lower_bound, upper_bound = (int(x) for x in seeding_count_str.split('-', 1))
                    if not (lower_bound <= seeders_count <= upper_bound):
                        return None
                elif seeders_count > int(seeding_count_str):
                    return None
            except ValueError:
                logger.error(f"无效的做种人数格式: {seeding_count_str}")
                return None

        title_nodes = elem.xpath('div[2]/div/a')
        zh_title_nodes = elem.xpath('div[2]/div/div[1]/div')
        size_nodes = elem.xpath('div[3]/div/div[1]')
        size_text = size_nodes[0].text.strip() if size_nodes and size_nodes[0].text else None
        added_titles = elem.xpath('div[3]/div/div[2]/span/@title')
        leechers = _num(elem.xpath('div[3]/div/div[4]/a'))
        finished = _num(elem.xpath('div[3]/div/div[5]/a'))
        free_tags = elem.xpath('div[2]/div/div[2]/div[contains(., "免费")]')

        title_text = title_nodes[0].text.strip() if title_nodes and title_nodes[0].text else "未知标题"
        zh_title_text = zh_title_nodes[0].text.strip() if zh_title_nodes and zh_title_nodes[0].text else "无中文标题"

        def _skip(reason):
            logger.info(f"预筛: {reason}，跳过 {title_text}")
            return None

        # 仅下载免费种子
        if self._free and not free_tags:
            return _skip("非免费种子")
        # 做种人数下限
        if self._min_seeders and seeders_count < int(self._min_seeders):
            return _skip(f"做种 {seeders_count} < {self._min_seeders}")
        # 下载人数下限（解析失败放行）
        if self._min_downloaders and leechers is not None and leechers < int(self._min_downloaders):
            return _skip(f"下载 {leechers} < {self._min_downloaders}")
        # 种子大小范围（torrent_size 支持 "1-5" 或单值上限）
        if size_text and self._torrent_size:
            size_gb = self._parse_size_to_gb(size_text)
            if size_gb is not None:
                torrent_size_str = str(self._torrent_size).strip()
                try:
                    if '-' in torrent_size_str:
                        lower_bound, upper_bound = (float(x) for x in torrent_size_str.split('-', 1))
                        if not (lower_bound <= size_gb <= upper_bound):
                            return _skip(f"大小 {size_gb:.2f}GB 不在 {torrent_size_str}GB 内")
                    elif size_gb > float(torrent_size_str):
                        return _skip(f"大小 {size_gb:.2f}GB > {torrent_size_str}GB")
                except ValueError:
                    logger.error(f"无效的种子大小格式: {torrent_size_str}")
                    return None
            else:
                logger.warning(f"无法解析种子大小: {size_text}，跳过大小检查")
        # 完成率上限（完成数/(完成数+下载数)，两者都解析到才判定）
        if self._completion_ratio_max and finished is not None and leechers is not None:
            ratio = finished / max(finished + leechers, 1)
            if ratio * 100 > float(self._completion_ratio_max):
                return _skip(f"完成率 {ratio * 100:.1f}% > {self._completion_ratio_max}%")
        # 发布时间上限（列表页精确时间，发布距今小时数；解析失败放行）
        if self._connect_time_max_hours and added_titles:
            try:
                published = datetime.datetime.strptime(added_titles[0].strip(), "%Y-%m-%d %H:%M:%S")
                hours = (datetime.datetime.now() - published).total_seconds() / 3600.0
                if hours > float(self._connect_time_max_hours):
                    return _skip(f"发布 {hours:.1f}h > {self._connect_time_max_hours}h")
            except ValueError:
                logger.debug(f"发布时间解析失败，放行: {added_titles[0]}")

        return {
            "title": title_text,
            "zh_title": zh_title_text,
            "size": size_text or "未知大小",
            "seeders": str(seeders_count),
        }

    def get_page(self) -> List[dict]:
        return None

    def stop_service(self):
        """
        停止服务
        """
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._event.set()
                    self._scheduler.shutdown()
                    self._event.clear()
                self._scheduler = None
        except Exception as e:
            print(str(e))

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
                        seeding_count_str = str(self._seeding_count)
                        is_in_range = False

                        if '-' in seeding_count_str:
                            # 范围格式，如 1-3
                            range_parts = seeding_count_str.split('-')
                            if len(range_parts) == 2:
                                try:
                                    lower_bound = int(range_parts[0])
                                    upper_bound = int(range_parts[1])
                                    if lower_bound <= seeders <= upper_bound:
                                        is_in_range = True
                                except ValueError:
                                    logger.error(f"无效的范围格式: {seeding_count_str}")
                                    continue
                        else:
                            # 单个数字格式，检查做种人数是否小于该数字
                            try:
                                if seeders <= int(seeding_count_str):
                                    is_in_range = True
                            except ValueError:
                                logger.error(f"无效的数字格式: {seeding_count_str}")
                                continue

                        if not is_in_range:
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
                        logger.info(f"开始下载种子: {download_link}")

                        # 下载种子文件
                        torrent_content, torrent_hash = self._download_torrent(download_link, self.site)
                        if not torrent_content:
                            logger.error(f"下载种子文件失败: {download_link}")
                            failed_downloaded_count += 1
                            continue

                        # 调用下载器下载种子
                        downloader = self._downloader
                        service_info = self.downloader_helper.get_service(downloader)
                        if service_info and service_info.instance:
                            try:
                                logger.debug(f"获取下载器实例成功: {downloader}")
                                # 准备下载参数
                                download_kwargs = {
                                    "content": torrent_content,  # 使用下载的种子内容而不是URL
                                    "cookie": self.site.cookie
                                }
                                if self._save_path:
                                    download_kwargs["download_dir"] = self._save_path
                                # 如果有自定义标签，则添加标签参数
                                if self._custom_tag:
                                    if service_info.type == "qbittorrent":
                                        download_kwargs["tag"] = self._custom_tag.split(',')
                                    elif service_info.type == "transmission":
                                        download_kwargs["labels"] = self._custom_tag.split(',')
                                logger.debug(f"下载种子参数: {download_kwargs}")
                                # 下载种子文件
                                result = service_info.instance.add_torrent(**download_kwargs)
                                logger.debug(f"下载结果: {result}")
                                if result:
                                    logger.info(f"成功下载种子: {download_link}")
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
                                    # 保存更新后的列表
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

        # 任务完成后将history_rescue_enabled设为false
        config = self.get_data("config") or {}
        config["history_rescue_enabled"] = False
        self.update_config(config=config)
