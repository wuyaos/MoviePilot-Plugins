# input: DigitalCore 站点 Cookie、UA、代理配置
# output: /api/v1/status 模拟登录结果
# pos: AutoPtCheckin 站点适配层；DigitalCore 首页为 SPA，不能使用通用 HTML 登录态判断
from typing import Tuple
from urllib.parse import urljoin

from ruamel.yaml import CommentedMap

from app.core.config import settings
from app.log import logger
from app.plugins.autoptcheckin.sites import _ISiteSigninHandler
from app.utils.http import RequestUtils


class DigitalCore(_ISiteSigninHandler):
    """DigitalCore 仅执行模拟登录，通过状态 API 确认 Cookie 登录态。"""

    site_url = "digitalcore.club"
    _status_path = "api/v1/status?timeSinceLastCheck=0"

    def signin(self, site_info: CommentedMap) -> Tuple[bool, str]:
        """站点没有独立签到流程，签到入口复用每日模拟登录。"""
        return self.login(site_info)

    def login(self, site_info: CommentedMap) -> Tuple[bool, str]:
        site = site_info.get("name")
        site_url = str(site_info.get("url") or "https://digitalcore.club").rstrip("/") + "/"
        status_url = urljoin(site_url, self._status_path)
        headers = {
            "User-Agent": site_info.get("ua") or settings.USER_AGENT,
            "Accept": "application/json",
            "Referer": site_url,
            "X-Requested-With": "XMLHttpRequest",
        }
        response = RequestUtils(
            headers=headers,
            cookies=site_info.get("cookie"),
            proxies=settings.PROXY if site_info.get("proxy") else None,
            timeout=site_info.get("timeout") or 20,
        ).get_res(url=status_url)

        if response is None:
            logger.warning(f"{site} 模拟登录失败，网络请求失败或超时")
            return False, "模拟登录失败，网络请求失败或超时"
        if response.status_code == 429:
            logger.warning(f"{site} 模拟登录失败，站点请求过于频繁（HTTP 429），请稍后重试")
            return False, "模拟登录失败，站点请求过于频繁（HTTP 429），请稍后重试"
        if response.status_code in (401, 403):
            logger.warning(f"{site} 模拟登录失败，Cookie已失效")
            return False, "模拟登录失败，Cookie已失效"
        if response.status_code != 200:
            logger.warning(f"{site} 模拟登录失败，状态码：{response.status_code}")
            return False, f"模拟登录失败，状态码：{response.status_code}"

        try:
            payload = response.json()
        except ValueError:
            logger.warning(f"{site} 模拟登录失败，状态接口返回非 JSON 数据")
            return False, "模拟登录失败，状态接口返回异常"

        user = payload.get("user") if isinstance(payload, dict) else None
        if not isinstance(user, dict) or not (user.get("id") or user.get("username")):
            logger.warning(f"{site} 模拟登录失败，Cookie已失效")
            return False, "模拟登录失败，Cookie已失效"

        logger.info(f"{site} 模拟登录成功")
        return True, "模拟登录成功"
