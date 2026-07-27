import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from sites.siqi import SiqiConfig


FARM_HTML = """
<div class="farm-page">
  <span>当前魔力值：12,345</span>
  <table>
    <tr><td>萝卜</td><td>20 魔力</td></tr>
    <tr data-seed-id="1"><td>萝卜</td><td>3</td></tr>
  </table>
  <a href="?action=harvest&amp;seed_id=1&amp;land_id=2&amp;plot_index=0">收获</a>
</div>
"""

FARM_JSON = """{
  "success": true,
  "user_bonus": 12345,
  "seeds": [{"id": 1, "name": "萝卜", "cost": 10, "base_reward": 20}],
  "user_lands": [{"land_id": 2, "plot_index": 0, "seed_id": 1, "is_ready": 1, "harvest_time": 1700000000}],
  "inventory": [{"seed_id": 1, "name": "萝卜", "quantity": 3}]
}"""

DYNAMIC_FARM_JSON = """{
  "success": true,
  "seeds": [
    {"id": 2, "name": "玉米", "cost": 30, "base_reward": 50, "grow_time": 600},
    {"id": 3, "name": "南瓜", "cost": 40, "base_reward": 70, "unlock_harvest": 10}
  ],
  "user_lands": [{"land_id": 2, "plot_index": 0, "seed_id": 3, "is_ready": 1}],
  "inventory": [{"seed_id": 3, "name": "南瓜", "quantity": 2}]
}"""

CAPTCHA_HTML = """
<script>window.harvestCaptcha = {"imagehash":"hash-123"};</script>
<img id="harvest-captcha" src="/captcha.php?id=7&amp;scene=harvest">
"""

STEAL_TARGETS_HTML = """
<button data-victim-id="42" data-username="Alice">Alice 的农场</button>
<button data-target-id="84" data-name="Bob">Bob 的农场</button>
"""

LIKE_TARGETS_HTML = """
<li data-username="Alice">Alice</li>
<li data-like-target="Bob">Bob</li>
"""


def _query(url):
    return parse_qs(urlparse(url).query)


def test_siqi_metadata_and_urls():
    config = SiqiConfig()

    assert config.site_id == "siqi"
    assert config.site_name == "思齐"
    assert config.domains == ["si-qi.xyz", "siqi.xyz"]
    assert config.get_farm_url() == "https://si-qi.xyz/plant_game.php?action=fetch"
    assert config.get_warehouse_url().endswith("?action=fetch")
    assert config.capabilities == {"captcha", "social", "sell_inventory", "plant_all"}
    assert config.currency == "魔力"
    assert config.crops["crop_1"]["action"] == "plant"

    assert config.get_harvest_all_submit_url() == "https://si-qi.xyz/plant_game.php"
    assert _query(config.get_harvest_plot_url(2, 0)) == {
        "action": ["harvest"], "land_id": ["2"], "plot_index": ["0"],
    }
    assert config.get_captcha_image_url("hash-123").endswith("captcha.php?imagehash=hash-123")
    assert _query(config.get_steal_target_url()) == {"action": ["get_victim_farm"]}
    assert config.get_steal_plot_url() == "https://si-qi.xyz/plant_game.php"
    assert _query(config.get_like_target_url()) == {"action": ["random_like_targets"]}
    assert config.get_like_submit_url() == "https://si-qi.xyz/plant_game.php"
    assert config.get_buy_plot_slot_url() == "https://si-qi.xyz/plant_game.php"


def test_siqi_farm_and_warehouse_parsers():
    config = SiqiConfig()

    assert config.parse_market_prices(FARM_HTML) == {"crop_1": 20}
    assert config.parse_bonus(FARM_HTML) == "12345"
    assert config.parse_crop_status(FARM_HTML)["crop_1"]["can_harvest"] is True
    assert config.parse_warehouse_items(FARM_HTML)[0]["quantity"] == 3

    assert config.parse_market_prices(FARM_JSON) == {"crop_1": 20}
    assert config.parse_bonus(FARM_JSON) == "12345"
    assert config.parse_crop_status(FARM_JSON)["crop_1_2_0"] == {
        "can_harvest": True,
        "land_id": 2,
        "plot_index": 0,
        "harvest_time": 1700000000,
        "state": "ripe",
        "seed_id": 1,
        "crop_key": "crop_1",
    }
    item = config.parse_warehouse_items(FARM_JSON)[0]
    assert item["name"] == "萝卜"
    assert item["quantity"] == 3
    assert item["sell_key"] == "1"
    assert item["crop_key"] == "crop_1"
    assert config.get_sell_key(FARM_JSON, "crop", 1) == "1"
    assert config.parse_warehouse_page(FARM_JSON)[1] is None


def test_siqi_html_action_response_does_not_leak_page_text_into_message():
    config = SiqiConfig()
    html = "<html><body>思齐种菜赚魔力<script>const text='收获成功';</script>" + "页面正文" * 200 + "</body></html>"

    result = config.parse_harvest_result(html)

    assert result == {"success": True, "message": "收获成功"}


def test_siqi_expired_harvest_time_marks_ripe_and_locked_land_stays_locked():
    config = SiqiConfig()
    payload = """{
      "success": true,
      "seeds": [{"id": 1, "name": "萝卜", "cost": 10}],
      "user_lands": [
        {"land_id": 1, "plot_index": 0, "seed_id": 1, "is_ready": 0, "harvest_time": 1},
        {"land_id": 1, "plot_index": 1, "seed_id": 1, "is_ready": 0, "harvest_time": 9999999999},
        {"land_id": 2, "plot_index": null, "seed_id": null, "is_ready": 0, "harvest_time": 1}
      ]
    }"""

    status = config.parse_crop_status(payload)
    lands = config.to_land_states(payload)

    assert status["crop_1_1_0"]["state"] == "ripe"
    assert status["crop_1_1_0"]["can_harvest"] is True
    assert status["crop_1_1_1"]["state"] == "growing"
    assert status["crop_1_1_1"]["can_harvest"] is False
    assert status["locked_2_None"]["state"] == "locked"
    assert status["locked_2_None"]["is_empty"] is False
    assert [land.state for land in lands] == ["ripe", "growing", "locked"]


def test_siqi_resolves_dynamic_crops_and_inventory_keys():
    config = SiqiConfig()

    assert config.resolve_crops(DYNAMIC_FARM_JSON) == {
        "crop_2": {
            "name": "玉米", "cost": 30, "base_reward": 50, "type": "crop", "id": 2,
            "action": "plant", "grow_time": 600, "unlock_harvest": 0,
        },
        "crop_3": {
            "name": "南瓜", "cost": 40, "base_reward": 70, "type": "crop", "id": 3,
            "action": "plant", "grow_time": None, "unlock_harvest": 10,
        },
    }
    assert config.resolve_crops("") is None
    assert config.parse_market_prices(DYNAMIC_FARM_JSON) == {
        "crop_2": 50,
        "crop_3": 70,
    }
    assert config.parse_crop_status(DYNAMIC_FARM_JSON)["crop_3_2_0"]["can_harvest"] is True
    assert config.parse_warehouse_items(DYNAMIC_FARM_JSON)[0]["crop_key"] == "crop_3"


def test_siqi_captcha_target_and_result_parsers():
    config = SiqiConfig()

    assert config.parse_captcha_info(CAPTCHA_HTML) == {
        "token": "hash-123",
        "imagehash": "hash-123",
        "image_url": "/captcha.php?id=7&scene=harvest",
    }
    assert config.parse_captcha_info(
        '{"success":true,"captcha":{"imagehash":"json-hash","image_url":"/captcha.php?id=8"}}'
    ) == {
        "token": "json-hash",
        "imagehash": "json-hash",
        "image_url": "/captcha.php?id=8",
    }
    assert config.parse_steal_targets(STEAL_TARGETS_HTML) == [
        {"target_id": "42", "name": "Alice"},
        {"target_id": "84", "name": "Bob"},
    ]
    assert config.parse_steal_targets(
        '{"success":true,"victim_id":42,"victim_name":"Alice","victim_plots":[{"land_id":2,"plot_index":0}]}'
    ) == [{
        "target_id": 42,
        "name": "Alice",
        "plots": [{"land_id": 2, "plot_index": 0}],
    }]
    assert config.parse_like_targets(LIKE_TARGETS_HTML) == ["Alice", "Bob"]
    assert config.parse_like_targets('{"success":true,"usernames":["Alice","Bob"]}') == ["Alice", "Bob"]
    assert config.parse_buy_slot_targets(
        '{"success":true,"lands":[{"id":2,"can_buy_slot":true},{"id":3,"can_buy_slot":false}]}'
    ) == [2]
    assert config.parse_buy_slot_targets(
        '{"success":true,"plot_slot":{"enabled":true,"next_slot_cost_by_land":{"2":100,"3":null}}}'
    ) == ["2"]

    steal_result = config.parse_steal_result('{"success":true,"reward":5,"msg":"偷菜成功"}')
    assert steal_result["success"] is True
    assert steal_result["message"] == "偷菜成功"
    assert steal_result["reward"] == 5
    assert config.parse_like_result("<div>点赞成功</div>")["success"] is True
    assert config.parse_buy_slot_result('{"success":false,"message":"魔力不足"}') == {
        "success": False,
        "message": "魔力不足",
    }


def test_siqi_empty_input_is_safe():
    config = SiqiConfig()

    assert config.parse_market_prices("") == {}
    assert config.parse_warehouse_items("") == []
    assert config.parse_bonus("") is None
    assert config.parse_captcha_info("") == {}
    assert config.parse_steal_targets("") == []
    assert config.parse_like_targets("") == []
    assert config.parse_steal_result("")["success"] is False
    assert config.parse_like_result("")["success"] is False
    assert config.parse_buy_slot_result("")["success"] is False


if __name__ == "__main__":
    test_siqi_metadata_and_urls()
    test_siqi_farm_and_warehouse_parsers()
    test_siqi_captcha_target_and_result_parsers()
    test_siqi_empty_input_is_safe()
    print("Siqi parser tests passed")
