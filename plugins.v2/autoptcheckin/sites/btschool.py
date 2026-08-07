from typing import Tuple

from ruamel.yaml import CommentedMap

from app.log import logger
from app.plugins.autoptcheckin.sites import _ISiteSigninHandler


class BTSchool(_ISiteSigninHandler):
    """
    学校签到（curl-cffi 绕过 Cloudflare）
    """
    site_url = "pt.btschool.club"
    _sign_text = '每日签到'


    def signin(self, site_info: CommentedMap) -> Tuple[bool, str]:
        site = site_info.get("name")
        site_cookie = site_info.get("cookie")
        ua = site_info.get("ua")
        timeout = site_info.get("timeout") or 60

        try:
            from app.plugins.autoptcheckin.helper.http_helper import CffiClient
        except ImportError:
            # curl-cffi 不可用时回退原逻辑
            return self._signin_fallback(site_info)

        client = CffiClient(cookie=site_cookie, ua=ua)

        logger.info(f"{site} 开始签到 (curl-cffi)")
        # 判断今日是否已签到
        status, html_text = client.get('https://pt.btschool.club', timeout=timeout)
        if not html_text:
            return False, '签到失败，请检查站点连通性'
        if "login.php" in html_text:
            return False, '签到失败，Cookie已失效'

        # 已签到（页面无"每日签到"入口）
        if self._sign_text not in html_text:
            logger.info(f"{site} 今日已签到")
            return True, '今日已签到'

        # 执行签到
        status, html_text = client.get(
            'https://pt.btschool.club/index.php?action=addbonus', timeout=timeout
        )
        if not html_text:
            return False, '签到失败，签到接口请求失败'

        if self._sign_text not in html_text:
            logger.info(f"{site} 签到成功")
            return True, '签到成功'

        return False, '签到失败'

    def _signin_fallback(self, site_info: CommentedMap) -> Tuple[bool, str]:
        """curl-cffi 不可用时回退到原逻辑"""
        site = site_info.get("name")
        site_cookie = site_info.get("cookie")
        ua = site_info.get("ua")
        proxy = site_info.get("proxy")
        render = site_info.get("render")
        timeout = site_info.get("timeout")

        logger.info(f"{site} 开始签到 (fallback)")
        html_text = self.get_page_source(
            url='https://pt.btschool.club',
            cookie=site_cookie, ua=ua, proxy=proxy, render=render,
            timeout=timeout)
        if not html_text:
            return False, '签到失败，请检查站点连通性'
        if "login.php" in html_text:
            return False, '签到失败，Cookie已失效'
        if self._sign_text not in html_text:
            return True, '今日已签到'

        html_text = self.get_page_source(
            url='https://pt.btschool.club/index.php?action=addbonus',
            cookie=site_cookie, ua=ua, proxy=proxy, render=render,
            timeout=timeout)
        if not html_text:
            return False, '签到失败，签到接口请求失败'
        if self._sign_text not in html_text:
            return True, '签到成功'

        return False, '签到失败'
