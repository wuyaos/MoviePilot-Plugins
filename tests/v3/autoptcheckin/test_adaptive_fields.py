"""Configuration input rows use width-driven columns, not credential counts."""
from pathlib import Path

ROOT = Path(__file__).parents[3] / 'plugins.v3' / 'autoptcheckin'


def test_schedule_and_credentials_use_adaptive_grid():
    source = (ROOT / 'frontend/src/Config.vue').read_text(encoding='utf-8')
    assert source.count('class="grid fields-grid"') == 4  # 3.37.0 移除全局 Browserless 分组后 5→4
    assert ':class="{three:(site.fields || []).length === 3}"' not in source
    css = (ROOT / 'frontend/src/preview.css').read_text(encoding='utf-8')
    assert '.grid.fields-grid {grid-template-columns:repeat(auto-fit,minmax(min(180px,100%),1fr))}' in css
    # Built assets are the actual plugin UI delivery path.
    built = list((ROOT / 'dist/assets').glob('__federation_expose_Config-*.css'))
    assert len(built) == 1
    assert 'repeat(auto-fit,minmax(min(180px,100%),1fr))' in built[0].read_text(encoding='utf-8')


def test_no_global_browserless_controls_remain():
    """3.37.0：全局 Browserless（地址/令牌/开关）已删除，仿真仅按站点配置。"""
    source = (ROOT / 'frontend/src/Config.vue').read_text(encoding='utf-8')
    assert 'browserless_enabled' not in source and 'browserless_url' not in source and 'browserless_token' not in source
    assert '启用 Browserless' not in source
    assert '仿真（无头浏览器渲染）' in source
