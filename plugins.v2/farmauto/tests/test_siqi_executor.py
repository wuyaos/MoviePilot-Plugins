import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from core.captcha import OcrRecognizer
from core.executor import FarmExecutor
from sites.siqi import SiqiConfig


class FakeResponse:
    def __init__(self, text="", content=b"image", status_code=200):
        self.text = text
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeHttpClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def _response(self):
        if not self.responses:
            raise AssertionError("发生了未预期的 HTTP 请求")
        return self.responses.pop(0)

    def get(self, url, cookies, retryable=True):
        self.calls.append(("GET", url, None))
        return self._response()

    def post(
        self,
        url,
        cookies,
        data=None,
        json=None,
        allow_redirects=True,
        retryable=False,
    ):
        self.calls.append(("POST", url, data))
        return self._response()


class FakeOcr:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def recognize(self, image_url, cookies, http_client):
        self.calls.append(image_url)
        return self.result


class Logger:
    def __init__(self):
        self.debug_messages = []
        self.error_messages = []

    def debug(self, message):
        self.debug_messages.append(message)

    def error(self, message):
        self.error_messages.append(message)


def test_captcha_harvest_submits_ocr_result():
    client = FakeHttpClient([
        FakeResponse('{"success":true,"captcha":{"imagehash":"hash-1","image_url":"https://si-qi.xyz/captcha.php?id=1"}}'),
        FakeResponse('{"success":true,"msg":"一键收获成功"}'),
    ])
    ocr = FakeOcr("AB12")
    executor = FarmExecutor(client, Logger(), ocr_recognizer=ocr)

    results = executor.run_siqi_extras(
        "session=value", SiqiConfig(),
        {"auto_captcha_harvest": True, "captcha_ocr": True},
    )

    assert len(results) == 1
    assert results[0].action == "harvest_captcha"
    assert results[0].success is True
    assert ocr.calls == ["https://si-qi.xyz/captcha.php?id=1"]
    assert client.calls[1][0] == "POST"
    assert client.calls[1][1].endswith("plant_game.php?option=harvest_all")
    assert client.calls[1][2] == {
        "option": "harvest_all",
        "imagehash": "hash-1",
        "imagestring": "AB12",
    }


def test_captcha_image_url_is_built_when_response_only_has_hash():
    client = FakeHttpClient([
        FakeResponse('{"success":true,"captcha":{"imagehash":"hash-only"}}'),
        FakeResponse('{"success":true,"msg":"一键收获成功"}'),
    ])
    ocr = FakeOcr("ZX90")
    executor = FarmExecutor(client, Logger(), ocr_recognizer=ocr)

    results = executor.run_siqi_extras(
        "session=value", SiqiConfig(),
        {"auto_captcha_harvest": True, "captcha_ocr": True},
    )

    assert results[0].success is True
    assert ocr.calls == ["https://si-qi.xyz/captcha.php?imagehash=hash-only"]


def test_captcha_ocr_failure_falls_back_to_each_ready_plot():
    client = FakeHttpClient([
        FakeResponse('{"success":true,"captcha":{"imagehash":"hash-1","image_url":"/captcha.php?id=1"}}'),
        FakeResponse('{"success":true,"user_lands":[{"land_id":2,"plot_index":0,"seed_id":1,"is_ready":1}]}'),
        FakeResponse("收获成功"),
    ])
    executor = FarmExecutor(client, Logger(), ocr_recognizer=FakeOcr(None))

    results = executor.run_siqi_extras(
        "session=value", SiqiConfig(),
        {"auto_captcha_harvest": True, "captcha_ocr": True},
    )

    assert results[0].success is True
    assert results[0].message == "逐格收获已尝试 1 格"
    assert client.calls[-1][0] == "GET"
    assert "action=harvest&land_id=2&plot_index=0" in client.calls[-1][1]
    assert not any(call[0] == "POST" for call in client.calls)


def test_captcha_ocr_fallback_logs_reason_and_plot_failure():
    client = FakeHttpClient([
        FakeResponse('{"success":true,"captcha":{"imagehash":"hash-1","image_url":"/captcha.php?id=1"}}'),
        FakeResponse('{"success":true,"user_lands":[{"land_id":2,"plot_index":0,"seed_id":1,"is_ready":1}]}'),
        FakeResponse("收获失败"),
    ])
    logger = Logger()
    executor = FarmExecutor(client, logger, ocr_recognizer=FakeOcr(None))

    results = executor.run_siqi_extras(
        "session=value", SiqiConfig(),
        {"auto_captcha_harvest": True, "captcha_ocr": True},
    )

    assert results[0].success is False
    assert any("OCR 未识别出验证码" in message for message in logger.debug_messages)
    assert any("逐格收获地块 2-0 失败" in message for message in logger.debug_messages)


def test_ocr_without_host_logs_debug(monkeypatch):
    logger = Logger()
    monkeypatch.setattr("core.captcha.logger", logger)
    monkeypatch.setattr(OcrRecognizer, "_ocr_host", staticmethod(lambda: None))

    assert OcrRecognizer().recognize("https://example.com/captcha", {}, FakeHttpClient([])) is None
    assert logger.debug_messages == ["[FarmAuto] OCR 未配置 OCR_HOST，跳过识别"]


def test_daily_steal_done_skips_request():
    client = FakeHttpClient([])
    executor = FarmExecutor(client, Logger(), ocr_recognizer=FakeOcr(None))

    results = executor.run_siqi_extras(
        "session=value", SiqiConfig(), {"auto_steal": True}, {"steal": True}
    )

    assert results == []
    assert client.calls == []


def test_all_siqi_switches_closed_do_not_request():
    client = FakeHttpClient([])
    executor = FarmExecutor(client, Logger(), ocr_recognizer=FakeOcr(None))

    assert executor.run_siqi_extras("session=value", SiqiConfig(), {}) == []
    assert client.calls == []
