# input: DarkLand 站点 Cookie、UA、代理配置
# output: 浏览器指纹模拟登录结果
# pos: AutoPtCheckin 站点适配层；DarkLand 仅执行登录访问，不提供独立签到流程
from typing import Tuple

from lxml import etree
from ruamel.yaml import CommentedMap

from app.core.config import settings
from app.helper.cloudflare import under_challenge
from app.log import logger
from app.plugins.autoptcheckin.sites import _ISiteSigninHandler
from app.utils.site import SiteUtils


class DarkLand(_ISiteSigninHandler):
    """DarkLand 使用浏览器指纹访问首页，并按退出表单确认登录态。"""

    site_url = "darkland.top"

    def signin(self, site_info: CommentedMap) -> Tuple[bool, str]:
        """站点没有独立签到流程，签到入口复用模拟登录。"""
        return self.login(site_info)

    def login(self, site_info: CommentedMap) -> Tuple[bool, str]:
        site = site_info.get("name")
        site_url = str(site_info.get("url") or "https://darkland.top").rstrip("/") + "/"
        try:
            from app.plugins.autoptcheckin.helper.http_helper import CffiClient

            status, page_text = CffiClient(
                cookie=site_info.get("cookie") or "",
                ua=site_info.get("ua") or settings.USER_AGENT,
                proxy=settings.PROXY_SERVER if site_info.get("proxy") else None,
                referer=site_url,
            ).get(site_url, timeout=site_info.get("timeout") or 60)
        except Exception as error:
            logger.warning(f"{site} 模拟登录失败，网络请求异常：{error}")
            return False, "模拟登录失败，网络请求失败或超时"

        if status == 0:
            logger.warning(f"{site} 模拟登录失败，网络请求失败或超时")
            return False, "模拟登录失败，网络请求失败或超时"
        if status == 429:
            logger.warning(f"{site} 模拟登录失败，站点请求过于频繁（HTTP 429），请稍后重试")
            return False, "模拟登录失败，站点请求过于频繁（HTTP 429），请稍后重试"
        if status != 200:
            logger.warning(f"{site} 模拟登录失败，状态码：{status}")
            return False, f"模拟登录失败，状态码：{status}"

        if SiteUtils.is_logged_in(page_text):
            logger.info(f"{site} 模拟登录成功")
            return True, "模拟登录成功"
        if under_challenge(page_text):
            logger.warning(f"{site} 模拟登录失败，站点被Cloudflare防护")
            return False, "模拟登录失败，站点被Cloudflare防护，请稍后重试"
        if self._has_login_form(page_text):
            logger.warning(f"{site} 模拟登录失败，Cookie已失效")
            return False, "模拟登录失败，Cookie已失效"

        logger.warning(f"{site} 模拟登录失败，登录状态未确认")
        return False, "模拟登录失败，登录状态未确认"

    @staticmethod
    def _has_login_form(page_text: str) -> bool:
        try:
            tree = etree.HTML(page_text or "")
            return bool(tree is not None and tree.xpath(
                '//input[@type="password"] | //form[contains(@action,"login")]'
            ))
        except Exception:
            return False
