import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from sites.skit import SkitConfig


HTML = """
<html><body>
<div class="points-display">当前魔力值: 12,345</div>
<div class="farm-section">
  <h2>农作物种植区</h2>
  <div class="farm-item">
    <h3>小麦</h3>
    <div class="item-info"><p>价格: 500</p></div>
    <p class="growing-status">剩余时间: 1小时20分钟</p>
  </div>
  <div class="farm-item">
    <h3>玉米</h3>
    <a class="btn" href="?action=harvest&type=crop&id=2">收获</a>
  </div>
</div>
<div class="farm-section">
  <h2>动物养殖区</h2>
  <div class="farm-item">
    <h3>鸡</h3>
    <a class="btn" href="?action=harvest&amp;type=animal&amp;id=1">收获</a>
  </div>
</div>
<div class="farm-section">
  <h2>仓库</h2>
  <table class="warehouse-table">
    <tr><th>图片</th><th>名称</th><th>数量</th><th>收获时间</th><th>剩余有效期</th><th>单价</th><th>总价</th><th>操作</th></tr>
    <tr>
      <td><img src="wheat.webp"></td><td>小麦</td><td>2</td><td>今天</td><td>45分钟</td><td>900</td><td>1800</td>
      <td><input type="checkbox" name="batch_keys[]" value="crop_1_42"><a class="sell-btn" href="?action=sell&amp;key=crop_1_42">出售</a></td>
    </tr>
  </table>
  <div class="pagination-info">页 1 共 2</div>
</div>
<div class="farm-section">
  <h2>菜市场</h2>
  <div class="market-category">
    <h3>农作物</h3>
    <table class="market-table"><tr><th>名称</th><th>价格</th></tr><tr><td>小麦</td><td>900</td></tr></table>
  </div>
  <div class="market-category">
    <h3>动物</h3>
    <table class="market-table"><tr><th>名称</th><th>价格</th></tr><tr><td>鸡</td><td>1,500 魔力</td></tr></table>
  </div>
</div>
</body></html>
"""


def test_skit_metadata_and_urls():
    config = SkitConfig()

    assert config.site_id == "skit"
    assert config.site_name == "拾刻"
    assert config.get_farm_url() == "https://www.ptskit.org/magic_farm.php"
    assert config.crops["animal_1"]["action"] == "breed"
    assert config.capabilities == {
        "harvest_all", "expiry_sale", "warehouse_pagination", "batch_sell"
    }
    assert config.supports_batch_sell()
    assert config.get_batch_sell_url() == (
        "https://www.ptskit.org/magic_farm.php?action=batch_sell&page=1&sort=expire_asc"
    )


def test_skit_market_status_and_bonus_parsers():
    config = SkitConfig()

    assert config.parse_market_prices(HTML) == {"crop_1": 900, "animal_1": 1500}
    statuses = config.parse_crop_status(HTML)
    assert statuses["crop_1"] == {"can_harvest": False, "remaining_minutes": 80}
    assert statuses["crop_2"] == {"can_harvest": True, "remaining_minutes": None}
    assert statuses["animal_1"] == {"can_harvest": True, "remaining_minutes": None}
    assert config.parse_bonus(HTML) == "12,345"


def test_skit_warehouse_pagination_and_sell_key():
    config = SkitConfig()

    items, next_page = config.parse_warehouse_page(HTML)
    assert next_page == 2
    assert items == [{
        "name": "小麦",
        "quantity": 2,
        "expire": "45分钟",
        "expire_raw": "45分钟",
        "expire_minutes": 45,
        "sell_key": "crop_1_42",
        "crop_key": "crop_1",
    }]
    assert config.get_sell_key(HTML, "crop", 1) == "crop_1_42"
    assert config.get_sell_key(HTML, "animal", 4) is None


def test_skit_empty_html_is_safe():
    config = SkitConfig()

    assert config.parse_market_prices("") == {}
    assert config.parse_warehouse_items("") == []
    assert config.parse_bonus("") is None


if __name__ == "__main__":
    test_skit_metadata_and_urls()
    test_skit_market_status_and_bonus_parsers()
    test_skit_warehouse_pagination_and_sell_key()
    test_skit_empty_html_is_safe()
    print("Skit parser tests passed")
