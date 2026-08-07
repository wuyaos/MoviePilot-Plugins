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


# NexusPHP attendance.php 页面签到状态，供通用签到处理器判断页面形态。
ATTENDANCE_SIGNED = "signed"        # 已签到：无签到表单且有成功/已签到文案
ATTENDANCE_FORM = "form"            # 未签到：存在 attendance 提交表单（可空 POST）
ATTENDANCE_CAPTCHA = "captcha"      # 需验证码：表单含 imagehash/验证码图片
ATTENDANCE_UNKNOWN = "unknown"      # 无法判断签到状态
ATTENDANCE_NOT_FOUND = "not_found"  # 签到页不存在：404/空响应/无签到入口，站点已改版或下线签到


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
    # 通用 NexusPHP 签到状态文案，供 detect_attendance_state 与 post_signin_once 兜底使用。
    _NEXUSPHP_SUCCESS_TEXTS = [
        "签到成功", "簽到成功", "签到已得", "簽到已得",
    ]
    _NEXUSPHP_REPEAT_TEXTS = [
        "今天已经签到过", "今天已經簽到過", "请勿重复刷新", "請勿重複刷新",
        "已经签到", "已經簽到", "今天已经签到", "今天已經簽到",
        "今天已簽到", "今日已簽到", "今日已签到",
    ]

    @classmethod
    def match(cls, url: str) -> bool:
        return StringUtils.url_equal(url, cls.site_url)

    @classmethod
    def detect_attendance_state(cls, html_text: str) -> str:
        """识别 NexusPHP attendance.php 页面签到状态。

        通用签到处理器在 GET 后调用本方法，避免"登录即成功"式误报：
        - NOT_FOUND：响应为 404 错误页或空内容，签到页已改版/下线。
        - CAPTCHA：表单含验证码，通用 GET/POST 无法完成，需专属适配器。
        - FORM：存在提交按钮的签到表单，未签到，可尝试空 POST。
        - SIGNED：无签到表单且命中成功/已签到文案。
        - UNKNOWN：无法判断，交由调用方保守处理。
        """
        if not html_text:
            return ATTENDANCE_UNKNOWN
        # 404 错误页特征：服务器默认 404 页或 PHP 空响应，说明签到入口已失效。
        # 命中时不再继续解析表单/文案，避免误报为"未确认"。
        lower = html_text.lower()
        if ("<title>404 not found</title>" in lower
                or "no input file specified" in lower
                or "<center><h1>404 not found</h1></center>" in lower):
            return ATTENDANCE_NOT_FOUND
        html = etree.HTML(html_text)
        if html is None:
            return ATTENDANCE_UNKNOWN
        if html.xpath('//form[contains(@action,"attendance")]//input[@name="imagehash"]'):
            return ATTENDANCE_CAPTCHA
        has_form = bool(html.xpath(
            '//form[contains(@action,"attendance.php")]//input[@type="submit"]'
        ))
        if has_form:
            return ATTENDANCE_FORM
        if any(t in html_text for t in cls._NEXUSPHP_SUCCESS_TEXTS) \
                or any(t in html_text for t in cls._NEXUSPHP_REPEAT_TEXTS):
            return ATTENDANCE_SIGNED
        return ATTENDANCE_UNKNOWN

    def signin(self, site_info: CommentedMap) -> Tuple[bool, str]:
        site = site_info.get("name")
        site_cookie = site_info.get("cookie")
        ua = site_info.get("ua")
        proxies = settings.PROXY if site_info.get("proxy") else None
        timeout = site_info.get("timeout")

        request = self._build_request(
            site_cookie=site_cookie,
            ua=ua,
            proxies=proxies,
            timeout=timeout,
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

    def _build_request(self, site_cookie, ua, proxies, timeout=None) -> RequestUtils:
        """构造请求客户端；严格确认站点补齐浏览器表单提交所需请求头。"""
        if not self._verify_page_state:
            return RequestUtils(
                cookies=site_cookie,
                ua=ua,
                referer=self._signin_url,
                proxies=proxies,
                timeout=timeout,
            )

        origin = f"{urlsplit(self._signin_url).scheme}://{urlsplit(self._signin_url).netloc}"
        headers = {
            "User-Agent": ua or settings.USER_AGENT,
            "Origin": origin,
            "Referer": self._signin_url,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        }
        return RequestUtils(cookies=site_cookie, headers=headers, proxies=proxies,
                            timeout=timeout)

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
