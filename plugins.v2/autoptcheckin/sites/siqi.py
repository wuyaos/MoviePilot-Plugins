import re
from typing import Tuple
from urllib.parse import urljoin

from ruamel.yaml import CommentedMap

from app.log import logger
from app.plugins.autoptcheckin.sites import _ISiteSigninHandler
from app.utils.string import StringUtils


class SiQi(_ISiteSigninHandler):
    """
    思齐 OCR 验证码签到：ddddocr 优先，失败后切换 OcrHelper
    """
    site_url = "si-qi.xyz"

    _succeed_regex = [
        r'这是您的第.*?次签到，已连续签到.*?天',
        r'您今天已经签到过了',
        r'attend-success-effect',
    ]

    @classmethod
    def match(cls, url: str) -> bool:
        return True if StringUtils.url_equal(url, cls.site_url) else False

    def signin(self, site_info: CommentedMap) -> Tuple[bool, str]:
        site = site_info.get("name")
        site_cookie = site_info.get("cookie")
        ua = site_info.get("ua")

        try:
            from app.plugins.autoptcheckin.helper.http_helper import CffiClient
            from app.plugins.autoptcheckin.helper.ocr_helper import recognize_captcha
        except ImportError as e:
            return False, f'签到失败：依赖缺失 {e}'

        client = CffiClient(cookie=site_cookie, ua=ua)

        # 1. GET 签到页
        status, html = client.get("https://si-qi.xyz/attendance.php")
        if not html:
            return False, '签到失败，请检查站点连通性'
        if "login.php" in html:
            return False, '签到失败，Cookie已失效'

        if self.sign_in_result(html, self._succeed_regex):
            logger.info(f"{site} 今日已签到")
            return True, '今日已签到'

        # 2. 提取 imagehash + 验证码图片
        hash_m = re.search(r'name="imagehash" value="([^"]+)"', html)
        img_m = re.search(r'<img[^>]*src="([^"]*image\.php[^"]*)"', html)
        if not hash_m or not img_m:
            return False, '签到失败，获取验证码参数失败'

        image_hash = hash_m.group(1)
        img_url = urljoin("https://si-qi.xyz/", img_m.group(1).replace("&amp;", "&"))

        # 3. 下载图片（ddddocr 用 bytes；OcrHelper 用 URL）
        img_bytes = client.get_bytes(img_url)
        if not img_bytes:
            return False, '签到失败，获取验证码图片失败'

        # ddddocr 优先（内部多次重试），失败后切换 OcrHelper
        code = recognize_captcha(
            image_bytes=img_bytes,
            image_url=img_url,
            cookie=site_cookie,
            ua=ua,
            min_len=4,
            engine='ddddocr',
        )
        if not code:
            logger.info(f"{site} ddddocr 识别失败，切换 OcrHelper")
            code = recognize_captcha(
                image_url=img_url,
                cookie=site_cookie,
                ua=ua,
                min_len=4,
                engine='ocrhelper',
            )

        if not code:
            return False, '签到失败，验证码识别失败'
        logger.info(f"{site} 验证码识别: {code}")

        # 4. POST 提交
        status, resp_text = client.post(
            "https://si-qi.xyz/attendance.php",
            data={"imagehash": image_hash, "imagestring": code},
        )
        if not resp_text:
            return False, '签到失败，提交签到请求失败'

        if self.sign_in_result(resp_text, self._succeed_regex):
            logger.info(f"{site} 签到成功")
            return True, '签到成功'

        return False, '签到失败'
