"""C3/C4 synthetic consumer-path fixtures. No real requests or credentials."""
import importlib
import json
import sys
from pathlib import Path
from urllib.parse import urljoin
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
from autoptcheckin.core.credentials import Credential
from autoptcheckin.core.models import LoginPage
from autoptcheckin.core.registry import get_native_module, discover_sites
from autoptcheckin.core.sitemodel import RecordSpec, SignContext
from autoptcheckin.core.native import NativeHttpClient

IDS = 'hdarea nexushd ttg u2 hdchina opencd pterclub zhuque'.split()
API = 'hdchina opencd pterclub zhuque'.split()
RECEIPTS = dict(hdchina={'state': 'success'}, opencd={'state': 'success'},
                pterclub={'status': '1'}, zhuque={'status': 200, 'data': {'bonus': 0}})


def message(text):
    return f'<div class="alert">{text}</div>'


def initial(sid):
    return {
        'ttg': '<script>signed_timestamp: "1234567890", signed_token: "fixture"</script>',
        'u2': '<form method="post" action="showup.php?action=show">' + ''.join(
            f'<input name="{key}" value="fixture">' for key in ('_csrf', 'req', 'hash', 'form'))
            + '<input type="submit" name="choice" value="作品"></form>',
        'hdchina': '<meta name="x-csrf" content="fixture">',
        'zhuque': '<meta name="x-csrf-token" content="fixture">',
    }.get(sid, '<main>签到</main>')


def signed(sid):
    return {'u2': '<a href="showup.php">已签到</a>', 'ttg': '<b style="color:green;">已签到</b>',
            'hdchina': '<a class="label label-default" href="#">已签到</a>',
            'opencd': '<a href="/plugin_sign-in.php?cmd=show-log">记录</a>',
            'hdarea': message('此次签到您获得'), 'nexushd': message('本次签到获得')}.get(sid, '<main>unknown</main>')


class Http:
    def __init__(self, site, *, fresh='<main>unknown</main>', receipt=None, before=None):
        self.site, self.fresh = site, fresh
        self.receipt = json.dumps(RECEIPTS[site.id]) if receipt is None and site.id in API else receipt or 'JS redirect'
        self.before = initial(site.id) if before is None else before
        self.calls, self.reads, self.actions = [], 0, []
        self.retained = None
        self.form = '<form id="frmSignin"><input name="imagehash" value="fixture"><img src="image.php?id=fixture"></form>'

    def retain_cookies(self, names):
        self.retained = names

    def get(self, url, **kwargs):
        self.calls.append(('get', url, kwargs))
        if url == urljoin(self.site.url, self.site.attendance_path):
            self.reads += 1
            return self.page(self.before if self.reads == 1 else self.fresh, url)
        if self.site.id == 'opencd' and url == self.site.url + 'plugin_sign-in.php':
            return self.page(self.form, url)
        self.actions.append(('get', url, kwargs))
        return self.page(self.receipt, url)

    def post(self, url, **kwargs):
        self.calls.append(('post', url, kwargs))
        self.actions.append(('post', url, kwargs))
        return self.page(self.receipt, url)

    @staticmethod
    def page(text, url):
        if isinstance(text, Exception):
            raise text
        return LoginPage(text, url)


def context(site, http, ocr=None):
    return SignContext(site.id, Credential('managed_site', 'fixture'), http,
                       ocr=ocr if ocr is not None else Mock(return_value='Ab1234'))


@pytest.fixture(autouse=True)
def daytime(monkeypatch):
    module = importlib.import_module('autoptcheckin.sites.native.u2')
    clock = Mock()
    clock.now.return_value.hour = 9
    monkeypatch.setattr(module, 'datetime', clock)
    return clock


@pytest.mark.parametrize('sid', [sid for sid in IDS if sid not in {'hdarea', 'nexushd'}])
@pytest.mark.parametrize('state', ['signed', 'unsigned', 'unknown'])
def test_c34_three_states_and_single_action(sid, state):
    site = get_native_module(sid)
    fresh = signed(sid) if state == 'signed' else message('未签到') if state == 'unsigned' else '<main>签到成功</main>'
    receipt = None if state == 'signed' else json.dumps({'success': False}) if sid == 'yema' and state == 'unsigned' else '{}'
    http = Http(site, fresh=fresh, receipt=receipt)
    result = site.signin(context(site, http))
    expected = 'success' if state == 'signed' else 'failed' if state == 'unsigned' and sid in {'hdarea', 'nexushd', 'ttg', 'yema'} else 'unconfirmed'
    assert result.status == expected
    assert len(http.actions) == 1 and http.reads == 2
    assert http.calls[0][1] == http.calls[-1][1] == urljoin(site.url, site.attendance_path)
    action = http.actions[0]
    if sid == 'hdarea':
        assert action[1].endswith('/sign_in.php') and dict(action[2]['data']) == {'action': 'sign_in'}
    if sid == 'nexushd':
        assert action[1].endswith('/signin.php') and dict(action[2]['data']) == {'action': 'post', 'content': ''}
    if sid == 'ttg':
        assert dict(action[2]['data']) == {'signed_timestamp': '1234567890', 'signed_token': 'fixture'}
    if sid == 'u2':
        assert dict(action[2]['data']) == {'_csrf': 'fixture', 'req': 'fixture', 'hash': 'fixture', 'form': 'fixture', 'message': '一切随缘~', 'choice': '作品'}
    if sid == 'hdchina':
        assert http.retained == {'hdchina'} and dict(action[2]['data']) == {'csrf': 'fixture'}
    if sid == 'zhuque':
        assert action[2] == {'headers': {'x-csrf-token': 'fixture'}, 'json': {'all': 1, 'resetModal': 'true'}}
        if state == 'signed':
            assert result.reward.reported == '0'


@pytest.mark.parametrize('sid', IDS)
@pytest.mark.parametrize('fresh_ok', [True, False])
def test_c34_timeout_never_retries_and_always_rereads(sid, fresh_ok):
    site = get_native_module(sid)
    http = Http(site, receipt=TimeoutError(), fresh=signed(sid) if fresh_ok else TimeoutError())
    result = site.signin(context(site, http))
    assert result.status == ('success' if fresh_ok and sid in {'hdarea', 'nexushd', 'ttg', 'u2', 'hdchina', 'opencd'} else 'unconfirmed')
    assert len(http.actions) == 1 and http.reads == 2


@pytest.mark.parametrize('sid', API)
def test_api_explicit_receipt_survives_failed_reread(sid):
    site = get_native_module(sid)
    http = Http(site, fresh=TimeoutError())
    assert site.signin(context(site, http)).status == 'success'
    assert len(http.actions) == 1 and http.reads == 2


@pytest.mark.parametrize('sid', ['hdarea', 'nexushd', 'ttg', 'u2', 'hdchina', 'opencd'])
def test_c34_already_skips_action(sid):
    site = get_native_module(sid)
    http = Http(site, before=signed(sid))
    assert site.signin(context(site, http)).status == 'already'
    assert not http.actions and http.reads == 1


@pytest.mark.parametrize('sid', IDS)
def test_c34_cancel_and_unavailable_pre_read(sid):
    site = get_native_module(sid)
    http = Http(site, before=TimeoutError())
    ctx = context(site, http)
    assert site.signin(ctx).status == 'network_error'
    assert not http.actions
    ctx.cancel.set()
    assert site.signin(ctx).status == 'cancelled'
    assert len(http.calls) == 1


@pytest.mark.parametrize('hour,submitted', [(8, False), (9, True), (23, True)])
def test_u2_nine_hour_boundary(daytime, hour, submitted):
    daytime.now.return_value.hour = hour
    site = get_native_module('u2')
    http = Http(site, fresh=signed('u2'))
    site.signin(context(site, http))
    assert bool(http.actions) == submitted


@pytest.mark.parametrize('sid', ['ttg', 'u2', 'hdchina', 'zhuque'])
@pytest.mark.parametrize('mutation', ['missing', 'duplicate', 'foreign'])
def test_dynamic_parameters_missing_ambiguous_or_foreign(sid, mutation):
    site = get_native_module(sid)
    before = initial(sid)
    if mutation == 'missing':
        before = '<main>unknown</main>'
    elif mutation == 'duplicate':
        before *= 2
    elif sid == 'u2':
        before = before.replace('showup.php?action=show', 'https://foreign.invalid/showup.php?action=show')
    else:
        before = before.replace('fixture', '')
    http = Http(site, before=before)
    site.signin(context(site, http))
    assert not http.actions


def test_u2_unrelated_csrf_and_js_are_not_evidence():
    site = get_native_module('u2')
    http = Http(site, before='<input name="_csrf" value="other">' + initial('u2'))
    assert site.signin(context(site, http)).status == 'unconfirmed'
    assert dict(http.actions[0][2]['data'])['_csrf'] == 'fixture'


@pytest.mark.parametrize('codes,submitted', [([None, 'Ab1234'], True), (['12345', '1234567'], False), (['Ab1234'], True)])
def test_opencd_six_character_fallback(codes, submitted):
    site = get_native_module('opencd')
    http, ocr = Http(site), Mock(side_effect=codes)
    site.signin(context(site, http, ocr))
    assert bool(http.actions) == submitted
    for call in ocr.call_args_list:
        assert call.kwargs['min_len'] == call.kwargs['max_len'] == 6
        assert call.kwargs['retry_times'] == 1
    assert [call.kwargs['engine'] for call in ocr.call_args_list] == ['ddddocr', 'ocrhelper'][:len(codes)]


def test_opencd_never_sends_cookie_to_foreign_image():
    site = get_native_module('opencd')
    http, ocr = Http(site), Mock()
    http.form = http.form.replace('image.php?id=fixture', 'https://foreign.invalid/image.php')
    site.signin(context(site, http, ocr))
    assert not http.actions and not ocr.called


@pytest.mark.parametrize('value,state', [(True, 'signed'), (False, 'unsigned'), (1, 'unconfirmed'), (0, 'unconfirmed'), ('true', 'unconfirmed'), ('false', 'unconfirmed'), (None, 'unconfirmed'), ({}, 'unconfirmed')])
def test_record_spec_bool_exact_type(value, state):
    site = get_native_module('hdchina')
    ctx = context(site, Http(site))
    spec = RecordSpec(source='response_json', response_field='success', status_map={True: 'signed', False: 'unsigned'})
    assert ctx.read_record(LoginPage(json.dumps({'success': value}), site.url), spec).status == state
    numeric = RecordSpec(source='response_json', response_field='success', status_map={0: 'signed', 1: 'unsigned'})
    if type(value) is bool:
        assert ctx.read_record(LoginPage(json.dumps({'success': value}), site.url), numeric).status == 'unconfirmed'


def test_c34_registry_remains_unverified():
    rows = {row['id']: row for row in discover_sites()['sites']}
    for sid in IDS:
        assert rows[sid]['hook_implemented'] and not rows[sid]['verified']


def test_native_http_cookie_refresh_json_headers(monkeypatch):
    network, config = Mock(), Mock()
    monkeypatch.setitem(sys.modules, 'app.sdk.network', network)
    monkeypatch.setitem(sys.modules, 'app.sdk.config', config)
    response = Mock(text='{}', url='https://fixture.invalid/', status_code=200)
    response.cookies.get_dict.return_value = {'refreshed': 'synthetic'}
    network.RequestUtils.return_value.get_res.return_value = response
    network.RequestUtils.return_value.post_res.return_value = response
    client = NativeHttpClient(Credential('managed_site', 'hdchina=synthetic; stale=synthetic'), {})
    other = NativeHttpClient(Credential('managed_site', 'other=synthetic'), {})
    client.retain_cookies({'hdchina'})
    client.get('https://fixture.invalid/')
    assert client.cookies == {'hdchina': 'synthetic', 'refreshed': 'synthetic'}
    assert other.cookies == {'other': 'synthetic'}
    client.post('https://fixture.invalid/action', headers={'x-csrf-token': 'synthetic'}, json={'all': 1})
    assert network.RequestUtils.call_args.kwargs['headers'] == {'x-csrf-token': 'synthetic'}
    assert network.RequestUtils.call_args.kwargs['content_type'].startswith('application/json')
    network.RequestUtils.return_value.post_res.assert_called_once_with(url='https://fixture.invalid/action', json={'all': 1})


@pytest.mark.parametrize('sid', API)
@pytest.mark.parametrize('value', [None, {}, [], 'unknown', 0.0, True])
def test_api_unknown_or_wrong_type_is_not_success(sid, value):
    site = get_native_module(sid)
    if sid == 'yema' and value is True:
        return
    http = Http(site, receipt=json.dumps({site.record_spec.response_field: value}))
    assert site.signin(context(site, http)).status == 'unconfirmed'
    assert len(http.actions) == 1 and http.reads == 2


@pytest.mark.parametrize('sid', ['hdchina', 'opencd'])
def test_api_safe_signed_marker_precedes_bad_receipt(sid):
    site = get_native_module(sid)
    http = Http(site, fresh=signed(sid), receipt='broken JSON')
    assert site.signin(context(site, http)).status == 'success'
    assert http.reads == 2


def test_opencd_unparseable_reread_preserves_valid_receipt():
    site = get_native_module('opencd')
    http = Http(site, fresh=' ')
    assert site.signin(context(site, http)).status == 'success'


def test_ttg_timestamp_must_have_exactly_ten_digits():
    site = get_native_module('ttg')
    for timestamp in ('123', '12345678901', 'abcdefghij'):
        http = Http(site, before=initial('ttg').replace('1234567890', timestamp))
        assert site.signin(context(site, http)).status == 'protocol_pending'
        assert not http.actions
