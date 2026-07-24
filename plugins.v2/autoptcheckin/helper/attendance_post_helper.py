# input: 无验证码 attendance.php 站点 Cookie、UA、代理配置
# output: NexusPHP attendance.php 空 POST 签到通用处理器
# pos: helper 层，供纯 POST 站点适配器复用；不直接被 ModuleHelper 加载
from typing import Tuple

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

    @classmethod
    def match(cls, url: str) -> bool:
        return StringUtils.url_equal(url, cls.site_url)

    def signin(self, site_info: CommentedMap) -> Tuple[bool, str]:
        site = site_info.get("name")
        site_cookie = site_info.get("cookie")
        ua = site_info.get("ua")
        proxies = settings.PROXY if site_info.get("proxy") else None

        res = RequestUtils(
            cookies=site_cookie,
            ua=ua,
            referer=self._signin_url,
            proxies=proxies,
        ).post_res(url=self._signin_url, data={})
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
