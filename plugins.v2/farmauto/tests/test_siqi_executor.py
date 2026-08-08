import base64
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


def _harvest_plan():
    return (
        [{"op": "harvest", "crop_key": "crop_1_2_0"}],
        {"crop_1": {"name": "萝卜", "base_reward": 20}},
        {"crop_1_2_0": {"crop_key": "crop_1", "land_id": 2, "plot_index": 0}},
    )


def test_core_harvest_submits_native_ocr_batch_api():
    client = FakeHttpClient([
        FakeResponse('{"success":true,"captcha":{"imagehash":"hash-1","image_url":"https://si-qi.xyz/captcha.php?id=1"}}'),
        FakeResponse('{"success":true,"msg":"一键收获成功","reward":20}'),
    ])
    ocr = FakeOcr("AB12")
    executor = FarmExecutor(client, Logger(), ocr_recognizer=ocr)
    plan, crops, statuses = _harvest_plan()

    result = executor._try_siqi_harvest_all(
        {"session": "value"}, SiqiConfig(), plan, crops, statuses,
    )

    assert result.action == "harvest_all"
    assert result.success is True
    assert result.target == "萝卜×1"
    # 思齐收获值进入背包，不是立即获得魔力；出售时才计入 profit。
    assert result.profit == 0
    assert result.value == 20
    assert result.value_unit == "收获值"
    assert ocr.calls == ["https://si-qi.xyz/captcha.php?id=1"]
    assert client.calls == [
        ("POST", "https://si-qi.xyz/plant_game.php", {"action": "get_harvest_all_captcha"}),
        ("POST", "https://si-qi.xyz/plant_game.php", {
            "action": "harvest_all", "imagehash": "hash-1", "imagestring": "AB12",
        }),
    ]


def test_core_harvest_builds_captcha_url_from_hash():
    client = FakeHttpClient([
        FakeResponse('{"success":true,"captcha":{"imagehash":"hash-only"}}'),
        FakeResponse('{"success":true,"msg":"一键收获成功"}'),
    ])
    ocr = FakeOcr("ZX90")
    executor = FarmExecutor(client, Logger(), ocr_recognizer=ocr)
    plan, crops, statuses = _harvest_plan()

    result = executor._try_siqi_harvest_all(
        {"session": "value"}, SiqiConfig(), plan, crops, statuses,
    )

    assert result.success is True
    assert ocr.calls == ["https://si-qi.xyz/captcha.php?imagehash=hash-only"]


def test_core_harvest_refreshes_captcha_after_rejection_then_succeeds():
    client = FakeHttpClient([
        FakeResponse('{"success":true,"captcha":{"imagehash":"hash-1","image_url":"/captcha.php?id=1"}}'),
        FakeResponse('{"success":false,"msg":"验证码错误"}'),
        FakeResponse('{"success":true,"captcha":{"imagehash":"hash-2","image_url":"/captcha.php?id=2"}}'),
        FakeResponse('{"success":true,"msg":"一键收获成功","reward":20}'),
    ])
    executor = FarmExecutor(client, Logger(), ocr_recognizer=FakeOcr("AB12"))
    plan, crops, statuses = _harvest_plan()

    result = executor._try_siqi_harvest_all(
        {"session": "value"}, SiqiConfig(), plan, crops, statuses,
    )

    assert result.success is True
    captcha_calls = [call for call in client.calls if call[2] == {"action": "get_harvest_all_captcha"}]
    submit_calls = [call for call in client.calls if call[2] and call[2].get("action") == "harvest_all"]
    assert len(captcha_calls) == 2
    assert [call[2]["imagehash"] for call in submit_calls] == ["hash-1", "hash-2"]


def test_core_harvest_three_ocr_failures_return_none_for_plot_fallback():
    client = FakeHttpClient([
        FakeResponse(f'{{"success":true,"captcha":{{"imagehash":"hash-{index}","image_url":"/captcha.php?id={index}"}}}}')
        for index in range(1, 4)
    ])
    logger = Logger()
    executor = FarmExecutor(client, logger, ocr_recognizer=FakeOcr(None))
    plan, crops, statuses = _harvest_plan()

    result = executor._try_siqi_harvest_all(
        {"session": "value"}, SiqiConfig(), plan, crops, statuses,
    )

    assert result is None
    assert len(client.calls) == 3
    assert all(call[2] == {"action": "get_harvest_all_captcha"} for call in client.calls)
    assert any("连续 3 轮失败，降级逐格收获" in message for message in logger.debug_messages)


def test_ocr_prefers_local_ddddocr(monkeypatch):
    monkeypatch.setattr(OcrRecognizer, "_recognize_local", classmethod(lambda cls, image: "LOCAL1"))
    monkeypatch.setattr(OcrRecognizer, "_recognize_moviepilot", classmethod(
        lambda cls, image: (_ for _ in ()).throw(AssertionError("本地识别成功后不应调用远端 OCR"))
    ))
    client = FakeHttpClient([FakeResponse(content=b"captcha-image")])

    assert OcrRecognizer().recognize("https://si-qi.xyz/image.php", {}, client) == "LOCAL1"


def test_ocr_uses_moviepilot_base64_protocol(monkeypatch):
    class OcrResponse:
        def raise_for_status(self):
            pass

        @staticmethod
        def json():
            return {"result": "AB12"}

    calls = []
    monkeypatch.setattr(OcrRecognizer, "_recognize_local", classmethod(lambda cls, image: None))
    monkeypatch.setattr(OcrRecognizer, "_ocr_host", staticmethod(lambda: "https://movie-pilot.org"))
    monkeypatch.setattr("core.captcha.requests.post", lambda url, json, timeout: (
        calls.append((url, json, timeout)) or OcrResponse()
    ))
    client = FakeHttpClient([FakeResponse(content=b"captcha-image")])

    result = OcrRecognizer().recognize("https://si-qi.xyz/captcha.php?id=1", {}, client)

    assert result == "AB12"
    assert calls == [(
        "https://movie-pilot.org/captcha/base64",
        {"base64_img": base64.b64encode(b"captcha-image").decode("utf-8")},
        30,
    )]


def test_ocr_without_host_logs_debug(monkeypatch):
    logger = Logger()
    monkeypatch.setattr("core.captcha.logger", logger)
    monkeypatch.setattr(OcrRecognizer, "_recognize_local", classmethod(lambda cls, image: None))
    monkeypatch.setattr(OcrRecognizer, "_ocr_host", staticmethod(lambda: None))

    assert OcrRecognizer().recognize(
        "https://example.com/captcha", {}, FakeHttpClient([FakeResponse(content=b"image")])
    ) is None
    assert logger.debug_messages == [
        "[FarmAuto] OCR 未配置 OCR_HOST，跳过识别",
        "[FarmAuto] OCR 未返回有效识别文本，准备降级逐格收获",
    ]


def test_daily_steal_done_skips_request():
    client = FakeHttpClient([])
    executor = FarmExecutor(client, Logger(), ocr_recognizer=FakeOcr(None))

    results = executor.run_siqi_extras(
        "session=value", SiqiConfig(), {"auto_steal": True}, {"steal": True}
    )

    assert results == []
    assert client.calls == []


def test_siqi_steal_uses_form_actions_and_finishes_session():
    client = FakeHttpClient([
        FakeResponse('{"success":true,"victim_id":"123","victim_plots":[{"land_id":"1","plot_index":"2","is_ready":"1"}]}'),
        FakeResponse('{"success":true,"msg":"偷菜成功"}'),
        FakeResponse('{"success":true}'),
    ])
    executor = FarmExecutor(client, Logger(), ocr_recognizer=FakeOcr(None))

    results = executor.run_siqi_extras(
        "session=value", SiqiConfig(), {"auto_steal": True},
    )

    assert results[0].success is True
    assert client.calls == [
        ("POST", "https://si-qi.xyz/plant_game.php", {"action": "get_victim_farm"}),
        ("POST", "https://si-qi.xyz/plant_game.php", {
            "victim_id": "123", "land_id": "1", "plot_index": "2",
            "action": "steal_vegetable",
        }),
        ("POST", "https://si-qi.xyz/plant_game.php", {"action": "finish_stealing"}),
    ]


def test_siqi_like_uses_remaining_quota_in_target_order():
    client = FakeHttpClient([
        FakeResponse('{"success":true,"usernames":["alice","bob","carol","dave"],"remaining_in_window":3,"max_per_window":3}'),
        FakeResponse('{"success":true,"msg":"点赞成功","remaining_in_window":0}'),
    ])
    executor = FarmExecutor(client, Logger(), ocr_recognizer=FakeOcr(None))

    results = executor.run_siqi_extras(
        "session=value", SiqiConfig(), {"auto_like": True},
    )

    assert results[0].success is True
    assert results[0].target == "alice、bob、carol"
    assert results[0].quantity == 3
    assert results[0].reason == "daily_exhausted"
    assert "剩余 0/3" in results[0].message
    assert client.calls == [
        ("POST", "https://si-qi.xyz/plant_game.php", {"action": "random_like_targets"}),
        ("POST", "https://si-qi.xyz/plant_game.php", {
            "action": "like_farm_batch", "usernames": "alice\nbob\ncarol",
        }),
    ]


def test_siqi_empty_targets_are_skipped_not_failed():
    client = FakeHttpClient([
        FakeResponse('{"success":true,"targets":[]}'),
        FakeResponse('{"success":true,"targets":[]}'),
        FakeResponse('{"success":true,"user_lands":[]}'),
    ])
    executor = FarmExecutor(client, Logger(), ocr_recognizer=FakeOcr(None))

    results = executor.run_siqi_extras(
        "session=value", SiqiConfig(),
        {"auto_steal": True, "auto_like": True, "auto_buy_slot": True},
    )

    assert [result.action for result in results] == ["steal", "like", "buy_slot"]
    assert all(result.success and result.skipped for result in results)


def test_siqi_buy_slot_checks_balance_before_posting():
    fetch = {
        "success": True,
        "user_bonus": 50,
        "user_stats": {"total_harvest": 1000},
        "lands": [{"id": 1, "unlock_harvest": 0}],
        "user_lands": [],
        "plot_slot": {
            "available": True,
            "next_slot_cost_by_land": {"1": 100},
        },
    }
    import json
    client = FakeHttpClient([FakeResponse(json.dumps(fetch))])
    executor = FarmExecutor(client, Logger(), ocr_recognizer=FakeOcr(None))

    result = executor._do_siqi_buy_slot({"session": "value"}, SiqiConfig())

    assert result.success is True and result.skipped is True
    assert result.reason == "insufficient_bonus"
    assert "还差 50" in result.message
    assert client.calls == [("GET", "https://si-qi.xyz/plant_game.php?action=fetch", None)]


def test_siqi_daily_exhausted_is_skipped_with_reason():
    client = FakeHttpClient([
        FakeResponse('{"success":false,"message":"今日偷菜次数已用完"}'),
    ])
    executor = FarmExecutor(client, Logger(), ocr_recognizer=FakeOcr(None))

    result = executor.run_siqi_extras(
        "session=value", SiqiConfig(), {"auto_steal": True},
    )[0]

    assert result.success is True and result.skipped is True
    assert result.reason == "daily_exhausted"
    assert len(client.calls) == 1


def test_all_siqi_switches_closed_do_not_request():
    client = FakeHttpClient([])
    executor = FarmExecutor(client, Logger(), ocr_recognizer=FakeOcr(None))

    assert executor.run_siqi_extras("session=value", SiqiConfig(), {}) == []
    assert client.calls == []
