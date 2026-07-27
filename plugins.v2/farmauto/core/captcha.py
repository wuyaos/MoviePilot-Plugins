import base64
import logging
import re
from typing import Optional

import requests

try:
    from app.log import logger
except ImportError:  # 允许核心模块在 MoviePilot 之外独立测试
    logger = logging.getLogger(__name__)


class OcrRecognizer:
    """思齐验证码识别：ddddocr 本地优先，MoviePilot OcrHelper 回退。"""

    _local_ocr = None
    _local_ocr_loaded = False

    @classmethod
    def _recognize_local(cls, image: bytes) -> Optional[str]:
        if not cls._local_ocr_loaded:
            cls._local_ocr_loaded = True
            try:
                import ddddocr

                cls._local_ocr = ddddocr.DdddOcr(show_ad=False, beta=True)
            except (ImportError, OSError) as error:
                logger.debug(f"[FarmAuto] ddddocr 不可用，改用 MoviePilot OCR：{error}")
        if cls._local_ocr is None:
            return None
        try:
            text = cls._normalize(cls._local_ocr.classification(image))
            return text if len(text) >= 4 else None
        except Exception as error:
            logger.debug(f"[FarmAuto] ddddocr 识别失败，改用 MoviePilot OCR：{error}")
            return None

    @staticmethod
    def _normalize(value) -> str:
        return re.sub(r"[^0-9A-Za-z]", "", str(value or "").strip())

    @classmethod
    def _recognize_moviepilot(cls, image: bytes) -> Optional[str]:
        image_b64 = base64.b64encode(image).decode("utf-8")
        try:
            from app.helper.ocr import OcrHelper

            text = cls._normalize(OcrHelper().get_captcha_text(image_b64=image_b64))
            return text if len(text) >= 4 else None
        except ImportError:
            # 仅供 MoviePilot 外独立测试；生产环境直接复用 OcrHelper。
            host = cls._ocr_host()
            if not host:
                logger.debug("[FarmAuto] OCR 未配置 OCR_HOST，跳过识别")
                return None
            response = requests.post(
                f"{host.rstrip('/')}/captcha/base64",
                json={"base64_img": image_b64},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            text = cls._normalize(
                payload.get("result") or payload.get("text") or payload.get("captcha_text")
            )
            return text if len(text) >= 4 else None

    @staticmethod
    def _ocr_host() -> Optional[str]:
        try:
            from app.config import get_config

            config = get_config() or {}
            host = config.get("OCR_HOST")
            if not host and isinstance(config.get("app"), dict):
                host = config["app"].get("OCR_HOST")
            if host:
                return str(host)
        except Exception as error:
            logger.debug(f"[FarmAuto] OCR 读取 app.config 配置失败：{error}")
        try:
            from app.core.config import settings

            host = getattr(settings, "OCR_HOST", None)
            return str(host) if host else None
        except Exception as error:
            logger.debug(f"[FarmAuto] OCR 读取 settings 配置失败：{error}")
            return None

    def recognize(self, image_url, cookies, http_client) -> Optional[str]:
        try:
            response = http_client.get(image_url, cookies)
            response.raise_for_status()
            image = response.content
            if not image:
                logger.debug("[FarmAuto] OCR 验证码图片为空，跳过识别")
                return None
            text = self._recognize_local(image)
            if text:
                return text
            text = self._recognize_moviepilot(image)
            if not text:
                logger.debug("[FarmAuto] OCR 未返回有效识别文本，准备降级逐格收获")
            return text
        except Exception as error:
            logger.debug(f"[FarmAuto] OCR 识别失败，准备降级逐格收获：{error}")
            return None
