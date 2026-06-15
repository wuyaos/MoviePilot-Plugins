# input: AutoPtCheckin 的 site_refresh 事件、KeePass/手动凭据配置、MoviePilot 站点表
# output: V2 站点 Cookie/UA 自动刷新插件
# pos: AutoPtCheckin Cookie 失效后的事件消费者，委托 SiteChain 使用当前 V2 浏览器登录实现
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from app.chain.site import SiteChain
from app.core.event import Event, eventmanager
from app.db.site_oper import SiteOper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType, NotificationType

from .cookiecloud import sync_cookie_to_cookiecloud
from .credentials import resolve_credential


class SiteRefresh(_PluginBase):
    plugin_name = "站点自动更新（自用版）"
    plugin_desc = "接收 Cookie 失效事件，使用当前 MoviePilot V2 浏览器登录流程刷新站点 Cookie 和 UA。"
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/refresh.png"
    plugin_version = "1.3.0"
    plugin_author = "wuyaos, thsrite"
    author_url = "https://github.com/wuyaos"
    plugin_config_prefix = "siterefresh_"
    plugin_order = 2
    auth_level = 2

    _enabled: bool = False
    _notify: bool = False
    _sync_cookiecloud: bool = True
    _refresh_sites: list = []
    _config: Dict[str, Any] = {}
    _last_result: Dict[str, Any] = {}

    def init_plugin(self, config: dict = None):
        self._ensure_plugin_log_file()
        config = config or {}
        self._config = config
        self._enabled = bool(config.get("enabled"))
        self._notify = bool(config.get("notify"))
        self._sync_cookiecloud = bool(config.get("sync_cookiecloud", True))
        self._refresh_sites = config.get("refresh_sites") or []
        self._last_result = self.get_data("last_result") or {}

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        return []

    def get_service(self) -> List[Dict[str, Any]]:
        return []

    @eventmanager.register(EventType.PluginAction)
    def site_refresh(self, event: Event = None):
        if not self.get_state() or not event or not event.event_data:
            return
        if event.event_data.get("action") != "site_refresh":
            return
        site_id = event.event_data.get("site_id")
        if not site_id:
            logger.error("SiteRefresh: 未获取到 site_id")
            return
        if self._refresh_sites and str(site_id) not in {str(x) for x in self._refresh_sites}:
            logger.info(f"SiteRefresh: 站点 {site_id} 未在刷新站点选择中，跳过")
            return
        site = SiteOper().get(site_id)
        if not site:
            logger.error(f"SiteRefresh: 未获取到 site_id {site_id} 对应的站点数据")
            return
        credential, msg = resolve_credential(self._config, site.name, site.url)
        if not credential:
            msg = f"未获取到站点 {site.name} 登录凭据：{msg}"
            logger.error(f"SiteRefresh: {msg}")
            self._record_result(site_name=site.name, site_id=site_id, success=False, message=msg)
            return
        logger.info(f"SiteRefresh: 开始尝试登录站点 {site.name}，匹配域名 {credential.domain}")
        try:
            state, message = SiteChain().update_cookie(site_info=site, username=credential.username,
                                                       password=credential.password,
                                                       two_step_code=credential.two_step_code)
        except Exception as exc:
            state, message = False, str(exc)
            logger.exception(f"SiteRefresh: 站点 {site.name} 自动更新 Cookie 和 UA 异常")
        logger.info(f"SiteRefresh: 站点 {site.name} 自动更新 Cookie 和 UA {'成功' if state else '失败'}")
        if not state and message:
            logger.error(f"SiteRefresh: 失败原因：{message}")
        if state and self._sync_cookiecloud:
            try:
                updated_site = SiteOper().get(site_id) or site
                ok, cc_msg = sync_cookie_to_cookiecloud(updated_site.url, getattr(updated_site, "cookie", "") or "")
            except Exception as exc:
                ok, cc_msg = False, f"CookieCloud 同步异常：{exc}"
            logger.info(f"SiteRefresh: CookieCloud 同步{'成功' if ok else '失败'}：{cc_msg}")
            message = f"{message or '成功'}；{cc_msg}"
        self._record_result(site_name=site.name, site_id=site_id, success=state, message=message)
        if self._notify:
            self.post_message(mtype=NotificationType.SiteMessage, title=f"站点 {site.name} Cookie 已失效。",
                              text=f"自动更新 Cookie 和 UA {'成功' if state else '失败'}{f'：{message}' if message else ''}")

    def _record_result(self, site_name: str, site_id: Any, success: bool, message: str = ""):
        self._last_result = {"site": site_name, "site_id": site_id, "success": bool(success),
                             "message": message or "", "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        self.save_data("last_result", self._last_result)

    @staticmethod
    def _site_options() -> List[Dict[str, Any]]:
        try:
            return [{"title": site.name, "value": site.id} for site in SiteOper().list_order_by_pri()]
        except Exception as exc:
            logger.warning(f"SiteRefresh: 获取站点列表失败：{exc}")
            return []

    def get_form(self) -> tuple[List[dict], Dict[str, Any]]:
        return [{"component": "VForm", "content": [
            {"component": "VRow", "content": [
                {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [
                    {"component": "VSwitch", "props": {"model": "enabled", "label": "启用插件"}}]},
                {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [
                    {"component": "VSwitch", "props": {"model": "notify", "label": "开启通知"}}]},
                {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [
                    {"component": "VSwitch", "props": {"model": "sync_cookiecloud", "label": "同步 CookieCloud"}}]}]},
            {"component": "VRow", "content": [{"component": "VCol", "props": {"cols": 12}, "content": [
                {"component": "VSelect", "props": {"chips": True, "multiple": True, "model": "refresh_sites",
                                                     "label": "刷新站点（为空则全部）", "items": self._site_options()}}]}]},
            {"component": "VRow", "content": [
                {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [
                    {"component": "VSwitch", "props": {"model": "keepass_enabled", "label": "启用 KeePass"}}]},
                {"component": "VCol", "props": {"cols": 12, "md": 8}, "content": [
                    {"component": "VTextField", "props": {"model": "keepass_webdav_url", "label": "KDBX WebDAV URL"}}]}]},
            {"component": "VRow", "content": [
                {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [
                    {"component": "VTextField", "props": {"model": "keepass_webdav_username", "label": "WebDAV 用户名"}}]},
                {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [
                    {"component": "VTextField", "props": {"model": "keepass_webdav_password", "label": "WebDAV 密码", "type": "password"}}]},
                {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [
                    {"component": "VTextField", "props": {"model": "keepass_master_password", "label": "KDBX 主密码", "type": "password"}}]}]},
            {"component": "VRow", "content": [{"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [
                {"component": "VTextField", "props": {"model": "keepass_cache_minutes", "label": "KDBX 缓存分钟", "placeholder": "5"}}]}]},
            {"component": "VRow", "content": [{"component": "VCol", "props": {"cols": 12}, "content": [
                {"component": "VTextarea", "props": {"model": "siteconf", "label": "手动站点凭据（KeePass 未命中时兜底）", "rows": 5,
                                                     "placeholder": "每行一个站点：\n域名domain|用户名|用户密码(|二次验证验证码或密钥)"}}]}]},
            {"component": "VRow", "content": [{"component": "VCol", "props": {"cols": 12}, "content": [
                {"component": "VAlert", "props": {"type": "info", "variant": "tonal",
                                                   "text": "KeePass 条目按 URL 域名自动匹配 MoviePilot 站点域名；KDBX 仅通过 WebDAV GET 只读下载到内存，不写入磁盘。"}}]}]},
        ]}], {"enabled": False, "notify": False, "sync_cookiecloud": True, "refresh_sites": [],
              "keepass_enabled": True, "keepass_webdav_url": "", "keepass_webdav_username": "",
              "keepass_webdav_password": "", "keepass_master_password": "", "keepass_cache_minutes": 5,
              "siteconf": ""}

    def get_page(self) -> List[dict]:
        data = self.get_data("last_result") or self._last_result
        if not data:
            return [{"component": "VAlert", "props": {"type": "info", "variant": "tonal", "text": "暂无刷新记录。"}}]
        text = f"最近刷新：{data.get('site')} | {data.get('time')} | {data.get('message') or ('成功' if data.get('success') else '失败')}"
        return [{"component": "VAlert", "props": {"type": "success" if data.get("success") else "error",
                                                    "variant": "tonal", "text": text}}]

    def stop_service(self):
        pass

    @staticmethod
    def _ensure_plugin_log_file():
        try:
            from app.core.config import settings
            path = settings.LOG_PATH / "plugins" / "siterefresh.log"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)
        except Exception as exc:
            logger.debug(f"SiteRefresh: 确保插件日志文件存在失败：{exc}")
