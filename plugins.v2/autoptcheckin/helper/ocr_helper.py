# input: 验证码图片 URL/bytes
# output: 识别结果字符串
# pos: helper 层，ddddocr 优先，MoviePilot OcrHelper 回退

from app.log import logger

try:
    import ddddocr
    _ocr = ddddocr.DdddOcr(show_ad=False)
    logger.info("ddddocr 加载成功")
except ImportError:
    _ocr = None
    logger.warning("ddddocr 未安装，将使用 OcrHelper 回退")

try:
    from app.helper.ocr import OcrHelper
except ImportError:
    OcrHelper = None


def recognize_captcha(
    image_url: str = None,
    image_bytes: bytes = None,
    cookie: str = None,
    ua: str = None,
    min_len: int = 4,
    proxy: bool = False,
) -> str | None:
    """识别验证码：ddddocr 优先，OcrHelper 回退

    Args:
        image_url: 验证码图片 URL（与 image_bytes 二选一）
        image_bytes: 验证码图片二进制（优先使用）
        cookie: 下载图片用的 cookie
        ua: User-Agent
        min_len: 最小识别长度
        proxy: 是否使用代理
    """
    # 获取图片数据
    if image_bytes is None and image_url:
        image_bytes = _download_image(image_url, cookie, ua, proxy)
    if not image_bytes:
        return None

    # 1. ddddocr
    if _ocr is not None:
        try:
            code = _ocr.classification(image_bytes)
            if code and len(code.strip()) >= min_len:
                logger.info(f"ddddocr 识别结果: {code.strip()}")
                return code.strip()
            logger.debug(f"ddddocr 结果过短: {code}")
        except Exception as e:
            logger.warning(f"ddddocr 识别失败: {e}")

    # 2. OcrHelper 回退
    if OcrHelper is not None and image_url:
        try:
            result = OcrHelper().get_captcha_text(
                image_url=image_url, cookie=cookie, ua=ua
            )
            if result and len(result.strip()) >= min_len:
                logger.info(f"OcrHelper 识别结果: {result.strip()}")
                return result.strip()
        except Exception as e:
            logger.warning(f"OcrHelper 识别失败: {e}")

    return None


def _download_image(
    url: str, cookie: str = None, ua: str = None, proxy: bool = False
) -> bytes | None:
    """下载验证码图片"""
    try:
        from app.plugins.autoptcheckin.helper.http_helper import CffiClient
        client = CffiClient(cookie=cookie or "", ua=ua)
        return client.get_bytes(url)
    except Exception:
        pass

    # 回退到 RequestUtils
    try:
        from app.core.config import settings
        from app.utils.http import RequestUtils
        headers = {"User-Agent": ua or "", "Cookie": cookie or ""}
        proxies = settings.PROXY if proxy else None
        res = RequestUtils(headers=headers, proxies=proxies).get_res(url=url)
        if res and res.status_code == 200:
            return res.content
    except Exception as e:
        logger.error(f"下载验证码图片失败: {e}")
    return None
