import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from sites.novahd import NovaHDConfig


HTML = """
<div class="points-display"><span>当前魔力: 9,876</span></div>
<h2>农作物种植区</h2>
<div class="farm-item"><h3>花生</h3><p class="growing-status">剩余时间：2小时5分钟</p></div>
<div class="farm-item"><h3>土豆</h3><a class="btn" href="?action=harvest&type=crop&id=4">收获</a></div>
<h2>仓库</h2>
<table class="warehouse-table">
<tr><th>图</th><th>名称</th><th>数量</th><th>剩余</th><th>操作</th></tr>
<tr><td><img></td><td><strong>花生</strong></td><td>3</td><td>1天2小时</td><td><a href="?action=sell&key=crop_3_77&page=1">出售</a></td></tr>
</table><div class="pagination-info">页 1 共 2</div>
<h2>菜市场</h2>
<table class="market-table"><tr><th>图</th><th>名称</th><th>价格</th></tr>
<tr><td><img src="p"></td><td>花生</td><td>2500</td></tr>
<tr><td><img src="c"></td><td><span>牛</span></td><td>12000</td></tr></table>
"""


def test_novahd_parsers():
    config = NovaHDConfig()
    assert config.parse_market_prices(HTML) == {"crop_3": 2500, "animal_4": 12000}
    status = config.parse_crop_status(HTML)
    assert status["crop_3"] == {
        "can_harvest": False,
        "remaining_minutes": 125,
        "state": "growing",
    }
    assert status["crop_4"]["can_harvest"] is True
    warehouse = config.parse_warehouse_items(HTML)
    assert warehouse[0]["crop_key"] == "crop_3"
    assert warehouse[0]["quantity"] == 3
    assert warehouse[0]["expire_minutes"] == 1560
    assert warehouse[0]["sell_key"] == "crop_3_77"
    assert config.parse_warehouse_page(HTML)[1] == 2
    assert config.parse_bonus(HTML) == "9876"
    assert config.get_sell_key(HTML, "crop", 3) == "crop_3_77"


def test_novahd_empty_html_is_safe():
    config = NovaHDConfig()
    assert config.parse_market_prices("") == {}
    assert config.parse_warehouse_items("") == []
    assert config.parse_bonus("") is None


if __name__ == "__main__":
    test_novahd_parsers()
    test_novahd_empty_html_is_safe()
    print("NovaHD parser tests passed")
