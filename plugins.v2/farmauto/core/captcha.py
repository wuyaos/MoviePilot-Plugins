from typing import Optional

import requests


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
        except Exception:
            pass
        try:
            from app.core.config import settings

            host = getattr(settings, "OCR_HOST", None)
            return str(host) if host else None
        except Exception:
            return None

    def recognize(self, image_url, cookies, http_client) -> Optional[str]:
        host = self._ocr_host()
        if not host:
            return None
        try:
            response = http_client.get(image_url, cookies)
            response.raise_for_status()
            image = response.content
            if not image:
                return None
            ocr_response = requests.post(
                f"{host.rstrip('/')}/captcha",
                files={"file": ("captcha.png", image, "image/png")},
                timeout=30,
            )
            ocr_response.raise_for_status()
            result = ocr_response.json()
            text = result.get("result") or result.get("text") or result.get("captcha_text")
            return str(text).strip() if text else None
        except Exception:
            return None
