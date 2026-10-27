"""执行结果统一契约：适配器原始值只在执行/记录边界归一，历史旧值兼容读取。

统一 status：signed/login_ok/failed/pending/skipped/cancelled。
reason 精确值：already_signed/result_unknown/network_error/maintenance/protocol_pending/auth_failed。
全部离线，不请求站点。
"""
import asyncio
import importlib
import sys
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
import autoptcheckin as entry
from autoptcheckin import AutoPtCheckin
from autoptcheckin.core.models import LoginPage, SignResult, SignStatus, unify_result
from autoptcheckin.core.state_store import DISABLED, FAILED, PENDING, SUCCESS, TrackStateStore

custom_module = importlib.import_module('autoptcheckin.core.custom')

FORM = '<form method="post" action="attendance.php"><input name="csrf" value="fixture"><button>签到</button></form>'
SIGNED = '<h1>今天已经签到</h1>'
SUCCESS_PAGE = '<h1>签到成功，获得 87 爆米花</h1>'
URL = 'https://custom.invalid/attendance.php'


@pytest.fixture
def probe(monkeypatch):
    """与 test_custom_verify 同构的 custom 端到端夹具；pages 为回放序列。"""
    calls = []
    pages = [LoginPage('<main>account home</main>', 'https://custom.invalid/')]

    class Http:
        def __init__(self, credential, info):
            assert credential.value == 'synthetic-cookie'

        def get(self, url):
            calls.append(('GET', url))
            page = pages.pop(0) if pages else pages
            if isinstance(page, Exception):
                raise page
            return LoginPage(page, url) if isinstance(page, str) else page

        def post(self, url, **kwargs):
            # custom 流程以提交后的回读为准，POST 响应本身不作为结论
            calls.append(('POST', url))
            return LoginPage(SUCCESS_PAGE, url)

    monkeypatch.setattr(custom_module, 'NativeHttpClient', Http)
    plugin = AutoPtCheckin()
    plugin.init_plugin({'custom_sites_data': [{'id': 'custom-60005', 'name': 'Fixture',
                        'url': 'https://custom.invalid/', 'cookie': 'synthetic-cookie'}],
                        'enabled_sites': ['custom-60005'], 'sign_sites': ['custom-60005']})
    return plugin, calls, pages


# ---- unify_result 纯映射 ----

@pytest.mark.parametrize('raw,reason,expected', [
    ('success', None, ('signed', '')),
    ('already', None, ('signed', 'already_signed')),
    ('signed', None, ('signed', '')),  # unify 本身不解释旧 signed；already 解释在旧读边界
    ('login_ok', None, ('login_ok', '')),
    ('failed', None, ('failed', '')),
    ('auth_failed', None, ('failed', 'auth_failed')),
    ('unconfirmed', None, ('pending', 'result_unknown')),
    ('network_error', None, ('pending', 'network_error')),
    ('maintenance', None, ('pending', 'maintenance')),
    ('protocol_pending', None, ('pending', 'protocol_pending')),
    ('skipped', 'signin_not_selected', ('skipped', 'signin_not_selected')),
    ('skipped', None, ('skipped', '')),  # 锁忙
    ('cancelled', None, ('cancelled', '')),
])
def test_unify_result_mapping(raw, reason, expected):
    assert unify_result(raw, reason) == expected


def test_unify_success_represents_this_time():
    """success 归 signed 不带 reason（代表本次成功）；原细分 reason 只留在 metadata。"""
    assert unify_result('success', 'some_detail') == ('signed', '')


def test_unify_enum_and_passthrough():
    assert unify_result(SignStatus.ALREADY) == ('signed', 'already_signed')


def test_unify_idempotent_new_signed_never_becomes_already():
    """幂等反例：新归一 signed（本次成功）二次归一不得漂移为 already_signed；
    legacy signed 的 already 解释只发生在旧读边界（version==1 状态表 / 旧 history）。"""
    once = unify_result('success')
    assert once == ('signed', '')
    assert unify_result(*once) == once
    assert unify_result('signed', '') == ('signed', '')
    assert unify_result('signed', 'already_signed') == ('signed', 'already_signed')


def test_unify_unknown_status_becomes_pending():
    """未知 status 按新契约归 pending（六值封闭），不透传出统一集之外。"""
    assert unify_result('something_new', '') == ('pending', 'result_unknown')


def test_unify_payload_keeps_raw_status_metadata():
    """未知 status 归 pending 时，原始值保留在 metadata.raw_status 供排障。"""
    payload = {"status": "something_new", "message": "未知值", "metadata": {}}
    result = AutoPtCheckin._unify_payload(payload)
    assert result['status'] == 'pending' and result['reason'] == 'result_unknown'
    assert result['metadata']['raw_status'] == 'something_new'


def test_track_state_v1_legacy_signed_is_already_v2_is_this_time():
    """version==1 旧表：status=signed（旧 already）→ already_signed；
    version==2 新表：status=signed 无 reason = 本次成功，compat 不得再解释。"""
    legacy = {'track.state': {'version': 1, 'day': '', 'updated': '', 'sites': {
        'a': {'sign': {'state': 'success', 'status': 'signed', 'message': '', 'time': '2026-01-01T00:00:00'}}}}}
    modern = {'track.state': {'version': 2, 'day': '', 'updated': '', 'sites': {
        'b': {'sign': {'state': 'success', 'status': 'signed', 'message': '', 'time': '2026-01-01T00:00:00'}}}}}
    old_store = TrackStateStore(lambda key: legacy.get(key), lambda key, value: None)
    assert old_store.entry_of('a', 'sign')['reason'] == 'already_signed'
    new_store = TrackStateStore(lambda key: modern.get(key), lambda key, value: None)
    assert new_store.entry_of('b', 'sign').get('reason') in (None, '')


# ---- 端到端：执行 → 记录 → API 载荷 ----

def test_end_to_end_success_becomes_signed_and_keeps_message(probe):
    plugin, calls, pages = probe
    pages[:] = [FORM, SUCCESS_PAGE]
    result = plugin._execute_site('custom-60005')
    assert result['status'] == 'signed'
    assert not result.get('reason')
    assert '签到成功' in result['message']
    record = plugin._history.list(1, 5)['items'][0]
    assert record['status'] == 'signed' and record['message'] == result['message']
    assert plugin._track_store().state_of('custom-60005', 'sign') == SUCCESS


def test_end_to_end_already_becomes_signed_with_reason(probe):
    plugin, calls, pages = probe
    pages[:] = [SIGNED]
    result = plugin._execute_site('custom-60005')
    assert result['status'] == 'signed'
    assert result['reason'] == 'already_signed'
    record = plugin._history.list(1, 5)['items'][0]
    assert record['status'] == 'signed' and record['reason'] == 'already_signed'
    assert plugin._track_store().state_of('custom-60005', 'sign') == SUCCESS


@pytest.mark.parametrize('raw,reason', [
    ('unconfirmed', 'result_unknown'),
    ('network_error', 'network_error'),
    ('maintenance', 'maintenance'),
    ('protocol_pending', 'protocol_pending'),
])
def test_end_to_end_pending_family_keeps_exact_reason(probe, raw, reason):
    """pending 族（unconfirmed/不可达/维护/协议）统一为 pending，reason 精确值；状态表四值 pending。"""
    plugin, calls, pages = probe
    result = _fake_record(plugin, SignStatus(raw))
    assert result['status'] == 'pending'
    assert result['reason'] == reason
    record = plugin._history.list(1, 5)['items'][0]
    assert record['status'] == 'pending' and record['reason'] == reason
    assert plugin._track_store().state_of('custom-60005', 'sign') == PENDING


def test_end_to_end_auth_failed_becomes_failed(probe):
    plugin, calls, pages = probe
    result = _fake_record(plugin, SignStatus.AUTH_FAILED)
    assert result['status'] == 'failed'
    assert result['reason'] == 'auth_failed'
    record = plugin._history.list(1, 5)['items'][0]
    assert record['status'] == 'failed' and record['reason'] == 'auth_failed'
    assert plugin._track_store().state_of('custom-60005', 'sign') == FAILED


def test_raw_detail_reason_survives_in_metadata(probe):
    """归一不覆盖 metadata：原细分 reason/诊断保留在 metadata 供排障。"""
    plugin, calls, pages = probe
    result = _fake_record(plugin, SignStatus.UNCONFIRMED, metadata_reason='captcha_unsolved')
    assert result['status'] == 'pending' and result['reason'] == 'result_unknown'
    assert result['metadata']['reason'] == 'captcha_unsolved'


def _fake_record(plugin, status, metadata_reason=None):
    """直达记录边界：构造原始结果走 _record_result，再取统一载荷。"""
    result = SignResult(status, '原始消息', site_id='custom-60005')
    result.metadata.update(action='sign', trigger='manual')
    if metadata_reason:
        result.metadata['reason'] = metadata_reason
    plugin._record_result(result)
    return plugin._unify_payload(asdict(result))


# ---- 旧值兼容 ----

def test_legacy_track_state_unconfirmed_failed_treated_pending():
    """旧 track.state：failed+unconfirmed 视 pending；真正 failed（含 auth_failed）仍 failed。"""
    data = {'track.state': {'version': 1, 'day': '', 'updated': '', 'sites': {
        'a': {'sign': {'state': 'failed', 'status': 'unconfirmed', 'message': '', 'time': '2026-01-01T00:00:00'}},
        'b': {'sign': {'state': 'failed', 'status': 'auth_failed', 'message': '', 'time': '2026-01-01T00:00:00'}},
        'c': {'sign': {'state': 'failed', 'status': 'failed', 'message': '', 'time': '2026-01-01T00:00:00'}},
        'd': {'sign': {'state': 'pending', 'status': 'network_error', 'message': '', 'time': '2026-01-01T00:00:00'}},
        'e': {'sign': {'state': 'success', 'status': 'signed', 'message': '', 'time': '2026-01-01T00:00:00'}},
    }}}
    store = TrackStateStore(lambda key: data.get(key), lambda key, value: data.__setitem__(key, value))
    rows = {sid: store.entry_of(sid, 'sign') for sid in 'abcde'}
    assert (rows['a']['state'], rows['a']['reason']) == (PENDING, 'result_unknown')
    assert (rows['b']['state'], rows['b']['reason']) == (FAILED, 'auth_failed')
    assert rows['c']['state'] == FAILED and not rows['c'].get('reason')
    assert (rows['d']['state'], rows['d']['reason']) == (PENDING, 'network_error')
    assert (rows['e']['state'], rows['e']['reason']) == (SUCCESS, 'already_signed')


def test_old_history_records_read_without_rewrite():
    """历史旧原始值只兼容读取，不批量重写；rebuild 派生的轨道状态按新口径。"""
    now = datetime(2026, 10, 26, 12)
    data = {}
    store = TrackStateStore(lambda key: data.get(key), lambda key, value: data.__setitem__(key, value))
    legacy = [{'time': now.isoformat(), 'site': 'a', 'action': 'sign', 'status': 'unconfirmed', 'message': ''},
              {'time': now.isoformat(), 'site': 'b', 'action': 'sign', 'status': 'signed', 'message': ''},
              {'time': now.isoformat(), 'site': 'c', 'action': 'sign', 'status': 'network_error', 'message': ''}]
    store.rebuild_from_history(legacy)
    assert store.state_of('a', 'sign') == PENDING
    assert store.state_of('b', 'sign') == SUCCESS
    assert store.state_of('c', 'sign') == PENDING
    assert store.entry_of('a', 'sign')['status'] == 'unconfirmed'  # 旧原始值保留在表内
    assert store.entry_of('a', 'sign')['reason'] == 'result_unknown'


# ---- 队列语义 ----

def _queue_plugin(monkeypatch, ids):
    plugin = entry.AutoPtCheckin()
    plugin._state = TrackStateStore()
    plugin._state.rollover()
    plugin._config = {'enabled_sites': ids, 'sign_sites': ids[:], 'login_sites': [],
                      'retry_count': 2}
    monkeypatch.setattr(entry, 'get_registry', lambda *args, **kwargs: {'sites': [
        {'id': sid, 'signin_capable': True, 'signin_applicable': True, 'login_capable': True}
        for sid in ids]})
    return plugin


def test_pending_not_retried_immediately(monkeypatch):
    """unconfirmed→pending：本轮不即时重试。"""
    plugin = _queue_plugin(monkeypatch, ['a'])
    calls = []

    def execute(site_id, **kwargs):
        calls.append(site_id)
        result = SignResult(SignStatus.UNCONFIRMED, '结果未确认', site_id=site_id)
        result.metadata.update(action='sign', trigger='manual')
        plugin._record_result(result)
        return plugin._unify_payload(asdict(result))

    plugin._execute_site = execute
    result = plugin._run_with_retry('a', 'sign', 'manual')
    assert result['status'] == 'pending' and result['reason'] == 'result_unknown'
    assert len(calls) == 1  # pending 不即时重试


def test_real_failed_still_retried(monkeypatch):
    plugin = _queue_plugin(monkeypatch, ['a'])
    calls = []

    def execute(site_id, **kwargs):
        calls.append(site_id)
        result = SignResult(SignStatus.FAILED, '明确未签', site_id=site_id)
        result.metadata.update(action='sign', trigger='manual')
        plugin._record_result(result)
        return plugin._unify_payload(asdict(result))

    plugin._execute_site = execute
    plugin._run_with_retry('a', 'sign', 'manual')
    assert len(calls) == 3  # 1 + retry_count=2


def test_success_dedup_out_of_queue(monkeypatch):
    plugin = _queue_plugin(monkeypatch, ['a', 'b'])
    store = plugin._track_store()
    store.apply_result('a', 'sign', 'signed')
    store.apply_result('b', 'sign', 'failed')
    assert plugin._due_for('sign') == ['b']


def test_cancel_and_busy_do_not_overwrite_conclusion(monkeypatch):
    """锁忙/取消只写历史，不覆盖已有结论（含 pending/result_unknown）。"""
    plugin = _queue_plugin(monkeypatch, ['a', 'b'])
    store = plugin._track_store()
    store.apply_result('a', 'sign', 'failed')
    store.apply_result('b', 'sign', 'unconfirmed')
    for sid, status in (('a', SignStatus.CANCELLED), ('b', SignStatus.SKIPPED)):
        result = SignResult(status, '空转', site_id=sid)
        result.metadata.update(action='sign', trigger='manual')
        plugin._record_result(result)
    assert store.state_of('a', 'sign') == FAILED
    assert (store.state_of('b', 'sign'), store.entry_of('b', 'sign')['reason']) == (PENDING, 'result_unknown')
    statuses = [item['status'] for item in plugin._history.list(1, 10)['items']]
    assert 'cancelled' in statuses and 'skipped' in statuses


def test_gate_skip_writes_disabled(monkeypatch):
    plugin = _queue_plugin(monkeypatch, ['a'])
    result = SignResult(SignStatus.SKIPPED, '未勾选', site_id='a')
    result.metadata.update(action='sign', trigger='manual', reason='signin_not_selected')
    plugin._record_result(result)
    payload = plugin._unify_payload(asdict(result))
    assert payload['status'] == 'skipped' and payload['reason'] == 'signin_not_selected'
    assert plugin._track_store().state_of('a', 'sign') == DISABLED


# ---- 统计口径（三卡） ----

def test_stats_three_cards_scope(monkeypatch):
    """成功/失败=启用勾选轨道的今日结论；待处理=有效队列 pending（含未执行）。"""
    plugin = _queue_plugin(monkeypatch, ['ok', 'bad', 'unknown', 'fresh', 'yesterday', 'off'])
    store = plugin._track_store()
    today = datetime.now().isoformat()
    yesterday = (datetime.now() - timedelta(days=1)).isoformat()
    store.apply_result('ok', 'sign', 'signed', time=today)
    store.apply_result('bad', 'sign', 'failed', time=today)
    store.apply_result('unknown', 'sign', 'unconfirmed', time=today)
    store.apply_result('yesterday', 'sign', 'failed', time=yesterday)
    plugin._config['sign_sites'].remove('off')
    plugin._recompute_track_states()
    data = asyncio.run(plugin.api_stats())['data']['latest']['sign']
    # unknown(结果待确认)+fresh(未执行) 计待处理；昨日失败不是今日结论也不算今日待处理；
    # off 已取消勾选：不进任何一卡。
    assert data == {'success': 1, 'failed': 1, 'pending': 2}


def test_stats_rows_carry_reason_for_display(monkeypatch):
    plugin = _queue_plugin(monkeypatch, ['a'])
    plugin._track_store().apply_result('a', 'sign', 'network_error')
    row = next(r for r in plugin._site_rows() if r['id'] == 'a')
    assert row['sign_state'] == PENDING
    assert row['sign_status'] == 'pending' and row['sign_reason'] == 'network_error'
