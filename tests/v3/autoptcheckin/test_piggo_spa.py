"""猪猪纯 HTTP 回归，全部合成账号与响应，禁止真实外网。"""
import copy
import hashlib
import json
import sys
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
from autoptcheckin import AutoPtCheckin
from autoptcheckin.core import native, registry
from autoptcheckin.core.models import LoginResult, LoginStatus, SignResult, SignStatus
from autoptcheckin.core.runner import SignRunner
from autoptcheckin.integrations import piggo as flow
from autoptcheckin.integrations import piggo_srp as srp
from autoptcheckin.sites.native import piggo

DATE = '2026-11-01'
CONFIG = {'piggo_username': 'fixture-user', 'piggo_password': 'fixture-password'}


def calendar(status='today', date=DATE):
    return {'selected': date, 'cells': [{'ymd': date, 'is_today': True, 'checked': status == 'checked'}],
            'detail': {'ymd': date, 'attendance': {'status': status}}}


@pytest.mark.parametrize('status', ['today', 'checked'])
def test_today_calendar_accepts_exact_evidence(status):
    assert piggo.calendar_today(calendar(status)) == {'date': DATE, 'status': status}


@pytest.mark.parametrize('change', [
    lambda p: p.update(selected='2026-10-31'),
    lambda p: p['detail'].update(ymd='2026-10-31'),
    lambda p: p['detail']['attendance'].update(status='makeup'),
    lambda p: p['cells'][0].update(is_today=False),
    lambda p: p['cells'][0].update(checked=True),
    lambda p: p['cells'].append(copy.deepcopy(p['cells'][0])),
    lambda p: p.update(cells=None), lambda p: p.update(detail=None),
])
def test_malformed_or_makeup_calendar_is_not_today(change):
    payload = calendar()
    change(payload)
    assert piggo.calendar_today(payload) is None


@pytest.fixture
def server(monkeypatch, tmp_path):
    from curl_cffi.requests import Cookies
    state = SimpleNamespace(path=tmp_path / 'http' / 'piggo.json', requests=[], sessions=[],
                            checked=False, rejected=False, post_error=False, errors={}, malformed=False,
                            callbacks=[], before_post=None)
    class Session:
        def __init__(self):
            self.cookies = Cookies()
            self.closed = False
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.closed = True
        def request(self, method, url, **kwargs):
            target = urlsplit(url)
            assert target.scheme == 'https' and target.netloc == 'piggo.me'
            assert kwargs['allow_redirects'] is False and kwargs['timeout'] == 25
            path = target.path.removeprefix(flow.BASE)
            state.requests.append((method, path, kwargs))
            if path in state.errors and state.errors[path]:
                value = state.errors[path].pop(0)
                if isinstance(value, Exception):
                    raise value
                return value
            if path == '/auth/guest-config':
                data = {'srp': True}
            elif path == '/auth/srp/challenge':
                assert kwargs['json'] == {'username': kwargs['json']['username']}
                data = {'s': 'ab', 'B': 'cd', 'ticket': 'fixture-ticket'}
            elif path == '/auth/srp/login':
                assert 'password' not in kwargs['json']
                self.cookies.set('pigo_np_web_session', 'fixture-cookie', domain='piggo.me', path='/')
                data = {'token': 'fixture-token', 'm2': 'fixture-m2', 'sign': 'a' * 64}
            elif path == '/auth/sign':
                assert kwargs['headers']['Authorization'] == 'Bearer fixture-token'
                assert self.cookies.get('pigo_np_web_session') == 'fixture-cookie'
                data = {'sign': 'a' * 64}
            elif path in ('/calendar', '/calendar/attendance'):
                headers = kwargs['headers']
                assert headers['Authorization'] == 'Bearer fixture-token'
                expected = flow.signed_headers('a' * 64, method, target.path, headers['ts'], headers['X-Spa-Nonce'])
                assert headers['X-Spa-Hmac'] == expected['X-Spa-Hmac']
                if path.endswith('/attendance'):
                    assert kwargs['json'] == {'ymd': DATE}
                    if state.before_post:
                        state.before_post()
                    if not state.rejected:
                        state.checked = True
                    if state.post_error:
                        raise TimeoutError('fixture accepted, response interrupted')
                data = {} if state.malformed else calendar('checked' if state.checked else 'today')
            else:
                pytest.fail('unexpected request: ' + path)
            return response(data=data)
    def create(proxy):
        session = Session()
        state.sessions.append(session)
        return session
    monkeypatch.setattr(flow, 'new_session', create)
    monkeypatch.setattr(flow, 'state_path', lambda: state.path)
    monkeypatch.setattr(flow, 'proof', lambda *a, **k: {'a': 'fixture-a', 'm1': 'fixture-m1', 'm2': 'fixture-m2'})
    return state


def response(status=200, code=0, data=None, msg=''):
    return SimpleNamespace(status_code=status, json=lambda: {'code': code, 'data': data or {}, 'msg': msg})


def run(server, **kwargs):
    return flow.run_piggo(piggo.Piggo(), {}, config=kwargs.pop('config', CONFIG),
                          action=kwargs.pop('action', 'sign'), **kwargs)


def calls(server, path):
    return [request for request in server.requests if request[1] == path]


def test_login_saves_cookie_jwt_then_restores_without_password(server):
    for _ in range(2):
        assert run(server, action='login', authenticated=lambda r, c: server.callbacks.append(c)).status == LoginStatus.LOGIN_OK
    saved = json.loads(server.path.read_text())
    assert saved['token'] == 'fixture-token' and saved['cookies'][0]['value'] == 'fixture-cookie'
    assert 'sign' not in saved and CONFIG['piggo_password'] not in server.path.read_text()
    assert len(calls(server, '/auth/srp/login')) == len(calls(server, '/auth/sign')) == 1
    assert all(session.closed for session in server.sessions)
    assert len(server.callbacks) == 2 and all('pig_token' not in c for c in server.callbacks)


@pytest.mark.parametrize('key', ['piggo_username', 'piggo_password'])
def test_changed_account_or_password_cannot_reuse_state(server, key):
    run(server, action='login')
    run(server, action='login', config={**CONFIG, key: 'another-value'})
    assert len(calls(server, '/auth/srp/login')) == 2


def test_expired_token_reauthenticates_once(server):
    run(server, action='login')
    server.errors['/auth/sign'] = [response(401, 401)]
    assert run(server, action='login').status == LoginStatus.LOGIN_OK
    assert len(calls(server, '/auth/srp/login')) == 2


@pytest.mark.parametrize('fault', [response(503), response(429), response(302), TimeoutError('synthetic'), response(data={'unknown': True})])
def test_network_or_unknown_is_not_auth_and_preserves_file(server, fault):
    run(server, action='login')
    before = server.path.read_bytes()
    server.errors['/calendar'] = [fault]
    assert run(server).status == SignStatus.UNCONFIRMED
    assert len(calls(server, '/auth/srp/login')) == 1
    assert not calls(server, '/calendar/attendance') and server.path.read_bytes() == before


def test_expired_signature_refreshes_get_only_once(server):
    run(server, action='login')
    server.errors['/calendar'] = [response(403, 403, msg='invalid HMAC signature')]
    assert run(server, action='login').status == LoginStatus.LOGIN_OK
    assert len(calls(server, '/auth/sign')) == 2
    assert len(calls(server, '/auth/srp/login')) == 1


def test_repeated_signature_failure_does_not_loop(server):
    server.errors['/calendar'] = [response(403, 403, msg='invalid HMAC')] * 2
    assert run(server).status == SignStatus.UNCONFIRMED
    assert len(calls(server, '/calendar')) == 2 and not server.path.exists()


@pytest.mark.parametrize('bad', [response(data={'token': 'fixture-token', 'm2': 'wrong'}), response(403, 403, msg='需要验证码')])
def test_unverified_login_never_saved_or_callback(server, bad):
    server.errors['/auth/srp/login'] = [bad]
    assert run(server, action='login', authenticated=lambda *a: pytest.fail('must not callback')).status == LoginStatus.UNCONFIRMED
    assert len(calls(server, '/auth/srp/login')) == 1 and not server.path.exists()


@pytest.mark.parametrize('accepted', [True, False])
def test_sign_submits_once_and_requires_new_get(server, accepted):
    server.rejected = not accepted
    result = run(server)
    assert result.status == (SignStatus.SUCCESS if accepted else SignStatus.UNCONFIRMED)
    assert len(calls(server, '/calendar/attendance')) == 1 and len(calls(server, '/calendar')) == 2


def test_post_timeout_after_acceptance_does_not_replay(server):
    server.post_error = True
    assert run(server).status == SignStatus.SUCCESS
    assert len(calls(server, '/calendar/attendance')) == 1


def test_already_does_not_submit(server):
    server.checked = True
    assert run(server).status == SignStatus.ALREADY
    assert not calls(server, '/calendar/attendance')


def test_read_only_no_state_or_expired_never_logs_in_or_saves(server):
    assert run(server, read_only=True).status == SignStatus.UNCONFIRMED
    assert not server.requests
    run(server, action='login')
    before = server.path.read_bytes()
    server.errors['/auth/sign'] = [response(401, 401)]
    assert run(server, read_only=True).status == SignStatus.UNCONFIRMED
    assert len(calls(server, '/auth/srp/login')) == 1 and server.path.read_bytes() == before


def test_read_only_valid_state_does_not_submit(server):
    run(server, action='login')
    before = server.path.read_bytes()
    assert run(server, read_only=True).status == SignStatus.UNCONFIRMED
    assert not calls(server, '/calendar/attendance') and server.path.read_bytes() == before


def test_cancel_does_not_request(server):
    stop = Event()
    stop.set()
    assert run(server, cancel=stop).status == SignStatus.CANCELLED
    assert not server.requests


def test_no_secret_leaks_in_error(server):
    server.errors['/auth/srp/login'] = [RuntimeError('fixture-password fixture-token')]
    result = run(server)
    assert 'fixture-password' not in str(result) and 'fixture-token' not in str(result)


def test_failed_atomic_replace_preserves_old_snapshot(server, monkeypatch):
    run(server, action='login')
    before = server.path.read_bytes()
    monkeypatch.setattr(flow.os, 'replace', lambda *a: (_ for _ in ()).throw(OSError('fixture')))
    assert run(server, action='login').status == LoginStatus.UNCONFIRMED
    assert server.path.read_bytes() == before and not list(server.path.parent.glob('.piggo-*'))


def test_registry_http_without_browser_and_totp_reserved():
    site = registry.get_native_module('piggo')
    assert type(site) is piggo.Piggo and site.credential.kind == 'password'
    assert site.emulate is False and site.headful is False
    assert 'piggo_totp' in AutoPtCheckin.SITE_KEYS


@pytest.mark.parametrize('action', ['sign', 'login'])
def test_dispatch_does_not_require_cookie_or_browser(monkeypatch, action):
    runner, history = SignRunner(), []
    runner.history = history.append
    monkeypatch.setattr(native, 'cookie_candidates', lambda *a, **k: pytest.fail('old Cookie path'))
    def execute(*a, **k):
        return LoginResult(LoginStatus.LOGIN_OK, 'fixture') if action == 'login' else SignResult(SignStatus.SUCCESS, 'fixture')
    monkeypatch.setattr(flow, 'run_piggo', execute)
    fn = native.run_native_login if action == 'login' else native.run_native
    result = fn(runner, piggo.Piggo(), {}, config=CONFIG)
    assert result.metadata['action'] == action and len(history) == 1


@pytest.mark.parametrize('public', ['00', srp.N_HEX])
def test_srp_rejects_invalid_server_public(public):
    with pytest.raises(ValueError):
        srp.proof('fixture-user', 'fixture-password', '001122', public)
