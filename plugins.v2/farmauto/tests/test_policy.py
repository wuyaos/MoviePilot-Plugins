import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from core.executor import FarmExecutor
from core.strategy import effective_site_mode, effective_site_policy, site_is_enabled
from sites.base import FarmSiteConfig


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


class FakeHttpClient:
    def __init__(self):
        self.urls = []

    def get(self, url, cookies):
        self.urls.append(url)
        if "sort=expire_asc" in url:
            return FakeResponse("warehouse")
        return FakeResponse("farm")


class FakeSiteConfig(FarmSiteConfig):
    site_id = "playlet"
    site_name = "PlayLet"
    base_url = "https://farm.test"
    crops = {
        "crop_1": {
            "name": "小麦", "cost": 100, "type": "crop", "id": 1, "action": "plant"
        }
    }

    def parse_market_prices(self, html):
        return {"crop_1": 110}

    def parse_crop_status(self, html):
        return {"crop_1": {"can_harvest": True}}

    def parse_warehouse_items(self, html):
        return [{
            "name": "小麦", "quantity": 1, "expire_raw": "1小时",
            "expire_minutes": 60, "sell_key": "crop_1_1", "crop_key": "crop_1",
        }]

    def get_sell_key(self, html, item_type, item_id):
        return "crop_1_1"


class Logger:
    def error(self, message):
        pass


def enabled_site_ids(site_ids, overrides):
    return [site_id for site_id in site_ids if site_is_enabled(overrides, site_id)]


def test_effective_mode_and_enabled_overrides():
    overrides = {
        "playlet": {"mode": "harvest"},
        "skit": {"enabled": False},
    }

    assert effective_site_mode("smart", overrides, "playlet") == "harvest"
    assert effective_site_mode("smart", overrides, "novahd") == "smart"
    assert "mode" not in effective_site_policy({}, overrides, "playlet")
    assert not site_is_enabled(overrides, "skit")
    assert site_is_enabled(overrides, "playlet")
    assert enabled_site_ids(["playlet", "skit"], overrides) == ["playlet"]


def test_min_profit_rate_override_is_used_by_smart_plan():
    global_policy = {
        "min_profit_rate": 0.0,
        "max_sell_per_run": 2,
        "request_interval": 0,
        "dry_run": True,
    }
    overrides = {"playlet": {"min_profit_rate": 0.2}}
    policy = effective_site_policy(global_policy, overrides, "playlet")

    report = FarmExecutor(FakeHttpClient(), Logger()).run_site(
        "session=value", FakeSiteConfig(), "smart", policy
    )

    assert policy["min_profit_rate"] == 0.2
    # min_profit_rate 不满足时跳过出售,但收获免费仍执行
    assert all(a.action != "sell" for a in report.actions)
    assert report.status == "skipped"
