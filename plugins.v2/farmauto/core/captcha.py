import logging
from typing import Optional

import requests

try:
    from app.log import logger
except ImportError:  # 允许核心模块在 MoviePilot 之外独立测试
    logger = logging.getLogger(__name__)


class OcrRecognizer:
    """MoviePilot OCR 服务适配器。"""

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
        host = self._ocr_host()
        if not host:
            logger.debug("[FarmAuto] OCR 未配置 OCR_HOST，跳过识别")
            return None
        try:
            response = http_client.get(image_url, cookies)
            response.raise_for_status()
            image = response.content
            if not image:
                logger.debug("[FarmAuto] OCR 验证码图片为空，跳过识别")
                return None
            ocr_response = requests.post(
                f"{host.rstrip('/')}/captcha",
                files={"file": ("captcha.png", image, "image/png")},
                timeout=30,
            )
            ocr_response.raise_for_status()
            result = ocr_response.json()
            text = result.get("result") or result.get("text") or result.get("captcha_text")
            if not text:
                logger.debug("[FarmAuto] OCR 服务未返回识别文本")
                return None
            return str(text).strip()
        except Exception as error:
            logger.debug(f"[FarmAuto] OCR 识别失败，准备降级逐格收获：{error}")
            return None
