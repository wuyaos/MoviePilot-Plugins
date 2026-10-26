"""Ralph R2 新门控契约：启用+勾选即可执行；unlock/verified 审批门控移除后的行为回归。"""
import asyncio
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
import autoptcheckin as entry
from autoptcheckin.core.models import SignResult, SignStatus
from autoptcheckin.core.notify import format_round_notifications
from autoptcheckin.core import registry as registry_module
from autoptcheckin.core.state_store import TrackStateStore


def _stub_environment(monkeypatch, site_id='hddolby'):
    monkeypatch.setattr(registry_module, 'managed_sites', lambda: [])
    monkeypatch.setattr(entry, 'managed_site', lambda sid: {})
    called = []
    monkeypatch.setattr(entry, 'run_native',
                        lambda runner, site, info, **kwargs: called.append(site.id) or SignResult(SignStatus.SUCCESS, 'ok'))
    return called


def test_by_domain_fallback_without_unlock_respects_enabled_gate(monkeypatch):
    """by-domain 按注册 ID 回退不再依赖 unlock，但仍受启用检查约束。"""
    module = importlib.import_module('autoptcheckin')
    plugin = module.AutoPtCheckin()
    # 未启用：回退能解析注册 ID，但执行被 site_disabled 拦下。
    called = _stub_environment(monkeypatch)
    result = asyncio.run(plugin.api_signin_by_domain(domain='hddolby'))['data']
    assert result['status'] == 'skipped' and result['metadata']['reason'] == 'site_disabled'
    assert not called


def test_by_domain_fallback_executes_enabled_and_selected_site(monkeypatch):
    module = importlib.import_module('autoptcheckin')
    plugin = module.AutoPtCheckin()
    plugin._config = {'enabled_sites': ['hddolby'], 'sign_sites': ['hddolby']}
    called = _stub_environment(monkeypatch)
    result = asyncio.run(plugin.api_signin_by_domain(domain='hddolby'))['data']
    assert result['status'] == 'signed'
    assert not result.get('reason')
    assert called == ['hddolby']


def test_by_domain_does_not_bypass_sign_selection(monkeypatch):
    """勾选检查不可绕过：启用但未勾签到的注册站不得执行。"""
    module = importlib.import_module('autoptcheckin')
    plugin = module.AutoPtCheckin()
    plugin._config = {'enabled_sites': ['hddolby'], 'sign_sites': []}
    called = _stub_environment(monkeypatch)
    result = asyncio.run(plugin.api_signin_by_domain(domain='hddolby'))['data']
    assert result['status'] == 'skipped' and result['metadata']['reason'] == 'signin_not_selected'
    assert not called


def _plugin_with_store():
    data = {}
    plugin = entry.AutoPtCheckin()
    plugin.get_data = lambda key: data.get(key)
    plugin.save_data = lambda key, value: data.__setitem__(key, value)
    return plugin, data


def test_legacy_gate_disabled_state_is_recomputed_to_pending():
    """旧 native_unverified 等审批 disabled 在重算后恢复为 pending（success 不降级）。"""
    plugin, data = _plugin_with_store()
    seed = TrackStateStore(lambda key: None, lambda key, value: data.__setitem__(key, value))
    seed.apply_result('hddolby', 'sign', 'skipped', reason='native_unverified')
    seed.apply_result('hdsky', 'sign', 'success')
    assert seed.state_of('hddolby', 'sign') == 'disabled'

    plugin._config = {'enabled_sites': ['hddolby', 'hdsky'], 'sign_sites': ['hddolby', 'hdsky']}
    plugin._recompute_track_states()
    assert plugin._track_store().state_of('hddolby', 'sign') == 'pending'
    assert plugin._track_store().state_of('hdsky', 'sign') == 'success'


def test_notify_filters_skipped_and_disabled_from_failure_counts_and_details():
    rendered = format_round_notifications({
        'sign': {'total': 3, 'executed': 1, 'next': 0, 'entries': [
            ('Busy', {'status': 'skipped', 'state': 'pending'}),
            ('Gated', {'status': 'skipped', 'state': 'disabled', 'reason': 'site_disabled'}),
            ('Done', {'status': 'success', 'message': '签到成功'}),
        ]},
        'login': {'total': 2, 'executed': 1, 'next': 0, 'entries': [
            ('Cancelled', {'status': 'cancelled', 'state': 'pending'}),
            ('LoginOk', {'status': 'login_ok'})]},
    })
    sign_text = rendered[0][2]
    assert '【Busy】' not in sign_text and '【Gated】' not in sign_text
    assert sign_text.splitlines()[:3] == ['全部签到: 3',
                                          '本次签到: 1（成功 1 · 失败 0 · 待处理 0）',
                                          '下轮待执行: 0']
    login_text = rendered[1][2]
    assert '【Cancelled】' not in login_text
    assert login_text.splitlines()[:3] == ['全部登录: 2',
                                           '本次登录: 1（成功 1 · 失败 0 · 待处理 0）',
                                           '下轮待执行: 0']


def test_lock_busy_attempt_is_not_counted_as_executed():
    """_last_round_results 只收录有明确结果的站点：锁忙跳过不算实际执行，避免旧快照误报。"""
    plugin = entry.AutoPtCheckin()
    plugin._recompute_track_states = lambda: None
    plugin._track_store = lambda: SimpleNamespace(rollover=lambda: None)
    plugin._due_for = lambda action: ['a', 'b'] if action == 'sign' else []
    outcomes = {'a': {'status': 'skipped'}, 'b': {'status': 'success'}}
    plugin._run_with_retry = lambda site_id, action, trigger: outcomes[site_id]
    plugin._notify_round = Mock()
    plugin._execute_all_round('scheduler')
    assert list(plugin._last_round_results) == [('b', 'sign')]
