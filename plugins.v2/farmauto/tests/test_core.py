import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from core.models import WarehouseItem, parse_expire_minutes
from core.strategy import is_expiry, plan_smart, should_sell
from sites.playlet import PlayLetConfig


def test_expiry_and_profit_policy():
    assert parse_expire_minutes("1天2小时3分钟") == 1563
    assert parse_expire_minutes("已过期") == 0
    assert parse_expire_minutes("未知") is None
    item = WarehouseItem("小麦", 1, "30分钟", 30, "crop_1", "crop_1")
    assert is_expiry(item, 60)
    crop = PlayLetConfig.crops["crop_1"]
    assert should_sell(crop, 501, {})
    assert not should_sell(crop, 500, {})
    assert should_sell(crop, 600, {"min_profit_rate": 0.2})


def test_smart_plan_orders_warehouse_before_field():
    config = PlayLetConfig()
    snapshot = {
        "market_prices": {"crop_1": 800},
        "crop_status": {"crop_1": {"can_harvest": True}},
    }
    warehouse = [{
        "name": "小麦", "quantity": 2, "expire_raw": "1小时",
        "expire_minutes": 60, "sell_key": "crop_1_1", "crop_key": "crop_1",
    }]
    plan = plan_smart(snapshot, warehouse, config, {"max_sell_per_run": 3})
    assert [step["op"] for step in plan] == ["sell", "harvest", "plant", "sell"]
    assert plan[0]["source"] == "warehouse"
    assert plan[-1]["source"] == "field"


if __name__ == "__main__":
    test_expiry_and_profit_policy()
    test_smart_plan_orders_warehouse_before_field()
    print("FarmAuto core smoke tests passed")
