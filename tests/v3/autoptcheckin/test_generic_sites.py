"""Offline generic declaration and registry consumer regression tests."""
import asyncio
import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / 'plugins.v3'))
from autoptcheckin.core import registry
from autoptcheckin.core.models import SignResult, SignStatus
from autoptcheckin.core.nexus import NexusSignin
from autoptcheckin.sites.native import generic


def test_generic_declarations_unique_and_credential_free():
    rows = json.loads(generic._DECLARATIONS.read_text(encoding='utf-8'))
    assert len(rows) == 96  # 已移除关闭站点 hares、52movie；52pt/hdwing/ptzone/yema 转独立模块
    assert len({row['id'] for row in rows}) == 96
    assert len({row['url'] for row in rows}) == 96
    assert not {'hares', '52movie'} & {row['id'] for row in rows}
    assert all({'id', 'name', 'url', 'protocol'} <= set(row) for row in rows)
    base = {'id', 'name', 'url', 'attendance_path', 'protocol'}
    base_rows = sum(set(row) == base for row in rows)
    assert base_rows == 46  # dragonhd 声明 signin_capable:false 进 extras（无签到适配）
    extras = [row for row in rows if set(row) != base]
    assert all(set(row) <= {'id', 'name', 'url', 'attendance_path', 'protocol', 'action_get', 'browserless', 'captcha', 'cloak_steps', 'emulate', 'form_data', 'form_path', 'login_notice', 'login_page_notice', 'message', 'protocol_pending', 'record_spec', 'referer', 'safe_read_path', 'signed_marker', 'signin_capable', 'status_map', 'use_default_message', 'cloak_entry_path', 'browser_login', 'slow', 'slow_timeout', 'headful', 'impersonate', 'reset_hour', 'success_texts'} for row in extras)
    assert not {'pterclub', 'pterclub_g', 'mteam', 'darkland', 'digitalcore', 'iptorrents'} & {row['id'] for row in rows}  # jpopsuki/nebulance/filelist 已转正为仅登录声明


def test_generic_dynamic_registry_and_default_message_chain():
    rows = registry.discover_sites()['sites']
    native = [row for row in rows if row['native']]
    # Baseline includes GTK and LP-Bits in addition to the original 46 declarations.
    assert len(list(generic._DECLARATIONS.parent.glob('*.py'))) - 2 == 31  # +hdwing AJAX + colapt JSON API
    assert len(native) == 127  # Native package discovery includes all declarations.
    assert len({row['id'] for row in rows}) == len(rows)
    for cls in generic.build_generic_sites():
        row = next(row for row in rows if row['id'] == cls.id)
        assert cls.__module__ == generic.__name__
        assert issubclass(cls, NexusSignin)
        assert row['native'] and row['hook_implemented']
        assert row['credential']['kind'] == 'cookie'
        if cls.id not in {'haidan', 'audiences', 'discfan', 'ptfans', 'hhanclub'}:
            assert cls().message_spec().message == NexusSignin.DEFAULT_MESSAGE_XPATHS


@pytest.mark.parametrize('site_id', range(60005, 60026))
def test_custom_numeric_ids_preserve_url_name_and_no_cookie(monkeypatch, site_id):
    monkeypatch.setattr(registry, 'managed_sites', lambda: [])
    rows = registry.get_registry([{'id': site_id, 'name': 'Synthetic', 'url': 'https://fixture.invalid/', 'cookie': 'synthetic'}])['sites']
    row = next(row for row in rows if row['id'] == site_id)
    assert row['name'] == 'Synthetic' and row['url'] == 'https://fixture.invalid/'
    assert 'cookie' not in row


def test_generic_enabled_and_selected_executes_under_scheduler(monkeypatch):
    """verified=False 的 generic 站启用并勾选后，调度轮直接执行（verified 运行时门控已移除）。"""
    module = importlib.import_module('autoptcheckin')
    plugin = module.AutoPtCheckin()
    plugin._config = {'enabled_sites': ['hddolby'], 'sign_sites': ['hddolby']}
    monkeypatch.setattr(registry, 'managed_sites', lambda: [])
    monkeypatch.setattr(module, 'managed_site', lambda *args: {})
    called = []
    monkeypatch.setattr(module, 'run_native',
                        lambda runner, site, info, **kwargs: called.append(site.id) or SignResult(SignStatus.SUCCESS, 'ok'))
    results = plugin._execute_all()
    assert [row['message'] for row in results] == ['ok']
    assert called == ['hddolby']
    assert plugin._track_store().state_of('hddolby', 'sign') == 'pending'  # run_native 被替换，结论由真实执行链回写
