import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from core.executor import FarmExecutor
from core.trend import PriceTrendStore
from sites.base import FarmSiteConfig


class FakeResponse:
    def __init__(self, text="成功", status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSiteConfig(FarmSiteConfig):
    site_id = "fake"
    site_name = "测试农场"
    base_url = "https://farm.test"
    crops = {
        "crop_1": {
            "name": "测试小麦",
            "cost": 100,
            "type": "crop",
            "id": 1,
            "action": "plant",
        }
    }

    def parse_market_prices(self, html):
        return {"crop_1": 150}

    def parse_crop_status(self, html):
        return {"crop_1": {"can_harvest": True}}

    def parse_warehouse_items(self, html):
        return [{
            "name": "测试小麦",
            "quantity": 1,
            "expire_raw": "1小时",
            "expire_minutes": 60,
            "sell_key": "warehouse_crop_1",
            "crop_key": "crop_1",
        }]

    def get_sell_key(self, html, item_type, item_id):
        return "field_crop_1"


class FakeHttpClient:
    def __init__(self, fail_token=None):
        self.fail_token = fail_token
        self.urls = []
        self.failed = False

    def get(self, url, cookies):
        self.urls.append(url)
        if self.fail_token and self.fail_token in url and not self.failed:
            self.failed = True
            raise RuntimeError("single action failed")
        if "sort=expire_asc" in url:
            return FakeResponse("仓库")
        if "action=harvest" in url:
            return FakeResponse("收获成功")
        if "action=plant" in url:
            return FakeResponse("种植成功")
        if "action=sell" in url:
            return FakeResponse("出售成功")
        return FakeResponse("农场首页")


class Logger:
    def error(self, message):
        pass


def run_smart(client, dry_run=False):
    return FarmExecutor(client, Logger()).run_site(
        "session=value",
        FakeSiteConfig(),
        "smart",
        {
            "max_sell_per_run": 2,
            "request_interval": 0,
            "dry_run": dry_run,
        },
    )


def test_smart_executes_warehouse_sell_harvest_plant_and_field_sell():
    report = run_smart(FakeHttpClient())

    assert [action.action for action in report.actions] == [
        "sell", "harvest", "plant", "sell"
    ]
    assert all(action.success for action in report.actions)
    assert report.trades_count == 4
    assert report.total_profit == 100
    assert report.status == "completed"


def test_dry_run_builds_plan_without_action_requests():
    client = FakeHttpClient()
    report = run_smart(client, dry_run=True)

    assert [action.action for action in report.actions] == [
        "sell", "harvest", "plant", "sell"
    ]
    assert report.trades_count == 0
    assert report.total_profit == 0
    assert len(client.urls) == 2
    assert not any("action=" in url for url in client.urls)


def test_single_action_exception_isolated_and_later_actions_continue():
    report = run_smart(FakeHttpClient(fail_token="action=plant"))

    assert [action.action for action in report.actions] == [
        "sell", "harvest", "plant", "sell"
    ]
    assert [action.success for action in report.actions] == [True, True, False, True]
    assert report.actions[2].message == "single action failed"
    assert report.trades_count == 3
    assert report.total_profit == 100
    assert report.status == "partial"


def test_harvest_failure_blocks_plant_and_field_sell_for_crop():
    report = run_smart(FakeHttpClient(fail_token="action=harvest"))

    assert [action.action for action in report.actions] == ["sell", "harvest"]
    assert [action.success for action in report.actions] == [True, False]
    assert report.trades_count == 1
    assert report.total_profit == 50
    assert report.status == "partial"


def test_market_prices_are_recorded_in_trend_store():
    trend_store = PriceTrendStore()

    FarmExecutor(FakeHttpClient(), Logger(), trend_store).run_site(
        "session=value",
        FakeSiteConfig(),
        "smart",
        {"request_interval": 0, "dry_run": True},
    )

    samples = trend_store.get("fake", "crop_1")
    assert len(samples) == 1
    assert samples[0][1] == 150
