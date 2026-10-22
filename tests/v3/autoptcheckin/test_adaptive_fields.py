"""Configuration input rows use width-driven columns, not credential counts."""
from pathlib import Path

ROOT = Path(__file__).parents[3] / 'plugins.v3' / 'autoptcheckin'


def test_schedule_and_credentials_use_adaptive_grid():
    source = (ROOT / 'frontend/src/Config.vue').read_text(encoding='utf-8')
    assert source.count('class="grid fields-grid"') == 5
    assert ':class="{three:(site.fields || []).length === 3}"' not in source
    css = (ROOT / 'frontend/src/preview.css').read_text(encoding='utf-8')
    assert '.grid.fields-grid {grid-template-columns:repeat(auto-fit,minmax(min(180px,100%),1fr))}' in css
    # Built assets are the actual plugin UI delivery path.
    built = list((ROOT / 'dist/assets').glob('__federation_expose_Config-*.css'))
    assert len(built) == 1
    assert 'repeat(auto-fit,minmax(min(180px,100%),1fr))' in built[0].read_text(encoding='utf-8')


def test_browserless_switch_has_accessible_name_without_duplicate_visible_label():
    source = (ROOT / 'frontend/src/Config.vue').read_text(encoding='utf-8')
    assert 'id="browserless-enabled" aria-label="启用 Browserless" v-model="model.browserless_enabled"></label>' in source
    assert '>启用 Browserless</label>' not in source
