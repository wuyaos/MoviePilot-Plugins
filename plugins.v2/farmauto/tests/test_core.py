import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from core.models import WarehouseItem, parse_expire_minutes
from core.strategy import (
    is_expiry, plan_generic_run, plan_harvest, plan_run, plan_siqi_run,
    plan_smart, should_sell,
)
from sites.playlet import PlayLetConfig
from sites.siqi import SiqiConfig


def test_default_action_result_parsers_reject_failure_text():
    config = PlayLetConfig()

    assert not config.parse_harvest_result("收获失败：魔力不足")["success"]
    assert not config.parse_plant_result("种植失败：魔力不足", "plant")["success"]
    assert not config.parse_plant_result("养殖失败：魔力不足", "breed")["success"]
    assert not config.parse_sell_result("出售失败：物品不存在")["success"]
    assert not config.parse_batch_sell_result("批量出售失败")["success"]


def test_default_action_result_parsers_keep_known_success_responses():
    config = PlayLetConfig()

    assert config.parse_harvest_result("收获成功")["success"]
    assert config.parse_plant_result("种植成功", "plant")["success"]
    assert config.parse_plant_result("养殖成功", "breed")["success"]
    assert config.parse_sell_result("出售成功，获得 100 魔力")["success"]


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


def _automation_fixture():
    config = PlayLetConfig()
    snapshot = {
        "market_prices": {"crop_1": 800},
        "crop_status": {"crop_1": {"can_harvest": True}},
    }
    warehouse = [{
        "name": "小麦", "quantity": 2, "expire_raw": "30分钟",
        "expire_minutes": 30, "sell_key": "crop_1_1", "crop_key": "crop_1",
    }]
    return config, snapshot, warehouse


def test_auto_sell_disabled_produces_no_sells():
    config, snapshot, warehouse = _automation_fixture()

    plan = plan_smart(snapshot, warehouse, config, {"auto_sell": False})

    assert "sell" not in [step["op"] for step in plan]


def test_auto_harvest_disabled_does_not_assume_field_was_harvested():
    config, snapshot, warehouse = _automation_fixture()

    plan = plan_smart(snapshot, warehouse, config, {"auto_harvest": False})

    field_ops = [step["op"] for step in plan if step["source"] == "field"]
    assert field_ops == []
    assert [step["op"] for step in plan] == ["sell"]


def test_auto_plant_disabled_still_harvests_and_sells():
    config, snapshot, warehouse = _automation_fixture()

    plan = plan_smart(snapshot, warehouse, config, {"auto_plant": False})

    ops = [step["op"] for step in plan]
    assert "harvest" in ops
    assert "sell" in ops
    assert "plant" not in ops


def test_expiry_and_profit_sales_can_both_be_disabled():
    config, snapshot, warehouse = _automation_fixture()

    plan = plan_harvest(
        snapshot,
        warehouse,
        config,
        {"auto_sell": False, "expiry_sale": False},
    )

    assert "sell" not in [step["op"] for step in plan]


def test_plan_run_merges_harvest_sell_and_expiry():
    """plan_run 统一流程：收获→出售(盈利/临期)→种植；不亏钱除临期。"""
    config = PlayLetConfig()
    snapshot = {
        "market_prices": {"crop_1": 800},
        "crop_status": {"crop_1": {"can_harvest": True}},
    }
    warehouse = [{
        "name": "小麦", "quantity": 2, "expire_raw": "30分钟",
        "expire_minutes": 30, "sell_key": "crop_1_1", "crop_key": "crop_1",
    }]
    plan = plan_run(snapshot, warehouse, config, {})
    ops = [step["op"] for step in plan]
    assert "harvest_all" in ops and "plant" in ops and "sell" in ops
    # 盈利出售走 warehouse
    sell_steps = [step for step in plan if step["op"] == "sell"]
    assert sell_steps and all(step["source"] == "warehouse" for step in sell_steps)


def test_generic_plan_skips_harvest_all_without_ready_crop():
    config = PlayLetConfig()
    snapshot = {
        "market_prices": {},
        "crop_status": {
            "crop_1": {"can_harvest": False, "state": "growing"},
            "crop_2": {"can_harvest": False, "state": "unknown"},
        },
    }

    plan = plan_generic_run(snapshot, [], config, {})

    assert "harvest_all" not in [step["op"] for step in plan]
    assert "plant" not in [step["op"] for step in plan]


def test_siqi_plan_harvests_each_ready_plot_and_plants_once():
    config = SiqiConfig()
    snapshot = {
        "market_prices": {"crop_1": 20},
        "crop_status": {
            "crop_1_1_0": {
                "can_harvest": True, "state": "ripe", "crop_key": "crop_1",
                "land_id": 1, "plot_index": 0,
            },
            "crop_1_1_1": {
                "can_harvest": True, "state": "ripe", "crop_key": "crop_1",
                "land_id": 1, "plot_index": 1,
            },
            "empty_1_2": {"can_harvest": False, "state": "empty", "plot_index": 2},
            "locked_2_None": {"can_harvest": False, "state": "locked", "plot_index": None},
        },
    }

    plan = plan_siqi_run(snapshot, [], config, {})

    assert [step["op"] for step in plan] == ["harvest", "harvest", "plant"]
    assert [step["crop_key"] for step in plan[:2]] == ["crop_1_1_0", "crop_1_1_1"]
    assert plan[-1]["crop_key"] == "all"


def test_plan_run_expiry_only_allows_loss():
    """临期但亏钱的仓库项，仅 expiry_sale 允许出售。"""
    config = PlayLetConfig()
    crop_1 = PlayLetConfig.crops["crop_1"]  # cost=500
    assert crop_1["cost"] == 500
    snapshot = {
        "market_prices": {"crop_1": 100},  # 市价 100 < 成本 500，亏钱
        "crop_status": {},
    }
    warehouse = [{
        "name": "小麦", "quantity": 1, "expire_raw": "30分钟",
        "expire_minutes": 30, "sell_key": "crop_1_1", "crop_key": "crop_1",
    }]
    # 关闭临期出售：不应出售亏钱项
    plan = plan_run(snapshot, warehouse, config, {"expiry_sale": False})
    assert "sell" not in [step["op"] for step in plan]
    # 开启临期出售：允许亏钱出售临期项
    plan = plan_run(snapshot, warehouse, config, {"expiry_sale": True})
    assert any(step["op"] == "sell" for step in plan)


if __name__ == "__main__":
    test_expiry_and_profit_policy()
    test_smart_plan_orders_warehouse_before_field()
    print("FarmAuto core smoke tests passed")
