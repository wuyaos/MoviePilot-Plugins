"""门控体系离线测试：micromamba run -n base python -m pytest tests/v3/downloadmanagerlocal/test_gating.py -q

覆盖 v3.5.1 门控回归（commit 5c0b3ec7 + review 修复）：
- MODULE_SWITCHES 注册表 / module_active / module_switch_on / build_module_switches
- PLUGIN_CONFIG_DEFAULTS 键数（117，防漂移）
- _TAG_FLAT_PREFIX_MAP 的 tag_enabled→enable 映射（review P1-2 回归）
- initialize_runtime_config 门控覆盖（总开关×模块开关矩阵、嵌套视图对齐）
宿主（app.sdk/app.plugins）全部替身；不连接 MoviePilot。
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
    pkg = PREFIX + '.modules'
    module(pkg, __path__=[str(PLUGIN / 'modules')])
    module(PREFIX + '.core', __path__=[str(PLUGIN / 'core')])
    autoremove = load('modules/autoremove/constants.py', '.constants', pkg + '.autoremove')
    module(pkg + '.autoremove', __path__=[str(PLUGIN / 'modules/autoremove')], **{
        'constants': autoremove})
    failclean = load('modules/failclean/constants.py', '.constants', pkg + '.failclean')
    module(pkg + '.failclean', __path__=[str(PLUGIN / 'modules/failclean')], **{
        'constants': failclean})
    hr = load('modules/hr/constants.py', '.constants', pkg + '.hr')
    module(pkg + '.hr', __path__=[str(PLUGIN / 'modules/hr')], **{'constants': hr})
    rename_mod = load('modules/rename/service.py', '.rename.service', pkg)
    site_tag = load('modules/sitetag/service.py', '.sitetag.service', pkg)
    utils_pkg = module(PREFIX + '.utils', __path__=[str(PLUGIN / 'utils')])
    utils_config = load('utils/config.py', '.config', PREFIX + '.utils')
    # core/config.py：下载器助手与 tracker 解析用替身
    module('app.plugins.downloadmanagerlocal.adapter', __path__=[str(PLUGIN / 'adapter')])
    module(PREFIX + '.adapter.moviepilot', create_downloader_helper=Mock())
    tracker = load('utils/tracker.py', '.tracker', PREFIX + '.utils')
    service_config = load('core/config.py', '.config', PREFIX + '.core')
    return types.SimpleNamespace(
        utils=utils_config, service=service_config,
        rename=rename_mod, site_tag=site_tag,
    )


def test_registry_and_defaults(gating):
    """注册表覆盖 7 模块、属性名与默认键存在、键数 117。"""
    u = gating.utils
    assert set(u.MODULE_SWITCHES) == {
        'transfer', 'rename', 'tag', 'hr', 'autoremove', 'failclean', 'upload_limit'}
    defaults = u.build_plugin_config_defaults()
    # 112 → 110（2026-10-28）：删除两个死键。`transfer_cron` / `transfer_event_enabled`
    # 全仓零读取（调度实际只有 fallback 间隔一条路径），且后者在 defaults 里被重复声明两次。
    # 110 → 117（阶段三）：新增 7 个模块观察模式键（OBSERVE_ONLY_KEYS）。
    assert len(defaults) == 119
    new_keys = {"transfer_delete_source_default", "transfer_delete_duplicate_default"}
    assert defaults["transfer_delete_source_default"] is False
    assert defaults["transfer_delete_duplicate_default"] is False
    assert len(defaults.keys() - new_keys) == 117
    for removed_key in ('onlyonce', 'hr_onlyonce', 'remover_onlyonce',
                        'rename_onlyonce', 'rename_retry', 'rename_recovery',
                        'transfer_cron', 'transfer_event_enabled'):
        assert removed_key not in defaults, removed_key
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


def test_custom_site_labels_loaded_from_nested_tag_config(gating):
    """回归（2026-10-28）：`_custom_site_labels` 必须来自已构建的嵌套 tag 配置。

    扁平键是 `tag_custom_sites_str`，它到 `custom_site_labels_str` 的别名只发生在
    `_flat_tag_module_config` 里，只有 `build_tag_config` 会解析并产出 `custom_site_labels`。
    早期实现直接读扁平 dict 的 `custom_site_labels` → 永远是空 dict：

    - 补全历史路径（走 `plugin._site_tag_config`）正常，所以站点标签用例一直是绿的；
    - **转移后打标路径**（`modules/sitetag/service.py` 读 `plugin._custom_site_labels`）
      静默忽略用户配置，表现为转移完成但目的端没站点标签，日志只留
      「转移后标签：无法识别站点，跳过打标」。

    实测触发场景：T-EXTRA 5/5 未打标、BATCH 107/107 未打标。
    """
    sc = gating.service
    u = gating.utils
    cfg = dict(u.build_plugin_config_defaults())
    cfg.update({
        'enabled': True,
        'tag_enabled': True,
        'tag_custom_sites_str': 'dml-test.local:6969/announce -> DML-CUSTOM',
    })

    plugin = _Recorder()
    sc.initialize_runtime_config(plugin, cfg)

    assert plugin._custom_site_labels == {'dml-test.local:6969/announce': 'DML-CUSTOM'}
    # 两处必须同源，不允许漂移
    assert plugin._custom_site_labels == plugin._site_tag_config['custom_site_labels']


def test_module_fault_helpers(gating):
    """运行异常快照：记录/清除/读取，只写内存，不依赖 plugin 预置属性。"""
    u = gating.utils
    plugin = SimpleNamespace()

    assert u.module_faults(plugin) == {}

    u.record_module_fault(plugin, 'hr', ' 下载器不可用 ')
    u.record_module_fault(plugin, 'transfer', '')
    assert u.module_faults(plugin) == {'hr': '下载器不可用', 'transfer': '未知原因'}

    u.clear_module_fault(plugin, 'hr')
    u.clear_module_fault(plugin, 'not-exist')
    assert u.module_faults(plugin) == {'transfer': '未知原因'}


def test_module_config_guarded_skips_closed_module(gating):
    """P2-1：关闭的模块不解析用户配置，只留「未启用」占位。"""
    sc = gating.service
    calls = []

    def builder():
        calls.append('called')
        return {'movie_format': '{{ title }}'}

    result = sc._module_config_guarded(
        SimpleNamespace(), 'rename', False, builder, {'enabled': False})

    assert result == {'enabled': False}
    assert calls == [], '关闭模块不得解析用户配置'


def test_module_config_guarded_marks_fault_on_bad_config(gating):
    """P2-1：启用模块配置解析失败只标记运行异常并回退占位，不抛给调用方。"""
    sc = gating.service
    plugin = SimpleNamespace()

    def boom():
        raise ValueError('坏配置')

    result = sc._module_config_guarded(plugin, 'rename', True, boom, {'enabled': False})

    assert result == {'enabled': False}
    assert plugin._module_faults == {'rename': '配置解析失败：坏配置'}


def test_initialize_runtime_config_skips_closed_module_parse(gating):
    """P2-1：总开关关闭时不解析 rename/tag 配置，运行时只有未启用占位。"""
    sc = gating.service
    u = gating.utils
    cfg = dict(u.build_plugin_config_defaults())
    cfg.update({'tag_siteprefix': '', 'tag_tracker_mappings_str': ''})

    plugin = _Recorder()
    sc.initialize_runtime_config(plugin, cfg)

    assert plugin._rename_config == {'enabled': False}
    assert plugin._site_tag_config == {'enable': False}
    assert plugin._custom_site_labels == {}
    assert plugin._module_faults == {}


def test_initialize_runtime_config_isolates_bad_module_config(gating, monkeypatch):
    """P2-1：坏配置只标记该模块运行异常，其它模块照常解析，插件总开关不变。"""
    sc = gating.service
    u = gating.utils
    cfg = dict(u.build_plugin_config_defaults())
    cfg.update({
        'enabled': True,
        'transfer_enabled': True,
        'tag_enabled': True,
        'tag_tracker_mappings_str': '',
    })

    def boom(_config):
        raise ValueError('坏 rename 配置')

    monkeypatch.setattr(sc, 'build_rename_config', boom)
    plugin = _Recorder()
    sc.initialize_runtime_config(plugin, cfg)

    assert plugin._rename_config == {'enabled': False}, '坏配置回退占位'
    assert plugin._module_faults == {'rename': '配置解析失败：坏 rename 配置'}
    assert plugin._rename_enabled is False, '故障模块不进入运行态'
    assert plugin._module_switches['rename'] is True, '用户开关不被改写'
    assert plugin._enabled is True, '插件总开关不变'
    assert plugin._transfer_enabled is True
    assert plugin._tag_enabled is True
    assert plugin._site_tag_config['enable'] is True, '其它模块照常解析'


def test_observe_only_resolver(gating):
    """阶段三观察模式口径：新键优先、旧键继承、老配置保持原行为、全新安装默认开启。"""
    u = gating.utils
    assert set(u.OBSERVE_ONLY_KEYS) == set(u.MODULE_SWITCHES)
    defaults = u.build_plugin_config_defaults()
    legacy = {'enabled': True, 'transfer_enabled': True, 'tag_enabled': True}

    for module, key in u.OBSERVE_ONLY_KEYS.items():
        assert key in defaults, key
        # 全新安装默认开启观察
        assert u.module_observe_only({}, module) is True, module
        # 老配置升级（无新键）保持升级前行为：允许执行
        assert u.module_observe_only(legacy, module) is False, module
        # 已保存新键以新值为准
        assert u.module_observe_only({key: True}, module) is True, module
        assert u.module_observe_only({key: False}, module) is False, module

    # 自动删种旧键 migration_observe_only 继承
    assert u.module_observe_only({'migration_observe_only': True}, 'autoremove') is True
    assert u.module_observe_only({'migration_observe_only': False}, 'autoremove') is False
    # 新键优先于旧键
    assert u.module_observe_only(
        {'migration_observe_only': True, 'remover_observe_only': False}, 'autoremove') is False
    # 旧键不泄漏到其它模块
    assert u.module_observe_only({'migration_observe_only': True}, 'transfer') is False
    # 未登记模块恒为 False
    assert u.module_observe_only({'x': 1}, 'unknown') is False


def test_observe_flags_snapshot(gating):
    """快照口径：一轮运行内固定；快照缺失或类型异常时按不观察处理。"""
    u = gating.utils
    assert u.build_module_observe_flags({}) == {name: True for name in u.OBSERVE_ONLY_KEYS}
    flags = u.build_module_observe_flags({'transfer_observe_only': False, 'hr_observe_only': True})
    assert flags['transfer'] is False
    assert flags['hr'] is True
    assert flags['upload_limit'] is False

    plugin = SimpleNamespace(_module_observe_only={'upload_limit': True})
    assert u.observe_only(plugin, 'upload_limit') is True
    assert u.observe_only(plugin, 'transfer') is False
    assert u.module_observe_flags(SimpleNamespace()) == {
        name: False for name in u.OBSERVE_ONLY_KEYS}
    assert u.observe_only(SimpleNamespace(), 'transfer') is False
    assert u.observe_only(SimpleNamespace(_module_observe_only=None), 'transfer') is False


def test_initialize_runtime_config_records_observe_snapshot(gating):
    """P3-1：初始化时把观察模式快照挂到插件实例，供各模块写边界读取。"""
    sc = gating.service
    u = gating.utils
    # 升级来的老配置：只带旧键，不含观察键（不能用 build_plugin_config_defaults，那里含全新安装默认值）
    cfg = {'enabled': True, 'transfer_enabled': True, 'transfer_observe_only': True}

    plugin = _Recorder()
    sc.initialize_runtime_config(plugin, cfg)

    assert plugin._module_observe_only['transfer'] is True
    assert plugin._module_observe_only['upload_limit'] is False
    assert set(plugin._module_observe_only) == set(u.OBSERVE_ONLY_KEYS)
