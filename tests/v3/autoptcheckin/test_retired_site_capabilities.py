"""Retired capabilities must not execute, even with stale user selections."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))

from autoptcheckin import AutoPtCheckin
from autoptcheckin.core import cloudsign, registry
from autoptcheckin.core.state_store import TrackStateStore


def test_hdwing_matches_managed_site_without_changing_identity(monkeypatch):
    monkeypatch.setattr(registry, 'managed_sites', lambda: [{
        'url': 'https://www.hdwing.org/', 'name': 'MP登记名称',
        'icon': '', 'proxy': False, 'render': False,
    }])
    rows = {row['id']: row for row in registry.get_registry()['sites']}
    assert rows['hdwing']['source'] == 'MP 站点'
    assert rows['hdwing']['name'] == 'MP登记名称'
    assert registry.site_id_for_domain('https://hdwing.org/') == 'hdwing'
    assert registry.site_id_for_domain('https://www.hdwing.org/') == 'hdwing'


def test_audiences_keeps_login_but_has_no_signing_transport():
    site = registry.get_native_module('audiences')
    row = next(row for row in registry.get_registry()['sites'] if row['id'] == 'audiences')
    assert site.signin_capable is False and site.login_capable is True
    assert site.attendance_path is None
    assert not getattr(site, 'emulate', False) and not getattr(site, 'cloak_steps', ())
    assert not row['emulate_capable'] and not row['cloudsign_capable']
    assert row['shield'] is None
    assert row['signin_note'] == '站点已取消签到功能'
    assert not cloudsign.enabled('audiences')
    assert 'audiences' not in cloudsign.CLOUD_RULES


@pytest.mark.parametrize('old_status', ['failed', 'success', 'pending'])
def test_old_selections_cannot_requeue_retired_actions(old_status):
    plugin = AutoPtCheckin()
    plugin._state = TrackStateStore()
    ids = ['audiences', 'momentpt']
    plugin._config = dict(enabled_sites=ids, sign_sites=ids, login_sites=ids,
                          site_cloudsign=['audiences'], site_emulate={'audiences': True})
    plugin._registry = registry.get_registry
    for sid in ids:
        for action in ('sign', 'login'):
            plugin._state.apply_result(sid, action, ('login_ok' if action == 'login' and old_status == 'success' else old_status))
    plugin._recompute_track_states()
    assert plugin._due_for('sign') == []
    assert 'momentpt' not in plugin._due_for('login')
    # Historical terminal conclusions are deliberately retained; capability gates win.
    expected = old_status if old_status in ('success', 'failed') else 'disabled'
    assert plugin._state.state_of('momentpt', 'sign') == expected
    assert plugin._state.state_of('momentpt', 'login') == expected
    assert plugin._state.state_of('audiences', 'sign') == expected
    assert plugin._state.state_of('audiences', 'login') != 'disabled'


@pytest.mark.parametrize('sid,action', [('audiences', 'sign'), ('momentpt', 'sign'), ('momentpt', 'login')])
def test_single_site_entry_rejects_retired_actions_before_io(sid, action, monkeypatch):
    plugin = AutoPtCheckin()
    plugin._config = dict(enabled_sites=[sid], sign_sites=[sid], login_sites=[sid],
                          site_cloudsign=['audiences'], site_emulate={'audiences': True})
    plugin._registry = registry.get_registry
    plugin._runner = SimpleNamespace(history=lambda *args, **kwargs: None)
    monkeypatch.setattr(plugin, '_record_result', lambda *args, **kwargs: None)
    result = plugin._execute_site(sid, action=action)
    assert result['status'] == 'skipped'
    assert result['metadata']['reason'] in ('signin_not_supported', 'login_not_supported')
