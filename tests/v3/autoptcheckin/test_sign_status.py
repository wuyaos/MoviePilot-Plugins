"""Pre-action transport/protocol outcomes never become failed sign-in counts."""
from unittest.mock import Mock

import pytest

from autoptcheckin.core.api_signin import ApiSignin
from autoptcheckin.core.custom import CustomNexusSignin
from autoptcheckin.core.get_signin import GetSignin
from autoptcheckin.core.history import HistoryStore
from autoptcheckin.core.models import LoginPage, SignResult, SignStatus
from autoptcheckin.core.nexus import NexusSignin
from autoptcheckin.core.sitemodel import RecordSpec
from test_get_signin_c2 import context

URL = 'https://fixture.invalid/attendance.php'


def site(kind):
    obj = CustomNexusSignin('fixture', {'url': 'https://fixture.invalid/'}) if kind is CustomNexusSignin else kind()
    obj.id, obj.url = 'fixture', 'https://fixture.invalid/'
    obj.action_path = '/action'
    obj.record_spec = RecordSpec('//h2', {'已签到': 'signed'})
    return obj


@pytest.mark.parametrize('kind', [NexusSignin, GetSignin, ApiSignin, CustomNexusSignin])
@pytest.mark.parametrize('value', [None, LoginPage('error', URL, 500), LoginPage('', URL), TimeoutError('private details')])
def test_signin_unavailable_pre_read_is_network_error(kind, value):
    obj, http = site(kind), Mock()
    http.get.side_effect = [value]
    result = obj.signin(context(obj, http))
    assert result.status == SignStatus.NETWORK_ERROR
    assert '签到页面不可达' in result.message
    assert 'private details' not in result.message
    assert http.get.call_count == 1
    http.post.assert_not_called()


@pytest.mark.parametrize('kind', [NexusSignin, ApiSignin, CustomNexusSignin])
@pytest.mark.parametrize('mode', ['missing_form', 'captcha', 'parse_error'])
def test_signin_unadapted_protocol_never_submits(kind, mode):
    obj, http = site(kind), Mock()
    http.get.return_value = LoginPage('<h2>unknown</h2>', URL)
    if mode == 'missing_form':
        obj.discover_form = Mock(return_value=None)
    elif mode == 'captcha':
        obj.discover_form = Mock(return_value=Mock())
        obj.solve_captcha = Mock(return_value=False)
    else:
        obj.discover_form = Mock(side_effect=ValueError('private details'))
    result = obj.signin(context(obj, http))
    assert result.status == SignStatus.PROTOCOL_PENDING
    assert 'private details' not in result.message
    assert http.get.call_count == 1
    http.post.assert_not_called()


def test_history_keeps_new_states_outside_four_counters():
    store = HistoryStore()
    for status in (SignStatus.MAINTENANCE, SignStatus.NETWORK_ERROR, SignStatus.PROTOCOL_PENDING):
        store.append(SignResult(status, site_id='fixture'))
    assert {item['status'] for item in store.list()['items']} == {'pending'}
    assert {item['reason'] for item in store.list()['items']} == {'maintenance', 'network_error', 'protocol_pending'}
    assert store.today_counts() == dict(signed=0, failed=0, pending=3)


@pytest.mark.parametrize('value', [None, LoginPage('error', URL, 500), TimeoutError()])
def test_native_read_only_network_error_is_recorded_once(monkeypatch, value):
    from contextlib import nullcontext
    from threading import Event
    from types import SimpleNamespace
    from autoptcheckin.core import native
    monkeypatch.setattr(native, 'cookiecloud_candidate', lambda url: SimpleNamespace(credential=None))
    obj, http = site(NexusSignin), Mock()
    http.get.side_effect = [value]
    runner = SimpleNamespace(locks=SimpleNamespace(acquire=lambda key: nullcontext(True)),
                             stop=Event(), history=Mock(), notify=None)
    result = native.run_native(runner, obj, {'url': obj.url, 'cookie': 'synthetic'},
                               read_only=True, context_factory=lambda *args: context(obj, http))
    assert result.status == SignStatus.NETWORK_ERROR
    runner.history.assert_called_once_with(result)
    assert http.get.call_count == 1
    http.post.assert_not_called()
