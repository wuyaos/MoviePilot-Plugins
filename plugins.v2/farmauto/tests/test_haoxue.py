import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from sites.haoxue import HaoxueConfig


HTML = """
<div class="points-display">当前火花： 6,543</div>
<h2>动物养殖区</h2>
<div class="farm-item"><h3>羊</h3><p class="growing-status">剩余时间: 3小时15分钟</p></div>
<div class="farm-item"><h3>猪</h3><a class="btn" href="?action=harvest&amp;type=animal&amp;id=2">收获</a></div>
<h2>仓库</h2>
<table class="warehouse-table"><tr><th>名称</th><th>数量</th><th>收获时间</th><th>剩余</th><th>操作</th></tr>
<tr><td>羊</td><td>4</td><td>2026-04-01</td><td>45分钟</td><td><a href="?action=sell&amp;key=animal_3_88&amp;page=2">出售</a></td></tr>
</table><div class="pagination-info">第 2 / 3 页</div>
<h2>菜市场</h2>
<table class="market-table"><tr><th>名称</th><th>价格</th></tr>
<tr><td><span>羊</span></td><!-- current --><td>6500</td></tr>
<tr><td>玉米</td><td>1400</td></tr></table>
"""


def test_haoxue_parsers():
    config = HaoxueConfig()
    assert config.parse_market_prices(HTML) == {"animal_3": 6500, "crop_2": 1400}
    status = config.parse_crop_status(HTML)
    assert status["animal_3"] == {"can_harvest": False, "remaining_minutes": 195}
    assert status["animal_2"]["can_harvest"] is True
    warehouse = config.parse_warehouse_items(HTML)
    assert warehouse[0]["crop_key"] == "animal_3"
    assert warehouse[0]["quantity"] == 4
    assert warehouse[0]["expire_minutes"] == 45
    assert warehouse[0]["sell_key"] == "animal_3_88"
    assert config.parse_warehouse_page(HTML)[1] == 3
    assert config.parse_bonus(HTML) == "6543"
    assert config.get_sell_key(HTML, "animal", 3) == "animal_3_88"


def test_haoxue_empty_html_is_safe():
    config = HaoxueConfig()
    assert config.parse_market_prices("") == {}
    assert config.parse_warehouse_items("") == []
    assert config.parse_bonus("") is None


if __name__ == "__main__":
    test_haoxue_parsers()
    test_haoxue_empty_html_is_safe()
    print("Haoxue parser tests passed")
