"""H&R 站点白名单（站点名口径）离线测试：micromamba run -n base python -m pytest tests/v3/downloadmanagerlocal/test_hr_site_scope.py -q

覆盖 v3.8.0 改造：
- _as_site_names：站点名规范化（strip/去重/中文逗号），旧格式数字 ID（站点库主键）丢弃
- HrConfig.site_in_scope：按站点名判定（白名单或自定义规则条目命中）
- HR_QNAP_CONFIG 基线为站点名数组（无数字残留）
宿主（app.*）全部替身；不连接 MoviePilot。
"""

import importlib.machinery
import importlib.util
import sys
import types
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[3] / 'plugins.v3/downloadmanagerlocal'
HR_DIR = PLUGIN / 'service' / 'hr'
PKG = 'app.plugins.downloadmanagerlocal.service.hr'


def _module(monkeypatch, name, **attrs):
    """带 __spec__ 的包替身（pytest 断言重写要求 spec 非 None）。"""
    path = attrs.pop('__path__', None)
    result = types.ModuleType(name)
    result.__spec__ = importlib.machinery.ModuleSpec(name, None, is_package=path is not None)
    if path is not None:
        result.__path__ = path
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
def hr(monkeypatch, tmp_path):
    _module(monkeypatch, 'app')
    _module(monkeypatch, 'app.sdk')
    _module(monkeypatch, 'app.sdk.config', settings=types.SimpleNamespace())
    _module(monkeypatch, 'app.sdk.logging', logger=__import__('logging').getLogger('test'))
    _module(monkeypatch, 'app.plugins')
    _module(monkeypatch, 'app.plugins.downloadmanagerlocal', __path__=str(PLUGIN))
    _module(monkeypatch, 'app.plugins.downloadmanagerlocal.service',
            __path__=str(PLUGIN / 'service'))
    _module(monkeypatch, PKG, __path__=str(HR_DIR))
    constants = _load_from_file(monkeypatch, f'{PKG}.constants', HR_DIR / 'constants.py')
    models = _load_from_file(monkeypatch, f'{PKG}.models', HR_DIR / 'models.py')
    rules = _load_from_file(monkeypatch, f'{PKG}.rules', HR_DIR / 'rules.py')
    return types.SimpleNamespace(models=models, rules=rules, constants=constants)
def test_as_site_names_keeps_names(hr):
    parse = hr.rules._as_site_names
    assert parse(['GGPT', ' 老师 ', 'GGPT', '', '52pt']) == ['GGPT', '老师', '52pt']
    assert parse('GGPT，52pt') == ['GGPT', '52pt']


def test_as_site_names_drops_legacy_ids(hr):
    parse = hr.rules._as_site_names
    assert parse([24, 40, '8.5', 'GGPT']) == ['GGPT']
    assert parse([24]) == []


def test_site_in_scope_by_name(hr):
    config = hr.models.HrConfig(sites=['GGPT', '52pt'])
    assert config.site_in_scope('GGPT') is True
    assert config.site_in_scope(' GGPT ') is True
    assert config.site_in_scope('ggpt') is False
    assert config.site_in_scope('老师') is False
    assert config.site_in_scope('') is False
    assert config.site_in_scope(None) is False


def test_site_in_scope_by_custom_rule(hr):
    config = hr.models.HrConfig(site_rules={'SomeSite': hr.models.HrSiteRule()})
    assert config.site_in_scope('SomeSite') is True


def test_qnap_baseline_uses_names(hr):
    baseline = hr.constants.HR_QNAP_CONFIG['hr_sites']
    assert baseline and all(isinstance(item, str) and item for item in baseline)
