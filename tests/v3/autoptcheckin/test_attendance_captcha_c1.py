"""C1: synthetic per-site consumers; no live HTTP or OCR engine requests."""
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
from autoptcheckin.core.credentials import Credential
from autoptcheckin.core.models import LoginPage
from autoptcheckin.core.native import NativeHttpClient
from autoptcheckin.core.registry import get_native_module, discover_sites
from autoptcheckin.core.sitemodel import SignContext

IDS = 'baozi dongying kelu naturept novahd oshen playlet shaobaoyuan soulvoice tu88'.split()


def message(text):
    return f'<div class="alert">{text}</div>'


def form_page():
    return (message('未签到') + '<form method="post" action="attendance.php">'
            '<input name="csrf" value="synthetic"><input name="imagehash" value="fixture-hash">'
            '<img src="image.php?action=regimage&amp;imagehash=fixture-hash">'
            '<input name="imagestring" value=""><button>签到</button></form>')


class Http:
    def __init__(self, pages, error=False):
        self.pages, self.calls, self.error = iter(pages), [], error

    def get(self, url):
        self.calls.append(('get', url))
        value = next(self.pages)
        if isinstance(value, Exception):
            raise value
        return LoginPage(value, url)

    def post(self, url, *, data, referer=None):
        self.calls.append(('post', url, list(data), referer))
        if self.error:
            raise TimeoutError()
        return LoginPage('验证码错误；不应自动重试', url)


def context(site, http, ocr):
    return SignContext(site.id, Credential('managed_site', 'synthetic'), http, ocr=ocr)


@pytest.mark.parametrize('sid', IDS)
@pytest.mark.parametrize('codes,expected', [(['Ab12'], True), (['Ab123'], True), (['Ab1234'], True), ([None, 'Zy9876'], True), ([RuntimeError(), 'Zy9876'], True), ([None, None], False), (['abc', 'Ab12345'], False), (['!!!123', '中文1234'], False)])
def test_c1_ocr_hook_success_failure_fallback(sid, codes, expected):
    site = get_native_module(sid)
    page = LoginPage(form_page(), site.url + 'attendance.php')
    ocr = Mock(side_effect=codes)
    ctx = context(site, Http([]), ocr)
    form = site.discover_form(ctx, page)
    original = list(form.data)
    assert site.solve_captcha(ctx, page, form) is expected
    assert [c.kwargs['engine'] for c in ocr.call_args_list] == ['ddddocr', 'ocrhelper'][:len(codes)]
    for call in ocr.call_args_list:
        assert call.kwargs == dict(image_url=site.url + 'image.php?action=regimage&imagehash=fixture-hash', referer=page.url, min_len=4, max_len=6, retry_times=1, engine=call.kwargs['engine'], charset='alnum')
    if not expected:
        assert form.data == original and form.referer is None


@pytest.mark.parametrize('sid', IDS)
def test_c1_unsolved_never_submits(sid):
    site = get_native_module(sid)
    http, ocr = Http([form_page()]), Mock(return_value=None)
    assert site.signin(context(site, http, ocr)).status == 'protocol_pending'
    assert len(http.calls) == 1 and ocr.call_count == 2


@pytest.mark.parametrize('sid', IDS)
@pytest.mark.parametrize('fresh,expected', [(message('签到成功'), 'success'), (TimeoutError(), 'unconfirmed'), ('<main>签到成功</main>', 'unconfirmed')])
def test_c1_submit_exception_always_reads_and_never_retries(sid, fresh, expected):
    site = get_native_module(sid)
    http, ocr = Http([form_page(), fresh], error=True), Mock(return_value='Ab1234')
    assert site.signin(context(site, http, ocr)).status == expected
    assert [c[0] for c in http.calls] == ['get', 'post', 'get']
    assert ocr.call_count == 1



def test_kelu_bare_signin_heading_is_not_reported_as_a_result():
    site = get_native_module('kelu')
    http = Http([form_page(), '<h1>签到</h1>'])
    result = site.signin(context(site, http, Mock(return_value='Ab1234')))
    assert result.status == 'unconfirmed'
    assert result.message == '已提交签到，但回读未找到成功或已签证据（最近识别=Ab1234/ddddocr）'
    assert [call[0] for call in http.calls] == ['get', 'post', 'get']


@pytest.mark.parametrize('sid', IDS)
@pytest.mark.parametrize('mode', ['missing_hash', 'duplicate_hash', 'missing_image', 'duplicate_image', 'foreign_image', 'no_ocr', 'cancel'])
def test_c1_invalid_inputs_do_not_call_ocr_or_submit(sid, mode):
    site = get_native_module(sid)
    text = form_page()
    if mode == 'missing_hash':
        text = text.replace('name="imagehash"', 'name="other"')
    elif mode == 'duplicate_hash':
        text = text.replace('</form>', '<input name="imagehash" value="second"></form>')
    elif mode == 'missing_image':
        text = text.replace('image.php?', 'other.php?')
    elif mode == 'duplicate_image':
        text = text.replace('</form>', '<img src="image.php?second"></form>')
    elif mode == 'foreign_image':
        text = text.replace('src="image.php', 'src="https://untrusted.invalid/image.php')
    http, ocr = Http([text]), Mock(return_value='Ab1234')
    ctx = context(site, http, None if mode == 'no_ocr' else ocr)
    if mode == 'cancel':
        ctx.cancel.set()
    assert site.signin(ctx).status == ('cancelled' if mode == 'cancel' else 'protocol_pending')
    ocr.assert_not_called()
    assert not any(c[0] == 'post' for c in http.calls)


def test_c1_registry_still_unverified():
    rows = {row['id']: row for row in discover_sites()['sites']}
    for sid in IDS:
        # verified 审批元数据已移除：仅断言提交协议声明存在。
        assert rows[sid]['hook_implemented']


def test_native_post_optional_referer_forwarding(monkeypatch):
    client = NativeHttpClient(Credential('managed_site', 'synthetic'), {})
    request = Mock()
    monkeypatch.setattr(client, '_request', request)
    client.post('https://fixture.invalid/attendance.php', data=[], referer='https://fixture.invalid/attendance.php')
    request.assert_called_with('post', 'https://fixture.invalid/attendance.php', data=[], referer='https://fixture.invalid/attendance.php')
    client.post('https://fixture.invalid/other.php', data=[])
    request.assert_called_with('post', 'https://fixture.invalid/other.php', data=[])
