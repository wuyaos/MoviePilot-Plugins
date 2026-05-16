import json
import time
from typing import Tuple, Optional

from ruamel.yaml import CommentedMap

from app.core.config import settings
from app.log import logger
from app.plugins.autoptcheckin.helper.ocr_helper import recognize_captcha
from app.plugins.autoptcheckin.sites import _ISiteSigninHandler
from app.utils.http import RequestUtils
from app.utils.string import StringUtils


class HDSky(_ISiteSigninHandler):
    """
    天空ocr签到：ddddocr 优先，失败后切换 OcrHelper，每轮获取新验证码
    """
    site_url = "hdsky.me"
    _sign_regex = ['已签到']

    @classmethod
    def match(cls, url: str) -> bool:
        return True if StringUtils.url_equal(url, cls.site_url) else False

    def signin(self, site_info: CommentedMap) -> Tuple[bool, str]:
        site = site_info.get("name")
        site_cookie = site_info.get("cookie")
        ua = site_info.get("ua")
        proxy = site_info.get("proxy")
        render = site_info.get("render")
        referer = site_info.get("url")

        # 判断今日是否已签到
        html_text = self.get_page_source(url='https://hdsky.me',
                                         cookie=site_cookie,
                                         ua=ua,
                                         proxy=proxy,
                                         render=render)
        if not html_text:
            logger.error(f"{site} 签到失败，请检查站点连通性")
            return False, '签到失败，请检查站点连通性'

        if "login.php" in html_text:
            logger.error(f"{site} 签到失败，Cookie已失效")
            return False, '签到失败，Cookie已失效'

        if self.sign_in_result(html_res=html_text, regexs=self._sign_regex):
            logger.info(f"{site} 今日已签到")
            return True, '今日已签到'

        # 按顺序尝试引擎：ddddocr → OcrHelper
        for engine in ('ddddocr', 'ocrhelper'):
            outcome = self._try_engine(engine, site, site_cookie, ua, proxy, referer)
            if outcome == 'success':
                logger.info(f"{site} 签到成功（引擎: {engine}）")
                return True, '签到成功'
            if outcome == 'already':
                return True, '今日已签到'
            if outcome == 'wrong_captcha':
                logger.warning(f"{site} {engine} 验证码错误，切换下一引擎")
                continue
            if outcome == 'no_result':
                logger.warning(f"{site} {engine} 识别无结果，切换下一引擎")
                continue
            # 'error' 或其他 — 不可重试的错误，直接失败
            return False, '签到失败'

        logger.error(f"{site} 所有引擎均未能识别验证码，签到失败")
        return False, '签到失败：验证码识别失败'

    # ------------------------------------------------------------------
    def _try_engine(self, engine: str, site: str, cookie: str,
                    ua: str, proxy: bool, referer: str) -> str:
        """
        使用指定引擎尝试一次签到。
        返回值: 'success' | 'already' | 'wrong_captcha' | 'no_result' | 'error'
        """
        img_hash = self._fetch_captcha_hash(site, cookie, ua, proxy)
        if not img_hash:
            return 'error'

        img_url = 'https://hdsky.me/image.php?action=regimage&imagehash=%s' % img_hash
        logger.info(f"{site} [{engine}] 验证码链接: {img_url}")

        code = recognize_captcha(
            image_url=img_url,
            cookie=cookie,
            ua=ua,
            min_len=6,
            retry_times=3,
            engine=engine,
        )
        if not code:
            return 'no_result'

        logger.info(f"{site} [{engine}] 识别结果: {code}")
        return self._submit(img_hash, code, cookie, ua, proxy, referer)

    def _fetch_captcha_hash(self, site: str, cookie: str,
                             ua: str, proxy: bool) -> Optional[str]:
        """获取验证码 hash，最多重试 3 次"""
        for attempt in range(1, 4):
            res = RequestUtils(
                cookies=cookie,
                ua=ua,
                content_type='application/x-www-form-urlencoded; charset=UTF-8',
                referer="https://hdsky.me/index.php",
                accept_type="*/*",
                proxies=settings.PROXY if proxy else None,
            ).post_res(url='https://hdsky.me/image_code_ajax.php', data={'action': 'new'})

            if res and res.status_code == 200:
                data = json.loads(res.text)
                if data.get("success"):
                    return data["code"]
            logger.info(f"获取 {site} 验证码失败，第 {attempt}/3 次重试")
            time.sleep(1)
        return None

    def _submit(self, img_hash: str, code: str, cookie: str,
                ua: str, proxy: bool, referer: str) -> str:
        """提交签到，返回语义结果字符串"""
        res = RequestUtils(
            cookies=cookie,
            ua=ua,
            referer=referer,
            proxies=settings.PROXY if proxy else None,
        ).post_res(
            url='https://hdsky.me/showup.php',
            data={'action': 'showup', 'imagehash': img_hash, 'imagestring': code},
        )
        if not res or res.status_code != 200:
            return 'error'

        resp = json.loads(res.text)
        if resp.get("success"):
            return 'success'
        msg = str(resp.get("message", ""))
        if msg == "date_unmatch":
            return 'already'
        if msg == "invalid_imagehash":
            return 'wrong_captcha'
        logger.warning(f"HDSky 未知响应: {resp}")
        return 'error'
