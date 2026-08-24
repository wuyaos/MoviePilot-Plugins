# input: RetroToon Cookie、UA、代理配置
# output: attendance.php CSRF 表单签到与模拟登录结果
# pos: AutoPtCheckin 站点适配层；RetroToon 使用 POST 领取每日奖励
from typing import Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests as _requests
from lxml import etree
from ruamel.yaml import CommentedMap

from app.core.config import settings
from app.log import logger
from app.plugins.autoptcheckin.sites import _ISiteSigninHandler
from app.utils.http import RequestUtils, cookie_parse
from app.utils.site import SiteUtils


class RetroToon(_ISiteSigninHandler):
    """RetroToon 每日奖励：先读取 CSRF 表单，再 POST claim 并复查页面状态。"""

    site_url = "retrotoon.world"
    _request_timeout = 30

    def signin(self, site_info: CommentedMap) -> Tuple[bool, str]:
        site = site_info.get("name")
        attendance_url = self._attendance_url(site_info.get("url"))
        session = _requests.Session()
        request_cookies = cookie_parse(site_info.get("cookie"))
        headers = self._page_headers(site_info.get("ua"), attendance_url)
        proxies = settings.PROXY if site_info.get("proxy") else None
        timeout = site_info.get("timeout") or self._request_timeout

        page_response = RequestUtils(
            headers=headers,
            cookies=request_cookies,
            session=session,
            proxies=proxies,
            timeout=timeout,
        ).get_res(url=attendance_url)
        failure = self._response_failure(site, page_response, "打开签到页面")
        if failure:
            return failure

        self._merge_response_cookies(request_cookies, session)
        page_html = page_response.text or ""
        if not SiteUtils.is_logged_in(page_html):
            logger.warning(f"{site} 签到失败，Cookie已失效")
            return False, "签到失败，Cookie已失效"

        state = self._attendance_state(page_html)
        if state == "claimed":
            logger.info(f"{site} 今日已签到")
            return True, self._claimed_message(page_html, already=True)

        claim = self._extract_claim_request(page_html, attendance_url)
        if claim is None:
            logger.warning(f"{site} 签到失败，未找到每日奖励领取表单")
            return False, "签到失败，未找到每日奖励领取表单"
        claim_url, claim_data = claim

        post_headers = {
            **headers,
            "Origin": f"{urlparse(attendance_url).scheme}://{urlparse(attendance_url).netloc}",
            "Referer": attendance_url,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        claim_response = RequestUtils(
            headers=post_headers,
            cookies=request_cookies,
            session=session,
            proxies=proxies,
            timeout=timeout,
        ).post_res(url=claim_url, data=claim_data)
        failure = self._response_failure(site, claim_response, "提交签到请求")
        if failure:
            return failure

        self._merge_response_cookies(request_cookies, session)
        claim_html = claim_response.text or ""
        if not SiteUtils.is_logged_in(claim_html):
            logger.warning(f"{site} 签到失败，Cookie已失效")
            return False, "签到失败，Cookie已失效"
        if self._attendance_state(claim_html) == "claimed":
            logger.info(f"{site} 签到成功")
            return True, self._claimed_message(claim_html)

        verify_response = RequestUtils(
            headers=headers,
            cookies=request_cookies,
            session=session,
            proxies=proxies,
            timeout=timeout,
        ).get_res(url=attendance_url)
        failure = self._response_failure(site, verify_response, "复查签到结果")
        if failure:
            return failure

        verify_html = verify_response.text or ""
        if not SiteUtils.is_logged_in(verify_html):
            logger.warning(f"{site} 签到结果未确认，Cookie已失效")
            return False, "签到失败，Cookie已失效"
        if self._attendance_state(verify_html) == "claimed":
            logger.info(f"{site} 签到成功（已复查确认）")
            return True, self._claimed_message(verify_html)

        logger.warning(f"{site} 签到结果未确认，领取表单仍存在")
        return False, "签到失败，签到结果未确认"

    def login(self, site_info: CommentedMap) -> Tuple[bool, str]:
        site = site_info.get("name")
        attendance_url = self._attendance_url(site_info.get("url"))
        response = RequestUtils(
            headers=self._page_headers(site_info.get("ua"), attendance_url),
            cookies=site_info.get("cookie"),
            proxies=settings.PROXY if site_info.get("proxy") else None,
            timeout=site_info.get("timeout") or self._request_timeout,
        ).get_res(url=attendance_url)
        failure = self._response_failure(site, response, "打开登录验证页面", login=True)
        if failure:
            return failure
        if not SiteUtils.is_logged_in(response.text or ""):
            logger.warning(f"{site} 模拟登录失败，Cookie已失效")
            return False, "模拟登录失败，Cookie已失效"
        logger.info(f"{site} 模拟登录成功")
        return True, "模拟登录成功"

    @staticmethod
    def _attendance_url(site_url: str) -> str:
        raw_url = str(site_url or "https://retrotoon.world").strip()
        if not raw_url.startswith(("http://", "https://")):
            raw_url = "https://" + raw_url
        parsed = urlparse(raw_url)
        return f"{parsed.scheme}://{parsed.netloc}/attendance.php"

    @staticmethod
    def _page_headers(ua: str, attendance_url: str) -> dict:
        return {
            "User-Agent": ua or settings.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": attendance_url,
        }

    @staticmethod
    def _merge_response_cookies(request_cookies: dict, session) -> None:
        request_cookies.update(session.cookies.get_dict())

    @staticmethod
    def _response_failure(site: str, response, action: str,
                          login: bool = False) -> Optional[Tuple[bool, str]]:
        prefix = "模拟登录失败" if login else "签到失败"
        if response is None:
            logger.warning(f"{site} {action}失败，网络请求失败或超时")
            return False, f"{prefix}，网络请求失败或超时"
        if response.status_code == 429:
            logger.warning(f"{site} {action}失败，站点请求过于频繁（HTTP 429）")
            return False, f"{prefix}，站点请求过于频繁（HTTP 429），请稍后重试"
        if response.status_code != 200:
            logger.warning(f"{site} {action}失败，状态码：{response.status_code}")
            return False, f"{prefix}，状态码：{response.status_code}"
        return None

    @staticmethod
    def _extract_claim_request(html_text: str, attendance_url: str) -> Optional[Tuple[str, Dict[str, str]]]:
        html = etree.HTML(html_text or "")
        if html is None:
            return None
        forms = html.xpath(
            '//form[.//*[@name="claim" and (self::input or self::button)]]'
        )
        if not forms:
            return None
        form = forms[0]
        data = {}
        for field in form.xpath(
            './/*[self::input or self::button][@name and not(@disabled)]'
        ):
            name = field.get("name")
            if not name:
                continue
            data[name] = field.get("value") or " ".join(field.itertext()).strip()
        if not data.get("csrf_token") or "claim" not in data:
            return None
        return urljoin(attendance_url, form.get("action") or attendance_url), data

    @classmethod
    def _attendance_state(cls, html_text: str) -> str:
        html = etree.HTML(html_text or "")
        if html is None:
            return "unknown"
        if html.xpath('//form[.//*[@name="claim" and (self::input or self::button)]]'):
            return "unclaimed"
        today_cells = html.xpath(
            '//*[contains(concat(" ", normalize-space(@class), " "), " att-cal-cell--today ")]'
        )
        if any(
            " att-cal-cell--claimed " in f" {' '.join((cell.get('class') or '').split())} "
            or cell.xpath('.//*[contains(concat(" ", normalize-space(@class), " "), " att-cal-claimed-tag ")]')
            for cell in today_cells
        ):
            return "claimed"
        reward_cards = html.xpath(
            '//*[contains(concat(" ", normalize-space(@class), " "), " rt-form-card ")]'
            '[.//*[contains(normalize-space(string(.)), "Daily Reward")]]'
        )
        reward_text = " ".join(" ".join(card.itertext()) for card in reward_cards).lower()
        if any(marker in reward_text for marker in (
            "already claimed", "claimed today", "reward claimed",
            "reward already collected", "come back tomorrow",
        )):
            return "claimed"
        return "unknown"

    @classmethod
    def _claimed_message(cls, html_text: str, already: bool = False) -> str:
        html = etree.HTML(html_text or "")
        if html is not None:
            today_cells = html.xpath(
                '//*[contains(concat(" ", normalize-space(@class), " "), " att-cal-cell--today ")]'
            )
            if today_cells:
                reward = " ".join(" ".join(today_cells[0].itertext()).split())
                if reward:
                    return ("今日已签到" if already else "签到成功") + f" | {reward}"
        return "今日已签到" if already else "签到成功"
