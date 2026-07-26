import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from sites.playlet import PlayLetConfig


HTML = """
<html><body>
<h2>菜市场</h2>
<h3>农作物种植区</h3>
<table><tr><td>小麦</td><td>880</td></tr></table>
<h3>动物养殖区</h3>
<table><tr><td>鸡</td><td>1680</td></tr></table>
<a href="?action=harvest&type=crop&id=1">收获</a>
<h2>仓库</h2>
<table><tr><td><img src="wheat.png"></td><td>小麦</td><td>2</td>
<td>1小时20分钟</td><td><a href="?action=sell&key=crop_1_42">出售</a></td></tr></table>
</body></html>
"""


def test_playlet_parsers():
    config = PlayLetConfig()
    prices = config.parse_market_prices(HTML)
    statuses = config.parse_crop_status(HTML)
    warehouse = config.parse_warehouse_items(HTML)

    assert prices["crop_1"] == 880
    assert prices["animal_1"] == 1680
    assert statuses["crop_1"]["can_harvest"] is True
    assert warehouse
    assert warehouse[0]["name"] == "小麦"
    assert warehouse[0]["quantity"] == 2
    assert warehouse[0]["expire_minutes"] == 80
    assert warehouse[0]["crop_key"] == "crop_1"


if __name__ == "__main__":
    test_playlet_parsers()
    print("FarmAuto PlayLet parser smoke test passed")
