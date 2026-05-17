# input: 验证码图片 URL/bytes
# output: 识别结果字符串
# pos: helper 层，ddddocr 优先，MoviePilot OcrHelper 回退

from collections import Counter
import re
from app.log import logger

try:
    import ddddocr
    _DDDDOCR_AVAILABLE = True
    _ocr_pool = {}
    logger.info("ddddocr 加载成功（beta 模型）")
except ImportError:
    ddddocr = None
    _DDDDOCR_AVAILABLE = False
    _ocr_pool = {}
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
    referer: str = None,
    min_len: int = 4,
    max_len: int = None,
    proxy: bool = False,
    retry_times: int = 1,
    engine: str = 'auto',
    charset: str = 'auto',
) -> str | None:
    """识别验证码

    Args:
        image_url: 验证码图片 URL（与 image_bytes 二选一，OcrHelper 必须有 URL）
        image_bytes: 验证码图片二进制（优先使用）
        cookie: 下载图片用的 cookie
        ua: User-Agent
        referer: 下载图片用的 Referer
        min_len: 最小识别长度
        max_len: 最大识别长度
        proxy: 是否使用代理
        retry_times: ddddocr 重试次数（同图取众数）
        engine: 引擎选择
            'auto'      — ddddocr 优先，失败后回退 OcrHelper（默认）
            'ddddocr'   — 仅 ddddocr，不回退
            'ocrhelper' — 仅 OcrHelper
        charset: 字符集策略
            'auto'   — 不限制模型字符集
            'alnum'  — 结果仅保留字母数字
            'digits' — 数字验证码，使用 ddddocr 数字模式
    """
    # 获取图片数据（ocrhelper 直接传 URL，不需要预下载）
    if engine != 'ocrhelper':
        if image_bytes is None and image_url:
            image_bytes = _download_image(image_url, cookie, ua, referer, proxy)
        if image_bytes and not _is_valid_image(image_bytes):
            logger.warning("验证码响应不是有效图片，跳过 ddddocr")
            image_bytes = None
        if not image_bytes:
            if engine == 'ddddocr':
                logger.warning("ddddocr：无法获取图片数据")
                return None
            # auto 模式下没有 bytes 也可以尝试 OcrHelper（via URL）

    # 1. ddddocr
    if engine in ('auto', 'ddddocr') and image_bytes:
        ocr = _get_ocr(charset)
        if ocr is None:
            if engine == 'ddddocr':
                logger.warning("ddddocr 不可用")
                return None
        else:
            results = []
            retry_times = max(1, int(retry_times or 1))
            for i in range(retry_times):
                try:
                    code = _normalize_code(ocr.classification(image_bytes), charset)
                    if _is_valid_code(code, min_len=min_len, max_len=max_len):
                        results.append(code)
                except Exception as e:
                    logger.debug(f"ddddocr 第 {i+1} 次识别失败: {e}")

            if results:
                result_code, count = Counter(results).most_common(1)[0]
                logger.info(f"ddddocr 识别结果: {result_code} (charset={charset}, 出现 {count}/{retry_times} 次)")
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
            result = _normalize_code(result, charset)
            if _is_valid_code(result, min_len=min_len, max_len=max_len):
                logger.info(f"OcrHelper 识别结果: {result} (charset={charset})")
                return result
            logger.warning("OcrHelper 识别结果无效")
        except Exception as e:
            logger.warning(f"OcrHelper 识别失败: {e}")
    elif engine == 'ocrhelper' and not image_url:
        logger.warning("OcrHelper 需要 image_url，但未提供")

    return None


def _get_ocr(charset: str):
    """按字符集隔离 ddddocr 实例，避免数字模式污染其他站点。"""
    if not _DDDDOCR_AVAILABLE:
        return None
    charset = charset or 'auto'
    if charset not in _ocr_pool:
        ocr = ddddocr.DdddOcr(show_ad=False, beta=True)
        if charset == 'digits':
            ocr.set_ranges(0)
        _ocr_pool[charset] = ocr
    return _ocr_pool[charset]


def _normalize_code(code: str, charset: str) -> str:
    code = (code or "").strip()
    if charset == 'digits':
        return re.sub(r"\D", "", code)
    if charset in ('alnum', 'auto'):
        return re.sub(r"[^0-9A-Za-z]", "", code)
    return code


def _is_valid_code(code: str, min_len: int, max_len: int = None) -> bool:
    if not code or len(code) < min_len:
        return False
    if max_len and len(code) > max_len:
        return False
    return True


def _is_valid_image(image_bytes: bytes) -> bool:
    if not image_bytes:
        return False
    try:
        from io import BytesIO
        from PIL import Image
        Image.open(BytesIO(image_bytes)).verify()
        return True
    except ImportError:
        logger.debug("Pillow 未安装，跳过验证码图片格式校验")
        return True
    except Exception as e:
        logger.debug(f"验证码图片格式校验失败: {e}")
        return False


def _download_image(
    url: str, cookie: str = None, ua: str = None, referer: str = None, proxy: bool = False
) -> bytes | None:
    """下载验证码图片"""
    try:
        from app.core.config import settings
        from app.plugins.autoptcheckin.helper.http_helper import CffiClient
        client = CffiClient(
            cookie=cookie or "",
            ua=ua,
            proxy=settings.PROXY_SERVER if proxy else None,
            referer=referer,
        )
        return client.get_bytes(url)
    except Exception as e:
        logger.debug(f"CffiClient 下载验证码失败，回退到 RequestUtils: {e}")

    # 回退到 RequestUtils
    try:
        from app.core.config import settings
        from app.utils.http import RequestUtils
        headers = {"User-Agent": ua or "", "Cookie": cookie or ""}
        if referer:
            headers["Referer"] = referer
        proxies = settings.PROXY if proxy else None
        res = RequestUtils(headers=headers, proxies=proxies).get_res(url=url)
        if res and res.status_code == 200:
            return res.content
    except Exception as e:
        logger.error(f"下载验证码图片失败: {e}")
    return None
