# input: rousi.pro 站点 token、UA、代理配置
# output: rousi.pro API token 签到处理器
# pos: AutoPtCheckin 站点适配层，JWT Bearer token 调用签到 API
from typing import Tuple

from ruamel.yaml import CommentedMap

from app.core.config import settings
from app.log import logger
from app.plugins.autoptcheckin.sites import _ISiteSigninHandler
from app.utils.http import RequestUtils


class RousiPro(_ISiteSigninHandler):
    """rousi.pro 签到：使用站点配置的 JWT token 调用签到 API。

    token 来自 MP 站点配置的 token 字段（用户手动填入 Bearer token），
    非插件自动登录获取。
    """

    site_url = "rousi.pro"

    def signin(self, site_info: CommentedMap) -> Tuple[bool, str]:
        site = site_info.get("name")
        ua = site_info.get("ua")
        token = site_info.get("token")
        timeout = site_info.get("timeout")
        if not token or token.strip() == "":
            logger.error(f"{site} 签到失败，缺少 Authorization 信息")
            return False, "签到失败，缺少 Authorization 信息"

        headers = {
            "Content-Type": "application/json",
            "User-Agent": ua,
            "Accept": "application/json, text/plain, */*",
            "Authorization": token if token.startswith("Bearer ") else f"Bearer {token}"
        }
        body = {"mode": "fixed"}
        res = RequestUtils(
            headers=headers,
            timeout=timeout,
            proxies=settings.PROXY if site_info.get("proxy") else None,
        ).post_res(
            url="https://rousi.pro/api/points/attendance",
            json=body
        )

        if res is not None and res.status_code == 200 and res.json().get("code", -1) == 0:
            logger.info(f"{site} 签到成功")
            return True, "签到成功"
        elif res is not None and res.status_code == 400 and res.json().get("code", -1) == 1:
            logger.info(f"{site} 今日已签到")
            return True, "今日已签到"
        elif res is not None and res.status_code == 401:
            logger.error(f"{site} 签到失败，Authorization 已失效")
            return False, "签到失败，Authorization 已失效"
        elif res is not None:
            logger.error(f"{site} 签到失败，状态码：{res.status_code}")
            return False, f"签到失败，状态码：{res.status_code}"
        else:
            logger.error(f"{site} 签到失败，无法访问网站")
            return False, "签到失败，无法访问网站"

    def login(self, site_info: CommentedMap) -> Tuple[bool, str]:
        """模拟登录：访问签到统计接口更新站点最后活跃时间。"""
        site = site_info.get("name")
        ua = site_info.get("ua")
        token = site_info.get("token")
        timeout = site_info.get("timeout")
        if not token or token.strip() == "":
            logger.error(f"{site} 模拟登录失败，缺少 Authorization 信息")
            return False, "模拟登录失败，缺少 Authorization 信息"

        headers = {
            "User-Agent": ua,
            "Accept": "application/json, text/plain, */*",
            "Authorization": token if token.startswith("Bearer ") else f"Bearer {token}"
        }
        res = RequestUtils(
            headers=headers,
            timeout=timeout,
            proxies=settings.PROXY if site_info.get("proxy") else None,
        ).get_res(
            url="https://rousi.pro/api/points/attendance/stats"
        )

        if res is not None and res.status_code == 200 and res.json().get("code", -1) == 0:
            logger.info(f"{site} 模拟登录成功")
            return True, "模拟登录成功"
        elif res is not None and res.status_code == 401:
            logger.error(f"{site} 模拟登录失败，Authorization 已失效")
            return False, "模拟登录失败，Authorization 已失效"
        elif res is not None:
            logger.error(f"{site} 模拟登录失败，状态码：{res.status_code}")
            return False, f"模拟登录失败，状态码：{res.status_code}"
        else:
            logger.error(f"{site} 模拟登录失败，无法访问网站")
            return False, "模拟登录失败，无法访问网站"
