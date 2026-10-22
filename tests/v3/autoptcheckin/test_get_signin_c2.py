"""C2 synthetic fixtures: action receipts never substitute for safe fresh pages."""
import sys
from pathlib import Path
from urllib.parse import urljoin
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
from autoptcheckin.core.credentials import Credential
from autoptcheckin.core.models import LoginPage
from autoptcheckin.core.native import NativeHttpClient
from autoptcheckin.core.registry import get_native_module, discover_sites
from autoptcheckin.core.sitemodel import SignContext

IDS = 'btschool haidan hdcity hdupt hhanclub pttime lajidui siqi'.split()
OCR_IDS = {'lajidui', 'siqi'}


def message(text):
    return f'<div class="alert">{text}</div>'


def signed(sid):
    return {'haidan': '<input value="已经打卡">', 'hdupt': '<span id="yiqiandao"></span>',
            'siqi': '<div class="notice attend-success-effect active"></div>',
            'hdcity': message('Already checked in today'), 'btschool': '<main>签到成功</main>'}.get(sid, message('已经签到' if sid == 'hhanclub' else '签到成功'))


def before(sid):
    if sid not in OCR_IDS:
        return '<main>每日签到</main>'
    return ('<form method="post" action="attendance.php"><input name="imagehash" value="fixture">'
            '<input name="imagestring"><input name="unrelated" value="omit">'
            '<img src="image.php?imagehash=fixture"><button>签到</button></form>')


class Http:
    def __init__(self, site, fresh, *, initial=None, action_error=False):
        self.site, self.fresh = site, fresh
        self.initial = before(site.id) if initial is None else initial
        self.action_error, self.calls, self.reads = action_error, [], 0

    def get(self, url, *, referer=None):
        self.calls.append(('get', url, referer))
        if url == urljoin(self.site.url, self.site.attendance_path):
            self.reads += 1
            text = self.initial if self.reads == 1 else self.fresh
            if isinstance(text, Exception):
                raise text
            return LoginPage(text, url)
        if self.action_error:
            raise TimeoutError()
        return LoginPage('签到成功 .23', url)

    def post(self, url, *, data, referer=None):
        self.calls.append(('post', url, referer, list(data)))
        if self.action_error:
            raise TimeoutError()
        return LoginPage('签到成功', url)


def context(site, http, ocr=None):
    return SignContext(site.id, Credential('managed_site', 'synthetic'), http,
                       ocr=ocr if ocr is not None else Mock(return_value='Ab1234'))


def actions(http):
    safe = urljoin(http.site.url, http.site.attendance_path)
    return [c for c in http.calls if c[0] == 'post' or c[1] != safe]


@pytest.mark.parametrize('sid', sorted(OCR_IDS))
@pytest.mark.parametrize('state', ['signed', 'unsigned', 'unknown'])
def test_c2_three_state_readback(sid, state):
    site = get_native_module(sid)
    fresh = signed(sid) if state == 'signed' else message('未签到') if state == 'unsigned' else '<main>签到成功</main>'
    http = Http(site, fresh)
    result = site.signin(context(site, http))
    expected = 'success' if state == 'signed' and sid != 'btschool' else 'failed' if state == 'unsigned' and sid not in {'btschool', 'haidan'} else 'unconfirmed'
    assert result.status == expected
    assert len(actions(http)) == 1 and http.reads == 2
    assert http.calls[0][1] == http.calls[-1][1] == urljoin(site.url, site.attendance_path)
    if sid == 'hhanclub':
        assert actions(http)[0][2] == site.url
    if sid in OCR_IDS:
        assert dict(actions(http)[0][3]) == {'imagehash': 'fixture', 'imagestring': 'Ab1234'}


@pytest.mark.parametrize('sid', IDS)
def test_c2_already_never_repeats_action_except_unconfirmable_btschool(sid):
    site = get_native_module(sid)
    http = Http(site, signed(sid), initial=signed(sid))
    result = site.signin(context(site, http))
    assert result.status == ('unconfirmed' if sid == 'btschool' else 'already')
    assert len(actions(http)) == (1 if sid == 'btschool' else 0)


@pytest.mark.parametrize('sid', IDS)
@pytest.mark.parametrize('fresh', ['signed', 'timeout', 'body'])
def test_c2_action_exception_still_reads_once(sid, fresh):
    site = get_native_module(sid)
    http = Http(site, signed(sid) if fresh == 'signed' else TimeoutError() if fresh == 'timeout' else '<body>签到成功</body>', action_error=True)
    result = site.signin(context(site, http))
    assert result.status == ('success' if fresh == 'signed' and sid != 'btschool' else 'unconfirmed')
    assert len(actions(http)) == 1 and http.reads == 2


@pytest.mark.parametrize('sid', IDS)
def test_c2_cancel_and_unavailable_pre_read_never_submit(sid):
    site = get_native_module(sid)
    http = Http(site, signed(sid), initial=TimeoutError())
    assert site.signin(context(site, http)).status == 'unconfirmed'
    assert not actions(http)
    ctx = context(site, http)
    ctx.cancel.set()
    assert site.signin(ctx).status == 'cancelled'
    assert len(http.calls) == 1


@pytest.mark.parametrize('sid', sorted(OCR_IDS))
@pytest.mark.parametrize('codes,expected', [([None, 'Ab12'], True), ([None, None], False), (['Ab12345', None], None)])
def test_c2_ocr_limits_fallback_and_no_retry(sid, codes, expected):
    site = get_native_module(sid)
    http, ocr = Http(site, signed(sid)), Mock(side_effect=codes)
    result = site.signin(context(site, http, ocr))
    submitted = sid == 'siqi' if expected is None else expected
    assert len(actions(http)) == int(submitted)
    assert result.status == ('success' if submitted else 'unconfirmed')
    for call in ocr.call_args_list:
        assert call.kwargs['max_len'] == (None if sid == 'siqi' else 6)
        assert call.kwargs['referer'] == site.url + 'attendance.php'
        assert call.kwargs['min_len'] == 4 and call.kwargs['retry_times'] == 1


@pytest.mark.parametrize('text', ['本次签到获得魅力', 'Got extra', '已签到', 'Already checked in today'])
def test_c2_hdcity_all_declared_languages(text):
    site = get_native_module('hdcity')
    assert site.signin(context(site, Http(site, message(text)))).status == 'success'


def test_c2_marker_class_is_not_text_or_substring():
    site = get_native_module('siqi')
    for text in ['<p>attend-success-effect</p>', '<p class="not-attend-success-effect"></p>']:
        assert site.signin(context(site, Http(site, text))).status == 'unconfirmed'


def test_c2_registry_still_gated_and_optional_get_referer(monkeypatch):
    rows = {row['id']: row for row in discover_sites()['sites']}
    for sid in IDS:
        assert rows[sid]['hook_implemented'] and not rows[sid]['verified'] and not rows[sid]['pilot_enabled']
    client = NativeHttpClient(Credential('managed_site', 'synthetic'), {})
    request = Mock()
    monkeypatch.setattr(client, '_request', request)
    client.get('https://fixture.invalid/action', referer='https://fixture.invalid/')
    request.assert_called_with('get', 'https://fixture.invalid/action', referer='https://fixture.invalid/')
    client.get('https://fixture.invalid/')
    request.assert_called_with('get', 'https://fixture.invalid/')
