# input: 无验证码 attendance.php 站点 Cookie、UA、代理配置
# output: NexusPHP attendance.php 空 POST 签到通用处理器
# pos: helper 层，供纯 POST 站点适配器复用；不直接被 ModuleHelper 加载
from typing import Tuple
from urllib.parse import urlsplit

from lxml import etree
from ruamel.yaml import CommentedMap

from app.core.config import settings
from app.log import logger
from app.plugins.autoptcheckin.sites import _ISiteSigninHandler
from app.utils.http import RequestUtils
from app.utils.site import SiteUtils
from app.utils.string import StringUtils


class _AttendancePostHandler(_ISiteSigninHandler):
    """无验证码 attendance.php 空 POST 签到通用基类。

    子类只需定义 ``site_url``、``_signin_url`` 与各自的成功/重复签到文案。
    本类刻意保持原有处理顺序和空 POST 行为，不负责收紧站点特有文案。
    """

    site_url = ""
    _signin_url = ""
    _success_texts = []
    _repeat_texts = []
    # 默认保持旧站点行为；仅经真实页面验证的站点按需开启严格状态确认。
    _verify_page_state = False
    _verified_success_texts = []

    @classmethod
    def match(cls, url: str) -> bool:
        return StringUtils.url_equal(url, cls.site_url)

    def signin(self, site_info: CommentedMap) -> Tuple[bool, str]:
        site = site_info.get("name")
        site_cookie = site_info.get("cookie")
        ua = site_info.get("ua")
        proxies = settings.PROXY if site_info.get("proxy") else None

        request = self._build_request(
            site_cookie=site_cookie,
            ua=ua,
            proxies=proxies,
        )

        if self._verify_page_state:
            page_res = request.get_res(url=self._signin_url)
            state, message = self._verify_attendance_page(site, page_res, before_post=True)
            if state is not None:
                return state, message

        res = request.post_res(url=self._signin_url, data={})
        if not res or res.status_code != 200:
            logger.error(f"{site} 签到失败，请检查站点连通性")
            return False, "签到失败，请检查站点连通性"

        html_text = res.text or ""
        if not SiteUtils.is_logged_in(html_text) or "login.php" in html_text:
            logger.error(f"{site} 签到失败，Cookie已失效")
            return False, "签到失败，Cookie已失效"

        if any(text in html_text for text in self._repeat_texts):
            if not self._verify_page_state:
                logger.info(f"{site} 今日已签到")
                return True, "今日已签到"
        if any(text in html_text for text in self._success_texts):
            if not self._verify_page_state:
                logger.info(f"{site} 签到成功")
                return True, "签到成功"

        if self._verify_page_state:
            verify_res = request.get_res(url=self._signin_url)
            state, message = self._verify_attendance_page(site, verify_res, before_post=False)
            if state is not None:
                return state, message
            logger.error(f"{site} 签到结果未确认，POST 返回 {html_text[:200]}")
            return False, "签到结果未确认"

        logger.error(f"{site} 签到失败，签到接口返回 {html_text[:200]}")
        return False, "签到失败"

    def _build_request(self, site_cookie, ua, proxies) -> RequestUtils:
        """构造请求客户端；严格确认站点补齐浏览器表单提交所需请求头。"""
        if not self._verify_page_state:
            return RequestUtils(
                cookies=site_cookie,
                ua=ua,
                referer=self._signin_url,
                proxies=proxies,
            )

        origin = f"{urlsplit(self._signin_url).scheme}://{urlsplit(self._signin_url).netloc}"
        headers = {
            "User-Agent": ua or settings.USER_AGENT,
            "Origin": origin,
            "Referer": self._signin_url,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        }
        return RequestUtils(cookies=site_cookie, headers=headers, proxies=proxies)

    def _verify_attendance_page(self, site, response, before_post: bool):
        """确认签到表单与明确状态文案；返回 None 表示首次签到表单仍可提交。"""
        if not response or response.status_code != 200:
            status = response.status_code if response is not None else "无响应"
            logger.error(f"{site} 签到结果未确认，复查状态码：{status}")
            return False, f"签到结果未确认，复查状态码：{status}"

        html_text = response.text or ""
        if not SiteUtils.is_logged_in(html_text) or "login.php" in html_text:
            logger.error(f"{site} 签到失败，Cookie已失效")
            return False, "签到失败，Cookie已失效"

        html = etree.HTML(html_text)
        form_present = bool(html is not None and html.xpath(
            '//form[contains(@action,"attendance.php") and '
            '(contains(@class,"attendance-checkin-form") or .//input[@type="submit"])]'
        ))
        success_texts = self._verified_success_texts or self._success_texts

        if not form_present and any(text in html_text for text in success_texts):
            if before_post:
                logger.info(f"{site} 今日已签到")
                return True, "今日已签到"
            logger.info(f"{site} 签到成功（已复查确认）")
            return True, "签到成功"

        if form_present:
            if before_post:
                return None, ""
            logger.error(f"{site} 签到结果未确认，复查后签到表单仍存在")
            return False, "签到结果未确认"

        logger.error(f"{site} 签到结果未确认，未找到签到表单或明确状态")
        return False, "签到结果未确认"
