# input: 验证码图片 URL/bytes
# output: 识别结果字符串
# pos: helper 层，ddddocr 优先，MoviePilot OcrHelper 回退

from collections import Counter
from app.log import logger

try:
    import ddddocr
    _ocr = ddddocr.DdddOcr(show_ad=False, beta=True)
    _ocr.set_ranges(0)  # 限制为数字 0-9
    logger.info("ddddocr 加载成功（beta 模型 + 数字模式）")
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
    retry_times: int = 3,
    engine: str = 'auto',
) -> str | None:
    """识别验证码

    Args:
        image_url: 验证码图片 URL（与 image_bytes 二选一，OcrHelper 必须有 URL）
        image_bytes: 验证码图片二进制（优先使用）
        cookie: 下载图片用的 cookie
        ua: User-Agent
        min_len: 最小识别长度
        proxy: 是否使用代理
        retry_times: ddddocr 重试次数（取众数）
        engine: 引擎选择
            'auto'      — ddddocr 优先，失败后回退 OcrHelper（默认）
            'ddddocr'   — 仅 ddddocr，不回退
            'ocrhelper' — 仅 OcrHelper
    """
    # 获取图片数据（ocrhelper 直接传 URL，不需要预下载）
    if engine != 'ocrhelper':
        if image_bytes is None and image_url:
            image_bytes = _download_image(image_url, cookie, ua, proxy)
        if not image_bytes:
            if engine == 'ddddocr':
                logger.warning("ddddocr：无法获取图片数据")
                return None
            # auto 模式下没有 bytes 也可以尝试 OcrHelper（via URL）

    # 1. ddddocr
    if engine in ('auto', 'ddddocr') and _ocr is not None and image_bytes:
        results = []
        for i in range(retry_times):
            try:
                code = _ocr.classification(image_bytes)
                if code and len(code.strip()) >= min_len:
                    results.append(code.strip())
            except Exception as e:
                logger.debug(f"ddddocr 第 {i+1} 次识别失败: {e}")

        if results:
            result_code, count = Counter(results).most_common(1)[0]
            logger.info(f"ddddocr 识别结果: {result_code} (出现 {count}/{retry_times} 次)")
            return result_code

        logger.warning(f"ddddocr {retry_times} 次均无有效结果")
        if engine == 'ddddocr':
            return None
        # auto 模式继续尝试 OcrHelper

    # 2. OcrHelper
    if engine in ('auto', 'ocrhelper') and OcrHelper is not None and image_url:
        try:
            result = OcrHelper().get_captcha_text(
                image_url=image_url, cookie=cookie, ua=ua
            )
            if result and len(result.strip()) >= min_len:
                logger.info(f"OcrHelper 识别结果: {result.strip()}")
                return result.strip()
            logger.warning("OcrHelper 识别结果无效")
        except Exception as e:
            logger.warning(f"OcrHelper 识别失败: {e}")
    elif engine == 'ocrhelper' and not image_url:
        logger.warning("OcrHelper 需要 image_url，但未提供")

    return None


def _download_image(
    url: str, cookie: str = None, ua: str = None, proxy: bool = False
) -> bytes | None:
    """下载验证码图片"""
    try:
        from app.plugins.autoptcheckin.helper.http_helper import CffiClient
        client = CffiClient(cookie=cookie or "", ua=ua)
        return client.get_bytes(url)
    except Exception as e:
        logger.debug(f"CffiClient 下载验证码失败，回退到 RequestUtils: {e}")

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
