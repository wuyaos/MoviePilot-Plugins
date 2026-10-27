import asyncio
import importlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
from autoptcheckin import AutoPtCheckin
from autoptcheckin.core.history import HistoryStore
from autoptcheckin.core.registry import discover_sites, site_id_for_domain
from autoptcheckin.core.models import Evidence, SignResult, SignStatus


def test_registry_discovers_only_native_package_and_isolates_import_failures(tmp_path, monkeypatch):
    package = tmp_path / 'fixture_sites'
    native = package / 'native'
    native.mkdir(parents=True)
    (package / '__init__.py').write_text('class _ISiteSigninHandler: pass\n')
    (package / 'legacy.py').write_text('raise RuntimeError("legacy module must not be imported")\n')
    (native / '__init__.py').write_text('')
    (native / 'broken.py').write_text('raise RuntimeError("offline failure")\n')
    monkeypatch.syspath_prepend(str(tmp_path))
    result = discover_sites('fixture_sites')
    assert result['sources'] == {'adapters': 0, 'integrations': 2}
    assert {site['id'] for site in result['sites']} == {'rousi', 'sunnypt'}
    assert result['skipped'] == [{'module': 'fixture_sites.native.broken', 'error': 'RuntimeError'}]


def test_domain_lookup_uses_native_and_integration_registry_matchers():
    assert site_id_for_domain('https://hdsky.me/index.php') == 'hdsky'
    assert site_id_for_domain('rousi.pro') == 'rousi'
    assert site_id_for_domain('https://sunnypt.top/user/attendance') == 'sunnypt'
    assert site_id_for_domain('unknown.invalid') is None


def test_history_persistence_pagination_retention():
    now = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
    data = {}
    store = HistoryStore(data.get, lambda key, value: data.update({key:value}), clock=lambda:now)
    for days, status in ((15,'success'),(14,'success'),(1,'failed'),(0,'success'),(0,'signed'),(0,'unconfirmed')):
        store.append({'time': (now-timedelta(days=days)).isoformat(), 'site':'fixture', 'status':status})
    assert store.list()['total'] == 5
    assert len(store.list(page=2,size=2)['items']) == 2
    assert store.list(page=99)['items'] == []
    # success→signed、signed(旧 already)→signed、unconfirmed→pending：统一三卡口径
    assert store.today_counts() == dict(signed=2, failed=0, pending=1)
    store.append(SignResult(SignStatus.ALREADY, site_id='fixture', evidence=Evidence(uid='12',status='signed')))
    record = store.list()['items'][0]
    assert set(record) == {'time','site','status','reason','message','reward','evidence','trigger','action'}
    assert data[store.KEY][-1]['evidence']['record_status'] == 'signed'
    reloaded = HistoryStore(data.get, clock=lambda:now+timedelta(days=91))
    assert reloaded.list()['total'] == 0
    assert data[store.KEY]  # read without save_data must not mutate source


def test_real_api_contract(monkeypatch):
    module = importlib.import_module('autoptcheckin')
    monkeypatch.setattr(module, 'get_registry', lambda *args, **kwargs: {'sites':[{'id':'fixture'}], 'sources':{'adapters':1,'integrations':0}})
    plugin = AutoPtCheckin()
    assert asyncio.run(plugin.api_sites())['data']['sites'] == [
        {'id': 'fixture', 'cf': 'unknown', 'proxy': False, 'emulate': False,
         'cloudsign_capable': False, 'cloudsign_selected': False, 'shield': None}]
    assert any(route['path'] == '/sites' and route['auth'] == 'bear' for route in plugin.get_api())
    assert asyncio.run(plugin.api_history())['data'] == {'total':0,'items':[]}
    plugin._history.append(SignResult(SignStatus.UNCONFIRMED, site_id='fixture'))
    assert asyncio.run(plugin.api_history(size=1))['data']['total'] == 1
    assert asyncio.run(plugin.api_status())['data']['today']['pending'] == 1


def test_registry_uses_managed_name_and_cached_icon(monkeypatch):
    from autoptcheckin.core import registry
    original = {'sites':[{'id':'sample','name':'Adapter','source':'插件适配'}, {'id':'other','name':'Other'}]}
    monkeypatch.setattr(registry, '_discovery', lambda: original)
    monkeypatch.setattr(registry, '_MATCHERS', {'sample':lambda url: url == 'https://sample.invalid/'})
    monkeypatch.setattr(registry, 'managed_sites', lambda: [{'url':'https://sample.invalid/','name':'Managed','icon':'data:image/png;base64,AA=='}])
    sites = registry.get_registry()['sites']
    assert sites[0]['name'] == 'Managed' and sites[0]['source'] == 'MP 站点'
    assert sites[0]['icon'].startswith('data:image/')
    assert sites[1]['name'] == 'Other' and sites[1]['icon'] == ''
    assert original['sites'][0]['name'] == 'Adapter'
