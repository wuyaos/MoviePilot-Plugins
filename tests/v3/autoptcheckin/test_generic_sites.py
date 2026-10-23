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
from autoptcheckin.core.nexus import NexusSignin
from autoptcheckin.sites.native import generic


def test_generic_declarations_unique_and_credential_free():
    rows = json.loads(generic._DECLARATIONS.read_text(encoding='utf-8'))
    assert len(rows) == 85
    assert len({row['id'] for row in rows}) == 85
    assert len({row['url'] for row in rows}) == 85
    assert all({'id', 'name', 'url'} <= set(row) for row in rows)
    base_rows = sum(set(row) == {'id', 'name', 'url', 'attendance_path'} for row in rows)
    assert base_rows == 50  # extras: emulate/cloak_steps/signin_capable/login_notice 声明站（含 pt_0ff/52pt/yema/piggo 等）
    extras = [row for row in rows if set(row) != {'id', 'name', 'url', 'attendance_path'}]
    assert all(set(row) <= {'id', 'name', 'url', 'attendance_path', 'action_get', 'browserless', 'captcha', 'cloak_steps', 'emulate', 'form_data', 'form_path', 'login_notice', 'message', 'protocol_pending', 'record_spec', 'referer', 'safe_read_path', 'signed_marker', 'signin_capable', 'status_map', 'use_default_message', 'cloak_entry_path'} for row in extras)
    assert not {'pterclub', 'pterclub_g', 'mteam', 'darkland', 'digitalcore', 'jpopsuki', 'nebulance', 'filelist', 'iptorrents'} & {row['id'] for row in rows}


def test_generic_dynamic_registry_and_default_message_chain():
    rows = registry.discover_sites()['sites']
    native = [row for row in rows if row['native']]
    # Baseline includes GTK and LP-Bits in addition to the original 46 declarations.
    assert len(list(generic._DECLARATIONS.parent.glob('*.py'))) - 2 == 29
    assert len(native) == 111  # Includes the newly declared ourbits site.
    assert len({row['id'] for row in rows}) == len(rows)
    for cls in generic.build_generic_sites():
        row = next(row for row in rows if row['id'] == cls.id)
        assert cls.__module__ == generic.__name__
        assert issubclass(cls, NexusSignin)
        assert row['native'] and not row['verified'] and row['hook_implemented']
        assert row['credential']['kind'] == 'cookie' and not row['pilot_enabled']
        if cls.id not in {'haidan', 'audiences', 'discfan', 'ptfans', 'hhanclub'}:
            assert cls().message_spec().message == NexusSignin.DEFAULT_MESSAGE_XPATHS


@pytest.mark.parametrize('site_id', range(60005, 60026))
def test_custom_numeric_ids_preserve_url_name_and_no_cookie(monkeypatch, site_id):
    monkeypatch.setattr(registry, 'managed_sites', lambda: [])
    rows = registry.get_registry([{'id': site_id, 'name': 'Synthetic', 'url': 'https://fixture.invalid/', 'cookie': 'synthetic'}])['sites']
    row = next(row for row in rows if row['id'] == site_id)
    assert row['name'] == 'Synthetic' and row['url'] == 'https://fixture.invalid/'
    assert 'cookie' not in row


def test_generic_unverified_gate_no_credentials_or_network(monkeypatch):
    module = importlib.import_module('autoptcheckin')
    plugin = module.AutoPtCheckin()
    plugin._config = {'enabled_sites': ['hddolby'], 'sign_sites': ['hddolby']}
    monkeypatch.setattr(registry, 'managed_sites', lambda: [])
    monkeypatch.setattr(module, 'managed_site', lambda *args: pytest.fail('credentials must not be read before gate'))
    assert plugin._execute_all() == []
    assert plugin._track_store().state_of('hddolby', 'sign') == 'disabled'


def test_generator_filters_sources_and_deduplicates(tmp_path, monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location('build_generic_sites', ROOT / 'scripts/build_generic_sites.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    native = tmp_path / 'plugins.v3/autoptcheckin/sites/native'
    native.mkdir(parents=True)
    (native / 'known.py').write_text("class Known:\n id = 'known'\n url = 'https://known.example/'\n", encoding='utf-8')
    rows = [{'id': 1, 'name': 'New', 'url': 'https://www.new.example/'},
            {'id': 2, 'name': 'Known', 'url': 'https://known.example/'},
            {'id': 3, 'name': 'Foreign', 'url': 'https://foreign.example/'},
            {'id': 4, 'name': 'Not selected', 'url': 'https://unused.example/'},
            {'id': 5, 'name': 'Alias', 'url': 'https://pterclub.net/'}]
    sites, config, log, out = [tmp_path / name for name in ('sites.json', 'config.json', 'cookies.log', 'out.json')]
    sites.write_text(json.dumps({'data': rows}), encoding='utf-8')
    config.write_text(json.dumps({'data': repr({'sign_sites': [1, 2, 3, 5], 'login_sites': [1, 60005], 'custom_sites_data': [{'id': 60005, 'name': 'Duplicate', 'url': 'https://new.example/'}]})}), encoding='utf-8')
    log.write_text('.new.example c_secure_pass len= 32\n.known.example c_secure_pass len= 32\n.unused.example c_secure_pass len= 32\npterclub.net c_secure_pass len= 32\n', encoding='utf-8')
    for key, value in dict(ROOT=tmp_path, SITES=sites, CONFIG=config, COOKIE_LOG=log, OUTPUT=out).items():
        monkeypatch.setattr(builder, key, value)
    # Alias exclusion applies even when the fixture omits the dedicated declaration.
    (native / 'pterclub.py').write_text("id = 'pterclub'\nurl = 'https://pterclub.com/'\n", encoding='utf-8')
    builder.main()
    result = json.loads(out.read_text(encoding='utf-8'))
    assert [row['id'] for row in result] == ['new']
    report = json.loads(capsys.readouterr().out)
    assert {row['id'] for row in report['excluded_rows']} == {2, 3, 5}
    assert builder.generic_id('https://www.hddolby.com/', set()) == 'hddolby'
    assert builder.generic_id('https://pt.sjtu.edu.cn/', set()) == 'pt_sjtu_edu'
    assert builder.generic_id('https://hddolby.com/', {'hddolby'}) == 'hddolby_g'
