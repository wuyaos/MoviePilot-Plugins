# input: DStudio 站点 Cookie、UA、代理配置与 MoviePilot RequestUtils
# output: DStudio attendance.php POST 签到处理器
# pos: AutoPtCheckin 站点适配层，纯 POST 签到（无验证码）
from typing import Tuple

from ruamel.yaml import CommentedMap

from app.core.config import settings
from app.log import logger
from app.plugins.autoptcheckin.sites import _ISiteSigninHandler
from app.utils.http import RequestUtils
from app.utils.site import SiteUtils
from app.utils.string import StringUtils


class DStudio(_ISiteSigninHandler):
    """
    DStudio（Depth Studio）签到：attendance.php 表单无验证码，POST 即签到。
    站点基于 NexusPHP，签到成功文案与通用 attendance 一致。
    """
    site_url = "dstudio.me"

    _success_texts = ["签到成功", "签到已得", "获得", "连续签到"]
    _repeat_texts = ["今天已经签到过", "请勿重复刷新", "已经签到", "今天已签到"]

    @classmethod
    def match(cls, url: str) -> bool:
        return True if StringUtils.url_equal(url, cls.site_url) else False

    def signin(self, site_info: CommentedMap) -> Tuple[bool, str]:
        site = site_info.get("name")
        site_cookie = site_info.get("cookie")
        ua = site_info.get("ua")
        proxies = settings.PROXY if site_info.get("proxy") else None

        res = RequestUtils(
            cookies=site_cookie,
            ua=ua,
            referer="https://dstudio.me/attendance.php",
            proxies=proxies,
        ).post_res(url="https://dstudio.me/attendance.php", data={})
        if not res or res.status_code != 200:
            logger.error(f"{site} 签到失败，请检查站点连通性")
            return False, "签到失败，请检查站点连通性"

        html_text = res.text or ""
        if not SiteUtils.is_logged_in(html_text) or "login.php" in html_text:
            logger.error(f"{site} 签到失败，Cookie已失效")
            return False, "签到失败，Cookie已失效"

        if any(text in html_text for text in self._repeat_texts):
            logger.info(f"{site} 今日已签到")
            return True, "今日已签到"
        if any(text in html_text for text in self._success_texts):
            logger.info(f"{site} 签到成功")
            return True, "签到成功"

        logger.error(f"{site} 签到失败，签到接口返回 {html_text[:200]}")
        return False, "签到失败"
