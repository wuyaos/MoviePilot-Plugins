# input: 憨憨站点 Cookie、UA、代理配置
# output: 憨憨 attendance.php GET 签到处理器
# pos: AutoPtCheckin 站点适配层，专属处理憨憨 Tailwind 前端站点的签到状态识别
from typing import Tuple

from lxml import etree
from ruamel.yaml import CommentedMap

from app.core.config import settings
from app.log import logger
from app.plugins.autoptcheckin.sites import _ISiteSigninHandler
from app.utils.http import RequestUtils
from app.utils.site import SiteUtils
from app.utils.string import StringUtils


class Hhanclub(_ISiteSigninHandler):
    """憨憨签到：attendance.php GET 即签到，站点 Tailwind 前端需带 Referer 才返回完整页。

    憨憨 attendance.php 无签到表单/按钮，访问即完成签到；
    站点对无 Referer 的请求只返回 Tailwind 框架壳，通用处理器会误判为"未确认"，
    因此专属适配器带 Referer 请求并识别「已连续签到/签到成功」文案。
    """

    site_url = "hhanclub.net"
    _signin_url = "https://hhanclub.net/attendance.php"
    # 憨憨签到成功与已签到文案（已连续签到N天，本次签到获得X个憨豆）
    _success_texts = ["签到成功", "本次签到获得", "已连续签到"]
    _repeat_texts = ["今天已经签到过", "今天已签到", "已经签到", "请勿重复刷新"]

    @classmethod
    def match(cls, url: str) -> bool:
        return StringUtils.url_equal(url, cls.site_url)

    def signin(self, site_info: CommentedMap) -> Tuple[bool, str]:
        site = site_info.get("name")
        site_cookie = site_info.get("cookie")
        ua = site_info.get("ua")
        proxies = settings.PROXY if site_info.get("proxy") else None
        timeout = site_info.get("timeout")

        # 憨憨站点对无 Referer 请求只返回 Tailwind 壳，必须显式带 Referer。
        headers = {
            "User-Agent": ua or settings.USER_AGENT,
            "Referer": "https://hhanclub.net/",
            "Cookie": site_cookie,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        res = RequestUtils(headers=headers, proxies=proxies,
                            timeout=timeout or 20).get_res(url=self._signin_url)
        if not res:
            logger.error(f"{site} 签到失败，请检查站点连通性")
            return False, "签到失败，请检查站点连通性"

        html_text = res.text or ""
        if res.status_code != 200:
            logger.warning(f"{site} 签到失败，状态码：{res.status_code}")
            return False, f"签到失败，状态码：{res.status_code}"

        if not SiteUtils.is_logged_in(html_text) or "login.php" in html_text:
            logger.error(f"{site} 签到失败，Cookie已失效")
            return False, "签到失败，Cookie已失效"

        # 憨憨 GET 访问即签到，识别页面文案判断签到结果
        if any(text in html_text for text in self._success_texts):
            logger.info(f"{site} 签到成功")
            return True, "签到成功"
        if any(text in html_text for text in self._repeat_texts):
            logger.info(f"{site} 今日已签到")
            return True, "今日已签到"

        # 兜底：页面异常短可能是站点返回了精简壳
        if len(html_text) < 2000:
            logger.warning(f"{site} 签到结果未确认，签到页可能改版")
            return False, "签到失败：签到结果未确认，签到页可能改版"
        logger.warning(f"{site} 签到结果未确认，签到页可能改版")
        return False, "签到失败：签到结果未确认，签到页可能改版"
