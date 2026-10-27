"""Configuration switches share state styles; adaptation is code capability, not selection."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / 'frontend.v3/autoptcheckin/src'
sys.path.insert(0, str(ROOT / 'plugins.v3'))
from autoptcheckin import AutoPtCheckin
from autoptcheckin.core.registry import get_registry


def test_emulate_capability_survives_user_overrides(monkeypatch):
    monkeypatch.setattr('autoptcheckin.core.registry.managed_sites', lambda: [])
    rows = {s['id']: s for s in get_registry([
        {'id': 'custom-fixture', 'name': 'Fixture', 'url': 'https://fixture.invalid', 'emulate': True}
    ])['sites']}
    for sid in ('yema', 'vclib', 'mteam'):
        assert rows[sid]['emulate_capable'] is True
    for sid in ('rousi', 'sunnypt', 'custom-fixture', 'hdsky'):
        assert rows[sid]['emulate_capable'] is False
    assert all(type(row['signin_capable']) is bool for row in rows.values())
    assert all(type(row['emulate_capable']) is bool for row in rows.values())
    plugin = AutoPtCheckin()
    for selected in (True, False):
        plugin._config = {'site_emulate': {sid: selected for sid in rows}}
        for sid, row in rows.items():
            capability = row['emulate_capable']
            plugin._apply_effective_flags(row)
            assert row['emulate'] is selected
            assert row['emulate_capable'] is capability


def test_switch_state_styles_have_no_context_overrides():
    css = (SRC / 'preview.css').read_text(encoding='utf-8')
    assert '.mini-switch input' not in css
    assert '.emulate-switch input' not in css
    assert '.switch input:checked{background:var(--ptc-switch-on)}' in css
    assert '.switch.adapt input{background:var(--ptc-switch-adapt)}' in css
    assert '.switch.adapt input:checked{background:var(--ptc-switch-on);box-shadow:inset 0 0 0 2px var(--ptc-switch-adapt)}' in css
    assert 'width:38px;height:22px' in css
    assert 'width:18px;height:18px;top:2px;left:2px' in css


def test_groups_and_optional_expand_keep_columns():
    source = (SRC / 'Config.vue').read_text(encoding='utf-8')
    assert 'const hasEmulate = site => site.emulate_capable === true' in source
    assert '<span v-else class="expand-placeholder" aria-hidden="true"></span>' in source
    css = (SRC / 'preview.css').read_text(encoding='utf-8')
    assert ':is(.expand-icon,.expand-placeholder)' in css
    assert 'switch-group-left { justify-content:flex-start; }' in css
    assert 'switch-group-right { margin-left:auto; justify-content:flex-end; }' in css
    assert source.count('class="switch mini-switch"><input type="checkbox" role="switch"') == 4
