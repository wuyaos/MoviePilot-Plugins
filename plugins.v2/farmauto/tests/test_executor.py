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

    def get(self, url, cookies, retryable=True):
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


class MultiCropSiteConfig(FakeSiteConfig):
    crops = {
        "crop_1": {
            "name": "测试小麦", "cost": 100, "type": "crop", "id": 1, "action": "plant",
        },
        "crop_2": {
            "name": "测试玉米", "cost": 200, "type": "crop", "id": 2, "action": "plant",
        },
    }

    def parse_market_prices(self, html):
        return {"crop_1": 150, "crop_2": 300}

    def parse_crop_status(self, html):
        return {
            "crop_1": {"can_harvest": False},
            "crop_2": {"can_harvest": False},
        }

    def parse_warehouse_items(self, html):
        return [
            {
                "name": "测试小麦", "quantity": 1, "expire_raw": "1小时",
                "expire_minutes": 60, "sell_key": "warehouse_crop_1", "crop_key": "crop_1",
            },
            {
                "name": "测试玉米", "quantity": 1, "expire_raw": "1小时",
                "expire_minutes": 60, "sell_key": "warehouse_crop_2", "crop_key": "crop_2",
            },
        ]


class DynamicCropSiteConfig(FakeSiteConfig):
    def resolve_crops(self, farm_html):
        return {
            "crop_2": {
                "name": "动态玉米", "cost": 200, "type": "crop", "id": 2,
                "action": "plant",
            }
        }

    def parse_market_prices(self, html):
        return {"crop_2": 300}

    def parse_crop_status(self, html):
        return {"crop_2": {"can_harvest": True}}

    def parse_warehouse_items(self, html):
        return [{
            "name": "动态玉米", "quantity": 1, "expire_raw": "1小时",
            "expire_minutes": 60, "sell_key": "warehouse_crop_2", "crop_key": "crop_2",
        }]


class BatchSellSiteConfig(MultiCropSiteConfig):
    capabilities = {"batch_sell"}


class BatchSellHttpClient(FakeHttpClient):
    def __init__(self, post_error=None):
        super().__init__()
        self.posts = []
        self.post_error = post_error

    def post(
        self,
        url,
        cookies,
        data=None,
        json=None,
        allow_redirects=True,
        retryable=False,
    ):
        self.posts.append({"url": url, "data": data})
        if self.post_error:
            raise self.post_error
        return FakeResponse("一键出售完成: 成功 2 个, 失败 0 个")


def run_multi_crop_smart(client, site_config, dry_run=False):
    return FarmExecutor(client, Logger()).run_site(
        "session=value",
        site_config,
        "smart",
        {"max_sell_per_run": 2, "request_interval": 0, "dry_run": dry_run},
    )


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
    assert report.total_profit == 0
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


def test_executor_uses_resolved_dynamic_crops():
    client = FakeHttpClient()
    report = FarmExecutor(client, Logger()).run_site(
        "session=value",
        DynamicCropSiteConfig(),
        "smart",
        {"max_sell_per_run": 2, "request_interval": 0},
    )

    assert [action.action for action in report.actions] == [
        "sell", "harvest", "plant", "sell"
    ]
    assert {action.target for action in report.actions} == {"动态玉米"}
    assert any("action=harvest&type=crop&id=2" in url for url in client.urls)
    assert any("action=plant&type=crop&id=2" in url for url in client.urls)


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


def test_batch_sell_posts_once_and_accumulates_each_item_profit():
    client = BatchSellHttpClient()
    report = run_multi_crop_smart(client, BatchSellSiteConfig())

    assert len(client.posts) == 1
    assert client.posts[0]["data"] == {
        "batch_keys[]": ["warehouse_crop_1", "warehouse_crop_2"]
    }
    assert [action.success for action in report.actions] == [True, True]
    assert [action.profit for action in report.actions] == [50, 100]
    assert report.trades_count == 2
    assert report.total_profit == 150


def test_batch_sell_does_not_duplicate_a_single_warehouse_key_by_quantity():
    client = BatchSellHttpClient()
    site_config = BatchSellSiteConfig()
    site_config.parse_warehouse_items = lambda html: [{
        "name": "测试小麦", "quantity": 3, "expire_raw": "1小时",
        "expire_minutes": 60, "sell_key": "warehouse_crop_1", "crop_key": "crop_1",
    }]

    report = run_multi_crop_smart(client, site_config)

    assert client.posts[0]["data"] == {"batch_keys[]": ["warehouse_crop_1"]}
    assert len(report.actions) == 1
    assert report.total_profit == 50


def test_batch_sell_failure_is_isolated_and_marks_the_batch_failed():
    client = BatchSellHttpClient(post_error=RuntimeError("batch action failed"))
    report = run_multi_crop_smart(client, BatchSellSiteConfig())

    assert len(client.posts) == 1
    assert [action.success for action in report.actions] == [False, False]
    assert all(action.message == "batch action failed" for action in report.actions)
    assert report.status == "partial"


def test_site_without_batch_sell_keeps_individual_get_requests():
    client = FakeHttpClient()
    report = run_multi_crop_smart(client, MultiCropSiteConfig())

    sell_urls = [url for url in client.urls if "action=sell" in url]
    assert len(sell_urls) == 2
    assert len(report.actions) == 2
    assert all(action.success for action in report.actions)


def test_batch_sell_dry_run_does_not_post_or_send_sell_get_requests():
    client = BatchSellHttpClient()
    report = run_multi_crop_smart(client, BatchSellSiteConfig(), dry_run=True)

    assert len(report.actions) == 2
    assert not client.posts
    assert not any("action=sell" in url for url in client.urls)


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
