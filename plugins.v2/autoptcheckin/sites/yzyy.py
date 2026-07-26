# input: yzyy 论坛站点 Cookie、UA、代理配置
# output: yzyy Discuz zqlj_sign 动态签到码签到结果
# pos: AutoPtCheckin 站点适配层，独立专用适配器，不复用 NexusPHP attendance 通用基类
import re
from typing import Optional, Tuple
from urllib.parse import urlparse

import requests as _requests
from lxml import etree
from ruamel.yaml import CommentedMap

from app.core.config import settings
from app.log import logger
from app.plugins.autoptcheckin.sites import _ISiteSigninHandler
from app.utils.http import RequestUtils


class Yzyy(_ISiteSigninHandler):
    """yzyy 论坛签到：Discuz zqlj_sign 插件动态签到码。

    独立专用适配器，不复用 NexusPHP attendance.php 通用基类。
    需要同一 HTTP Session 贯穿签到页与签到请求，保证服务端临时会话连续，
    否则 zqlj_sign 的 sign token 会因 session 不一致而静默失效。
    """

    site_url = "yzyy.org"
    _request_timeout = 30

    def signin(self, site_info: CommentedMap) -> Tuple[bool, str]:
        site = site_info.get("name")
        site_cookie = site_info.get("cookie")
        ua = site_info.get("ua") or settings.USER_AGENT
        proxy = settings.PROXY if site_info.get("proxy") else None
        site_url = self._normalize_site_url(site_info.get("url"))

        session = _requests.Session()
        sign_page_url = self._sign_page_url(site_url)
        headers = self._build_headers(ua, sign_page_url)

        # 1. 获取签到页
        page_html = self._fetch_page(
            url=sign_page_url, cookie=site_cookie, headers=headers,
            session=session, proxy=proxy,
        )
        if page_html is None:
            logger.error(f"{site} 签到失败，获取签到页面失败")
            return False, "签到失败，获取签到页面失败"

        # 2. 检查登录状态
        if self._is_not_logged_in(page_html):
            logger.error(f"{site} 签到失败，Cookie已失效")
            return False, "签到失败，Cookie已失效"

        # 3. 检查当前用户签到按钮状态
        button_status = self._check_sign_button_status(page_html)
        if button_status == "already_signed":
            info = self._extract_reward_info(page_html)
            logger.info(f"{site} 今日已签到")
            return True, "今日已签到" + (f" | {info}" if info else "")

        # 4. 提取动态签到链接（仅从当前用户 .signbtn 区域）
        sign_url = self._extract_sign_url(page_html, site_url)
        if not sign_url:
            logger.error(f"{site} 签到失败，未找到签到链接")
            return False, "签到失败，未找到签到链接"

        # 5. 执行签到请求（沿用同一 Session，保证 sign token 有效）
        result_html = self._fetch_page(
            url=sign_url, cookie=site_cookie,
            headers={**headers, "referer": sign_page_url},
            session=session, proxy=proxy,
        )
        if result_html is None:
            logger.error(f"{site} 签到失败，签到请求失败")
            return False, "签到失败，签到请求失败"
        if self._is_not_logged_in(result_html):
            logger.error(f"{site} 签到失败，Cookie已失效")
            return False, "签到失败，Cookie已失效"

        # 6. 判断签到结果
        success, info = self._parse_sign_result(result_html)
        if success:
            logger.info(f"{site} 签到成功：{info}")
            return True, f"签到成功：{info}" if info else "签到成功"
        logger.error(f"{site} 签到失败：{info}")
        return False, f"签到失败：{info}"

    @staticmethod
    def _normalize_site_url(site_url: str) -> str:
        """规范化站点地址，仅保留 scheme 与 netloc，避免配置带 path 干扰。"""
        site_url = (site_url or "").strip().rstrip("/")
        if not site_url:
            return "https://yzyy.org"
        if not site_url.startswith(("http://", "https://")):
            site_url = "https://" + site_url
        if site_url.startswith("http://"):
            site_url = "https://" + site_url[len("http://"):]
        parsed = urlparse(site_url)
        return f"{parsed.scheme}://{parsed.netloc}"

    @staticmethod
    def _sign_page_url(site_url: str) -> str:
        return f"{site_url}/plugin.php?id=zqlj_sign"

    @staticmethod
    def _build_headers(ua: str, sign_page_url: str) -> dict:
        return {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "referer": sign_page_url,
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "upgrade-insecure-requests": "1",
            "user-agent": ua,
        }

    @staticmethod
    def _fetch_page(url: str, cookie: str, headers: dict, session, proxy) -> Optional[str]:
        try:
            res = RequestUtils(
                headers=headers,
                cookies=cookie,
                timeout=30,
                session=session,
                proxies=proxy,
            ).get_res(url=url)
            if not res or res.status_code != 200:
                return None
            return res.text
        except Exception as e:
            logger.error(f"请求页面异常：{e}")
            return None

    @staticmethod
    def _is_not_logged_in(html: str) -> bool:
        keywords = ["请登录", "需要先登录", "请先登录", "未登录", "您还没有登录"]
        return any(keyword in (html or "") for keyword in keywords)

    @staticmethod
    def _extract_sign_button_area(html: str) -> str:
        """提取当前用户签到按钮 .signbtn 区域。"""
        try:
            tree = etree.HTML(html or "")
            nodes = tree.xpath('//div[contains(concat(" ", normalize-space(@class), " "), " signbtn ")]')
            if nodes:
                return etree.tostring(nodes[0], encoding="unicode", method="html")
        except Exception as e:
            logger.warning(f"解析签到按钮区域失败：{e}")
        return ""

    def _check_sign_button_status(self, html: str) -> str:
        """返回 already_signed / need_sign / unknown。"""
        button_area = self._extract_sign_button_area(html)
        if not button_area:
            logger.warning("未找到 .signbtn 签到按钮区域，无法判断当前用户签到状态")
            return "unknown"
        if "今日已打卡" in button_area:
            return "already_signed"
        if "点击打卡" in button_area:
            return "need_sign"
        return "unknown"

    def _extract_sign_url(self, html: str, site_url: str) -> Optional[str]:
        """从当前用户签到按钮区域提取动态签到链接。"""
        button_area = self._extract_sign_button_area(html)
        if not button_area:
            return None
        match = re.search(
            r'<a[^>]*href=["\']([^"\']*plugin\.php\?id=zqlj_sign&(?:amp;)?sign=[a-f0-9]{8}[^"\']*)["\']',
            button_area, re.I | re.S,
        )
        if not match:
            return None
        sign_url = match.group(1).replace("&amp;", "&")
        if sign_url.startswith("http"):
            return sign_url
        if sign_url.startswith("/"):
            return f"{site_url}{sign_url}"
        return f"{site_url}/{sign_url}"

    def _parse_sign_result(self, html: str) -> Tuple[bool, str]:
        """优先看签到请求响应里的明确提示，按钮状态仅作兜底。"""
        try:
            if html and "打卡成功" in html:
                info = self._extract_reward_info(html) or "打卡成功"
                return True, info
            if html and "恭喜" in html and "打卡" in html:
                return True, "打卡成功"
            if html and ("请勿重复" in html or "已经打卡" in html):
                info = self._extract_reward_info(html)
                return True, info or "今日已打卡"
            if html and ("签到失败" in html or "打卡失败" in html):
                return False, "签到失败"
            button_status = self._check_sign_button_status(html)
            if button_status == "already_signed":
                info = self._extract_reward_info(html)
                return True, info or "今日已打卡"
            if button_status == "need_sign":
                return False, "签到后按钮仍显示点击打卡"
            return False, "无法识别签到结果"
        except Exception as e:
            return False, f"解析签到结果异常：{str(e)}"

    def _extract_reward_info(self, html: str) -> str:
        """提取当前用户签到奖励信息，优先限定在我的记录区域。"""
        try:
            import html as html_module
            html = html_module.unescape(html or "")
            my_area = self._extract_my_record_area(html)
            if my_area:
                html = my_area
            info_parts = []
            recent_match = re.search(r"最近奖励[：:]\s*([\d.]+)\s*影币", html)
            if recent_match:
                info_parts.append(f"获得 {recent_match.group(1).strip()} 影币")
            else:
                total_match = re.search(r"累计奖励[：:]\s*([\d.]+)\s*影币", html)
                if total_match:
                    info_parts.append(f"累计 {total_match.group(1).strip()} 影币")
            continuous_match = re.search(r"连续打卡[：:]\s*([\d.]+)\s*天", html)
            if continuous_match:
                info_parts.append(f"连续 {continuous_match.group(1).strip()} 天")
            total_days_match = re.search(r"累计打卡[：:]\s*([\d.]+)\s*天", html)
            if total_days_match:
                info_parts.append(f"累计 {total_days_match.group(1).strip()} 天")
            month_match = re.search(r"本月打卡[：:]\s*([\d.]+)\s*天", html)
            if month_match:
                info_parts.append(f"本月 {month_match.group(1).strip()} 天")
            level_match = re.search(r"当前打卡等级[：:]\s*([^\s<]+)", html)
            if level_match:
                info_parts.append(f"等级: {level_match.group(1).strip()}")
            if not info_parts:
                if "影币" in html:
                    info_parts.append("签到成功")
                else:
                    return ""
            return " | ".join(info_parts)
        except Exception as e:
            logger.error(f"提取奖励信息异常：{e}")
            return ""

    @staticmethod
    def _extract_my_record_area(html: str) -> str:
        """提取我的记录区域，避免从排行榜提取其他用户奖励。"""
        html = html or ""
        match = re.search(r'<tbody[^>]*id=["\']tb_my["\'][^>]*>(.*?)</tbody>', html, re.I | re.S)
        if match:
            return match.group(1)
        match = re.search(r'<div[^>]*id=["\']ct_mine["\'][^>]*>(.*?)</div>', html, re.I | re.S)
        if match:
            return match.group(1)
        return ""
