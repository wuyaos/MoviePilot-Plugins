import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from sites.playlet import PlayLetConfig


HTML = """
<div class="points-display">当前魔力值: 12,345</div>
<div class="farm-section">
  <h2>农作物种植区</h2>
  <div class="farm-item"><h3>小麦</h3><p>成长时间: 4小时</p><p class="growing-status">剩余时间: 1小时20分钟</p></div>
  <div class="farm-item"><h3>玉米</h3><a class="btn" href="?action=harvest&amp;type=crop&amp;id=2">收获</a></div>
</div>
<div class="farm-section"><h2>动物养殖区</h2>
  <div class="farm-item"><h3>鸡</h3><a href="?action=harvest&type=animal&id=1">收获</a></div>
</div>
<div class="farm-section"><h2>仓库</h2>
  <table class="warehouse-table">
    <tr><th>图</th><th>名称</th><th>数量</th><th>剩余</th><th>操作</th></tr>
    <tr><td><img src="x.png"></td><td>小麦</td><td>2</td><td>30分钟</td><td><a href="?action=sell&amp;key=crop_1_9&amp;page=1">出售</a></td></tr>
  </table><div class="pagination-info">页 1 共 3</div>
</div>
<div class="farm-section"><h2>菜市场</h2>
  <div class="market-category"><h3>农作物</h3><table class="market-table"><tr><th>图</th><th>名称</th><th>价格</th></tr><tr><td><img></td><td><b>小麦</b></td><td>880</td></tr></table></div>
  <div class="market-category"><h3>动物</h3><table class="market-table"><tr><td><img></td><td>鸡</td><td>1680</td></tr></table></div>
</div>
"""


def test_playlet_parsers():
    config = PlayLetConfig()
    assert config.parse_market_prices(HTML) == {"crop_1": 880, "animal_1": 1680}
    status = config.parse_crop_status(HTML)
    assert status["crop_1"] == {
        "can_harvest": False,
        "remaining_minutes": 80,
        "state": "growing",
        "grow_time": "4小时",
    }
    assert status["crop_2"]["can_harvest"] is True
    assert status["animal_1"]["can_harvest"] is True
    warehouse = config.parse_warehouse_items(HTML)
    assert warehouse[0]["crop_key"] == "crop_1"
    assert warehouse[0]["quantity"] == 2
    assert warehouse[0]["expire_minutes"] == 30
    assert warehouse[0]["sell_key"] == "crop_1_9"
    assert config.parse_warehouse_page(HTML)[1] == 2
    assert config.parse_bonus(HTML) == "12345"
    assert config.supports("warehouse_pagination")


def test_playlet_empty_html_is_safe():
    config = PlayLetConfig()
    assert config.parse_market_prices("") == {}
    assert config.parse_warehouse_items("") == []
    assert config.parse_bonus("") is None


if __name__ == "__main__":
    test_playlet_parsers()
    test_playlet_empty_html_is_safe()
    print("PlayLet parser tests passed")
