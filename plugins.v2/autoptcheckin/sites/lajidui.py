# input: 垃圾堆 Cookie、UA、代理配置与 attendance.php 验证码表单
# output: 垃圾堆签到处理器，自动识别验证码并提交签到
# pos: AutoPtCheckin 站点适配层，处理 NexusPHP 验证码签到页
from typing import Tuple
from urllib.parse import urljoin

from lxml import etree
from ruamel.yaml import CommentedMap

from app.core.config import settings
from app.log import logger
from app.plugins.autoptcheckin.helper.ocr_helper import recognize_captcha
from app.plugins.autoptcheckin.sites import _ISiteSigninHandler
from app.utils.string import StringUtils


class LaJiDui(_ISiteSigninHandler):
    """
    垃圾堆签到：attendance.php 展示验证码表单，需提交 imagehash + imagestring。
    """
    site_url = "pt.lajidui.top"

    _success_texts = ["签到成功", "签到已得", "获得", "连续签到"]
    _repeat_texts = ["今天已经签到过", "请勿重复刷新", "已经签到"]

    @classmethod
    def match(cls, url: str) -> bool:
        return True if StringUtils.url_equal(url, cls.site_url) else False

    def signin(self, site_info: CommentedMap) -> Tuple[bool, str]:
        site = site_info.get("name")
        site_cookie = site_info.get("cookie")
        ua = site_info.get("ua")
        proxy = site_info.get("proxy")

        try:
            from app.plugins.autoptcheckin.helper.http_helper import CffiClient
        except ImportError as e:
            return False, f"签到失败：依赖缺失 {e}"

        try:
            client = CffiClient(
                cookie=site_cookie,
                ua=ua,
                proxy=settings.PROXY_SERVER if proxy else None,
                referer="https://pt.lajidui.top/attendance.php",
            )
        except ImportError as e:
            return False, f"签到失败：依赖缺失 {e}"

        status, html_text = client.get("https://pt.lajidui.top/attendance.php")
        if status != 200:
            logger.error(f"{site} 签到失败，状态码：{status}")
            return False, f"签到失败，状态码：{status}"
        if not html_text:
            logger.error(f"{site} 签到失败，请检查站点连通性")
            return False, "签到失败，请检查站点连通性"
        if "login.php" in html_text:
            logger.error(f"{site} 签到失败，Cookie已失效")
            return False, "签到失败，Cookie已失效"
        if any(text in html_text for text in self._repeat_texts):
            logger.info(f"{site} 今日已签到")
            return True, "今日已签到"
        # 已签到页面可能直接显示签到结果文本而非重复提示
        if any(text in html_text for text in self._success_texts):
            logger.info(f"{site} 今日已签到（页面已显示签到结果）")
            return True, "今日已签到"

        html = etree.HTML(html_text)
        image_hash = ""
        image_src = ""
        if html is not None:
            hash_values = html.xpath('//input[@name="imagehash"]/@value')
            image_values = html.xpath('//form//img[contains(@src, "image.php")]/@src')
            image_hash = hash_values[0] if hash_values else ""
            image_src = image_values[0] if image_values else ""
        if not image_hash or not image_src:
            logger.error(f"{site} 签到失败，获取验证码参数失败")
            return False, "签到失败，获取验证码参数失败"

        image_url = urljoin("https://pt.lajidui.top/", image_src.replace("&amp;", "&"))
        image_bytes = client.get_bytes(image_url)
        if not image_bytes:
            logger.error(f"{site} 签到失败，获取验证码图片失败")
            return False, "签到失败，获取验证码图片失败"

        code = recognize_captcha(
            image_bytes=image_bytes,
            image_url=image_url,
            cookie=site_cookie,
            ua=ua,
            referer="https://pt.lajidui.top/attendance.php",
            min_len=4,
            max_len=6,
            retry_times=1,
            engine="ddddocr",
            charset="alnum",
            proxy=proxy,
        )
        if not code:
            logger.info(f"{site} ddddocr 识别失败，切换 OcrHelper")
            code = recognize_captcha(
                image_url=image_url,
                cookie=site_cookie,
                ua=ua,
                referer="https://pt.lajidui.top/attendance.php",
                min_len=4,
                max_len=6,
                engine="ocrhelper",
                charset="alnum",
                proxy=proxy,
            )
        if not code:
            logger.error(f"{site} 签到失败，验证码识别失败")
            return False, "签到失败：验证码识别失败"

        logger.info(f"{site} 验证码识别: {code}")
        status, resp_text = client.post(
            "https://pt.lajidui.top/attendance.php",
            data={"imagehash": image_hash, "imagestring": code},
        )
        if status != 200:
            logger.error(f"{site} 签到失败，状态码：{status}")
            return False, f"签到失败，状态码：{status}"
        if not resp_text:
            logger.error(f"{site} 签到失败，提交签到请求失败")
            return False, "签到失败，提交签到请求失败"
        if "login.php" in resp_text:
            logger.error(f"{site} 签到失败，Cookie已失效")
            return False, "签到失败，Cookie已失效"
        if any(text in resp_text for text in self._repeat_texts):
            logger.info(f"{site} 今日已签到")
            return True, "今日已签到"
        if any(text in resp_text for text in self._success_texts):
            logger.info(f"{site} 签到成功")
            return True, "签到成功"

        logger.error(f"{site} 签到失败，签到接口返回 {resp_text[:200]}")
        return False, "签到失败"
