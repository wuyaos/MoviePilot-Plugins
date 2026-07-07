# input: AutoPtCheckin 的 site_refresh 事件、KeePass/手动凭据配置、MoviePilot 站点表
# output: V2 站点 Cookie/UA 自动刷新插件
# pos: AutoPtCheckin Cookie 失效后的事件消费者，委托 SiteChain 使用当前 V2 浏览器登录实现
from __future__ import annotations

import base64
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

from app import schemas
from app.core.event import Event, eventmanager
from app.db.site_oper import SiteOper
from app.helper.browser import PlaywrightHelper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType, NotificationType

from .cookiecloud import sync_cookie_to_cookiecloud
from .credentials import resolve_credential


class SiteRefresh(_PluginBase):
    plugin_name = "站点自动更新（自用版）"
    plugin_desc = "接收 Cookie 失效事件，使用当前 MoviePilot V2 浏览器登录流程刷新站点 Cookie 和 UA。"
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/refresh.png"
    plugin_version = "1.3.1"
    plugin_author = "wuyaos, thsrite"
    author_url = "https://github.com/wuyaos"
    plugin_config_prefix = "siterefresh_"
    plugin_order = 2
    auth_level = 2

    _enabled: bool = False
    _notify: bool = False
    _sync_cookiecloud: bool = True
    _browser_headless: bool = False
    _refresh_sites: list = []
    _config: Dict[str, Any] = {}
    _last_result: Dict[str, Any] = {}
    _refresh_history: List[Dict[str, Any]] = []
    _refreshing_site_ids: set = set()
    _last_refresh_at: dict = {}
    _refresh_lock = threading.Lock()
    _batch_refresh_lock = threading.Lock()  # 批量刷新锁，确保全局只有一批站点在刷新
    _refresh_cooldown: int = 600
    _browser_site_timeout: int = 60

    def init_plugin(self, config: dict = None):
        self._ensure_plugin_log_file()
        config = config or {}
        self._config = config
        self._enabled = bool(config.get("enabled"))
        self._notify = bool(config.get("notify"))
        self._sync_cookiecloud = bool(config.get("sync_cookiecloud", True))
        self._browser_headless = bool(config.get("browser_headless", False))
        self._refresh_sites = config.get("refresh_sites") or []
        self._refresh_cooldown = int(config.get("refresh_cooldown", 600))
        self._browser_site_timeout = int(config.get("browser_site_timeout", 60))
        self._last_result = self.get_data("last_result") or {}
        self._refresh_history = self.get_data("refresh_history") or []

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        return [{
            "path": "/refresh/{site_id}",
            "summary": "手动触发指定站点刷新",
            "endpoint": self.refresh_site_api,
            "methods": ["GET"],
        }]

    def get_service(self) -> List[Dict[str, Any]]:
        return []

    @eventmanager.register(EventType.PluginAction)
    def site_refresh(self, event: Event = None):
        if not self.get_state() or not event or not event.event_data:
            return
        if event.event_data.get("action") != "site_refresh":
            return
        site_ids = event.event_data.get("site_ids") or ([event.event_data.get("site_id")] if event.event_data.get("site_id") else [])
        if not site_ids:
            logger.error("SiteRefresh: 未获取到 site_ids/site_id")
            return
        logger.info(f"SiteRefresh: 收到 site_refresh 事件，站点 IDs={site_ids}")
        self._refresh_sites_batch(site_ids, force=False)

    def refresh_site_api(self, site_id: Any, force: bool = False) -> schemas.Response:
        results = self._refresh_sites_batch([site_id], force=force)
        result = results[0] if results else {"success": False, "message": "站点未刷新"}
        return schemas.Response(success=result.get("success"), message=result.get("message"))

    def _login_in_tab(self, context, site, username: str, password: str,
                      two_step_code: Optional[str], entry_page=None) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """在复用浏览器上下文中登录单站点，每站独立 tab 和 cookie。"""
        try:
            from app.helper.cloudflare import under_challenge
        except Exception:
            under_challenge = None
        from app.helper.cookie import CookieHelper
        from app.utils.site import SiteUtils
        from app.utils.twofa import TwoFactorAuth
        from lxml import etree

        login_xpaths = CookieHelper._SITE_LOGIN_XPATH
        deadline = time.monotonic() + self._browser_site_timeout
        page = entry_page
        own_page = entry_page is None

        def remaining_timeout() -> int:
            return max(1000, int(deadline - time.monotonic()) * 1000)

        try:
            if own_page:
                page = context.new_page()
            page.set_default_timeout(self._browser_site_timeout * 1000)
            login_url = getattr(site, "login_url", None) or site.url
            logger.info(f"SiteRefresh: 打开登录页 {login_url}")
            page.goto(login_url, timeout=remaining_timeout())
            logger.info(f"SiteRefresh: 等待页面加载 {site.url}")
            try:
                page.wait_for_load_state("domcontentloaded", timeout=remaining_timeout())
            except Exception:
                pass
            try:
                page.wait_for_load_state("networkidle", timeout=remaining_timeout())
            except Exception:
                pass

            html_text = page.content()
            is_under_challenge = False
            if under_challenge:
                try:
                    is_under_challenge = under_challenge(html_text or "")
                except Exception:
                    is_under_challenge = False
            cf_keywords = ["security service to protect against malicious bots", "Checking your browser", "Just a moment", "Cloudflare"]
            if is_under_challenge or any(kw.lower() in (html_text or "").lower() for kw in cf_keywords):
                msg = "站点被Cloudflare防护，请打开站点浏览器仿真"
                logger.warning(f"SiteRefresh: {msg}（URL={page.url}）")
                return False, msg, None, None
            if not html_text:
                msg = f"获取源码失败（URL={page.url}, 加载后 HTML 为空）"
                logger.warning(f"SiteRefresh: {msg}")
                return False, msg, None, None
            logger.info(f"SiteRefresh: 登录页源码长度 {len(html_text)}，当前 URL {page.url}")

            html = etree.HTML(html_text)
            username_xpath = next((x for x in login_xpaths["username"] if html.xpath(x)), None)
            if not username_xpath:
                title = html.xpath('//title/text()')
                msg = f"未找到用户名输入框（页面标题={title}, URL={page.url}）"
                logger.warning(f"SiteRefresh: {msg}")
                return False, msg, None, None
            logger.info(f"SiteRefresh: 命中用户名 xpath {username_xpath}")
            password_xpath = next((x for x in login_xpaths["password"] if html.xpath(x)), None)
            if not password_xpath:
                msg = f"未找到密码输入框（URL={page.url}）"
                logger.warning(f"SiteRefresh: {msg}")
                return False, msg, None, None

            otp_code = ""
            if two_step_code:
                try:
                    otp_code = TwoFactorAuth(two_step_code).get_code()
                except Exception:
                    otp_code = ""
            twostep_xpath = None
            if otp_code:
                twostep_xpath = next((x for x in login_xpaths["twostep"] if html.xpath(x)), None)

            captcha_xpath = next((x for x in login_xpaths["captcha"] if html.xpath(x)), None)
            captcha_img_xpath = next((x for x in login_xpaths.get("captcha_img", []) if html.xpath(x)), None)
            if captcha_xpath:
                if not captcha_img_xpath:
                    msg = f"站点 {site.name} 需要验证码但未找到图片（captcha_xpath 命中，captcha_img_xpath 未命中，URL={page.url}）"
                    logger.warning(f"SiteRefresh: {msg}")
                    return False, msg, None, None
                img_src = html.xpath(captcha_img_xpath)
                img_src = img_src[0] if img_src else ""
                if hasattr(img_src, "get"):
                    img_src = img_src.get("src") or ""
                if img_src:
                    captcha_url = urljoin(site.url, str(img_src))
                    image_bytes = None
                    try:
                        b64 = page.evaluate(
                            """async (url) => {
                                try {
                                    const r = await fetch(url, {credentials: 'include'});
                                    const buf = await r.arrayBuffer();
                                    const bytes = new Uint8Array(buf);
                                    let binary = '';
                                    for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
                                    return btoa(binary);
                                } catch (e) { return ''; }
                            }""",
                            captcha_url,
                        )
                        if b64:
                            image_bytes = base64.b64decode(b64)
                            logger.info(f"SiteRefresh: 浏览器取得验证码图片 {len(image_bytes)} 字节")
                    except Exception as e:
                        logger.warning(f"SiteRefresh: 浏览器取验证码图片失败: {e}")
                    try:
                        from .helper.ocr_helper import recognize_captcha
                        captcha_code = recognize_captcha(
                            image_bytes=image_bytes,
                            image_url=captcha_url if not image_bytes else None,
                            retry_times=3,
                        ) or ""
                    except Exception as e:
                        logger.warning(f"SiteRefresh: 验证码识别异常: {e}")
                        captcha_code = ""
                    if captcha_code:
                        logger.info(f"SiteRefresh: 验证码识别结果: {captcha_code}")
                        captcha_el = page.query_selector(captcha_xpath)
                        if captcha_el:
                            captcha_el.fill(captcha_code)
                    else:
                        msg = f"验证码识别失败（站点={site.name}, 图片URL={captcha_url}, 图片字节={len(image_bytes) if image_bytes else 0}）"
                        logger.warning(f"SiteRefresh: {msg}")
                        return False, msg, None, None
                else:
                    msg = "未获取到验证码图片地址（img_src 为空）"
                    logger.warning(f"SiteRefresh: {msg}")
                    return False, msg, None, None

            submit_xpath = next((x for x in login_xpaths["submit"] if html.xpath(x)), None)
            if not submit_xpath:
                msg = f"未找到登录按钮（URL={page.url}）"
                logger.warning(f"SiteRefresh: {msg}")
                return False, msg, None, None

            try:
                page.wait_for_selector(submit_xpath, timeout=remaining_timeout())
                page.fill(username_xpath, username)
                page.fill(password_xpath, password)
                if twostep_xpath:
                    page.fill(twostep_xpath, otp_code)
                logger.info(f"SiteRefresh: 点击登录按钮 {submit_xpath}")
                page.click(submit_xpath)
                try:
                    page.wait_for_url(lambda url: "login" not in url.lower(), timeout=remaining_timeout())
                except Exception:
                    try:
                        page.locator(password_xpath).press("Enter")
                        page.wait_for_url(lambda url: "login" not in url.lower(), timeout=remaining_timeout())
                    except Exception:
                        pass
                try:
                    page.wait_for_load_state("networkidle", timeout=remaining_timeout())
                except Exception:
                    pass
                logger.info(f"SiteRefresh: 登录后 URL {page.url}")
            except Exception as e:
                msg = f"仿真登录失败（URL={page.url}）：{e}"
                logger.warning(f"SiteRefresh: {msg}")
                return False, msg, None, None

            if "verify" in (page.url or ""):
                if not otp_code:
                    msg = f"需要二次验证码（站点={site.name}）"
                    logger.warning(f"SiteRefresh: {msg}")
                    return False, msg, None, None
                html2 = etree.HTML(page.content() or "")
                for xpath in login_xpaths["twostep"]:
                    if html2.xpath(xpath):
                        try:
                            otp_code = TwoFactorAuth(two_step_code).get_code()
                            page.fill(xpath, otp_code)
                            page.click(submit_xpath)
                            page.wait_for_load_state("networkidle", timeout=remaining_timeout())
                        except Exception as e:
                            msg = f"二次验证码输入失败：{e}"
                            logger.warning(f"SiteRefresh: {msg}")
                            return False, msg, None, None
                        break

            try:
                page.wait_for_load_state("domcontentloaded", timeout=remaining_timeout())
            except Exception:
                pass
            final_url = page.url or ""
            final_html = page.content() or ""
            if not final_html:
                msg = f"获取登录后源码失败（URL={page.url}）"
                logger.warning(f"SiteRefresh: {msg}")
                return False, msg, None, None
            cookie = CookieHelper.parse_cookies(context.cookies([site.url]))
            url_left = "login" not in final_url.lower()
            logged_html = SiteUtils.is_logged_in(final_html)
            has_uid_pass = ("uid=" in cookie) or ("pass=" in cookie)
            success = logged_html or (url_left and has_uid_pass)
            logger.info(f"SiteRefresh: 登录态判定 {success}，源码判定 {logged_html}，URL离开登录页 {url_left}，Cookie含uid/pass {has_uid_pass}，登录后 URL {final_url}")
            if success:
                ua = page.evaluate("() => window.navigator.userAgent")
                return True, "登录成功", cookie, ua
            final_doc = etree.HTML(final_html)
            error_xpath = next((x for x in login_xpaths["error"]
                                if html.xpath(x) or (final_doc is not None and final_doc.xpath(x))), None)
            if error_xpath:
                err = ((final_doc.xpath(error_xpath) if final_doc is not None else None)
                       or html.xpath(error_xpath) or ["登录失败"])[0]
                msg = str(err)
                logger.warning(f"SiteRefresh: 登录失败，站点返回错误：{msg}")
                return False, msg, None, None
            snippet = (final_html[:500] if final_html else "").replace('\n', ' ')
            logger.warning(f"SiteRefresh: 登录失败兜底，站点={site.name} URL={final_url} 登录后HTML片段: {snippet}")
            return False, f"登录失败（站点={site.name}, 登录后URL={final_url}, 离开登录页={url_left}, cookie含uid/pass={has_uid_pass}）", None, None
        except Exception as e:
            return False, f"浏览器操作异常：{e}", None, None
        finally:
            if own_page and page:
                try:
                    page.close()
                except Exception as e:
                    logger.warning(f"SiteRefresh: 关闭站点 {site.name} 页面失败：{e}")

    def get_config_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self._enabled,
            "notify": self._notify,
            "sync_cookiecloud": self._sync_cookiecloud,
            "browser_headless": self._browser_headless,
            "refresh_sites": self._refresh_sites,
            "refresh_cooldown": self._refresh_cooldown,
            "browser_site_timeout": self._browser_site_timeout,
            "keepass_enabled": self._config.get("keepass_enabled", True),
            "keepass_webdav_url": self._config.get("keepass_webdav_url", ""),
            "keepass_webdav_username": self._config.get("keepass_webdav_username", ""),
            "keepass_webdav_password": self._config.get("keepass_webdav_password", ""),
            "keepass_master_password": self._config.get("keepass_master_password", ""),
            "keepass_cache_minutes": self._config.get("keepass_cache_minutes", 5),
            "siteconf": self._config.get("siteconf", "")
        }

    def _refresh_site_in_context(self, context, site_id: Any, entry_page=None) -> Dict[str, Any]:
        started_at = time.monotonic()
        site = SiteOper().get(site_id)
        if not site:
            msg = f"未获取到 site_id {site_id} 对应的站点数据"
            logger.error(f"SiteRefresh: {msg}")
            return {"success": False, "message": msg, "site": ""}
        logger.info(f"SiteRefresh: 开始刷新站点 {site.name}（{site.url}，ID={site.id}）")
        credential, msg = resolve_credential(self._config, site.name, site.url)
        if not credential:
            msg = f"未获取到站点 {site.name} 登录凭据：{msg}"
            logger.warning(f"SiteRefresh: 站点 {site.name} 登录失败：{msg}")
            self._record_result(site_name=site.name, site_id=site_id, site_url=site.url, success=False, message=msg)
            logger.warning(f"SiteRefresh: 站点 {site.name} 刷新失败（耗时 {time.monotonic() - started_at:.1f}s）：{msg}")
            return {"success": False, "message": msg, "site": site.name}
        try:
            state, message, cookie, ua = self._login_in_tab(
                context, site, credential.username, credential.password, credential.two_step_code, entry_page=entry_page
            )
        except Exception as exc:
            state, message = False, str(exc)
            cookie = ua = None
            logger.error(f"SiteRefresh: 站点 {site.name} 自动更新 Cookie 和 UA 异常：{exc}")
        if state:
            logger.info(f"SiteRefresh: 站点 {site.name} 浏览器登录成功")
        else:
            logger.warning(f"SiteRefresh: 站点 {site.name} 登录失败：{message}")
        if state and cookie:
            try:
                SiteOper().update(site.id, {"cookie": cookie, "ua": ua})
                logger.info(f"SiteRefresh: 站点 {site.name} Cookie/UA 已更新")
            except Exception as exc:
                state = False
                message = f"回写 Cookie/UA 失败：{exc}"
                logger.error(f"SiteRefresh: 站点 {site.name} {message}")
        if state and self._sync_cookiecloud:
            try:
                updated_site = SiteOper().get(site_id) or site
                ok, cc_msg = sync_cookie_to_cookiecloud(updated_site.url, cookie or getattr(updated_site, "cookie", "") or "")
            except Exception as exc:
                ok, cc_msg = False, f"CookieCloud 同步异常：{exc}"
            logger.info(f"SiteRefresh: 站点 {site.name} CookieCloud 同步{'成功' if ok else '失败'}：{cc_msg}")
            message = f"{message or '成功'}；{cc_msg}"
        self._record_result(site_name=site.name, site_id=site_id, site_url=site.url, success=state, message=message)
        elapsed = time.monotonic() - started_at
        if state:
            logger.info(f"SiteRefresh: 站点 {site.name} 刷新成功（耗时 {elapsed:.1f}s）")
        else:
            logger.warning(f"SiteRefresh: 站点 {site.name} 刷新失败（耗时 {elapsed:.1f}s）：{message}")
        result = {"success": bool(state), "message": message or "", "site": site.name}
        if self._notify:
            self.post_message(mtype=NotificationType.SiteMessage, title=f"站点 {result.get('site')} Cookie 已失效。",
                              text=f"自动更新 Cookie 和 UA {'成功' if result.get('success') else '失败'}{('：' + result.get('message')) if result.get('message') else ''}")
        return result

    def _reserve_site_ids(self, site_ids, force: bool = False):
        reserved = []
        allowed_sites = {str(x) for x in self._refresh_sites}
        now = time.time()
        with self._refresh_lock:
            for site_id in site_ids:
                site = SiteOper().get(site_id)
                site_name = getattr(site, "name", "") if site else ""
                site_label = f"{site_name}（ID={site_id}）" if site_name else f"ID={site_id}"
                sid = str(site_id)
                if allowed_sites and sid not in allowed_sites:
                    logger.info(f"SiteRefresh: 站点 {site_label} 未在刷新站点选择中，跳过")
                    continue
                if sid in self._refreshing_site_ids:
                    logger.info(f"SiteRefresh: 站点 {site_label} 正在刷新中，跳过重复事件")
                    continue
                last = self._last_refresh_at.get(sid, 0)
                if not force and self._refresh_cooldown > 0 and (now - last) < self._refresh_cooldown:
                    logger.info(f"SiteRefresh: 站点 {site_label} 冷却中（剩余 {int(self._refresh_cooldown - (now - last))}s），跳过")
                    continue
                self._refreshing_site_ids.add(sid)
                reserved.append(site_id)
        return reserved

    def _refresh_sites_batch(self, site_ids, force: bool = False) -> List[Dict[str, Any]]:
        reserved_site_ids = self._reserve_site_ids(site_ids, force=force)
        if not reserved_site_ids:
            return []

        results = []
        first_site = SiteOper().get(reserved_site_ids[0])
        if not first_site:
            result = self._refresh_missing_site(reserved_site_ids[0])
            with self._refresh_lock:
                for site_id in reserved_site_ids:
                    sid = str(site_id)
                    self._refreshing_site_ids.discard(sid)
                    self._last_refresh_at[sid] = time.time()
            return [result]
        entry_url = first_site.url

        def batch_handler(page):
            context = page.context
            for idx, site_id in enumerate(reserved_site_ids):
                site = SiteOper().get(site_id)
                if site and bool(getattr(site, "proxy", 0)):
                    msg = "该站需代理，跳过批量模式"
                    logger.warning(f"SiteRefresh: 站点 {site.name} {msg}")
                    self._record_result(site_name=site.name, site_id=site_id, site_url=site.url, success=False, message=msg)
                    results.append({"success": False, "message": msg, "site": site.name})
                    continue
                try:
                    if idx == 0:
                        result = self._refresh_site_in_context(context, site_id, entry_page=page)
                    else:
                        result = self._refresh_site_in_context(context, site_id)
                    results.append(result)
                except Exception as exc:
                    site_name = getattr(site, "name", "") if site else ""
                    site_url = getattr(site, "url", "") if site else ""
                    msg = f"刷新异常: {exc}"
                    self._record_result(site_name=site_name, site_id=site_id, site_url=site_url, success=False, message=msg)
                    results.append({"success": False, "message": str(exc), "site": site_name})
            return None

        with self._batch_refresh_lock:
            try:
                PlaywrightHelper().action(
                    url=entry_url,
                    callback=batch_handler,
                    headless=self._browser_headless,
                    timeout=max(60, self._browser_site_timeout * max(1, len(reserved_site_ids))),
                    proxies=None
                )
            except Exception as exc:
                logger.error(f"SiteRefresh: 批量刷新浏览器异常: {exc}")
                for site_id in reserved_site_ids:
                    site = SiteOper().get(site_id)
                    site_name = getattr(site, "name", "") if site else ""
                    site_url = getattr(site, "url", "") if site else ""
                    msg = f"浏览器异常: {exc}"
                    self._record_result(site_name=site_name, site_id=site_id, site_url=site_url, success=False, message=msg)
                    results.append({"success": False, "message": str(exc), "site": site_name})
            finally:
                with self._refresh_lock:
                    for site_id in reserved_site_ids:
                        sid = str(site_id)
                        self._refreshing_site_ids.discard(sid)
                        self._last_refresh_at[sid] = time.time()
        return results

    def _refresh_missing_site(self, site_id: Any) -> Dict[str, Any]:
        msg = f"未获取到 site_id {site_id} 对应的站点数据"
        logger.error(f"SiteRefresh: {msg}")
        return {"success": False, "message": msg, "site": ""}

    def _record_result(self, site_name: str, site_id: Any, site_url: str = "", success: bool = False,
                       message: str = ""):
        self._last_result = {"site": site_name, "site_id": site_id, "site_url": site_url or "", "success": bool(success),
                             "message": message or "", "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        self._refresh_history = [self._last_result] + (self.get_data("refresh_history") or self._refresh_history or [])
        self._refresh_history = self._refresh_history[:50]
        self.save_data("last_result", self._last_result)
        self.save_data("refresh_history", self._refresh_history)

    @staticmethod
    def _site_options() -> List[Dict[str, Any]]:
        try:
            return [{"title": site.name, "value": site.id} for site in SiteOper().list_order_by_pri()]
        except Exception as exc:
            logger.warning(f"SiteRefresh: 获取站点列表失败：{exc}")
            return []

    def get_form(self) -> tuple[List[dict], Dict[str, Any]]:
        return [{"component": "VForm", "content": [
            {"component": "VCard", "props": {"variant": "outlined", "class": "mt-3"}, "content": [
                {"component": "VCardTitle", "props": {"class": "d-flex align-center"}, "content": [
                    {"component": "VIcon", "props": {"color": "primary", "class": "mr-2"}, "text": "mdi-tune"},
                    {"component": "span", "text": "通用设置"}]},
                {"component": "VDivider"},
                {"component": "VCardText", "content": [
                    {"component": "VRow", "content": [
                        {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [
                            {"component": "VSwitch", "props": {"model": "enabled", "label": "启用插件", "color": "primary"}}]},
                        {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [
                            {"component": "VSwitch", "props": {"model": "notify", "label": "开启通知", "color": "info"}}]},
                        {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [
                            {"component": "VSwitch", "props": {"model": "sync_cookiecloud", "label": "同步 CookieCloud", "color": "success"}}]}]},
                    {"component": "VRow", "content": [
                        {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [
                            {"component": "VSwitch", "props": {"model": "browser_headless", "label": "无头模式（关闭更稳定）", "color": "warning",
                                                              "hint": "关闭无头模式可绕过部分站点自动化检测；服务器无显示器时需开启"}}]},
                        {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [
                            {"component": "VTextField", "props": {"model": "refresh_cooldown", "label": "刷新冷却(秒)", "type": "number",
                                                                 "placeholder": "600", "hint": "同一站点冷却期内不重复刷新，0=不冷却"}}]},
                        {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [
                            {"component": "VTextField", "props": {"model": "browser_site_timeout", "label": "单站超时(秒)", "type": "number",
                                                                 "placeholder": "60", "hint": "单站浏览器登录总超时，超时只关该站 tab 不影响其他站"}}]}]},
                    {"component": "VRow", "content": [{"component": "VCol", "props": {"cols": 12}, "content": [
                        {"component": "VSelect", "props": {"chips": True, "multiple": True, "model": "refresh_sites",
                                                             "label": "刷新站点（为空则全部）", "items": self._site_options(),
                                                             "hint": "为空时刷新全部站点；选择后仅响应这些站点的失效事件"}}]}]}]}]},
            {"component": "VCard", "props": {"variant": "outlined", "class": "mt-3"}, "content": [
                {"component": "VCardTitle", "props": {"class": "d-flex align-center"}, "content": [
                    {"component": "VIcon", "props": {"color": "success", "class": "mr-2"}, "text": "mdi-database-lock"},
                    {"component": "span", "text": "KeePass WebDAV 凭据"},
                    {"component": "VSpacer"},
                    {"component": "VSwitch", "props": {"model": "keepass_enabled", "label": "启用 KeePass", "color": "success", "hide-details": True}}]},
                {"component": "VDivider"},
                {"component": "VCardText", "content": [
                    {"component": "VRow", "content": [{"component": "VCol", "props": {"cols": 12}, "content": [
                        {"component": "VTextField", "props": {"model": "keepass_webdav_url", "label": "KDBX WebDAV URL",
                                                             "placeholder": "https://example.com/dav/passwords.kdbx",
                                                             "hint": "通过 WebDAV GET 只读下载 KDBX；不会写入磁盘", "clearable": True}}]}]},
                    {"component": "VRow", "content": [
                        {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [
                            {"component": "VTextField", "props": {"model": "keepass_webdav_username", "label": "WebDAV 用户名",
                                                                 "placeholder": "WebDAV 登录用户名", "autocomplete": "new-username", "clearable": True}}]},
                        {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [
                            {"component": "VTextField", "props": {"model": "keepass_webdav_password", "label": "WebDAV 密码", "type": "password",
                                                                 "autocomplete": "new-password", "clearable": True}}]}]},
                    {"component": "VRow", "content": [
                        {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [
                            {"component": "VTextField", "props": {"model": "keepass_master_password", "label": "KDBX 主密码", "type": "password",
                                                                 "hint": "KDBX 数据库主密码", "autocomplete": "new-password", "clearable": True}}]},
                        {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [
                            {"component": "VTextField", "props": {"model": "keepass_cache_minutes", "label": "KDBX 缓存分钟", "type": "number",
                                                                 "placeholder": "5", "hint": "内存缓存分钟数，减少 WebDAV 请求；建议 5 分钟"}}]}]}]}]},
            {"component": "VCard", "props": {"variant": "outlined", "class": "mt-3"}, "content": [
                {"component": "VCardTitle", "props": {"class": "d-flex align-center"}, "content": [
                    {"component": "VIcon", "props": {"color": "warning", "class": "mr-2"}, "text": "mdi-file-key"},
                    {"component": "span", "text": "手动凭据兜底"}]},
                {"component": "VDivider"},
                {"component": "VCardText", "content": [{"component": "VTextarea", "props": {
                    "model": "siteconf", "label": "手动站点凭据（KeePass 未命中时兜底）", "rows": 6,
                    "auto-grow": True, "placeholder": "# 每行一个站点，支持 # 注释\nexample.com|username|password\npt.example.com|username|password|2FA密钥或验证码",
                    "hint": "KeePass 未命中或未启用时使用；域名不要带路径；格式：域名|用户名|密码(|二步验证码或密钥)"}}]}]},
            {"component": "VCard", "props": {"variant": "outlined", "class": "mt-3"}, "content": [
                {"component": "VCardTitle", "props": {"class": "d-flex align-center"}, "content": [
                    {"component": "VIcon", "props": {"color": "info", "class": "mr-2"}, "text": "mdi-information"},
                    {"component": "span", "text": "使用说明"}]},
                {"component": "VDivider"},
                {"component": "VCardText", "content": [{"component": "VList", "props": {"density": "comfortable", "lines": "two"}, "content": [
                    {"component": "VListItem", "content": [
                        {"component": "template", "props": {"v-slot:prepend": ""}, "content": [{"component": "VIcon", "props": {"color": "success"}, "text": "mdi-database-search"}]},
                        {"component": "VListItemTitle", "text": "凭据优先级"},
                        {"component": "VListItemSubtitle", "text": "启用 KeePass 时优先按站点域名匹配 KDBX，未命中再使用手动凭据"}]},
                    {"component": "VListItem", "content": [
                        {"component": "template", "props": {"v-slot:prepend": ""}, "content": [{"component": "VIcon", "props": {"color": "warning"}, "text": "mdi-file-key"}]},
                        {"component": "VListItemTitle", "text": "手动格式"},
                        {"component": "VListItemSubtitle", "text": "域名|用户名|密码(|二步验证码或密钥)，支持 # 注释"}]},
                    {"component": "VListItem", "content": [
                        {"component": "template", "props": {"v-slot:prepend": ""}, "content": [{"component": "VIcon", "props": {"color": "primary"}, "text": "mdi-web"}]},
                        {"component": "VListItemTitle", "text": "域名匹配"},
                        {"component": "VListItemSubtitle", "text": "填写根域名或站点 host，不要带路径"}]},
                    {"component": "VListItem", "content": [
                        {"component": "template", "props": {"v-slot:prepend": ""}, "content": [{"component": "VIcon", "props": {"color": "info"}, "text": "mdi-cloud-sync"}]},
                        {"component": "VListItemTitle", "text": "CookieCloud 同步"},
                        {"component": "VListItemSubtitle", "text": "刷新成功后可同步 CookieCloud"}]}]}]}]}
        ]}], {"enabled": False, "notify": False, "sync_cookiecloud": True, "browser_headless": False, "refresh_sites": [],
              "refresh_cooldown": 600, "browser_site_timeout": 60,
              "keepass_enabled": True, "keepass_webdav_url": "", "keepass_webdav_username": "",
              "keepass_webdav_password": "", "keepass_master_password": "", "keepass_cache_minutes": 5,
              "siteconf": ""}

    def get_page(self) -> List[dict]:
        history = self.get_data("refresh_history") or self._refresh_history or []
        if not isinstance(history, list):
            history = [history]
        history = sorted(history, key=lambda x: x.get("time", "") if isinstance(x, dict) else "", reverse=True)
        data = (history[0] if history else None) or self.get_data("last_result") or self._last_result
        if data and not history:
            history = [data]

        frost_style = 'background-color: rgba(var(--v-theme-surface), 0.75); backdrop-filter: blur(5px); -webkit-backdrop-filter: blur(5px); outline: 1px solid rgba(var(--v-theme-on-surface), 0.12); border-radius: 8px; box-sizing: border-box;'
        total = len(history)
        success_count = sum(1 for item in history if isinstance(item, dict) and item.get("success"))
        success_rate = f"{(success_count / total * 100):.0f}%" if total else "0%"
        is_success = bool(data and data.get("success"))

        def stat_block(icon: str, color: str, value: Any, label: str) -> dict:
            return {"component": "VCol", "props": {"cols": 12, "md": 4, "class": "pa-2"}, "content": [
                {"component": "div", "props": {"class": "text-center pa-3 d-flex flex-column justify-center", "style": frost_style}, "content": [
                    {"component": "div", "props": {"class": "d-flex justify-center align-center mb-1"}, "content": [
                        {"component": "VIcon", "props": {"style": f"color: {color};", "class": "mr-1"}, "text": icon},
                        {"component": "span", "props": {"class": "text-h6 font-weight-bold"}, "text": str(value) if value not in (None, "") else "—"}
                    ]},
                    {"component": "div", "props": {"class": "text-caption text-medium-emphasis"}, "text": label}
                ]}
            ]}

        rows = []
        for item in history[:30]:
            if not isinstance(item, dict):
                continue
            row_success = bool(item.get("success"))
            rows.append({"component": "tr", "content": [
                {"component": "td", "content": [{"component": "div", "content": [
                    {"component": "div", "props": {"class": "font-weight-medium"}, "text": item.get("site") or "—"},
                    {"component": "div", "props": {"class": "text-caption text-medium-emphasis"}, "text": item.get("site_url") or "—"}
                ]}]},
                {"component": "td", "props": {"class": "text-caption"}, "text": str(item.get("site_id") or "—")},
                {"component": "td", "props": {"class": "text-caption"}, "text": item.get("time") or "—"},
                {"component": "td", "content": [{"component": "VChip", "props": {"color": "success" if row_success else "error", "size": "small", "variant": "elevated"}, "content": [
                    {"component": "VIcon", "props": {"start": True, "size": "small"}, "text": "mdi-check-circle" if row_success else "mdi-alert-circle"},
                    {"component": "span", "text": "成功" if row_success else "失败"}
                ]}]},
                {"component": "td", "content": [{"component": "div", "props": {"class": "text-caption"}, "text": item.get("message") or ("成功" if row_success else "失败")}]}
            ]})

        components = [{"component": "VCard", "props": {"variant": "outlined", "class": "mt-3 mb-4", "style": frost_style}, "content": [
            {"component": "VCardTitle", "props": {"class": "d-flex align-center"}, "content": [
                {"component": "VIcon", "props": {"color": "primary", "class": "mr-2"}, "text": "mdi-history"},
                {"component": "span", "props": {"class": "text-h6 font-weight-bold"}, "text": "刷新记录"},
                {"component": "VSpacer"},
                {"component": "VChip", "props": {"color": "success" if is_success else "error", "size": "small", "variant": "elevated"}, "content": [
                    {"component": "VIcon", "props": {"start": True, "size": "small"}, "text": "mdi-check-circle" if is_success else "mdi-alert-circle"},
                    {"component": "span", "text": "成功" if is_success else "失败"}
                ]} if data else {"component": "span", "text": ""}
            ]},
            {"component": "VDivider"},
            {"component": "VCardText", "props": {"class": "pa-2"}, "content": [
                {"component": "VRow", "props": {"no-gutters": True}, "content": [
                    stat_block("mdi-web", "#1976D2", data.get("site") if data else "—", "最近刷新站点"),
                    stat_block("mdi-check-circle" if is_success else "mdi-alert", "#4CAF50" if is_success else "#F44336", "成功" if is_success else "失败" if data else "—", "最近结果状态"),
                    stat_block("mdi-counter", "#7E57C2", total, "刷新总次数")
                ]},
                {"component": "div", "props": {"class": "d-flex justify-center mt-2"}, "content": [
                    {"component": "VChip", "props": {"color": "success" if total and success_count == total else "primary", "variant": "tonal"}, "content": [
                        {"component": "VIcon", "props": {"start": True, "size": "small"}, "text": "mdi-percent"},
                        {"component": "span", "text": f"成功率：{success_count}/{total}（{success_rate}）"}
                    ]}
                ]}
            ]}
        ]}]

        if not rows:
            components.append({"component": "VAlert", "props": {"type": "info", "variant": "tonal", "text": "暂无刷新记录", "prepend-icon": "mdi-information"}})
            return components

        components.extend([
            {"component": "VCard", "props": {"variant": "outlined", "class": "mb-4", "style": frost_style}, "content": [
                {"component": "VCardTitle", "props": {"class": "d-flex align-center"}, "content": [
                    {"component": "VIcon", "props": {"color": "primary", "class": "mr-2"}, "text": "mdi-table-clock"},
                    {"component": "span", "props": {"class": "text-h6 font-weight-bold"}, "text": "历史记录"}
                ]},
                {"component": "VDivider"},
                {"component": "VCardText", "props": {"class": "pa-0 pa-md-2"}, "content": [
                    {"component": "VResponsive", "content": [
                        {"component": "VTable", "props": {"hover": True, "density": "comfortable"}, "content": [
                            {"component": "thead", "content": [{"component": "tr", "content": [
                                {"component": "th", "text": "站点"},
                                {"component": "th", "text": "站点ID"},
                                {"component": "th", "text": "时间"},
                                {"component": "th", "text": "状态"},
                                {"component": "th", "text": "消息"}
                            ]}]},
                            {"component": "tbody", "content": rows}
                        ]}
                    ]}
                ]}
            ]},
            {"component": "style", "text": ".v-table { border-radius: 8px; overflow: hidden; } .v-table th { background-color: rgba(var(--v-theme-primary), 0.05); color: rgb(var(--v-theme-primary)); font-weight: 600; }"}
        ])
        return components

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
