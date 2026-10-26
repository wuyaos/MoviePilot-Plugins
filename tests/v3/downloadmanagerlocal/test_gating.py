"""门控体系离线测试：micromamba run -n base python -m pytest tests/v3/downloadmanagerlocal/test_gating.py -q

覆盖 v3.5.1 门控回归（commit 5c0b3ec7 + review 修复）：
- MODULE_SWITCHES 注册表 / module_active / module_switch_on / build_module_switches
- PLUGIN_CONFIG_DEFAULTS 键数（113，防漂移）
- _TAG_FLAT_PREFIX_MAP 的 tag_enabled→enable 映射（review P1-2 回归）
- initialize_runtime_config 门控覆盖（总开关×模块开关矩阵、嵌套视图对齐）
宿主（app.sdk/app.plugins）全部替身；不连接 MoviePilot。
"""

import importlib.machinery
import importlib.util


import sys
import types
from pathlib import Path
from unittest.mock import Mock

import pytest

PLUGIN = Path(__file__).resolve().parents[3] / 'plugins.v3/downloadmanagerlocal'
PREFIX = 'app.plugins.downloadmanagerlocal'


@pytest.fixture
def gating(monkeypatch):
    def module(name, **attrs):
        """带 __spec__ 的包替身（pytest 断言重写要求 spec 非 None）。"""
        path = attrs.pop('__path__', None)
        result = types.ModuleType(name)
        result.__spec__ = importlib.machinery.ModuleSpec(
            name, None, is_package=path is not None)
        if path is not None:
            result.__path__ = path
        result.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, result)
        return result
    module('app')
    module('app.sdk')
    module('app.plugins')
    module('app.plugins.downloadmanagerlocal', __path__=[str(PLUGIN)])
    module('app.sdk.logging', logger=Mock())
    module('app.sdk.logging', logger=Mock())
    module('app.application')
    module('app.application.torrent')
    module('app.application.torrent.download', TorrentHelper=Mock())
    module('app.db')
    module('app.db.oper')
    module('app.db.oper.downloadhistory', DownloadHistoryOper=Mock())
    module('app.db.oper.site', SiteOper=Mock())
    module('app.modules.qbittorrent', Qbittorrent=type('Qbittorrent', (), {}))
    module('app.modules.transmission', Transmission=type('Transmission', (), {}))
    module('app.sdk.network', RequestUtils=Mock(), SitesHelper=Mock())
    module('app.sdk.services', DownloaderHelper=Mock())
    module('app.sdk.utilities', StringUtils=Mock())
    module('app.sdk.media', MetaBase=object, MetaInfo=Mock, resolve_media_identity=Mock())
    module('app.sdk.config', settings=Mock())
    module('app.modules')
    module('app.modules.filemanager')
    module('app.modules.filemanager.transhandler', TransHandler=Mock())
    module('app.schemas')
    module('app.schemas.types', MediaType=Mock(), MessageType=Mock())
    module('bencode', bdecode=Mock(), bencode=Mock())

    def load(relpath, name, pkg):
        spec = importlib.util.spec_from_file_location(
            pkg + name, PLUGIN / relpath)
        result = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = result
        spec.loader.exec_module(result)
        return result

    # utils/config.py 依赖四个常量/默认值来源，全部加载真实文件
    pkg = PREFIX + '.service'
    module(pkg, __path__=[str(PLUGIN / 'service')])
    autoremove = load('service/autoremove/constants.py', '.constants', pkg + '.autoremove')
    module(pkg + '.autoremove', __path__=[str(PLUGIN / 'service/autoremove')], **{
        'constants': autoremove})
    failclean = load('service/failclean/constants.py', '.constants', pkg + '.failclean')
    module(pkg + '.failclean', __path__=[str(PLUGIN / 'service/failclean')], **{
        'constants': failclean})
    hr = load('service/hr/constants.py', '.constants', pkg + '.hr')
    module(pkg + '.hr', __path__=[str(PLUGIN / 'service/hr')], **{'constants': hr})
    rename_mod = load('service/rename.py', '.rename', pkg)
    site_tag = load('service/site_tag.py', '.site_tag', pkg)
    utils_pkg = module(PREFIX + '.utils', __path__=[str(PLUGIN / 'utils')])
    utils_config = load('utils/config.py', '.config', PREFIX + '.utils')
    # service/config.py：下载器助手与 tracker 解析用替身
    module('app.plugins.downloadmanagerlocal.adapter', __path__=[str(PLUGIN / 'adapter')])
    module(PREFIX + '.adapter.moviepilot', create_downloader_helper=Mock())
    tracker = load('utils/tracker.py', '.tracker', PREFIX + '.utils')
    service_config = load('service/config.py', '.config', pkg)
    return types.SimpleNamespace(
        utils=utils_config, service=service_config,
        rename=rename_mod, site_tag=site_tag,
    )


def test_registry_and_defaults(gating):
    """注册表覆盖 7 模块、属性名与默认键存在、键数 113。"""
    u = gating.utils
    assert set(u.MODULE_SWITCHES) == {
        'transfer', 'rename', 'tag', 'hr', 'autoremove', 'failclean', 'upload_limit'}
    defaults = u.build_plugin_config_defaults()
    assert len(defaults) == 113
    for flat_key, attr in u.MODULE_SWITCHES.values():
        assert flat_key in defaults, flat_key


def test_module_active_matrix(gating):
    """module_active = 总开关 AND 模块开关；module_switch_on 只读裸开关。"""
    u = gating.utils
    cfg = dict(u.build_plugin_config_defaults())
    for name in u.MODULE_SWITCHES:
        assert u.module_active(cfg, name) is False
    cfg['enabled'] = True
    # rename/tag 默认开（沿用原插件语义），其余默认关
    assert u.module_active(cfg, 'rename') is True
    assert u.module_active(cfg, 'tag') is True
    assert u.module_active(cfg, 'transfer') is False
    for name in u.MODULE_SWITCHES:
        cfg[u.MODULE_SWITCHES[name][0]] = True
        assert u.module_active(cfg, name) is True
    cfg['enabled'] = False
    for name in u.MODULE_SWITCHES:
        assert u.module_active(cfg, name) is False
    cfg['enabled'] = True
    assert u.module_switch_on(cfg, 'transfer') is True


def test_build_module_switches_snapshot(gating):
    """裸值快照与注册表一一对应，且不受总开关影响。"""
    u = gating.utils
    cfg = dict(u.build_plugin_config_defaults())
    cfg['enabled'] = True
    cfg['transfer_enabled'] = True
    snap = u.build_module_switches(cfg)
    assert snap == {'transfer': True, 'rename': True, 'tag': True,
                    'hr': False, 'autoremove': False, 'failclean': False,
                    'upload_limit': False}


def test_tag_flat_map_enable_regression(gating):
    """review P1-2 回归：tag_enabled 必须登记进 _TAG_FLAT_PREFIX_MAP。"""
    svc = gating.service
    assert svc._TAG_FLAT_PREFIX_MAP.get('tag_enabled') == 'enable'
    nested = svc._flat_tag_module_config({'tag_enabled': False, 'tag_downloaders': ['d1']})
    assert nested['enable'] is False
    assert nested['downloaders'] == ['d1']


class _Recorder:
    """记录门控属性写入的最小 plugin 替身。"""

    def __init__(self):
        self._rename_config = {}
        self._site_tag_config = {}
        self._tracker_mappings = {}


def test_initialize_runtime_config_gating(gating):
    """总开关×模块开关矩阵：属性/嵌套视图均为门控值（review P1-2 的功能修复点）。"""
    sc = gating.service
    u = gating.utils
    base = dict(u.build_plugin_config_defaults())
    base.update({'tag_siteprefix': '', 'tag_tracker_mappings_str': ''})

    # 总开关关：所有模块属性 False，嵌套视图被门控值覆盖
    plugin = _Recorder()
    sc.initialize_runtime_config(plugin, dict(base))
    assert plugin._enabled is False
    for attr in ('_transfer_enabled', '_rename_enabled', '_tag_enabled',
                 '_hr_enabled', '_remover_enabled', '_failcleanup_enabled',
                 '_upload_limit_enabled'):
        assert getattr(plugin, attr) is False, attr
    assert plugin._site_tag_config['enable'] is False
    assert plugin._rename_config['enabled'] is False

    # 总开关开 + tag_enabled 显式 False：嵌套 enable 必须被压住（双保险：映射+覆盖）
    cfg = dict(base)
    cfg['enabled'] = True
    plugin2 = _Recorder()
    sc.initialize_runtime_config(plugin2, cfg)
    assert plugin2._tag_enabled is True
    assert plugin2._site_tag_config['enable'] is True
    cfg['tag_enabled'] = False
    plugin3 = _Recorder()
    sc.initialize_runtime_config(plugin3, cfg)
    assert plugin3._tag_enabled is False
    assert plugin3._site_tag_config['enable'] is False
    # 裸值快照可用于展示层区分「插件停用」vs「模块停用」
    assert plugin3._module_switches['tag'] is False
    assert plugin3._module_switches['rename'] is True
