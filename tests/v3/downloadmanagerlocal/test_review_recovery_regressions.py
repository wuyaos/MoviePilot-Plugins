"""Offline counterexamples for S1: stop occurs inside external IO, before state save."""
import copy
import importlib.util
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('dml_upload_tests', ROOT / 'tests/v3/downloadmanagerlocal/test_upload_limit_rows_and_history.py')
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)
svc = base.svc


def durable_storage(plugin, initial):
    plugin._data['upload_limit_state'] = copy.deepcopy(initial)
    real = plugin.save_data
    def save(key, value):
        real(key, copy.deepcopy(value))
    plugin.save_data = save
    plugin._upload_limit_stop_event = threading.Event()


def test_global_success_then_stop_must_keep_restore_record(svc, monkeypatch):
    state = base._empty_state()
    plugin = base.FakePlugin(state=copy.deepcopy(state))
    durable_storage(plugin, state)
    qb = base.FakeQb()
    plugin.add_downloader('QB1', qb)
    real_write = svc.service.write_global_upload_limit
    def write_then_stop(*args, **kwargs):
        result = real_write(*args, **kwargs)
        plugin._upload_limit_stop_event.set()
        return result
    monkeypatch.setattr(svc.service, 'write_global_upload_limit', write_then_stop)
    result = svc.service.run_upload_limit_cycle(plugin, now=1000)
    assert result['service_status'] == 'stopped'
    assert qb.transfer.upload_limit == 100 * 1024
    persisted = plugin._data['upload_limit_state']
    assert persisted['downloaders'].get('QB1', {}).get('last_written_global'), 'External write succeeded, but restart loses its restore record'


def test_torrent_success_then_stop_must_keep_restore_record(svc, monkeypatch):
    state = base._empty_state()
    state.update(management_active=True, cycle=1, last_run_at=1000)
    state['downloaders'] = {'QB1': base._seed_downloader()}
    key = 'QB1:aaa111'
    state['torrents'] = {key: {
        'downloader_id': 'QB1', 'downloader_type': 'qbittorrent', 'torrent_hash': 'aaa111',
        'site_key': 'site-a', 'grace_until': 0,
        'original_settings': {'limit_bps': 0, 'enabled': False},
        'upload_rate_bps': 5120, 'upload_demand_peers': 1, 'last_seen_at': 1000,
    }}
    plugin = base.FakePlugin(state=copy.deepcopy(state))
    durable_storage(plugin, state)
    plugin._upload_limit_site_rules = {'site-a': {'limit_kib': 100}}
    qb = base.FakeQb(upload_limit_bps=100*1024, alt_up_limit=100*1024,
        torrents=[base._qb_torrent('aaa111', tags='🏠site-a', up_limit=0, upspeed=5120, num_leechs=1)])
    plugin.add_downloader('QB1', qb)
    real_write = svc.service.write_torrent_upload_limit
    def write_then_stop(*args, **kwargs):
        result = real_write(*args, **kwargs)
        plugin._upload_limit_stop_event.set()
        return result
    monkeypatch.setattr(svc.service, 'write_torrent_upload_limit', write_then_stop)
    result = svc.service.run_upload_limit_cycle(plugin, now=2000)
    assert result['service_status'] == 'stopped'
    assert len(qb.torrent_limit_calls) == 1
    persisted = plugin._data['upload_limit_state']
    assert persisted['torrents'][key].get('last_written_settings'), 'External write succeeded, but restart loses last_written_settings'


def test_qb_partial_restore_retry_must_restore_alt_limit(svc, monkeypatch):
    state = base._empty_state()
    state['downloaders'] = {'QB1': base._seed_downloader()}
    qb = base.FakeQb(upload_limit_bps=100*1024, alt_up_limit=100*1024)
    plugin = base.FakePlugin(state=state)
    plugin.add_downloader('QB1', qb)
    real_prefs = qb.app_set_preferences
    calls = []
    def fail_once(prefs):
        calls.append(prefs)
        if len(calls) == 1:
            raise RuntimeError('injected alt restore failure')
        return real_prefs(prefs)
    monkeypatch.setattr(qb, 'app_set_preferences', fail_once)
    first = svc.service._restore_one_downloader(plugin, state, 'QB1')
    assert first['errors']
    assert qb.transfer.upload_limit == 0
    second = svc.service._restore_one_downloader(plugin, state, 'QB1')
    assert not second['errors']
    assert qb._prefs['alt_up_limit'] == 0, 'Retry discarded its ledger with plugin alt limit still active'


def test_tr_rpc_dict_metainfo_must_be_exported(svc, monkeypatch):
    import base64
    from types import SimpleNamespace
    export = base._load(monkeypatch, 'modules/transfer/payload_export.py', base.PREFIX + '.modules.transfer.payload_export')
    expected = b'd4:infod4:name1:xee'
    monkeypatch.setattr(export, '_tr_rpc', lambda *a, **kw: {'torrents': [{'torrent': base64.b64encode(expected).decode(), 'torrentFile': '/remote/file.torrent'}]})
    monkeypatch.setattr(export, '_read_bytes', lambda *a: None)
    service = SimpleNamespace(config=SimpleNamespace(config={'host': 'http://offline.invalid'}))
    assert export._tr_export(object(), 'aaa111', service=service) == expected

def test_qb_export_reuses_authenticated_client(svc, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock
    export = base._load(monkeypatch, 'modules/transfer/payload_export.py', base.PREFIX + '.modules.transfer.payload_export')
    client = SimpleNamespace(torrents_export=Mock(return_value=b'torrent-bytes'))
    assert export._qb_export(SimpleNamespace(qbc=client), 'aaa111') == b'torrent-bytes'
    client.torrents_export.assert_called_once_with(torrent_hash='aaa111')

def test_qb_restore_keeps_manual_normal_limit_but_restores_alt(svc):
    state = base._empty_state()
    state['downloaders'] = {'QB1': base._seed_downloader()}
    qb = base.FakeQb(upload_limit_bps=222*1024, alt_up_limit=100*1024)
    plugin = base.FakePlugin(state=state)
    plugin.add_downloader('QB1', qb)
    result = svc.service._restore_one_downloader(plugin, state, 'QB1')
    assert not result['errors']
    assert result['preserved_manual'] == 1
    assert qb.transfer.upload_limit == 222*1024
    assert qb._prefs['alt_up_limit'] == 0


@base.pytest.mark.parametrize('stop_during_failure', [False, True])
def test_qb_partial_takeover_is_durable_and_restorable_after_restart(svc, monkeypatch, stop_during_failure):
    """第二个接管 RPC 失败（可同时停止）时，第一步写入的恢复证据已落盘。"""
    state = base._empty_state()
    plugin = base.FakePlugin(state=copy.deepcopy(state))
    durable_storage(plugin, state)
    qb = base.FakeQb(upload_limit_bps=0, alt_up_limit=0)
    plugin.add_downloader('QB1', qb)
    real_prefs = qb.app_set_preferences
    snapshots = []

    def fail_second_step(prefs):
        snapshots.append(copy.deepcopy(plugin._data['upload_limit_state']))
        if stop_during_failure:
            plugin._upload_limit_stop_event.set()
        raise RuntimeError('injected alternate takeover failure')

    monkeypatch.setattr(qb, 'app_set_preferences', fail_second_step)
    svc.service.run_upload_limit_cycle(plugin, now=1000)
    assert qb.transfer.upload_limit == 100 * 1024
    assert qb._prefs['alt_up_limit'] == 0
    # 在第二个 RPC 内就已经可从持久化存储读到第一步成功记录，而非等轮次末。
    partial = snapshots[0]['downloaders']['QB1']
    assert partial['original_global']['upload_limit_bps'] == 0
    assert partial['last_written_global']['upload_limit_bps'] == 100 * 1024
    assert partial['last_written_global']['alternate_upload_limit_bps'] == 0

    persisted = copy.deepcopy(plugin._data['upload_limit_state'])
    restarted = base.FakePlugin(state=persisted)
    restarted.add_downloader('QB1', qb)
    monkeypatch.setattr(qb, 'app_set_preferences', real_prefs)
    report = svc.service._restore_one_downloader(restarted, persisted, 'QB1')
    assert not report['errors']
    assert report['global_restored'] is True
    assert report['preserved_manual'] == 0
    assert qb.transfer.upload_limit == 0
    assert qb._prefs['alt_up_limit'] == 0
    assert 'QB1' not in persisted['downloaders']
