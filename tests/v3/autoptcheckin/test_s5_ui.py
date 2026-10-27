"""S5 UI 源码约束；实际布局仍以宿主截图为准。"""
from pathlib import Path
import importlib
import sys

PLUGIN = Path(__file__).parents[3] / 'plugins.v3/autoptcheckin'
FRONTEND = Path(__file__).parents[3] / 'frontend.v3/autoptcheckin'
sys.path.insert(0, str(PLUGIN.parent))


def test_compact_site_management_contract():
    source = (FRONTEND / 'src/Config.vue').read_text(encoding='utf8')
    assert '筛选已启用站点' in source
    assert 'filteredSelected' in source and 'selectedGroups' not in source
    assert '全部展开' in source and '全部收起' in source and 'expandSites' in source and 'collapseSites' in source
    assert 'v-for="site in filteredSelected"' in source
    assert '立即签到' not in source
    assert '立即运行一次' not in source and '清理本日缓存' not in source
    assert '时间窗口' in source and 'applyTimeWindow' in source
    assert '开始时（0–23）' not in source and '结束时（0–23）' not in source
    assert 'retry_count' in source
    assert 'pinyin-pro' in source or 'pinyinIndex' in source


def test_embedded_views_do_not_render_second_frame():
    for name in ('Config', 'Page'):
        assert 'card embedded-card' in (FRONTEND / f'src/{name}.vue').read_text(encoding='utf8')
    css = (FRONTEND / 'src/preview.css').read_text(encoding='utf8')
    assert '.card.embedded-card {border:0; border-radius:0; box-shadow:none;' in css
    assert 'height:36px' in css and 'max-height:68vh; overflow:auto' in css


def test_hdsky_can_emulate_login():
    registry = importlib.import_module('autoptcheckin.core.registry').get_registry()
    site = next(site for site in registry['sites'] if site['id'] == 'hdsky')
    assert site['login_capable'] and site['signin_capable']


def test_no_hardcoded_colors_outside_tokens():
    """使用处禁止硬编码颜色；--ptc-* 令牌定义行是唯一合法位置。"""
    import re
    pattern = re.compile(r'#[0-9a-fA-F]{3,8}\b|rgba?\(')

    def violations(line: str) -> bool:
        seg = re.sub(r'rgba?\(var\([^)]*\)\)', '', line)   # 剥 rgb(var) 整体
        seg = re.sub(r'--ptc-[\w-]+\s*:[^;}]*', '', seg)   # 剥令牌定义
        seg = re.sub(r'var\([^)]*\)', '', seg)             # 剥 var 引用
        return bool(pattern.search(seg))

    for name in ('preview.css', 'Config.vue', 'Page.vue'):
        text = (FRONTEND / f'src/{name}').read_text(encoding='utf8')
        bad = [f'{name}:{n}' for n, line in enumerate(text.splitlines(), 1) if violations(line)]
        assert not bad, f'硬编码颜色: {bad}'


def test_data_page_has_live_execution_and_loading():
    source = (FRONTEND / 'src/Page.vue').read_text(encoding='utf8')
    assert "execute('signin_by_domain',site.id)" in source
    assert "execute('verify_site',site.id)" not in source
    assert "site.sign_selected && !site.sign_disabled_struct && trackChip(site,'sign')" in source
    assert 'toggleSitePaused' in source and 'paused_sites: [...paused]' in source and 'site_track' not in source
    assert 'class="pwr"' in (FRONTEND / 'src/Config.vue').read_text(encoding='utf8')
    assert 'await load()' in source
