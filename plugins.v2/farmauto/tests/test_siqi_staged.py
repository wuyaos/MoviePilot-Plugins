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
        if "action=harvest" in url:
            return Response('{"success":true,"msg":"收获成功"}')
        # 初始 fetch：两格成熟；收获后 refresh：两格空；种植后 refresh：玉米生长且背包有萝卜。
        responses = [
            self._farm([
                {"land_id": 1, "plot_index": 0, "seed_id": 1, "is_ready": 1},
                {"land_id": 1, "plot_index": 1, "seed_id": 1, "is_ready": 1},
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
        if data and data.get("action") == "plant_fill_empty":
            return Response('{"success":true,"msg":"种植成功"}')
        if data and data.get("action") == "sell_inventory":
            return Response('{"success":true,"msg":"出售成功"}')
        raise AssertionError(f"unexpected POST {data}")


class Logger:
    def error(self, _message):
        pass


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
        "session=value", SiqiConfig(), "smart",
        {"request_interval": 0}, {"default_seed_id": 3},
    )

    assert report.actions == []
    assert not any(call[0] == "POST" for call in client.calls)
    assert report.status == "completed"
    assert report.message == "无可执行操作"


def test_siqi_staged_flow_harvests_all_then_plants_default_seed_once_and_sells_inventory():
    client = StagedClient()
    report = FarmExecutor(client, Logger()).run_site(
        "session=value",
        SiqiConfig(),
        "smart",
        {"request_interval": 0, "max_sell_per_run": 2},
        {"default_seed_id": 3},
    )

    assert [action.action for action in report.actions] == ["harvest", "harvest", "plant", "sell", "sell"]
    assert [action.plot_index for action in report.actions[:2]] == [0, 1]
    assert report.actions[2].target == "玉米"
    assert report.actions[2].profit == -30
    plant_calls = [call for call in client.calls if call[0] == "POST" and call[2].get("action") == "plant_fill_empty"]
    assert plant_calls == [("POST", "https://si-qi.xyz/plant_game.php", {
        "action": "plant_fill_empty", "seed_id": 3,
    })]
    sell_calls = [call for call in client.calls if call[0] == "POST" and call[2].get("action") == "sell_inventory"]
    assert len(sell_calls) == 2
    assert all(call[2]["seed_id"] == 1 for call in sell_calls)
