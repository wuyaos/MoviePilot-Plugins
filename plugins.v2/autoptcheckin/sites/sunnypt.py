# input: SunnyPT 站点 Cookie（含 AuthSession JWT）、UA、代理配置与 MoviePilot RequestUtils
# output: SunnyPT REST API 签到处理器
# pos: AutoPtCheckin 站点适配层，Next.js 前端 + Bearer JWT 鉴权，非 NexusPHP attendance.php
import base64
import json
import re
from typing import Tuple

from ruamel.yaml import CommentedMap

from app.core.config import settings
from app.log import logger
from app.plugins.autoptcheckin.sites import _ISiteSigninHandler
from app.utils.http import RequestUtils
from app.utils.string import StringUtils


class SunnyPT(_ISiteSigninHandler):
    """
    SunnyPT 签到：Next.js 前端 + 独立 REST API（https://api.sunnypt.top），Bearer JWT 鉴权。

    cookie 中的 AuthSession 为外层 JWT，其 payload 含 accessToken 字段；
    用 accessToken 作为 Bearer Token 调用 /api/v1/attendance/check-in 完成每日签到。
    API 不接受 Cookie 鉴权，必须用 Bearer Token。
    """
    site_url = "sunnypt.top"

    _api_base = "https://api.sunnypt.top"
    _signin_url = f"{_api_base}/api/v1/attendance/check-in"

    @classmethod
    def match(cls, url: str) -> bool:
        return True if StringUtils.url_equal(url, cls.site_url) else False

    @staticmethod
    def _extract_access_token(cookie: str) -> str:
        """从 Cookie 提取 AuthSession JWT 并解码出 accessToken"""
        if not cookie:
            return ""
        m = re.search(r"AuthSession=([^;]+)", cookie, re.IGNORECASE)
        if not m:
            return ""
        auth_session = m.group(1).strip()
        parts = auth_session.split(".")
        if len(parts) < 2:
            return ""
        payload_b64 = parts[1]
        # JWT base64url，补齐 padding
        payload_b64 += "=" * (-len(payload_b64) % 4)
        try:
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            return payload.get("accessToken", "") or ""
        except Exception as e:
            logger.error(f"SunnyPT 解码 AuthSession 失败：{e}")
            return ""

    def signin(self, site_info: CommentedMap) -> Tuple[bool, str]:
        site = site_info.get("name")
        site_cookie = site_info.get("cookie")
        ua = site_info.get("ua")
        proxies = settings.PROXY if site_info.get("proxy") else None

        token = self._extract_access_token(site_cookie)
        if not token:
            logger.error(f"{site} 签到失败，Cookie 中未找到有效的 AuthSession")
            return False, "签到失败，Cookie已失效"

        res = RequestUtils(
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": ua,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            proxies=proxies,
            referer="https://sunnypt.top/user/attendance",
        ).post_res(url=self._signin_url, data={})
        if not res or res.status_code != 200:
            logger.error(f"{site} 签到失败，请检查站点连通性")
            return False, "签到失败，请检查站点连通性"

        try:
            ret = res.json()
        except Exception:
            logger.error(f"{site} 签到失败，签到接口返回 {res.text[:200]}")
            return False, "签到失败"

        code = ret.get("code")
        msg = ret.get("msg", "") or ""
        if code == 0:
            logger.info(f"{site} 签到成功")
            return True, "签到成功"
        # 400001: 今天已经签到过了
        if code == 400001 or "已经签到" in msg or "已签到" in msg:
            logger.info(f"{site} 今日已签到")
            return True, "今日已签到"
        # 400000: 用户未登录 / Token 失效
        if code == 400000 or "未登录" in msg:
            logger.error(f"{site} 签到失败，Cookie已失效")
            return False, "签到失败，Cookie已失效"

        logger.error(f"{site} 签到失败，{msg}（code={code}）")
        return False, f"签到失败，{msg}"
