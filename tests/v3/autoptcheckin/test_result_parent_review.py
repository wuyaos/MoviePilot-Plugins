"""父代理独立构造：配置重算与重复归一不得擦掉执行结论。"""
from copy import deepcopy

import pytest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
from autoptcheckin import AutoPtCheckin
from autoptcheckin.core.state_store import TrackStateStore


@pytest.mark.parametrize('reason', ['network_error', 'maintenance', 'protocol_pending', 'result_unknown'])
def test_reconfigure_keeps_pending_result_until_new_execution(reason):
    store = TrackStateStore()
    store.apply_result('fixture', 'sign', 'pending', reason=reason,
                       message='保留原诊断', metadata={'page_action': 'probe'})
    before = store.entry_of('fixture', 'sign')
    store.reconfigure({'fixture': {'sign': ('pending', None)}})
    assert store.entry_of('fixture', 'sign') == before
    assert store.due_sites('sign') == ['fixture']
    store.reconfigure({'fixture': {'sign': ('disabled', 'signin_not_selected')}})
    assert store.entry_of('fixture', 'sign')['reason'] == 'signin_not_selected'


@pytest.mark.parametrize('raw', ['success', 'already', 'auth_failed', 'unconfirmed', 'network_error'])
def test_payload_unification_is_idempotent_including_reason(raw):
    first = AutoPtCheckin._unify_payload({'status': raw, 'message': '诊断', 'metadata': {}})
    assert AutoPtCheckin._unify_payload(deepcopy(first)) == first
