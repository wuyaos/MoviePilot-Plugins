"""Configuration input rows use width-driven columns, not credential counts."""
from pathlib import Path

ROOT = Path(__file__).parents[3] / 'plugins.v3' / 'autoptcheckin'


def test_schedule_and_credentials_use_adaptive_grid():
    source = (Path(__file__).parents[3] / 'frontend.v3/autoptcheckin/src/Config.vue').read_text(encoding='utf-8')
    assert source.count('class="grid fields-grid"') == 5  # Browserless 全局配置组恢复后共 5 组
    assert ':class="{three:(site.fields || []).length === 3}"' not in source
    css = (Path(__file__).parents[3] / 'frontend.v3/autoptcheckin/src/preview.css').read_text(encoding='utf-8')
    assert '.grid.fields-grid {grid-template-columns:repeat(auto-fit,minmax(min(180px,100%),1fr))}' in css
    built = list((ROOT / 'dist/assets').glob('__federation_expose_Config-*.css'))
    assert len(built) == 1
    assert 'repeat(auto-fit,minmax(min(180px,100%),1fr))' in built[0].read_text(encoding='utf-8')


def test_global_browserless_contract():
    """Browserless 服务配置为全局项，不得混入每站 /site_config 键。"""
    import json
    import re

    defaults = json.loads((ROOT / 'config_defaults.json').read_text(encoding='utf-8'))
    assert 'browserless_url' in defaults and 'browserless_token' in defaults

    source = (ROOT / '__init__.py').read_text(encoding='utf-8')
    match = re.search(r'^\s+SITE_KEYS\s*=\s*\((.*?)\)', source, re.MULTILINE | re.DOTALL)
    assert match, 'SITE_KEYS whitelist not found'
    site_keys = set(re.findall(r'["\']([^"\']+)["\']', match.group(1)))
    assert {'browserless_url', 'browserless_token'}.isdisjoint(site_keys)
