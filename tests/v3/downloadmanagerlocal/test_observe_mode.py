"""观察模式（阶段三）写边界离线测试。

运行：micromamba run -n base python -X utf8 -m pytest tests/v3/downloadmanagerlocal/test_observe_mode.py -q

宿主（app / 下载器适配层 / allocator）全部替身；只加载真实的 `utils/config.py` 与
`modules/uploadlimit/service.py`。锁定三条语义：

1. 观察模式下 `run_upload_limit_cycle` 直接返回 observe 状态，不调用任何限速写函数；
2. 观察模式下 `restore_upload_limits` 不执行恢复（决策 B：已有额度保持原样）；
3. 未开启观察时守卫不误拦（走原有状态错误分支）。
"""

import importlib.machinery
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

PLUGIN = Path(__file__).resolve().parents[3] / 'plugins.v3/downloadmanagerlocal'
PREFIX = 'app.plugins.downloadmanagerlocal'

UPLOAD_ADAPTER_NAMES = (
    'expected_global_upload_settings',
    'expected_torrent_upload_settings',
    'global_settings_equal',
    'global_settings_from_dict',
    'global_settings_to_dict',
    'list_upload_torrents',
    'read_global_upload_settings',
    'restore_global_upload_settings',
    'restore_torrent_upload_settings',
    'settings_from_dict',
    'settings_to_dict',
    'torrent_settings_equal',
    'write_global_upload_limit',
    'write_torrent_upload_limit',
)

ALLOCATOR_NAMES = (
    'adjust_auto_probe_count',
    'aggregate_pool_demand_kib',
    'allocate_site_pools',
    'allocate_task_limits',
    'estimate_task_demand_kib',
    'initial_auto_probe_count',
    'is_task_probe_candidate',
    'select_probe_keys',
)


def _module(monkeypatch, name, **attrs):
    """注册带 __spec__ 的模块替身（pytest 断言重写要求 spec 非 None）。"""
    path = attrs.pop('__path__', None)
    module = types.ModuleType(name)
    module.__spec__ = importlib.machinery.ModuleSpec(name, None, is_package=path is not None)
    if path is not None:
        module.__path__ = path
    module.__dict__.update(attrs)
    monkeypatch.setitem(sys.modules, name, module)
    return module


@pytest.fixture
def observe(monkeypatch):
    """加载真实观察模式解析器与上传限速服务，返回两者及下载器适配层替身。"""
    _module(monkeypatch, 'app')
    _module(monkeypatch, 'app.sdk')
    _module(monkeypatch, 'app.sdk.logging', logger=Mock())
    _module(monkeypatch, PREFIX, __path__=[str(PLUGIN)])
    _module(monkeypatch, PREFIX + '.adapter', __path__=[str(PLUGIN / 'adapter')])
    _module(monkeypatch, PREFIX + '.model', __path__=[str(PLUGIN / 'model')])
    _module(monkeypatch, PREFIX + '.modules', __path__=[str(PLUGIN / 'modules')])
    _module(
        monkeypatch,
        PREFIX + '.modules.uploadlimit',
        __path__=[str(PLUGIN / 'modules/uploadlimit')],
    )

    # utils/config.py 的默认值来源：本测试只关心观察模式契约，不加载各模块实现
    _module(
        monkeypatch,
        PREFIX + '.modules.autoremove.constants',
        MIGRATION_OBSERVE_ONLY_KEY='migration_observe_only',
        build_remover_config_defaults=Mock(return_value={}),
    )
    _module(
        monkeypatch,
        PREFIX + '.modules.failclean.constants',
        build_failclean_config_defaults=Mock(return_value={}),
    )
    _module(
        monkeypatch,
        PREFIX + '.modules.hr.constants',
        build_hr_config_defaults=Mock(return_value={}),
    )
    _module(
        monkeypatch,
        PREFIX + '.modules.rename.service',
        build_rename_flat_defaults=Mock(return_value={}),
    )
    _module(
        monkeypatch,
        PREFIX + '.modules.sitetag.service',
        DEFAULT_TAG_CONFIG={
            'interval_cron': '0 3 * * *',
            'enable_media_tag': False,
            'enable_tag': True,
            'enable_category': False,
            'enable_del_tags': False,
            'downloaders': [],
            'all_cat': [],
            'all_cat_rename': [],
            'rename_type': 'movie',
            'path_rename': False,
            'catprefix': '',
        },
    )
    upload_adapter = _module(
        monkeypatch,
        PREFIX + '.adapter.upload_limit',
        **{name: Mock() for name in UPLOAD_ADAPTER_NAMES},
    )
    _module(monkeypatch, PREFIX + '.model.state', UPLOAD_LIMIT_STATE_KEY='upload_limit_state')
    _module(
        monkeypatch,
        PREFIX + '.model.upload_limit',
        UPLOAD_LIMIT_FAILURE_NOTIFY_THRESHOLD=3,
        UploadPool=type('UploadPool', (), {}),
        migrate_upload_limit_state=Mock(side_effect=lambda state: state),
        pool_state_key=Mock(return_value='pool'),
    )
    _module(
        monkeypatch,
        PREFIX + '.modules.uploadlimit.allocator',
        **{name: Mock() for name in ALLOCATOR_NAMES},
    )

    def load(relpath, name, package):
        spec = importlib.util.spec_from_file_location(package + name, PLUGIN / relpath)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    utils_pkg = _module(monkeypatch, PREFIX + '.utils', __path__=[str(PLUGIN / 'utils')])
    config_module = load('utils/config.py', '.config', PREFIX + '.utils')
    service_module = load('modules/uploadlimit/service.py', '.service', PREFIX + '.modules.uploadlimit')
    return SimpleNamespace(
        utils=config_module,
        service=service_module,
        adapter=upload_adapter,
        utils_pkg=utils_pkg,
    )


def _plugin(**overrides):
    """构造能通过上传限速门控的最小插件替身。"""
    plugin = SimpleNamespace(
        _upload_limit_enabled=True,
        _upload_limit_downloaders=['QB1'],
        _upload_limit_downloader_limits_kib={'QB1': 1024},
        _upload_limit_site_rules={},
        _upload_limit_state={'last_summary': {'service_status': 'running'}, 'downloaders': {}},
        _module_observe_only={'upload_limit': True},
    )
    for key, value in overrides.items():
        setattr(plugin, key, value)
    return plugin


def test_observe_blocks_upload_limit_cycle_writes(observe):
    """观察模式下整轮限速协调不产生任何写操作，也不恢复已有额度。"""
    plugin = _plugin(_module_observe_only={'upload_limit': True})

    status = observe.service.run_upload_limit_cycle(plugin, reason='test')

    assert status['observe_only'] is True
    assert status['service_status'] == 'observe_only'
    for name in ('write_global_upload_limit', 'write_torrent_upload_limit',
                 'restore_global_upload_settings', 'restore_torrent_upload_settings'):
        assert getattr(observe.adapter, name).call_count == 0, name
    assert plugin._upload_limit_state['downloaders'] == {}


def test_observe_blocks_upload_limit_restore(observe):
    """决策 B：观察期内不执行恢复，返回明确回执且不触碰下载器。"""
    plugin = _plugin(_module_observe_only={'upload_limit': True})

    result = observe.service.restore_upload_limits(plugin)

    assert result['code'] == 1
    assert result['observe_only'] is True
    assert '不执行上传限速恢复' in result['msg']
    assert observe.adapter.restore_torrent_upload_settings.call_count == 0
    assert observe.adapter.restore_global_upload_settings.call_count == 0


def test_observe_guard_passes_through_when_disabled(observe):
    """未开启观察时不触发守卫：仍进入原有恢复流程（以状态错误分支验证）。"""
    plugin = _plugin(
        _module_observe_only={'upload_limit': False},
        _upload_limit_state_error='状态损坏',
    )

    result = observe.service.restore_upload_limits(plugin)

    assert result['code'] == 1
    assert '无法安全恢复' in result['msg']
    assert 'observe_only' not in result


def test_observe_defaults_fresh_install_only(observe):
    """决策 A 契约：全新安装默认开启观察，老配置升级保持升级前行为。"""
    utils = observe.utils
    assert all(utils.module_observe_only({}, name) for name in utils.OBSERVE_ONLY_KEYS)
    assert not any(
        utils.module_observe_only({'enabled': True}, name) for name in utils.OBSERVE_ONLY_KEYS
    )
