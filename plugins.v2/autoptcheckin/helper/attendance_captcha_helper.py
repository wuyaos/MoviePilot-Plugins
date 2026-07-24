# input: 站点 Cookie、UA、代理配置
# output: NexusPHP attendance.php 验证码签到通用基类
# pos: helper 层，供 site 适配子类复用；不直接被 ModuleHelper 加载
from typing import Tuple
from urllib.parse import urljoin

from lxml import etree
from ruamel.yaml import CommentedMap

from app.core.config import settings
from app.log import logger
from app.plugins.autoptcheckin.helper.http_helper import CffiClient
from app.plugins.autoptcheckin.helper.ocr_helper import recognize_captcha
from app.plugins.autoptcheckin.sites import _ISiteSigninHandler
from app.utils.string import StringUtils


class _AttendanceCaptchaHandler(_ISiteSigninHandler):
    """
    NexusPHP attendance.php 验证码签到通用基类。

    子类只需设置：
      - site_url:  站点匹配域名（用于 match）
      - _signin_url: 签到页完整 URL（含 https://）
    可选覆盖：
      - _success_texts / _repeat_texts: 签到成功/已签到文案
    """
    site_url = ""
    _signin_url = ""

    # 仅保留可唯一确认签到完成的文案；“获得”“连续签到”等会出现在
    # 奖励说明、导航栏等未签到页面中，不能作为成功依据。
    _success_texts = [
        "签到成功", "簽到成功",
        "签到已得", "簽到已得",
    ]
    _repeat_texts = [
        "今天已经签到过", "今天已經簽到過",
        "请勿重复刷新", "請勿重複刷新",
        "已经签到", "已經簽到",
        "今天已经签到", "今天已經簽到",
        "今天已簽到", "今日已簽到", "今日已签到",
    ]
    _failure_texts = [
        "图片代码无效", "圖片代碼無效", "图片验证码无效", "圖片驗證碼無效",
        "验证码错误", "驗證碼錯誤", "验证码不正确", "驗證碼不正確",
        "验证码已过期", "驗證碼已過期", "验证码失效", "驗證碼失效",
        "验证码校验失败", "驗證碼校驗失敗", "验证失败", "驗證失敗",
    ]

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
                referer=self._signin_url,
            )
        except ImportError as e:
            return False, f"签到失败：依赖缺失 {e}"

        # 1. 打开签到页，判断登录态与是否已签到
        status, html_text = client.get(self._signin_url)
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
        if any(text in html_text for text in self._success_texts):
            logger.info(f"{site} 今日已签到（页面已显示签到结果）")
            return True, "今日已签到"

        # 2. 解析验证码 imagehash / image.php 图片地址
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

        base = self._signin_url.rsplit("/", 1)[0] + "/"
        image_url = urljoin(base, image_src.replace("&amp;", "&"))
        image_bytes = client.get_bytes(image_url)
        if not image_bytes:
            logger.error(f"{site} 签到失败，获取验证码图片失败")
            return False, "签到失败，获取验证码图片失败"

        # 3. ddddocr 优先，OcrHelper 回退
        code = recognize_captcha(
            image_bytes=image_bytes,
            image_url=image_url,
            cookie=site_cookie,
            ua=ua,
            referer=self._signin_url,
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
                referer=self._signin_url,
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

        # 4. 提交签到
        status, resp_text = client.post(
            self._signin_url,
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
        resp_html = etree.HTML(resp_text)
        if resp_html is not None and resp_html.xpath('//form[contains(@action,"attendance")]//input[@name="imagehash"]'):
            logger.error(f"{site} 签到失败，验证码错误或被拒")
            return False, "签到失败：验证码错误或被拒"
        if any(text in resp_text for text in self._failure_texts):
            logger.error(f"{site} 签到失败，验证码无效")
            return False, "签到失败：验证码无效"
        # POST 响应可能混入导航栏、奖励说明等文本，不能只靠响应全文判定
        # 成功。重新读取签到页，确认验证码表单已消失且存在精确成功状态。
        verify_status, verify_html = client.get(self._signin_url)
        if verify_status != 200 or not verify_html:
            logger.error(f"{site} 签到结果未确认，复查状态码：{verify_status}")
            return False, f"签到结果未确认，复查状态码：{verify_status}"
        if "login.php" in verify_html:
            logger.error(f"{site} 签到结果未确认，Cookie已失效")
            return False, "签到失败，Cookie已失效"
        verify_dom = etree.HTML(verify_html)
        if verify_dom is not None and verify_dom.xpath(
                '//form[contains(@action,"attendance")]//input[@name="imagehash"]'):
            logger.error(f"{site} 签到失败，复查后验证码表单仍存在")
            return False, "签到失败：验证码错误或签到结果未生效"
        if any(text in verify_html for text in self._failure_texts):
            logger.error(f"{site} 签到失败，复查页面显示验证码无效")
            return False, "签到失败：验证码无效"
        if any(text in verify_html for text in self._repeat_texts):
            logger.info(f"{site} 今日已签到")
            return True, "今日已签到"
        if any(text in verify_html for text in self._success_texts):
            logger.info(f"{site} 签到成功（已复查确认）")
            return True, "签到成功"

        logger.error(f"{site} 签到结果未确认，POST 返回 {resp_text[:200]}")
        return False, "签到结果未确认"
