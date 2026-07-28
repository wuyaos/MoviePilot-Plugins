import json
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from core.executor import FarmExecutor
from sites.siqi import SiqiConfig


class Response:
    def __init__(self, text):
        self.text = text
        self.status_code = 200

    def raise_for_status(self):
        return None


class StagedClient:
    def __init__(self):
        self.calls = []
        self.fetch_count = 0

    @staticmethod
    def _farm(plots, inventory=None, bonus=10000):
        return json.dumps({
            "success": True,
            "user_bonus": bonus,
            "seeds": [
                {"id": 1, "name": "萝卜", "cost": 10, "base_reward": 20},
                {"id": 3, "name": "玉米", "cost": 30, "base_reward": 50},
            ],
            "user_lands": plots,
            "inventory": inventory or [],
        }, ensure_ascii=False)

    def get(self, url, cookies, retryable=True):
        self.calls.append(("GET", url, None))
        # 初始 fetch：is_ready 未刷新，但 harvest_time 已过期；收获后两格空；随后种玉米。
        responses = [
            self._farm([
                {"land_id": 1, "plot_index": 0, "seed_id": 1, "is_ready": 0, "harvest_time": 1},
                {"land_id": 1, "plot_index": 1, "seed_id": 1, "is_ready": 0, "harvest_time": 1},
                {"land_id": 2, "plot_index": None, "seed_id": None, "is_ready": 0},
            ]),
            self._farm([
                {"land_id": 1, "plot_index": 0, "seed_id": None, "is_ready": 0},
                {"land_id": 1, "plot_index": 1, "seed_id": None, "is_ready": 0},
                {"land_id": 2, "plot_index": None, "seed_id": None, "is_ready": 0},
            ], inventory=[{"seed_id": 1, "name": "萝卜", "quantity": 2}]),
            self._farm([
                {"land_id": 1, "plot_index": 0, "seed_id": 3, "is_ready": 0},
                {"land_id": 1, "plot_index": 1, "seed_id": 3, "is_ready": 0},
                {"land_id": 2, "plot_index": None, "seed_id": None, "is_ready": 0},
            ], inventory=[{"seed_id": 1, "name": "萝卜", "quantity": 2}]),
            self._farm([
                {"land_id": 1, "plot_index": 0, "seed_id": 3, "is_ready": 0},
                {"land_id": 1, "plot_index": 1, "seed_id": 3, "is_ready": 0},
            ], inventory=[{"seed_id": 1, "name": "萝卜", "quantity": 2}]),
        ]
        response = responses[min(self.fetch_count, len(responses) - 1)]
        self.fetch_count += 1
        return Response(response)

    def post(self, url, cookies, data=None, json=None, allow_redirects=True, retryable=False):
        self.calls.append(("POST", url, data))
        if data and data.get("action") == "harvest":
            return Response('{"success":true,"msg":"收获成功","reward":20}')
        if data and data.get("action") == "plant_fill_empty":
            return Response('{"success":true,"msg":"种植成功"}')
        if data and data.get("action") == "sell_inventory":
            return Response('{"success":true,"msg":"出售成功"}')
        raise AssertionError(f"unexpected POST {data}")


class Logger:
    def error(self, _message):
        pass


class BatchHarvestClient(StagedClient):
    def __init__(self, ocr_success=True):
        super().__init__()
        self.ocr_success = ocr_success

    def post(self, url, cookies, data=None, json=None, allow_redirects=True, retryable=False):
        self.calls.append(("POST", url, data))
        if data and data.get("action") == "get_harvest_all_captcha":
            return Response('{"success":true,"captcha":{"imagehash":"hash-1","image_url":"/captcha.php?id=1"}}')
        if data and data.get("action") == "harvest_all":
            return Response('{"success":true,"msg":"一键收获成功","reward":40}')
        if data and data.get("action") == "plant_fill_empty":
            return Response('{"success":true,"msg":"种植成功"}')
        if data and data.get("action") == "sell_inventory":
            return Response('{"success":true,"msg":"出售成功"}')
        if data and data.get("action") == "harvest":
            return Response('{"success":true,"msg":"逐格收获成功","reward":20}')
        raise AssertionError(f"unexpected POST {data}")


class BatchOcr:
    def __init__(self, value):
        self.value = value

    def recognize(self, _image_url, _cookies, _http_client):
        return self.value


class NoEmptyClient(StagedClient):
    def get(self, url, cookies, retryable=True):
        self.calls.append(("GET", url, None))
        if "action=harvest" in url:
            raise AssertionError("没有成熟地块时不应发送收获请求")
        farm = self._farm([
            {"land_id": 1, "plot_index": 0, "seed_id": 3, "is_ready": 0},
            {"land_id": 2, "plot_index": None, "seed_id": None, "is_ready": 0},
        ])
        return Response(farm)


def test_siqi_staged_flow_without_ready_or_empty_plot_skips_harvest_and_plant():
    client = NoEmptyClient()
    report = FarmExecutor(client, Logger()).run_site(
        "session=value", SiqiConfig(),
        {"request_interval": 0}, {"default_seed_id": 3},
    )

    assert report.actions == []
    assert not any(call[0] == "POST" for call in client.calls)
    assert report.status == "completed"
    assert report.message == "无可执行操作"


def test_siqi_staged_flow_uses_native_batch_harvest_when_ocr_succeeds():
    client = BatchHarvestClient()
    report = FarmExecutor(client, Logger(), ocr_recognizer=BatchOcr("AB12")).run_site(
        "session=value", SiqiConfig(),
        {"request_interval": 0, "max_sell_per_run": 2},
        {"default_seed_id": 3, "captcha_ocr": True},
    )

    assert [action.action for action in report.actions] == ["harvest_all", "plant", "sell", "sell"]
    assert report.actions[0].target == "萝卜×2"
    assert report.actions[0].profit == 40
    harvest_calls = [call for call in client.calls if call[0] == "POST" and call[2].get("action") in ("harvest_all", "harvest")]
    assert harvest_calls == [("POST", "https://si-qi.xyz/plant_game.php", {
        "action": "harvest_all", "imagehash": "hash-1", "imagestring": "AB12",
    })]


def test_siqi_staged_flow_ocr_failure_falls_back_to_each_plot():
    client = BatchHarvestClient()
    report = FarmExecutor(client, Logger(), ocr_recognizer=BatchOcr(None)).run_site(
        "session=value", SiqiConfig(),
        {"request_interval": 0, "max_sell_per_run": 2},
        {"default_seed_id": 3, "captcha_ocr": True},
    )

    assert [action.action for action in report.actions[:2]] == ["harvest", "harvest"]
    harvest_calls = [call for call in client.calls if call[0] == "POST" and call[2].get("action") in ("harvest_all", "harvest")]
    assert harvest_calls == [
        ("POST", "https://si-qi.xyz/plant_game.php", {"action": "harvest", "land_id": 1, "plot_index": 0}),
        ("POST", "https://si-qi.xyz/plant_game.php", {"action": "harvest", "land_id": 1, "plot_index": 1}),
    ]


def test_siqi_staged_flow_harvests_each_plot_when_ocr_disabled():
    client = StagedClient()
    report = FarmExecutor(client, Logger()).run_site(
        "session=value",
        SiqiConfig(),
        {"request_interval": 0, "max_sell_per_run": 2},
        {"default_seed_id": 3, "captcha_ocr": False},
    )

    assert [action.action for action in report.actions] == ["harvest", "harvest", "plant", "sell", "sell"]
    assert [action.plot_index for action in report.actions[:2]] == [0, 1]
    harvest_calls = [call for call in client.calls if call[0] == "POST" and call[2].get("action") == "harvest"]
    assert harvest_calls == [
        ("POST", "https://si-qi.xyz/plant_game.php", {"action": "harvest", "land_id": 1, "plot_index": 0}),
        ("POST", "https://si-qi.xyz/plant_game.php", {"action": "harvest", "land_id": 1, "plot_index": 1}),
    ]
    assert report.actions[2].target == "玉米"
    assert report.actions[2].quantity == 2
    assert report.actions[2].profit == -60
    plant_calls = [call for call in client.calls if call[0] == "POST" and call[2].get("action") == "plant_fill_empty"]
    assert plant_calls == [("POST", "https://si-qi.xyz/plant_game.php", {
        "action": "plant_fill_empty", "seed_id": 3,
    })]
    sell_calls = [call for call in client.calls if call[0] == "POST" and call[2].get("action") == "sell_inventory"]
    assert len(sell_calls) == 2
    assert all(call[2]["seed_id"] == 1 for call in sell_calls)


class InsufficientStockClient(StagedClient):
    """模拟快照 quantity 大于实际可售数量：前两次出售成功，第三次报"背包中该作物数量不足"。"""

    def __init__(self):
        super().__init__()
        self.sell_count = 0

    def get(self, url, cookies, retryable=True):
        self.calls.append(("GET", url, None))
        responses = [
            self._farm([
                {"land_id": 1, "plot_index": 0, "seed_id": 1, "is_ready": 0, "harvest_time": 1},
                {"land_id": 1, "plot_index": 1, "seed_id": 1, "is_ready": 0, "harvest_time": 1},
                {"land_id": 2, "plot_index": None, "seed_id": None, "is_ready": 0},
            ]),
            self._farm([
                {"land_id": 1, "plot_index": 0, "seed_id": None, "is_ready": 0},
                {"land_id": 1, "plot_index": 1, "seed_id": None, "is_ready": 0},
                {"land_id": 2, "plot_index": None, "seed_id": None, "is_ready": 0},
            ], inventory=[{"seed_id": 3, "name": "玉米", "quantity": 3}]),
            self._farm([], inventory=[{"seed_id": 3, "name": "玉米", "quantity": 3}]),
            self._farm([], inventory=[{"seed_id": 3, "name": "玉米", "quantity": 3}]),
        ]
        response = responses[min(self.fetch_count, len(responses) - 1)]
        self.fetch_count += 1
        return Response(response)

    def post(self, url, cookies, data=None, json=None, allow_redirects=True, retryable=False):
        self.calls.append(("POST", url, data))
        if data and data.get("action") == "harvest":
            return Response('{"success":true,"msg":"收获成功","reward":20}')
        if data and data.get("action") == "plant_fill_empty":
            return Response('{"success":true,"msg":"种植成功"}')
        if data and data.get("action") == "sell_inventory":
            self.sell_count += 1
            if self.sell_count <= 2:
                return Response('{"success":true,"msg":"出售成功"}')
            return Response('{"success":false,"msg":"背包中该作物数量不足"}')
        raise AssertionError(f"unexpected POST {data}")


def test_siqi_staged_sell_stops_on_insufficient_stock_without_partial():
    client = InsufficientStockClient()
    report = FarmExecutor(client, Logger()).run_site(
        "session=value", SiqiConfig(),
        {"request_interval": 0, "max_sell_per_run": 50, "auto_sell": True},
        {"default_seed_id": 3, "captcha_ocr": False},
    )

    sell_actions = [action for action in report.actions if action.action == "sell"]
    assert len(sell_actions) == 3
    assert sell_actions[0].success and sell_actions[1].success
    # 第三次卖空后的软停止：不计成功，但 skipped=True，不污染站点状态。
    assert not sell_actions[2].success
    assert sell_actions[2].skipped is True
    # 卖空后立即停止，不会继续对空库存发请求。
    sell_calls = [call for call in client.calls if call[0] == "POST" and call[2].get("action") == "sell_inventory"]
    assert len(sell_calls) == 3
    # 软停止不计失败，站点应为 completed。
    assert report.status == "completed"
