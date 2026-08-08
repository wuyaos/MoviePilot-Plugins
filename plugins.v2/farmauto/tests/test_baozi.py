import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from sites.baozi import BaoziConfig


HTML = """
<html><body>
<h2>菜市场</h2>
<table>
  <tr><td>小麦</td><td>880</td></tr>
  <tr><td>鸡</td><td>1680</td></tr>
</table>
<!-- 仓库 -->
<table>
  <tr>
    <td>小麦</td><td>2</td><td>1天2小时</td>
    <td><a href="?action=sell&key=crop_1_42">出售</a></td>
  </tr>
</table>
</body></html>
"""


BONUS_HTML = """
<div>
  <a href="mybonus.php"><span>魔力值 ：</span></a> 3,424.6
</div>
"""


IMAGE_MARKET_HTML = """
<table>
  <tr><td><img src="wheat.png"></td><td>小麦</td><td>920</td></tr>
  <tr><td><img src="cow.png"></td><td>牛</td><td>12000</td></tr>
</table>
"""


def test_baozi_parsers():
    config = BaoziConfig()

    assert config.parse_bonus(BONUS_HTML) == "3424.6"
    assert config.parse_market_prices(HTML) == {
        "crop_1": 880,
        "animal_1": 1680,
    }

    warehouse = config.parse_warehouse_items(HTML)
    assert len(warehouse) == 1
    assert warehouse[0]["name"] == "小麦"
    assert warehouse[0]["quantity"] == 2
    assert warehouse[0]["expire"] == "1天2小时"
    assert warehouse[0]["expire_raw"] == "1天2小时"
    assert warehouse[0]["expire_minutes"] == 1560
    assert warehouse[0]["sell_key"] == "crop_1_42"
    assert warehouse[0]["crop_key"] == "crop_1"


def test_baozi_image_market_and_adapter_contract():
    config = BaoziConfig()

    assert config.parse_market_prices(IMAGE_MARKET_HTML) == {
        "crop_1": 920,
        "animal_4": 12000,
    }
    assert config.get_sell_key("", "crop", 3) == "crop_3"
    assert config.get_sell_key("", "animal", 4) == "animal_4"
    assert config.supports("harvest_all")
    assert not config.supports("warehouse_pagination")


def test_baozi_empty_html_is_safe():
    config = BaoziConfig()

    assert config.parse_bonus("") is None
    assert config.parse_market_prices("") == {}
    assert config.parse_warehouse_items("") == []
