"""Offline regression artifacts; run from repository root. No real site IO."""
import base64
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from threading import Event
from unittest.mock import Mock
import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
from autoptcheckin.core.credentials import Credential
from autoptcheckin.core import native
from autoptcheckin.core.models import LoginPage
from autoptcheckin.core.cloak import CloakHttpClient


def response(text='ok', status=200, cookies=None):
    return SimpleNamespace(content=text.encode(), text=text, url='https://fixture.invalid/',
                           status_code=status, headers={}, cookies=SimpleNamespace(get_dict=lambda: cookies or {}))


@pytest.fixture(autouse=True)
def host_stubs(monkeypatch):
    from types import ModuleType
    app = ModuleType('app'); app.__path__ = []
    sdk = ModuleType('app.sdk'); sdk.__path__ = []
    network = ModuleType('app.sdk.network'); network.RequestUtils = Mock()
    config = ModuleType('app.sdk.config'); config.settings = SimpleNamespace(PROXY={'https': 'http://proxy.invalid'})
    log = ModuleType('app.log'); log.logger = Mock()
    app.sdk = sdk; sdk.network = network; sdk.config = config
    for name, module in [('app', app), ('app.sdk', sdk), ('app.sdk.network', network),
                         ('app.sdk.config', config), ('app.log', log)]:
        monkeypatch.setitem(sys.modules, name, module)

@pytest.fixture
def cffi(monkeypatch):
    session = Mock()
    session.cookies.get_dict.return_value = {'rotated': 'fixture'}
    session.get.return_value = response(cookies={'image': 'fixture'})
    session.post.return_value = response()
    factory = Mock(return_value=session)
    monkeypatch.setitem(sys.modules, 'curl_cffi', SimpleNamespace(requests=SimpleNamespace(Session=factory)))
    import app.sdk.network as network
    fallback = Mock(side_effect=AssertionError('unexpected HTTP fallback'))
    monkeypatch.setattr(network, 'RequestUtils', fallback)
    return session, factory, fallback


def client():
    return native.NativeHttpClient(Credential('fixture', 'sid=fixture'),
                                   {'url': 'https://fixture.invalid/', 'impersonate': True})


@pytest.mark.parametrize('payload', [{'data': [('csrf', 'fixture'), ('claim', '1')]}, {'json': {'mode': 'fixed'}}])
def test_cffi_forwards_body_headers_and_referer(cffi, payload):
    session, factory, fallback = cffi
    with client() as http:
        http.post('https://fixture.invalid/action', headers={'X-CSRF-Token': 'fixture'},
                  referer='https://fixture.invalid/form', **payload)
        args = session.post.call_args.kwargs
        assert all(args[k] == v for k, v in payload.items())
        assert args['headers']['X-CSRF-Token'] == 'fixture'
        assert args['headers']['Referer'] == 'https://fixture.invalid/form'
        assert args['cookies']['rotated'] == 'fixture'
    factory.assert_called_once_with(impersonate='chrome')
    session.close.assert_called_once()
    fallback.assert_not_called()


def test_uncertain_cffi_post_never_falls_back_or_replays(cffi):
    session, _, fallback = cffi
    session.post.side_effect = TimeoutError('fixture timeout')
    with client() as http, pytest.raises(TimeoutError):
        http.post('https://fixture.invalid/action', data=[('claim', '1')])
    assert session.post.call_count == 1
    fallback.assert_not_called()
    session.close.assert_called_once()


def test_image_and_page_share_transport_and_cookie_jar(cffi):
    session, factory, _ = cffi
    with client() as http:
        http.get('https://fixture.invalid/form')
        assert http.get_bytes('https://fixture.invalid/image', referer='https://fixture.invalid/form') == b'ok'
        assert http.cookies['image'] == 'fixture'
        assert session.get.call_args.kwargs['headers']['Referer'].endswith('/form')
    factory.assert_called_once()


def test_browser_image_stays_in_actor_and_not_native_http():
    http = object.__new__(CloakHttpClient)
    http.http = SimpleNamespace(get_bytes=Mock(side_effect=AssertionError('wrong transport')))
    page = Mock()
    page.evaluate.return_value = {'status': 200, 'body': base64.b64encode(b'image').decode()}
    http.session = SimpleNamespace(page=page)
    http._run = lambda fn: fn()
    http._sync_cookies = Mock()
    assert http.get_bytes('https://fixture.invalid/image', referer='https://fixture.invalid/form') == b'image'
    assert page.evaluate.call_args.args[1]['options']['referrer'].endswith('/form')
    http._sync_cookies.assert_called_once()


def test_ocr_fallback_reuses_bytes_and_new_attempt_refetches(monkeypatch):
    from autoptcheckin.helper import ocr_helper
    recognize = Mock(side_effect=[None, 'Ab12', 'Cd34'])
    monkeypatch.setattr(ocr_helper, 'recognize_captcha', recognize)
    ctx = native.native_context(SimpleNamespace(id='fixture'), Credential('fixture', ''), {}, None, Event())
    image = Mock(side_effect=[b'first', b'second'])
    ctx.http = SimpleNamespace(get_bytes=image)
    args = {'image_url': 'https://fixture.invalid/image', 'referer': 'https://fixture.invalid/form'}
    ctx.ocr(**args, engine='ddddocr')
    ctx.ocr(**args, engine='ocrhelper')
    ctx.ocr(**args, engine='ddddocr')
    assert image.call_count == 2
    assert [c.kwargs['image_bytes'] for c in recognize.call_args_list] == [b'first', b'first', b'second']
    assert all('image_url' not in c.kwargs for c in recognize.call_args_list)


def test_ocrhelper_bytes_are_sent_as_base64_not_downloaded(monkeypatch):
    from autoptcheckin.helper import ocr_helper
    service = Mock()
    service.get_captcha_text.return_value = 'Ab12'
    monkeypatch.setattr(ocr_helper, 'OcrHelper', lambda: service)
    assert ocr_helper.recognize_captcha(image_bytes=b'fixture-image', engine='ocrhelper') == 'Ab12'
    service.get_captcha_text.assert_called_once_with(image_b64=base64.b64encode(b'fixture-image').decode())


from datetime import datetime
from autoptcheckin.integrations import rousi
from autoptcheckin.core.sitemodel import SignContext
from autoptcheckin.core.state_store import TrackStateStore
from autoptcheckin.core.models import SignResult
from autoptcheckin.sites.native.retrotoon import RetroToon


class PeerClient:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []
    def _call(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return reply
    def get(self, url, **kwargs): return self._call('get', url, **kwargs)
    def post(self, url, **kwargs): return self._call('post', url, **kwargs)


def peer_body(data, status=200):
    return LoginPage(json.dumps(data), 'https://fixture.invalid/', status)


@pytest.mark.parametrize('post', [peer_body({}, 201), TimeoutError('accepted but timed out'), peer_body({'success': True})])
def test_rousi_fresh_state_confirms_success_without_replaying_post(post):
    http = PeerClient([peer_body({'user': {'id': 1}, 'csrf_token': 'fixture'}),
                       peer_body({'claimed_today': False, 'policy': {'settings': {'enabled': True, 'fixed_enabled': True}}}), post,
                       peer_body({'claimed_today': True, 'today_record': {'total_reward': 10}})])
    result = rousi.signin(http, {})
    assert result.status == 'success'
    assert '已回读确认' in result.message and '10' in result.message
    assert [c[0] for c in http.calls] == ['get', 'get', 'post', 'get']
    headers = http.calls[2][2]['headers']
    assert headers['X-CSRF-Token'] == 'fixture' and headers['Idempotency-Key']


@pytest.mark.parametrize('fresh', [peer_body({'claimed_today': False, 'policy': {'settings': {'enabled': True, 'fixed_enabled': True}}}), peer_body({}, 503), TimeoutError()])
def test_rousi_post_success_alone_does_not_confirm_claim(fresh):
    http = PeerClient([peer_body({'user': {'id': 1}, 'csrf_token': 'fixture'}),
                       peer_body({'claimed_today': False, 'policy': {'settings': {'enabled': True, 'fixed_enabled': True}}}), peer_body({'success': True}), fresh])
    assert rousi.signin(http, {}).status == 'unconfirmed'
    assert sum(c[0] == 'post' for c in http.calls) == 1


@pytest.mark.parametrize('settings,expected', [
    ({'enabled': True, 'fixed_enabled': False, 'random_enabled': True}, 'random'),
    ({'enabled': True, 'fixed_enabled': True, 'random_enabled': True}, 'fixed'),
    ({'enabled': False}, None),
    ({'enabled': True, 'fixed_enabled': False, 'random_enabled': False}, None)])
def test_rousi_uses_available_reward_mode_or_stops_before_post(settings, expected):
    http = PeerClient([peer_body({'user': {'id': 1}, 'csrf_token': 'fixture'}),
                       peer_body({'claimed_today': False, 'policy': {'settings': settings}}),
                       peer_body({}), peer_body({'claimed_today': True})])
    result = rousi.signin(http, {})
    posts = [c for c in http.calls if c[0] == 'post']
    if expected:
        assert posts[0][2]['json'] == {'mode': expected}
        assert result.status == 'success'
    else:
        assert not posts and result.status == 'protocol_pending'


def test_rousi_account_refresh_then_claim_has_final_get():
    auth = {'user': {'id': 1}, 'csrf_token': 'fixture'}
    http = PeerClient([peer_body({}, 401), peer_body({}, 401), peer_body(auth), peer_body(auth),
                       peer_body({'claimed_today': False, 'policy': {'settings': {'enabled': True, 'fixed_enabled': True}}}), peer_body({'success': True}),
                       peer_body({'claimed_today': True})])
    result = rousi.signin(http, {'rousi_username': 'fixture', 'rousi_password': 'fixture'})
    assert result.status == 'success' and http.calls[-1][0] == 'get'


CLAIM = ('<form method="post"><input name="csrf_token" value="fixture">'
         '<button name="claim" value="1">Claim reward</button></form>')
DONE = '<div class="rt-form-card"><h2>Daily Reward</h2><p>Already claimed today</p></div>'
CALENDAR = '<div class="att-cal-cell att-cal-cell--today att-cal-cell--claimed">+12 points</div>'


class PageClient:
    def __init__(self, pages):
        self.pages = iter(pages)
        self.calls = []
    def get(self, url, **kwargs):
        self.calls.append(('get', url))
        return LoginPage(next(self.pages), url)
    def post(self, url, **kwargs):
        self.calls.append(('post', url, kwargs))
        return LoginPage('untrusted', url)


def retro(http):
    return RetroToon().signin(SignContext('retrotoon', Credential('fixture', ''), http))


@pytest.mark.parametrize('claimed', [CALENDAR, DONE.replace('Already', 'already')])
def test_retrotoon_form_beats_hidden_done_text_and_calendar(claimed):
    http = PageClient([CLAIM + claimed, CALENDAR])
    result = retro(http)
    assert result.status == 'success'
    assert [c[0] for c in http.calls] == ['get', 'post', 'get']
    assert dict(http.calls[1][2]['data']) == {'csrf_token': 'fixture', 'claim': '1'}
    assert result.message.startswith('签到成功')


def test_retrotoon_today_calendar_confirms_already_without_post():
    http = PageClient([CALENDAR])
    assert retro(http).status == 'already'
    assert len(http.calls) == 1


@pytest.mark.parametrize('fake', [
    '<div class="att-cal-cell--yesterday att-cal-cell--claimed">+12</div>',
    '<div class="not-att-cal-cell--today att-cal-cell--claimed">+12</div>',
    '<div class="att-cal-cell--today not-att-cal-cell--claimed">+12</div>'])
def test_retrotoon_other_days_and_class_substrings_never_confirm(fake):
    assert retro(PageClient([fake])).status != 'already'


def test_retrotoon_readback_with_claim_still_present_is_not_success():
    assert retro(PageClient([CLAIM, CLAIM + DONE])).status == 'unconfirmed'


def test_site_reset_success_expiry_reenters_real_auto_queue(monkeypatch):
    import autoptcheckin as entry
    from autoptcheckin.core import nexus
    class Clock(datetime):
        current = datetime(2026, 11, 1, 8, 59)
        @classmethod
        def now(cls): return cls.current
    monkeypatch.setattr(nexus, 'datetime', Clock)
    storage = {}
    store = TrackStateStore(storage.get, storage.__setitem__, clock=Clock.now)
    store.rollover()
    plugin = entry.AutoPtCheckin()
    plugin._config.update(enabled_sites=['retrotoon'], sign_sites=['retrotoon'], login_sites=[])
    plugin._state = store
    plugin._registry = lambda: {'sites': [{'id': 'retrotoon', 'signin_capable': True, 'login_capable': True}]}
    plugin._history = SimpleNamespace(append=Mock())
    result = retro(PageClient([CALENDAR]))
    result.site_id = 'retrotoon'; result.metadata['action'] = 'sign'
    plugin._record_result(result)
    assert store.state_of('retrotoon', 'sign') == 'success'
    assert plugin._due_for('sign') == []
    assert result.message == '昨日已签，站点 9 点后刷新'
    Clock.current = datetime(2026, 11, 1, 9, 0)
    # Reload still honors the persisted expiry (not just the in-memory result).
    plugin._state = TrackStateStore(storage.get, storage.__setitem__, clock=Clock.now)
    calls = []
    plugin._run_with_retry = lambda site, action, trigger: calls.append((site, action)) or {'status': 'signed'}
    plugin._notify_round = Mock()
    plugin._execute_all('scheduler')
    assert calls == [('retrotoon', 'sign')]


def test_new_claim_before_reset_also_expires_and_normal_daily_success_does_not(monkeypatch):
    from autoptcheckin.core import nexus
    class Clock(datetime):
        @classmethod
        def now(cls): return datetime(2026, 11, 1, 8, 30)
    monkeypatch.setattr(nexus, 'datetime', Clock)
    fresh = retro(PageClient([CLAIM, CALENDAR]))
    assert fresh.status == 'success' and fresh.metadata['success_expires_at'] == datetime(2026, 11, 1, 9).timestamp()
    now = [datetime(2026, 11, 1, 8, 30)]
    store = TrackStateStore(clock=lambda: now[0]); store.rollover()
    store.apply_result('ordinary', 'sign', 'success')
    store.apply_result('retrotoon', 'sign', 'success', metadata=fresh.metadata)
    now[0] = datetime(2026, 11, 1, 9)
    store.rollover()
    assert store.state_of('ordinary', 'sign') == 'success'
    assert store.state_of('retrotoon', 'sign') == 'pending'


@pytest.mark.parametrize('proxy', ['http://proxy.invalid', {'http': 'http://proxy.invalid', 'https': 'http://proxy.invalid'}])
def test_cffi_proxy_accepts_sdk_mapping_and_url(cffi, proxy):
    from app.sdk.config import settings
    settings.PROXY = proxy
    session, _, _ = cffi
    with native.NativeHttpClient(Credential('fixture', 'sid=fixture'), {'impersonate': True, 'proxy': True}) as http:
        http.get('https://fixture.invalid/')
    assert session.get.call_args.kwargs['proxies'] == {'http': 'http://proxy.invalid', 'https': 'http://proxy.invalid'}


@pytest.mark.parametrize('action', ['sign', 'login'])
def test_btschool_default_fingerprint_reaches_both_production_entrypoints(cffi, action):
    from autoptcheckin.sites.native.btschool import BTSchool
    from autoptcheckin.core.runner import SignRunner
    session, factory, fallback = cffi
    authed = '<a href="userdetails.php?id=1">fixture</a><a href="logout.php">退出</a>'
    form = authed + '<a href="index.php?action=addbonus">签到</a>'
    session.get.side_effect = ([response(form), response('action accepted'), response(authed)]
                               if action == 'sign' else [response(authed), response(authed)])
    info = {'cookie': 'sid=fixture'}
    site = BTSchool(); site.url = 'https://fixture.invalid/'
    if action == 'sign':
        result = native.run_native(SignRunner(), site, info)
        assert result.status == 'success'
        assert any('action=addbonus' in call.args[0] for call in session.get.call_args_list)
    else:
        result = native.run_native_login(SignRunner(), site, info)
        assert result.status == 'login_ok'
    factory.assert_called_once_with(impersonate='chrome')
    fallback.assert_not_called()
    session.close.assert_called_once()


def test_peergo_unknown_activity_configuration_never_submits():
    http = PeerClient([peer_body({'user': {'id': 1}, 'csrf_token': 'fixture'}), peer_body({'claimed_today': False})])
    result = rousi.signin(http, {})
    assert result.status == 'protocol_pending'
    assert not any(c[0] == 'post' for c in http.calls)
