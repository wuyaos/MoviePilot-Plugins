"""Ralph R3 每站执行配置契约：siteconf 有效配置解析、旧 site_browserless 迁移与代理语义。"""
import asyncio
import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
import autoptcheckin as entry
from autoptcheckin.core import cloudsign, siteconf
from autoptcheckin.core.cloudsign import CLOUD_SITES
from autoptcheckin.core.siteconf import cloak_proxy, resolve


def _plugin_with_store():
    data = {}
    plugin = entry.AutoPtCheckin()
    plugin.get_data = lambda key: data.get(key)
    plugin.save_data = lambda key, value: data.__setitem__(key, value)
    return plugin, data


# ---------- siteconf.resolve：覆盖表三态 ----------

def test_proxy_missing_key_inherits_mp_and_explicit_bool_wins():
    config = {}
    assert resolve('hdsky', config, mp_proxy=True)['proxy'] is True
    assert resolve('hdsky', config, mp_proxy=False)['proxy'] is False
    # 显式 false 最高优先：绝不被继承值或 PROXY_HOST 兜底重新开启。
    config = {'site_proxy': {'hdsky': False}}
    assert resolve('hdsky', config, mp_proxy=True)['proxy'] is False
    config = {'site_proxy': {'hdsky': True}}
    assert resolve('hdsky', config, mp_proxy=False)['proxy'] is True
    # 覆盖表键存在性判断：显式 false 不得经 `or` 回退；键经 _normalize_site_keys 统一为 str。
    config = {'site_proxy': {'0': True}}
    assert resolve(0, config, mp_proxy=False)['proxy'] is True


def test_emulate_missing_key_inherits_render_or_declaration():
    declared = {'declared_emulate': True}
    assert resolve('s', {}, mp_render=True, **declared)['emulate'] is True
    assert resolve('s', {}, mp_render=False, **declared)['emulate'] is True
    assert resolve('s', {}, mp_render=True)['emulate'] is True
    assert resolve('s', {})['emulate'] is False
    # 显式 false 关闭内置声明；显式 true 打开未声明站。
    assert resolve('s', {'site_emulate': {'s': False}}, mp_render=True, **declared)['emulate'] is False
    assert resolve('s', {'site_emulate': {'s': True}})['emulate'] is True


def test_cloudsign_capability_is_declaration_and_selection_is_explicit():
    for sid in CLOUD_SITES:
        assert resolve(sid, {})['cloudsign_capable'] is True
    assert resolve('hdsky', {})['cloudsign_capable'] is False
    assert resolve('custom-1', {}, cloudsign_capable=False)['cloudsign_capable'] is False
    # 有能力且用户选择才 selected；显式 [] 不得经 falsy 回填。
    assert resolve('audiences', {'site_cloudsign': []})['cloudsign_selected'] is False
    assert resolve('audiences', {'site_cloudsign': ['audiences']})['cloudsign_selected'] is True
    assert resolve('audiences', {'site_cloudsign': ['vclib']})['cloudsign_selected'] is False
    assert resolve('audiences', {'site_cloudsign': [123, 'audiences']})['cloudsign_selected'] is True


# ---------- cloak_proxy：显式关闭不被 PROXY_HOST 兜底 ----------

def test_cloak_proxy_off_never_reenabled_by_proxy_host(monkeypatch):
    monkeypatch.setenv('PROXY_HOST', 'http://proxy.invalid:7890')
    assert cloak_proxy(False, {}) is None
    assert cloak_proxy(False, {'site_proxy': {'s': False}}) is None
    assert cloak_proxy(False, {'cloak_proxy': 'http://legacy.invalid:1080'}) is None
    # 旧 cloak_proxy 全局遗留兼容：显式值优先，'off'=强制直连。
    assert cloak_proxy(True, {'cloak_proxy': 'http://legacy.invalid:1080'}) == 'http://legacy.invalid:1080'
    assert cloak_proxy(True, {'cloak_proxy': 'off'}) is None
    assert cloak_proxy(False, {'cloak_proxy': 'off'}) is None


def test_cloak_proxy_enabled_uses_host_settings(monkeypatch):
    monkeypatch.delenv('PROXY_HOST', raising=False)
    settings = type('S', (), {'PROXY': {'http': 'http://p.invalid:1', 'https': 'http://p.invalid:2'}})()
    monkeypatch.setitem(sys.modules, 'app.sdk.config', type('M', (), {'settings': settings}))
    assert cloak_proxy(True, {}) == 'http://p.invalid:2'
    settings.PROXY = None
    assert cloak_proxy(True, {}) is None


# ---------- 迁移：旧名单 / token 播种 / 幂等 ----------

DECLARED_EMULATE = {'ourbits', 'audiences', 'hdkyl', 'mua_xloli', 'pt_0ff', 'vclib', 'piggo', '52pt', 'yema', 'anthelion'}


def _emulate_map(plugin):
    return plugin._config.get('site_emulate') or {}


def test_migration_legacy_list_members_true_and_deseclared_false():
    plugin, data = _plugin_with_store()
    plugin.init_plugin({'enabled_sites': ['ourbits'], 'sign_sites': ['ourbits'],
                        'site_browserless': ['ourbits', 'audiences']})
    overrides = _emulate_map(plugin)
    assert overrides['ourbits'] is True and overrides['audiences'] is True
    # 旧名单未包含的声明仿真站 = 用户明确取消：显式 false，防止内置默认复活。
    assert all(overrides[sid] is False for sid in DECLARED_EMULATE - {'ourbits', 'audiences'})
    # 无旧语义的站不盲填。
    assert 'hdsky' not in overrides and 'mteam' not in overrides
    assert 'site_browserless' not in plugin._config
    assert 'site_browserless' not in data['site_config']


def test_migration_token_seed_three_sites_and_requires_real_config():
    plugin, data = _plugin_with_store()
    plugin.init_plugin({'enabled_sites': ['audiences'], 'sign_sites': ['audiences'],
                        'browserless_token': 'tk', 'site_browserless': []})
    assert plugin._config['site_cloudsign'] == list(CLOUD_SITES)
    # 旧真实配置（自定义非默认 BQL URL，无 token）同样满足原 configured 口径。
    plugin2, _ = _plugin_with_store()
    plugin2.init_plugin({'browserless_url': 'http://cb.local:3000', 'site_browserless': []})
    assert plugin2._config['site_cloudsign'] == list(CLOUD_SITES)
    # 默认 URL + 空 token：从未配过云签，不播种（新用户默认关闭）。
    plugin3, _ = _plugin_with_store()
    plugin3.init_plugin({'browserless_url': cloudsign.DEFAULT_BROWSERLESS_URL})
    assert 'site_cloudsign' not in plugin3._config


def test_migration_token_only_without_legacy_list_still_seeds():
    """D1：旧用户只配过 token（无 site_browserless 键）同样保留当时有效云签选择。"""
    plugin, _ = _plugin_with_store()
    plugin.init_plugin({'browserless_token': 'tk'})
    assert plugin._config['site_cloudsign'] == list(CLOUD_SITES)
    # 无旧名单键：仿真站不盲填 false，走新默认（内置声明 emulate 继承）。
    assert 'site_emulate' not in plugin._config


def test_migration_idempotent_and_explicit_empty_cloudsign_preserved():
    plugin, data = _plugin_with_store()
    plugin.init_plugin({'browserless_token': 'tk', 'site_browserless': ['ourbits']})
    assert plugin._config['site_cloudsign'] == list(CLOUD_SITES)
    # 用户随后显式关闭云签并保存：空数组必须保留，reload/再次迁移不得回填。
    plugin.update_config = lambda config: data.setdefault('host', {}).update(config)
    asyncio.run(plugin.api_save_config({'site_cloudsign': [], 'site_emulate': {'ourbits': True}}))
    assert plugin._config['site_cloudsign'] == []
    stale_host = {'browserless_token': 'tk', 'site_browserless': ['ourbits']}
    plugin.init_plugin(stale_host)
    assert plugin._config['site_cloudsign'] == []
    assert plugin._config['site_emulate'] == {'ourbits': True}
    assert 'site_browserless' not in plugin._config
    assert 'site_browserless' not in data['site_config']


def test_migration_site_config_residue_does_not_resurrect():
    """C1：持久化 site_config 残留旧键，合并链路与重复 reload 均不得复活。"""
    plugin, data = _plugin_with_store()
    plugin.init_plugin({'site_browserless': ['ourbits']})
    assert 'site_browserless' not in data['site_config']
    # 模拟更早版本遗留：持久化层再度出现旧键 + host 配置已无旧键。
    data['site_config']['site_browserless'] = ['piggo']
    plugin.init_plugin({})
    assert 'site_browserless' not in plugin._config
    assert 'site_browserless' not in data['site_config']
    # piggo 未被残留复活：迁移物化的显式 false 终结内置声明继承。
    assert plugin._config['site_emulate']['piggo'] is False
    assert siteconf.resolve('piggo', plugin._config, declared_emulate=True)['emulate'] is False


def test_partial_save_keeps_per_site_overrides_and_never_resurrects_legacy():
    plugin, data = _plugin_with_store()
    plugin.init_plugin({'enabled_sites': ['hdsky', 'custom-1'],
                        'site_emulate': {'hdsky': True, 'custom-1': True},
                        'site_proxy': {'hdsky': False}})
    plugin.update_config = lambda config: data.setdefault('host', {}).update(config)
    asyncio.run(plugin.api_save_config({'enabled': True}))
    # partial PUT 不得重置未提交键。
    assert plugin._config['site_emulate'] == {'hdsky': True, 'custom-1': True}
    assert plugin._config['site_proxy'] == {'hdsky': False}
    # 宿主持久化同样无旧键残留。
    assert 'site_browserless' not in data['host']
    assert 'site_browserless' not in data['site_config']


def test_site_cloudsign_normalization_filters_unknown_ids():
    plugin, _ = _plugin_with_store()
    plugin.init_plugin({'site_cloudsign': [123, 'audiences', 'audiences', '52pt', 'custom-1', 'hdsky']})
    # 云签仅有三站实现：数字/未声明/自定义 ID（含 52pt 等仅仿真站）的脏项过滤，去重收口。
    assert plugin._config['site_cloudsign'] == ['audiences']


def test_site_keys_accept_new_fields_and_reject_unknown():
    plugin, data = _plugin_with_store()
    plugin.update_config = lambda config: data.setdefault('host', {}).update(config)
    import asyncio as aio
    ok = aio.run(plugin.api_save_site_config({'site_emulate': {'hdsky': True}, 'site_proxy': {'hdsky': False},
                                              'site_cloudsign': ['audiences']}))
    assert ok['success'] is True
    assert plugin._config['site_emulate'] == {'hdsky': True}
    assert aio.run(plugin.api_save_site_config({'site_browserless': ['hdsky']}))['success'] is False


# ---------- 迁移缺口回归：incoming 优先级与逐键独立迁移 ----------

def test_migration_incoming_empty_list_beats_stored_list():
    """incoming site_browserless=[] 表示用户已全部取消：不得用持久化旧名单复活。"""
    plugin, data = _plugin_with_store()
    data['site_config'] = {'site_browserless': ['vclib', 'ourbits']}
    plugin.init_plugin({'site_browserless': []})
    overrides = _emulate_map(plugin)
    assert overrides['vclib'] is False and overrides['ourbits'] is False
    assert 'site_browserless' not in plugin._config
    assert 'site_browserless' not in data['site_config']


def test_migration_missing_incoming_falls_back_to_stored_list():
    """host config 缺旧键而持久化 site_config 有：以 stored 为旧名单继续迁移。"""
    plugin, data = _plugin_with_store()
    data['site_config'] = {'site_browserless': ['vclib']}
    plugin.init_plugin({})
    assert plugin._config['site_emulate']['vclib'] is True
    assert 'site_browserless' not in data['site_config']


def test_migration_custom_data_incoming_empty_beats_stored():
    """incoming custom_sites_data=[] 不得经 `or` 回退持久化旧条目。"""
    plugin, data = _plugin_with_store()
    data['site_config'] = {'site_browserless': ['7'],
                           'custom_sites_data': [{'id': '7', 'name': 'X', 'url': 'https://x.invalid/', 'emulate': True}]}
    plugin.init_plugin({'site_browserless': ['7'], 'custom_sites_data': []})
    # incoming 已删除该 custom 条目：旧名单成员不再按旧条目声明复活。
    assert (plugin._config.get('site_emulate') or {}).get('7') is not True


def test_migration_site_proxy_only_does_not_drop_legacy_conversions():
    """部分升级：只保存过 site_proxy 时，emulate 转换与云签播种仍各自独立进行，不得删旧键丢状态。"""
    plugin, data = _plugin_with_store()
    plugin.init_plugin({'site_proxy': {'hdsky': False},
                        'site_browserless': ['vclib'], 'browserless_token': 'tk'})
    assert plugin._config['site_proxy'] == {'hdsky': False}
    assert plugin._config['site_emulate']['vclib'] is True
    assert all(plugin._config['site_emulate'][sid] is False
               for sid in DECLARED_EMULATE - {'vclib'})
    assert plugin._config['site_cloudsign'] == list(CLOUD_SITES)
    assert 'site_browserless' not in plugin._config
    assert 'site_browserless' not in data['site_config']


def test_migration_cloudsign_present_emulate_absent_still_converts():
    """site_cloudsign 已存在（显式值）而 site_emulate 缺失：emulate 旧名单转换照常进行。"""
    plugin, data = _plugin_with_store()
    plugin.init_plugin({'site_cloudsign': ['audiences'], 'site_browserless': ['ourbits']})
    assert plugin._config['site_cloudsign'] == ['audiences']  # 显式值保留，不回填
    assert plugin._config['site_emulate']['ourbits'] is True
    assert 'site_browserless' not in plugin._config


def test_migration_explicit_empty_emulate_map_preserved():
    """显式 site_emulate={} 覆盖旧名单：用户清空仿真，旧名单不得复活。"""
    plugin, data = _plugin_with_store()
    plugin.init_plugin({'site_emulate': {}, 'site_browserless': ['vclib']})
    assert plugin._config['site_emulate'] == {}
    assert 'site_browserless' not in plugin._config


def test_new_user_token_with_explicit_empty_cloudsign_not_seeded():
    """新用户只配 token 且显式 site_cloudsign=[]：键存在即用户显式值，不得 seed。"""
    plugin, data = _plugin_with_store()
    plugin.init_plugin({'browserless_token': 'tk', 'site_cloudsign': []})
    assert plugin._config['site_cloudsign'] == []
    # 持久化后再 reload 也不得回填。
    plugin.init_plugin({'browserless_token': 'tk'})
    assert plugin._config['site_cloudsign'] == []


# ---------- custom 删除：覆盖脏项清理 ----------

def test_purge_custom_overrides_on_delete_keeps_builtin_ids():
    plugin, data = _plugin_with_store()
    plugin.init_plugin({'custom_sites_data': [{'id': '7', 'name': 'X', 'url': 'https://x.invalid/'}],
                        'site_emulate': {'7': True, 'audiences': True},
                        'site_proxy': {'7': True}})
    plugin.update_config = lambda config: data.setdefault('host', {}).update(config)
    asyncio.run(plugin.api_save_config({'custom_sites_data': []}))
    assert '7' not in plugin._config['site_emulate'] and '7' not in plugin._config['site_proxy']
    # 内置/未知 ID 不清（ID 复用防护只针对已删除的 custom 条目）。
    assert plugin._config['site_emulate']['audiences'] is True


# ---------- /sites 与 /stats 一致 ----------

def test_sites_and_stats_share_effective_flags(monkeypatch):
    from autoptcheckin.core import registry as registry_module
    monkeypatch.setattr(registry_module, 'managed_sites', lambda: [])
    plugin, _ = _plugin_with_store()
    plugin._config = {'enabled_sites': ['hdsky', 'custom-1'], 'site_emulate': {'hdsky': True},
                      'site_cloudsign': ['audiences'],
                      'custom_sites_data': [{'id': 'custom-1', 'name': 'C', 'url': 'https://c.invalid/', 'emulate': True}]}
    sites = {row['id']: row for row in asyncio.run(plugin.api_sites())['data']['sites']}
    stats_rows = {row['id']: row for row in asyncio.run(plugin.api_stats())['data']['sites']}
    for sid in ('hdsky', 'custom-1'):
        for key in ('proxy', 'emulate', 'cloudsign_capable', 'cloudsign_selected', 'shield'):
            assert sites[sid][key] == stats_rows[sid][key], (sid, key)
    assert sites['hdsky']['emulate'] is True and sites['hdsky']['proxy'] is False
    assert sites['custom-1']['emulate'] is True
    # 云签徽标仅实际选择显示：有能力未选择回退仿真徽标。
    assert sites['audiences']['cloudsign_capable'] is True
    assert sites['audiences']['cloudsign_selected'] is True and sites['audiences']['shield'] == 'cloud'
    plugin._config['site_cloudsign'] = []
    sites = {row['id']: row for row in asyncio.run(plugin.api_sites())['data']['sites']}
    assert sites['audiences']['cloudsign_selected'] is False and sites['audiences']['shield'] == 'emulate'
    # 注册表声明不被有效值反写污染。
    fresh = next(row for row in registry_module.get_registry([])['sites'] if row['id'] == 'audiences')
    assert fresh['shield'] == 'cloud' and 'proxy' not in fresh


# ---------- 执行入口与有效配置同源 ----------

def test_native_cloak_client_follows_render_and_explicit_proxy_off(monkeypatch):
    from autoptcheckin.core import cloak
    seen = {}

    class FakeClient:
        def __init__(self, http, info, site, proxy=None):
            seen['proxy'] = proxy

    monkeypatch.setattr(cloak, 'CloakHttpClient', FakeClient)
    site = type('S', (), {'id': 'hdsky', 'url': 'https://h.invalid/', 'emulate': False})()
    # MP render 继承开启仿真。
    client = cloak.native_cloak_client(site, object(), {'url': site.url, 'render': 1}, {})
    assert isinstance(client, FakeClient)
    # 显式 site_proxy=false：直连，不被 PROXY_HOST 兜底。
    monkeypatch.setenv('PROXY_HOST', 'http://proxy.invalid:7890')
    cloak.native_cloak_client(site, object(), {'url': site.url, 'render': 1}, {'site_proxy': {'hdsky': False}})
    assert seen['proxy'] is None
    # site_proxy=true：代理与本地 HTTP 同源（settings.PROXY）。
    settings = type('S', (), {'PROXY': {'https': 'http://p.invalid:2', 'http': 'http://p.invalid:1'}})()
    monkeypatch.setitem(sys.modules, 'app.sdk.config', type('M', (), {'settings': settings}))
    cloak.native_cloak_client(site, object(), {'url': site.url, 'render': 1}, {'site_proxy': {'hdsky': True}})
    assert seen['proxy'] == 'http://p.invalid:2'


@pytest.mark.parametrize('proxy', [True, False])
def test_custom_login_follows_selected_emulate(monkeypatch, proxy):
    from autoptcheckin.core import custom as custom_module
    from autoptcheckin.core.models import LoginPage, LoginResult, LoginStatus
    from contextlib import contextmanager
    from types import SimpleNamespace
    from unittest.mock import Mock
    from autoptcheckin.core.runner import SignRunner
    runner = SignRunner(history=lambda result: None)
    seen = {}

    proxy_flag = proxy
    @contextmanager
    def client(credential, info, config, proxy=None):
        seen['emulate'] = info['emulate']
        assert info['proxy'] is proxy_flag
        yield Mock(**{'get.return_value': LoginPage('<main>ok</main>', 'https://c.invalid/'),
                      'cookies': {}})

    monkeypatch.setattr(custom_module, 'custom_client', client)
    info = {'id': 'custom-1', 'url': 'https://c.invalid/', 'cookie': 'synthetic', 'emulate': False, 'uid': ''}
    result = custom_module.run_custom(runner, 'custom-1', info, enabled=True, selected=True,
                                      config={'site_emulate': {'custom-1': True}, 'site_proxy': {'custom-1': proxy}}, action='login')
    # custom 登录同样遵守选中仿真（旧「custom 登录不走仿真」契约由 site_emulate 取代）。
    assert seen['emulate'] is True
    assert result.metadata['transport'] == 'cloak'
    assert result.status == LoginStatus.LOGIN_OK


def test_missing_config_message_names_token():
    assert 'browserless_token' in cloudsign.missing_config({})
    assert 'browserless_token' in cloudsign.missing_config({'browserless_token': ' '})
    assert cloudsign.missing_config({'browserless_token': 'tk'}) == ''
    assert cloudsign.missing_config({'browserless_url': 'http://cb.local:3000'}) == ''
