"""B01 模块配置摘要投影离线测试。

覆盖：模块门控、总开关门控、配置完整性 active、旧配置缺键、敏感字段哨兵、
只读（不改配置存储、不触发通知/识别）。
宿主（app.* / uploadlimit.service）全部替身；不连接 MoviePilot。
"""
import copy
import importlib.machinery
import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import Mock

import pytest

PLUGIN = Path(__file__).resolve().parents[3] / 'plugins.v3/downloadmanagerlocal'
PREFIX = 'app.plugins.downloadmanagerlocal'

DEFAULTS = {
    "transfer_fallback_enabled": True,
    "transfer_fallback_interval_minutes": 60,
    "seed_autostart": True,
    "seed_skipverify": False,
    "seed_check_interval": 60,
    "rename_cron_enabled": False,
    "rename_cron": "",
    "rename_on_download_added": True,
    "rename_movie_format": "[{{title}}]",
    "rename_tv_format": "[{{title}}]",
    "rename_downloaders": [],
    "hr_enable_site_config": False,
    "hr_check_period": 10,
    "hr_downloader": [],
    "hr_sites": [],
    "remover_action": "pause",
    "remover_downloaders": [],
    "remover_cron": "0 */12 * * *",
    "remover_size": "", "remover_ratio": "", "remover_time": "", "remover_upspeed": "",
    "remover_labels": "", "remover_pathkeywords": "", "remover_trackerkeywords": "",
    "remover_errorkeywords": "", "remover_torrentstates": "", "remover_torrentcategorys": "",
    "failcleanup_cron": "0 */2 * * *",
    "failcleanup_clean_repeat": True,
    "upload_limit_downloaders": [],
    "upload_limit_downloader_limits_kib": {},
    "upload_limit_site_rules": {},
}


def _module(monkeypatch, name, **attrs):
    result = types.ModuleType(name)
    path = attrs.get('__path__')
    result.__spec__ = importlib.machinery.ModuleSpec(name, None, is_package=path is not None)
    result.__dict__.update(attrs)
    monkeypatch.setitem(sys.modules, name, result)
    return result


def _load_from_file(monkeypatch, name, file_path):
    spec = importlib.util.spec_from_file_location(name, file_path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def summary(monkeypatch):
    """加载真实 config_summary 投影，替换 utils.config 与 uploadlimit.service 依赖。"""
    _module(monkeypatch, 'app')
    _module(monkeypatch, 'app.sdk')
    _module(monkeypatch, 'app.sdk.logging', logger=Mock())
    _module(monkeypatch, 'app.plugins')
    _module(monkeypatch, PREFIX, __path__=[str(PLUGIN)])
    _module(monkeypatch, PREFIX + '.controller', __path__=[str(PLUGIN / 'controller')])
    _module(monkeypatch, PREFIX + '.modules', __path__=[str(PLUGIN / 'modules')])
    _module(monkeypatch, PREFIX + '.utils', __path__=[str(PLUGIN / 'utils')])
    _module(monkeypatch, PREFIX + '.utils.config',
            PLUGIN_CONFIG_DEFAULTS=DEFAULTS,
            build_module_switches=lambda cfg: {k: bool(cfg.get(v[0])) for k, v in {
                'transfer': ('transfer_enabled', '_transfer_enabled'),
                'rename': ('rename_enabled', '_rename_enabled'),
                'tag': ('tag_enabled', '_tag_enabled'),
                'hr': ('hr_enabled', '_hr_enabled'),
                'autoremove': ('remover_enabled', '_remover_enabled'),
                'failclean': ('failcleanup_enabled', '_failcleanup_enabled'),
                'upload_limit': ('upload_limit_enabled', '_upload_limit_enabled'),
            }.items()},
            module_observe_flags=lambda plugin: {},
            is_upload_limit_active=lambda plugin: False)
    _module(monkeypatch, PREFIX + '.modules.uploadlimit', __path__=[str(PLUGIN / 'modules' / 'uploadlimit')])
    _module(monkeypatch, PREFIX + '.modules.uploadlimit.service',
            get_upload_limit_status=lambda plugin: {})
    module = _load_from_file(monkeypatch, PREFIX + '.controller.config_summary',
                             PLUGIN / 'controller' / 'config_summary.py')
    return module


def _fake_plugin(config=None, *, switches=None, enabled_attrs=None,
                 transfer_active=False, hr_service=None, tag_config=None):
    config = dict(config or {})
    if switches is None:
        switches = {
            'transfer': config.get('transfer_enabled', False),
            'rename': config.get('rename_enabled', False),
            'tag': config.get('tag_enabled', False),
            'hr': config.get('hr_enabled', False),
            'autoremove': config.get('remover_enabled', False),
            'failclean': config.get('failcleanup_enabled', False),
            'upload_limit': config.get('upload_limit_enabled', False),
        }
    plugin = types.SimpleNamespace(
        get_config=lambda: copy.deepcopy(config),
        _module_switches=dict(switches),
        _module_observe_only={},
        _transfer_active=transfer_active,
        _hr_service=hr_service,
        _autoremove_service=None,
        _failclean_service=None,
        _site_tag_config=tag_config if isinstance(tag_config, dict) else None,
    )
    default_enabled = {
        '_transfer_enabled': False, '_rename_enabled': False, '_tag_enabled': False,
        '_hr_enabled': False, '_remover_enabled': False, '_failcleanup_enabled': False,
        '_upload_limit_enabled': False,
    }
    default_enabled.update(enabled_attrs or {})
    for attr, value in default_enabled.items():
        setattr(plugin, attr, value)
    return plugin


def _fields(summary_module, plugin, module_key):
    data = summary_module.build_module_config_summary(plugin)
    return {field['key']: field for field in data['modules'][module_key]['fields']}


def test_seven_modules_and_shape(summary):
    """固定七个模块，每模块含 enabled/bare_switch/active/scope/schedule/protection/fields。"""
    plugin = _fake_plugin({'enabled': True})
    data = summary.build_module_config_summary(plugin)
    assert data['code'] == 0
    assert set(data['modules']) == {
        'transfer', 'rename', 'hr', 'autoremove', 'failclean', 'tag', 'upload_limit'}
    for module in data['modules'].values():
        for key in ('enabled', 'bare_switch', 'observe_only', 'active', 'scope', 'schedule',
                    'protection', 'fields'):
            assert key in module, (module['key'], key)
        assert isinstance(module['fields'], list)
        for field in module['fields']:
            assert {'key', 'label', 'value', 'category', 'source'} <= set(field), field


def test_module_disabled_gates_enabled(summary):
    """模块开关关闭：模块 enabled=False，且 hr 删除保护（门控子项）为关闭。"""
    plugin = _fake_plugin(
        {'enabled': True, 'hr_enabled': False, 'hr_protection_enabled': True},
        enabled_attrs={'_hr_enabled': False})
    data = summary.build_module_config_summary(plugin)
    hr = data['modules']['hr']
    assert hr['enabled'] is False
    assert hr['active'] is False
    guard = _fields(summary, plugin, 'hr')['guard']
    assert guard['value'] == '关闭'


def test_total_switch_off_gates_sub_item_enabled(summary):
    """总开关关闭但子项开关为真：模块 enabled 仍为 False。"""
    plugin = _fake_plugin(
        {'enabled': False, 'hr_enabled': True, 'hr_protection_enabled': True},
        enabled_attrs={'_hr_enabled': False})
    data = summary.build_module_config_summary(plugin)
    assert data['modules']['hr']['enabled'] is False
    # 裸开关仍反映已保存配置（hr_enabled=True），但门控 enabled 为假
    assert data['modules']['hr']['bare_switch'] is True


def test_transfer_active_reflects_integrity(summary):
    """配置完整性：transfer active 使用 _transfer_active，不因开关开启就置真。"""
    on = _fake_plugin({'enabled': True, 'transfer_enabled': True},
                      enabled_attrs={'_transfer_enabled': True}, transfer_active=False)
    assert summary.build_module_config_summary(on)['modules']['transfer']['active'] is False
    ready = _fake_plugin({'enabled': True, 'transfer_enabled': True},
                         enabled_attrs={'_transfer_enabled': True}, transfer_active=True)
    assert summary.build_module_config_summary(ready)['modules']['transfer']['active'] is True


def test_upload_limit_active_false_when_incomplete(summary):
    """上传限速配置不完整：active 为 False（is_upload_limit_active 替身返回 False）。"""
    plugin = _fake_plugin({'enabled': True, 'upload_limit_enabled': True},
                          enabled_attrs={'_upload_limit_enabled': True})
    data = summary.build_module_config_summary(plugin)
    assert data['modules']['upload_limit']['enabled'] is True
    assert data['modules']['upload_limit']['active'] is False


def test_legacy_config_missing_keys_no_fake_values(summary):
    """旧配置缺键：不抛错，布尔回退真实默认值，列表回退未配置，不做假 0。"""
    plugin = _fake_plugin({})
    data = summary.build_module_config_summary(plugin)
    transfer = _fields(summary, plugin, 'transfer')
    assert transfer['fallback']['value'] == '开启'  # 默认 True
    assert transfer['interval']['value'] == '60 分钟'  # 默认 60，不是 0 分钟
    hr = _fields(summary, plugin, 'hr')
    assert hr['downloaders']['value'] == '未配置'
    assert hr['interval']['value'] == '10 分钟'


def test_invalid_values_do_not_crash(summary):
    """非法配置值（非数字周期/非法额度）不抛错，按未配置或忽略处理。"""
    plugin = _fake_plugin({
        'enabled': True,
        'hr_check_period': 'abc',
        'upload_limit_downloader_limits_kib': {'QB1': 'oops'},
        'upload_limit_site_rules': {'GGPT': {'limit_kib': 'bad'}},
    })
    data = summary.build_module_config_summary(plugin)
    hr_interval = _fields(summary, plugin, 'hr')['interval']['value']
    assert hr_interval == '未配置'
    upload = _fields(summary, plugin, 'upload_limit')
    assert upload['global']['value'] == '未配置'
    assert upload['sites']['value'] == '未配置'

def test_sensitive_values_never_leak(summary):
    """敏感字段哨兵：摘要 JSON 不出现任何哨兵字符串。"""
    sentinels = [
        'SENTINEL_API_KEY_abc123',
        'SENTINEL_PASSWORD_xyz789',
        'SENTINEL_COOKIE_session=deadbeef',
        'SENTINEL_TOKEN_bearer-foo',
    ]
    config = {
        'enabled': True,
        'api_key': sentinels[0],
        'password': sentinels[1],
        'cookie': sentinels[2],
        'token': sentinels[3],
        'download_manager_token': sentinels[3],
    }
    plugin = _fake_plugin(config)
    data = summary.build_module_config_summary(plugin)
    text = json.dumps(data, ensure_ascii=False)
    for sentinel in sentinels:
        assert sentinel not in text, sentinel


def test_summary_is_read_only(summary):
    """只读：调用前后配置存储逐字节不变，不触发 save_data/update_config/post_message。"""
    config = {'enabled': True, 'transfer_enabled': True, 'transfer_fallback_enabled': False}
    before = copy.deepcopy(config)
    plugin = _fake_plugin(config, enabled_attrs={'_transfer_enabled': True})
    plugin.save_data = Mock()
    plugin.update_config = Mock()
    plugin.post_message = Mock()
    summary.build_module_config_summary(plugin)
    assert plugin.get_config() == before
    plugin.save_data.assert_not_called()
    plugin.update_config.assert_not_called()
    plugin.post_message.assert_not_called()
