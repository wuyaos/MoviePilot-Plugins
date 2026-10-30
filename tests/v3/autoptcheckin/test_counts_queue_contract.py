"""统计/队列契约反例；全部离线，不请求站点。"""
from datetime import datetime, timedelta

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
import autoptcheckin as entry
from autoptcheckin.core.notify import _counts
from autoptcheckin.core.state_store import TrackStateStore


def test_next_count_never_inferred_from_failure_details():
    # 旧轮66条非成功明细不能覆盖真实的3个待执行站点。
    entries = [(str(i), {'status': 'failed'}) for i in range(66)]
    assert _counts({'total': 66, 'executed': 3, 'next': 3}, entries)[3] == 3
    assert _counts({'total': 66, 'executed': 0, 'next': 0}, entries)[3] == 0


def test_pending_without_result_is_still_next_not_failure():
    assert _counts({'total': 11, 'executed': 0, 'next': 11}, []) == (11, 0, 0, 11)


def _plugin(monkeypatch, ids):
    plugin = entry.AutoPtCheckin()
    plugin._state = TrackStateStore()
    plugin._state.rollover()
    plugin._config = {'enabled_sites': ids, 'sign_sites': ids[:], 'login_sites': []}
    monkeypatch.setattr(entry, 'get_registry', lambda *args, **kwargs: {'sites': [
        {'id': sid, 'signin_capable': True, 'signin_applicable': True, 'login_capable': True}
        for sid in ids]})
    plugin._registry = lambda: entry.get_registry(
        plugin._config.get('custom_sites_data', []),
        sign_sites=plugin._config.get('sign_sites', []),
    )
    return plugin


def test_63_legacy_gate_skips_are_requeued_not_lost(monkeypatch):
    ids = [str(i) for i in range(66)]
    plugin = _plugin(monkeypatch, ids)
    store = plugin._track_store()
    for sid in ids[:63]:
        store.apply_result(sid, 'sign', 'skipped', reason='native_unverified')
    for sid in ids[63:]:
        store.apply_result(sid, 'sign', 'failed')
    assert len(plugin._due_for('sign')) == 3
    plugin._recompute_track_states()
    assert set(plugin._due_for('sign')) == set(ids)
    store.apply_result(ids[-1], 'sign', 'success')
    assert len(plugin._due_for('sign')) == 65


def test_selection_busy_cancel_and_success_define_actual_queue(monkeypatch):
    plugin = _plugin(monkeypatch, ['pending', 'failed', 'done', 'off'])
    store = plugin._track_store()
    plugin._recompute_track_states()
    store.apply_result('pending', 'sign', 'network_error')
    store.apply_result('failed', 'sign', 'failed')
    store.apply_result('done', 'sign', 'success')
    store.apply_result('off', 'sign', 'failed')
    plugin._config['sign_sites'].remove('off')
    plugin._recompute_track_states()
    store.apply_result('pending', 'sign', 'skipped')
    store.apply_result('failed', 'sign', 'cancelled')
    store.apply_result('done', 'sign', 'skipped')
    assert plugin._due_for('sign') == ['pending', 'failed']


def test_new_day_requeues_success_but_not_unselected(monkeypatch):
    plugin = _plugin(monkeypatch, ['done', 'off'])
    now = datetime(2026, 10, 26, 23, 59)
    store = TrackStateStore(clock=lambda: now)
    plugin._state = store
    store.rollover()
    plugin._recompute_track_states()
    for sid in ('done', 'off'):
        store.apply_result(sid, 'sign', 'success')
    plugin._config['sign_sites'] = ['done']
    assert plugin._due_for('sign') == []
    now += timedelta(minutes=2)
    store.rollover()
    plugin._recompute_track_states()
    assert plugin._due_for('sign') == ['done']


def test_round_summary_uses_immutable_result_not_later_site_status(monkeypatch):
    plugin = _plugin(monkeypatch, ['a', 'old'])
    plugin._recompute_track_states()
    store = plugin._track_store()
    store.apply_result('old', 'sign', 'failed')
    plugin._last_round_results = {('a', 'sign'): {'status': 'success', 'message': '本轮成功'}}
    # 同一站后续手动动作不可改写上一轮推送的实际结果。
    store.apply_result('a', 'sign', 'failed')
    data = plugin._round_summary()['sign']
    # 本轮计数口径是 round_entries；entries 里的旧待办只补明细。
    assert _counts(data, data['round_entries']) == (2, 1, 1, 2)
    assert [e['status'] for _, e in data['round_entries']] == ['success']
    assert len(data['entries']) == 2


def test_stats_excludes_unselected_and_previous_day_results(monkeypatch):
    import asyncio
    plugin = _plugin(monkeypatch, ['a'])
    today = datetime.now().isoformat()
    yesterday = (datetime.now() - timedelta(days=1)).isoformat()
    monkeypatch.setattr(plugin, '_site_rows', lambda: [
        {'sign_selected': False, 'sign_state': 'failed', 'sign_status': 'failed', 'sign_time': today},
        {'sign_selected': True, 'sign_state': 'failed', 'sign_status': 'failed', 'sign_time': yesterday},
        {'sign_selected': True, 'sign_state': 'pending', 'sign_status': 'unconfirmed', 'sign_time': today},
    ])
    result = asyncio.run(plugin.api_stats())['data']['latest']['sign']
    assert result == {'success': 0, 'failed': 0, 'pending': 1}


def test_disabled_capability_excludes_retained_failure_from_queue(monkeypatch):
    plugin = _plugin(monkeypatch, ['a', 'b'])
    for sid in ('a', 'b'):
        for track in ('sign', 'login'):
            plugin._track_store().apply_result(sid, track, 'failed')
    plugin._config['login_sites'] = ['a', 'b']
    monkeypatch.setattr(entry, 'get_registry', lambda *args, **kwargs: {'sites': [
        {'id': 'a', 'signin_capable': False, 'signin_applicable': False, 'login_capable': False},
        {'id': 'b', 'signin_capable': True, 'signin_applicable': True, 'login_capable': True},
    ]})
    plugin._recompute_track_states()
    assert plugin._track_store().state_of('a', 'sign') == 'failed'
    assert plugin._due_for('sign') == ['b']
    assert plugin._due_for('login') == ['b']
    summary = plugin._round_summary()
    assert summary['sign']['next'] == summary['login']['next'] == 1


def test_rendered_notification_does_not_count_old_pending_as_current(monkeypatch):
    from autoptcheckin.core.notify import format_round_notifications
    plugin = _plugin(monkeypatch, ['done', 'old'])
    plugin._recompute_track_states()
    plugin._track_store().apply_result('done', 'sign', 'success')
    plugin._track_store().apply_result('old', 'sign', 'network_error', message='旧轮超时')
    plugin._last_round_results = {('done', 'sign'): {'status': 'success'}}
    summary = plugin._round_summary()
    text = format_round_notifications(summary)[0][2]
    assert text.splitlines()[:3] == ['全部签到: 2',
                                     '本次签到: 1（成功 1 · 失败 0 · 待处理 0）',
                                     '下轮待执行: 1']
    assert '旧轮超时' in text
    # 第二轮无实际结果时，旧待办仍可用于测试推送，但不能冒充本轮执行；计数为 0 仍显示头部。
    plugin._last_round_results = {}
    text = format_round_notifications(plugin._round_summary())[0][2]
    assert text.splitlines()[:3] == ['全部签到: 2',
                                     '本次签到: 0（成功 0 · 失败 0 · 待处理 0）',
                                     '下轮待执行: 1']


def test_paused_site_is_excluded_from_due_summary_and_stats(monkeypatch):
    import asyncio
    plugin = _plugin(monkeypatch, ['a', 'b'])
    plugin._config['paused_sites'] = ['a']
    plugin._recompute_track_states()
    assert plugin._due_for('sign') == ['b']
    summary = plugin._round_summary()['sign']
    assert summary['total'] == 1 and summary['next'] == 1
    rows = {row['id']: row for row in plugin._site_rows()}
    assert rows['a']['site_paused'] is True and rows['b']['site_paused'] is False
    result = asyncio.run(plugin.api_stats())['data']['latest']['sign']
    assert result == {'success': 0, 'failed': 0, 'pending': 1}
    assert plugin._track_store().entry_of('a', 'sign') == {}


def test_paused_site_leftover_round_detail_drops_from_notification(monkeypatch):
    # 本轮跑过之后才暂停：_last_round_results 会残留一整天，通知不得再列该站明细。
    from autoptcheckin.core.notify import format_round_notifications
    plugin = _plugin(monkeypatch, ['a', 'b'])
    plugin._recompute_track_states()
    plugin._last_round_results = {
        ('a', 'sign'): {'status': 'failed', 'message': 'A站点维护中，本轮跳过'},
        ('b', 'sign'): {'status': 'failed', 'message': 'B本轮失败'},
    }
    summary = plugin._round_summary()['sign']
    assert sorted(label for label, _ in summary['entries']) == ['a', 'b']
    assert 'A站点维护中' in format_round_notifications(plugin._round_summary())[0][2]

    plugin._config['paused_sites'] = ['a']
    summary = plugin._round_summary()['sign']
    assert [label for label, _ in summary['entries']] == ['b']
    assert [result['status'] for _, result in summary['round_entries']] == ['failed']
    text = format_round_notifications(plugin._round_summary())[0][2]
    assert text.splitlines()[:3] == ['全部签到: 1',
                                     '本次签到: 1（成功 0 · 失败 1 · 待处理 0）',
                                     '下轮待执行: 1']
    assert 'B本轮失败' in text and 'A站点维护中' not in text

def test_paused_single_site_apis_refuse_without_state_or_history(monkeypatch):
    import asyncio
    plugin = _plugin(monkeypatch, ['a'])
    plugin._config['paused_sites'] = ['a']
    plugin._execute_site = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('must not execute'))
    before = plugin._track_store().snapshot()
    signin = asyncio.run(plugin.api_signin_by_domain(domain='a'))
    login = asyncio.run(plugin.api_login_by_domain(domain='a'))
    assert signin == login == {'success': False, 'message': '站点已暂停执行', 'data': None}
    assert plugin._track_store().snapshot() == before
    assert plugin._history.list(1, 100)['items'] == []
