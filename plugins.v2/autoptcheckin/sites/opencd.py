import json
import time
from typing import Tuple

from lxml import etree
from ruamel.yaml import CommentedMap

from app.core.config import settings
from app.log import logger
from app.plugins.autoptcheckin.helper.ocr_helper import recognize_captcha
from app.plugins.autoptcheckin.sites import _ISiteSigninHandler
from app.utils.http import RequestUtils
from app.utils.string import StringUtils


class Opencd(_ISiteSigninHandler):
    """
    皇后ocr签到
    """
    site_url = "open.cd"
    _repeat_text = "/plugin_sign-in.php?cmd=show-log"

    @classmethod
    def match(cls, url: str) -> bool:
        return True if StringUtils.url_equal(url, cls.site_url) else False

    def signin(self, site_info: CommentedMap) -> Tuple[bool, str]:
        site = site_info.get("name")
        site_cookie = site_info.get("cookie")
        ua = site_info.get("ua")
        proxy = site_info.get("proxy")
        render = site_info.get("render")

        # 判断今日是否已签到
        html_text = self.get_page_source(url='https://www.open.cd',
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

        if self._repeat_text in html_text:
            logger.info(f"{site} 今日已签到")
            return True, '今日已签到'

        # 获取签到页面
        html_text = self.get_page_source(url='https://www.open.cd/plugin_sign-in.php',
                                         cookie=site_cookie,
                                         ua=ua,
                                         proxy=proxy,
                                         render=render)
        if not html_text:
            logger.error(f"{site} 签到失败，请检查站点连通性")
            return False, '签到失败，请检查站点连通性'

        html = etree.HTML(html_text)
        if not html:
            return False, '签到失败'

        img_url_path = html.xpath('//form[@id="frmSignin"]//img/@src')
        img_hash_list = html.xpath('//form[@id="frmSignin"]//input[@name="imagehash"]/@value')
        if not img_url_path or not img_hash_list:
            logger.error(f"{site} 签到失败，获取签到参数失败")
            return False, '签到失败，获取签到参数失败'

        img_get_url = 'https://www.open.cd/%s' % img_url_path[0]
        img_hash = img_hash_list[0]
        logger.debug(f"{site} 验证码链接: {img_get_url}")

        # ddddocr 优先（内部多次重试取众数），失败后切换 OcrHelper
        ocr_result = recognize_captcha(
            image_url=img_get_url,
            cookie=site_cookie,
            ua=ua,
            min_len=6,
            retry_times=3,
            engine='ddddocr',
        )
        if not ocr_result or len(ocr_result) != 6:
            logger.info(f"{site} ddddocr 识别失败，切换 OcrHelper")
            ocr_result = recognize_captcha(
                image_url=img_get_url,
                cookie=site_cookie,
                ua=ua,
                min_len=6,
                engine='ocrhelper',
            )
            if ocr_result and len(ocr_result) != 6:
                ocr_result = None

        if not ocr_result:
            logger.error(f'{site} 签到失败：所有引擎均无法识别验证码')
            return False, '签到失败：验证码识别失败'

        logger.info(f"{site} 验证码识别成功: {ocr_result}")
        sign_res = RequestUtils(
            cookies=site_cookie,
            ua=ua,
            proxies=settings.PROXY if proxy else None,
        ).post_res(
            url='https://www.open.cd/plugin_sign-in.php?cmd=signin',
            data={'imagehash': img_hash, 'imagestring': ocr_result},
        )
        if sign_res and sign_res.status_code == 200:
            logger.debug(f"sign_res返回 {sign_res.text}")
            sign_dict = json.loads(sign_res.text)
            if sign_dict['state']:
                logger.info(f"{site} 签到成功")
                return True, '签到成功'
            logger.error(f"{site} 签到失败，签到接口返回 {sign_dict}")
            return False, '签到失败'

        logger.error(f'{site} 签到失败：签到接口请求失败')
        return False, '签到失败'
