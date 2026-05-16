# input: checker.py, helper.py, config.py, entities.py
# output: PtHitAndRun 插件类（注册到 MoviePilot；事件监听 + 定时服务 + 配置表单 + 详情页）
# pos: 插件入口，组装各子模块并暴露 _PluginBase 接口
"""PtHitAndRun — PT 站 H&R 种子自动管理助手（魔改版）。"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import pytz
from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.core.context import Context, TorrentInfo
from app.core.event import Event, eventmanager
from app.helper.downloader import DownloaderHelper
from app.helper.sites import SitesHelper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import NotificationType, ServiceInfo
from app.schemas.types import EventType

from app.plugins.pthitandrun.checker import HNRChecker
from app.plugins.pthitandrun.config import HNRConfig, NotifyMode
from app.plugins.pthitandrun.entities import HNRStatus, TaskType, TorrentHistory, TorrentTask
from app.plugins.pthitandrun.helper import TorrentHelper

LOG_PREFIX = "【PtH&R】"


class PtHitAndRun(_PluginBase):
    plugin_name = "H&R助手Pro"
    plugin_desc = "PT站H&R种子自动标签管理，支持多条件OR判定、按大小分级、自动发现。"
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/hitandrun.png"
    plugin_version = "1.1.0"
    plugin_author = "wuyaos"
    author_url = "https://github.com/wuyaos"
    plugin_config_prefix = "pthitandrun_"
    plugin_order = 24
    auth_level = 2

    def __init__(self):
        super().__init__()
        self._cfg: Optional[HNRConfig] = None
        self._checker: Optional[HNRChecker] = None
        self._helpers: Dict[str, TorrentHelper] = {}  # downloader_name -> TorrentHelper
        self._scheduler: Optional[BackgroundScheduler] = None
        self._event = threading.Event()
        self._downloader_helper = DownloaderHelper()
        self._sites_helper = SitesHelper()

    # ---- 初始化 ----

    def init_plugin(self, config: dict = None):
        self.stop_service()
        if not config:
            return
        try:
            self._cfg = HNRConfig(**config)
        except Exception as e:
            logger.error(f"{LOG_PREFIX}配置解析失败: {e}")
            return

        downloaders = self._get_downloaders()
        if not downloaders:
            return
        self._helpers = downloaders
        self._checker = HNRChecker(
            config=self._cfg, helpers=self._helpers,
            get_data=self.get_data, save_data=self.save_data,
            send_message=self._send_message,
        )
        if self._cfg.onlyonce:
            self._cfg.onlyonce = False
            self._update_config()
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            self._scheduler.add_job(self._checker.full_scan, "date",
                                    run_date=datetime.now(pytz.timezone(settings.TZ)) + timedelta(seconds=3),
                                    name="H&R全量扫描")
            self._scheduler.start()

    # ---- 下载器 ----

    def _get_downloaders(self) -> Dict[str, TorrentHelper]:
        """获取所有已配置的可用下载器，返回 {name: TorrentHelper}。"""
        if not self._cfg or not self._cfg.downloader:
            return {}
        helpers: Dict[str, TorrentHelper] = {}
        for name in self._cfg.downloader:
            svc = self._downloader_helper.get_service(name=name, type_filter="qbittorrent")
            if svc and not svc.instance.is_inactive():
                helpers[name] = TorrentHelper(svc.instance)
            else:
                logger.warning(f"{LOG_PREFIX}下载器 {name} 不可用")
        return helpers

    # ---- 事件监听 ----

    @eventmanager.register(EventType.DownloadAdded)
    def on_download_added(self, event: Event = None):
        if not self._cfg or not self._cfg.enabled or not self._checker:
            return
        if not event or not event.event_data:
            return
        downloader = event.event_data.get("downloader")
        if not downloader or (self._cfg.downloader and downloader not in self._cfg.downloader):
            return
        torrent_hash = event.event_data.get("hash")
        context: Context = event.event_data.get("context")
        if not torrent_hash or not context or not context.torrent_info:
            return
        ti = context.torrent_info
        task_type = TaskType.NORMAL if ti.description else TaskType.RSS_SUBSCRIBE
        logger.info(f"{LOG_PREFIX}下载事件: {ti.title} [{task_type.to_chinese()}] @ {downloader}")
        self._process_new_torrent(torrent_hash, ti, task_type, downloader_name=downloader)

    @eventmanager.register(EventType.PluginTriggered)
    def on_brush_download(self, event: Event = None):
        if not self._cfg or not self._cfg.enabled or not self._checker:
            return
        if not event or not event.event_data:
            return
        if event.event_data.get("event_name") != "brushflow_download_added":
            return
        downloader = event.event_data.get("downloader")
        if not downloader or (self._cfg.downloader and downloader not in self._cfg.downloader):
            return
        torrent_hash = event.event_data.get("hash")
        torrent_data = event.event_data.get("data")
        if not torrent_hash or not torrent_data:
            return
        logger.info(f"{LOG_PREFIX}刷流事件: {torrent_hash} @ {downloader}")
        self._process_new_torrent(torrent_hash, torrent_data, TaskType.BRUSH, downloader_name=downloader)

    def _process_new_torrent(self, torrent_hash: str, torrent_data: Union[dict, TorrentInfo],
                             task_type: TaskType, downloader_name: str = ""):
        """处理新种子：创建任务、初始化 H&R 参数、打标签、保存。"""
        if not self._helpers or not self._checker:
            return
        th = self._helpers.get(downloader_name) or next(iter(self._helpers.values()), None)
        if not th:
            return
        torrents = th.get_torrents(hashes=torrent_hash)
        if not torrents:
            logger.warning(f"{LOG_PREFIX}下载器中未找到种子 {torrent_hash}")
            return
        torrent = torrents[0]
        site_id, site_name = TorrentHelper.get_site_by_torrent(torrent)
        if site_id not in (self._cfg.sites or []):
            logger.debug(f"{LOG_PREFIX}站点 {site_name} 未启用 H&R，跳过")
            return
        info = th.get_torrent_info(torrent)
        # 从 torrent_data 提取基本信息
        if isinstance(torrent_data, TorrentInfo):
            title = torrent_data.title or info.get("title", "")
            desc = torrent_data.description or ""
            hit_and_run = torrent_data.hit_and_run
            size = torrent_data.size or info.get("total_size", 0)
        else:
            title = torrent_data.get("title") or info.get("title", "")
            desc = torrent_data.get("description", "")
            hit_and_run = torrent_data.get("hit_and_run", False)
            size = torrent_data.get("size") or info.get("total_size", 0)

        task = TorrentTask(
            hash=torrent_hash, site=site_id, site_name=site_name,
            title=title, description=desc, size=size,
            hit_and_run=hit_and_run, task_type=task_type,
            time=info.get("add_on", 0) or time.time(),
            seeding_time=info.get("seeding_time", 0),
            ratio=info.get("ratio", 0),
            uploaded=info.get("uploaded", 0),
            downloaded=info.get("downloaded", 0),
            downloader=downloader_name,
        )
        if not self._checker.init_task(task):
            logger.info(f"{LOG_PREFIX}{site_name}: {task.identifier} 未命中 H&R")
            return

        self._checker.save_task(task)
        logger.info(f"{LOG_PREFIX}{site_name}: {task.identifier} 已纳入 H&R 管理 "
                    f"[做种{task.hr_duration}h/期限{task.hr_deadline_days}天"
                    f"{f'/率{task.hr_ratio}' if task.hr_ratio else ''}"
                    f"{f'/传{task.hr_upload_multiplier}倍' if task.hr_upload_multiplier else ''}]")

    # ---- 服务注册 ----

    def get_service(self) -> List[Dict[str, Any]]:
        if not self._cfg or not self._cfg.enabled:
            return []
        services = [{
            "id": "PtHitAndRunCheck",
            "name": "H&R状态检查",
            "trigger": "interval",
            "func": self._checker.check if self._checker else lambda: None,
            "kwargs": {"minutes": self._cfg.check_period},
        }]
        if self._cfg.auto_discover and self._checker:
            services.append({
                "id": "PtHitAndRunDiscover",
                "name": "H&R自动发现",
                "trigger": "interval",
                "func": self._checker.auto_discover,
                "kwargs": {"minutes": self._cfg.check_period * 2},
            })
        return services

    def get_state(self) -> bool:
        return bool(self._cfg and self._cfg.enabled)

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    # ---- 配置表单 ----

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        dl_opts = [{"title": c.name, "value": c.name}
                   for c in self._downloader_helper.get_configs().values()
                   if c.type == "qbittorrent"]
        site_opts = [{"title": s.get("name"), "value": s.get("id")}
                     for s in self._sites_helper.get_indexers() if s.get("id")]
        notify_opts = [
            {"title": "不发送", "value": "none"},
            {"title": "仅异常", "value": "on_error"},
            {"title": "全部", "value": "always"},
        ]
        return [
            {"component": "VForm", "content": [
                # 开关行
                _row([
                    _col(3, _switch("enabled", "启用插件")),
                    _col(3, _switch("auto_discover", "自动发现")),
                    _col(3, _switch("enable_site_config", "站点独立配置")),
                    _col(3, _switch("onlyonce", "立即运行一次")),
                ]),
                # 下载器 + 站点
                _row([
                    _col(4, _select("downloader", "下载器", dl_opts, multiple=True)),
                    _col(8, _select("sites", "站点列表", site_opts, multiple=True)),
                ]),
                # 参数行
                _row([
                    _col(3, _select("notify", "通知方式", notify_opts)),
                    _col(3, _text("check_period", "扫描间隔(分钟)")),
                    _col(3, _text("hit_and_run_tag", "H&R标签")),
                    _col(3, _text("auto_cleanup_days", "自动清理天数")),
                ]),
                # 全局 H&R 规则
                _row([
                    _col(3, _text("hr_duration", "做种时间(小时)")),
                    _col(3, _text("additional_seed_time", "附加做种时间(小时)")),
                    _col(3, _text("hr_deadline_days", "考核期(天)")),
                    _col(3, _text("hr_ratio", "分享率")),
                ]),
                _row([
                    _col(3, _text("hr_upload_multiplier", "上传倍数")),
                ]),
                # 说明
                _row([
                    _col(12, {"component": "VAlert", "props": {
                        "type": "info", "variant": "tonal", "density": "compact", "class": "mt-1 mb-2",
                    }, "content": [{"component": "div", "props": {"class": "text-body-2"}, "content": [
                        {"component": "div", "props": {"class": "font-weight-medium"}, "text": "配置说明："},
                        {"component": "div", "text": "• 全局规则：上方的做种时间/考核期/分享率/上传倍数为所有站点的默认值"},
                        {"component": "div", "text": "• 站点独立配置：开启后在下方 YAML 中为每个站点设置独立规则，未设置的字段自动继承全局值"},
                        {"component": "div", "text": "• 满足条件（OR 关系）：做种时间达标 / 分享率达标 / 上传量>=种子大小*N倍 / 上传量>=下载量，满足任一即通过"},
                        {"component": "div", "text": "• 自动发现：开启后定时扫描下载器，将直接在下载器中添加的种子也纳入 H&R 管理"},
                        {"component": "div", "text": "• H&R标签：满足前打标签保护种子不被删种插件删除，满足后自动移除标签"},
                    ]}]}),
                ]),
                # 站点配置 YAML
                _row([
                    _col(12, {"component": "VTextarea", "props": {
                        "model": "site_config_str", "label": "站点独立配置 (YAML)",
                        "rows": 10,
                        "placeholder": "- site_name: '站点名'\n  hr_duration: 48\n  hr_deadline_days: 14\n  hr_ratio: 1.0",
                        "hint": "每站一个条目（- 开头），未设置字段继承全局配置。详见 https://github.com/wuyaos/MoviePilot-Plugins/blob/main/plugins.v2/pthitandrun/rule.yaml",
                        "persistent-hint": True,
                    }}),
                ]),
            ]},
        ], {
            "enabled": False, "auto_discover": False,
            "enable_site_config": False, "onlyonce": False,
            "downloader": [], "sites": [], "notify": "always",
            "check_period": 10, "hit_and_run_tag": "H&R",
            "auto_cleanup_days": 15,
            "hr_duration": 48, "hr_deadline_days": 14,
            "additional_seed_time": 24,
            "hr_ratio": "", "hr_upload_multiplier": "",
            "site_config_str": "",
        }

    # ---- 详情页 ----

    def get_page(self) -> List[dict]:
        try:
            return self._build_page()
        except Exception as e:
            logger.error(f"{LOG_PREFIX}详情页构建失败: {e}")
            return [{"component": "VAlert", "props": {
                "type": "error", "variant": "tonal",
                "text": f"详情页加载失败: {e}",
            }}]

    def _build_page(self) -> List[dict]:
        tasks_raw = self.get_data("torrents")
        tasks: Dict[str, TorrentTask] = {}
        if tasks_raw and isinstance(tasks_raw, dict):
            for k, v in tasks_raw.items():
                try:
                    tasks[k] = TorrentTask(**v) if isinstance(v, dict) else TorrentTask.parse_raw(v)
                except Exception:
                    continue

        total = len(tasks)
        in_progress = sum(1 for t in tasks.values() if t.hr_status == HNRStatus.IN_PROGRESS)
        compliant = sum(1 for t in tasks.values() if t.hr_status == HNRStatus.COMPLIANT)
        overdue = sum(1 for t in tasks.values() if t.hr_status == HNRStatus.OVERDUE)

        # 统计卡片
        stat_row = _row([
            _col(3, _stat_card("总任务", str(total), "mdi-format-list-bulleted", "primary")),
            _col(3, _stat_card("进行中", str(in_progress), "mdi-progress-clock", "info")),
            _col(3, _stat_card("已满足", str(compliant), "mdi-check-circle", "success")),
            _col(3, _stat_card("已过期", str(overdue), "mdi-alert-circle", "error")),
        ])

        # 任务列表
        if not tasks:
            table = {"component": "VAlert", "props": {
                "type": "info", "variant": "tonal", "density": "compact",
                "class": "ma-3", "text": "暂无 H&R 任务",
            }}
        else:
            rows = []
            for task in sorted(tasks.values(), key=lambda t: t.time or 0, reverse=True)[:50]:
                status_color = {
                    HNRStatus.IN_PROGRESS: "info", HNRStatus.COMPLIANT: "success",
                    HNRStatus.OVERDUE: "error", HNRStatus.NEEDS_SEEDING: "warning",
                }.get(task.hr_status, "grey")
                remain = task.remain_time()
                remain_str = f"{remain:.1f}h" if remain is not None else "-"
                rows.append({"component": "tr", "content": [
                    {"component": "td", "text": task.site_name or "-"},
                    {"component": "td", "text": (task.title or "-")[:40]},
                    {"component": "td", "text": f"{(task.seeding_time or 0) / 3600:.1f}h"},
                    {"component": "td", "text": f"{task.ratio:.2f}"},
                    {"component": "td", "text": remain_str},
                    {"component": "td", "text": task.formatted_deadline()},
                    {"component": "td", "content": [{"component": "VChip", "props": {
                        "color": status_color, "variant": "tonal", "size": "small",
                    }, "text": task.hr_status.to_chinese() if task.hr_status else "-"}]},
                ]})
            table = {"component": "VTable", "props": {"density": "compact"}, "content": [
                {"component": "thead", "content": [{"component": "tr", "content": [
                    {"component": "th", "text": h} for h in
                    ["站点", "种子", "做种", "分享率", "剩余", "截止", "状态"]
                ]}]},
                {"component": "tbody", "content": rows},
            ]}

        return [stat_row, {"component": "VCard", "props": {
            "variant": "flat", "class": "mb-3",
        }, "content": [
            {"component": "VCardTitle", "props": {"class": "text-subtitle-2 pa-3"}, "text": "H&R 任务列表"},
            table,
        ]}]

    # ---- 辅助 ----

    def _send_message(self, title: str, text: str):
        self.post_message(mtype=NotificationType.SiteMessage, title=title, text=text)

    def _update_config(self):
        if self._cfg:
            excludes = {"site_config_str", "site_infos", "site_configs"}
            self.update_config(self._cfg.to_dict(exclude=excludes))

    def stop_service(self):
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._event.set()
                    self._scheduler.shutdown()
                    self._event.clear()
                self._scheduler = None
        except Exception:
            pass


# ---- UI 工具函数 ----

def _row(cols: list) -> dict:
    return {"component": "VRow", "content": cols}

def _col(n: int, content: dict) -> dict:
    return {"component": "VCol", "props": {"cols": 12, "md": n}, "content": [content]}

def _switch(model: str, label: str) -> dict:
    return {"component": "VSwitch", "props": {"model": model, "label": label}}

def _select(model: str, label: str, items: list, multiple: bool = False) -> dict:
    props: Dict[str, Any] = {"model": model, "label": label, "items": items}
    if multiple:
        props.update({"multiple": True, "chips": True, "clearable": True})
    return {"component": "VSelect", "props": props}

def _text(model: str, label: str) -> dict:
    return {"component": "VTextField", "props": {"model": model, "label": label}}

def _stat_card(title: str, value: str, icon: str, color: str) -> dict:
    return {"component": "VCard", "props": {"variant": "tonal", "class": "pa-3 text-center"}, "content": [
        {"component": "VIcon", "props": {"icon": icon, "color": color, "size": "28"}},
        {"component": "div", "props": {"class": "text-h6 mt-1"}, "text": value},
        {"component": "div", "props": {"class": "text-caption"}, "text": title},
    ]}
