"""Vue 联邦及阶段1本地 API 契约，不访问真实站点。"""
import asyncio
import importlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).parents[3]
PKG = ROOT / 'plugins.v3' / 'autoptcheckin'
sys.path.insert(0, str(PKG.parent))
Plugin = importlib.import_module('autoptcheckin').AutoPtCheckin


def run(coro):
    return asyncio.run(coro)


def test_render_and_api_contract():
    plugin = Plugin()
    assert plugin.get_render_mode() == ('vue', 'dist/assets')
    assert plugin.get_form()[0] is None
    assert plugin.get_form()[1]["enabled"] is False
    assert plugin.get_page() is None
    routes = {(item['path'], method) for item in plugin.get_api() for method in item['methods']}
    assert {('/config', 'GET'), ('/config', 'PUT'), ('/site_config', 'GET'),
            ('/site_config', 'PUT'), ('/stats', 'GET'), ('/history', 'GET')} <= routes
    assert all(item['auth'] == 'bear' for item in plugin.get_api())
    assert all(callable(item['endpoint']) and item['endpoint'].__self__ is plugin for item in plugin.get_api())
    plugin.init_plugin({'enabled': True, 'onlyonce': True})
    once = plugin.get_service()
    assert len(once) == 1 and 'once' in once[0]['id']
    assert run(plugin.api_signin_by_domain())['success'] is False


def test_config_persistence_and_isolation():
    plugin = Plugin()
    saved = {}
    plugin.update_config = lambda config: saved.update(config)
    config = {'enabled': False, 'browserless_enabled': False, 'enabled_sites': ['rousi']}
    assert run(plugin.api_save_config(config))['success']
    assert saved == config
    result = run(plugin.api_config())
    result['data']['enabled_sites'].clear()
    assert run(plugin.api_config())['data']['enabled_sites'] == ['rousi']


def test_site_config_persistence_and_reload():
    data = {}
    plugin = Plugin()
    plugin.save_data = lambda key, value: data.update({key: value})
    plugin.get_data = lambda key: data.get(key)
    plugin.update_config = lambda config: None
    config = {'enabled_sites': ['rousi'], 'sign_sites': ['rousi'], 'rousi_username': 'offline-user'}
    assert run(plugin.api_save_site_config(config))['success']
    config['enabled_sites'].clear()
    plugin.init_plugin({})
    assert run(plugin.api_site_config())['data']['enabled_sites'] == ['rousi']
    assert run(plugin.api_config())['data']['rousi_username'] == 'offline-user'
    assert run(plugin.api_save_site_config({'unknown': True}))['success'] is False


def test_empty_results_do_not_fabricate_evidence():
    plugin = Plugin()
    stats = run(plugin.api_stats())['data']
    assert stats['next_schedule'] is None and stats['sites'] == []
    assert stats['schedule'] == {'mode': 'interval', 'interval_hours': 2, 'begin_hour': 9, 'end_hour': 23}
    plugin._config = {'cron_mode': 'cron', 'cron': '5 8 * * *'}
    assert run(plugin.api_stats())['data']['schedule'] == {'mode': 'cron', 'cron': '5 8 * * *'}
    assert run(plugin.api_history())['data']['items'] == []


def test_site_tracks_action_selection_keys():
    """数据页站点卡按钮按 sign_selected/login_selected 渲染，键名与前端一致。"""
    plugin = Plugin()
    plugin.init_plugin({'enabled': True, 'enabled_sites': ['hdsky', '52pt'],
                        'sign_sites': ['hdsky'], 'login_sites': ['52pt']})
    rows = {row['id']: row for row in run(plugin.api_stats())['data']['sites']}
    assert rows['hdsky']['sign_selected'] is True and rows['hdsky']['login_selected'] is False
    assert rows['52pt']['sign_selected'] is False and rows['52pt']['login_selected'] is True
    assert all('signin_selected' not in row for row in rows.values())


def test_frontend_defaults_and_distribution():
    defaults = json.loads((PKG / 'config_defaults.json').read_text(encoding='utf8'))
    assert defaults['enabled_sites'] == []
    assert defaults['browserless_enabled'] is False
    assert {'rousi_username', 'rousi_password', 'sunnypt_username', 'sunnypt_password', 'sunnypt_token'} <= defaults.keys()
    remote = (PKG / 'dist/assets/remoteEntry.js').read_text(encoding='utf8')
    assert './Config' in remote and './Page' in remote
    assert not (PKG / 'form_builder.py').exists()
