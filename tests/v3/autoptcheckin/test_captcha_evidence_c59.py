"""C59: 验证码站失败现场留证（识别结果/原因 + 提交响应切片）与 UA 兜底（合成数据，不发请求）。"""
import sys
from pathlib import Path
from unittest.mock import Mock


sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
from autoptcheckin.core.attendance_captcha import solve_attendance_captcha
from autoptcheckin.core.credentials import Credential
from autoptcheckin.core.models import LoginPage
from autoptcheckin.core.native import NativeHttpClient, browser_ua, response_note
from autoptcheckin.core.nexus import captcha_hint
from autoptcheckin.core.registry import get_native_module
from autoptcheckin.core.sitemodel import SignContext

SID = 'kelu'


def page(message, hash_value='h1', captcha=True):
    form = ''
    if captcha:
        form = ('<form method="post" action="attendance.php">'
                '<input name="csrf" value="synthetic">'
                f'<input name="imagehash" value="{hash_value}">'
                f'<img src="image.php?action=regimage&amp;imagehash={hash_value}">'
                '<input name="imagestring" value=""><button>签到</button></form>')
    return f'<div class="alert">{message}</div>{form}'


class Http:
    """提交响应只留切片（模拟 NativeHttpClient.last_post），回读页面照旧走 get。"""

    def __init__(self, pages, note=None):
        self.pages, self.calls = iter(pages), []
        self.last_post = note

    def get(self, url):
        self.calls.append(('get', url))
        return LoginPage(next(self.pages), url)

    def post(self, url, *, data, referer=None):
        self.calls.append(('post', url, list(data), referer))
        return LoginPage('已提交', url)


def context(site, http, ocr=None):
    return SignContext(site.id, Credential('managed_site', 'synthetic'), http,
                       ocr=ocr or Mock(return_value='Ab1234'))


def test_browser_ua_keeps_a_real_browser_ua():
    ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36'
    assert browser_ua(ua) == ua


def test_browser_ua_falls_back_for_empty_plugin_and_library_defaults():
    for value in (None, '', '   ', 'MoviePilot Plugin/AutoPtCheckin', 'python-requests/2.32.3'):
        assert browser_ua(value).startswith('Mozilla/5.0')
    assert 'Plugin/' not in browser_ua('Mozilla/5.0 MoviePilot Plugin/AutoPtCheckin')


def test_response_note_flags_a_rejected_captcha_submission():
    note = response_note(LoginPage('您輸入的驗證碼不正確 驗證碼 <form>imagehash</form> imagestring', 'x'))
    assert note['still_captcha'] is True
    assert '驗證碼' in note['snippet']


def test_response_note_keeps_a_success_snippet_and_handles_a_missing_page():
    note = response_note(LoginPage('<b>簽到成功</b>，已連續簽到 33 天', 'x'))
    assert note['still_captcha'] is False
    assert '簽到成功' in note['snippet'] and '連續' in note['snippet']
    assert response_note(None) == {'status': None, 'still_captcha': False, 'snippet': ''}


def test_native_client_records_the_post_note():
    client = NativeHttpClient(Credential('managed_site', 'synthetic'), {'ua': None, 'url': 'https://x.invalid/'})
    client._request = lambda method, url, **kwargs: LoginPage('验证码错误 imagehash imagestring', url)
    client.post('https://x.invalid/attendance.php', data=[('imagehash', 'h')])
    assert client.last_post['still_captcha'] is True and client.last_post['status'] == 200


def test_captcha_trace_records_the_recognized_code():
    site = get_native_module(SID)
    http = Http([page('未签到')])
    ctx = context(site, http)
    form = site.discover_form(ctx, LoginPage(page('未签到'), site.url + 'attendance.php'))
    assert site.solve_captcha(ctx, LoginPage(page('未签到'), site.url + 'attendance.php'), form) is True
    assert ctx.captcha_trace == {'code': 'Ab1234', 'engine': 'ddddocr', 'length': 6}


def test_captcha_trace_records_why_the_image_was_unusable():
    site = get_native_module(SID)
    ctx = context(site, Http([]))
    broken = ('<form method="post" action="attendance.php"><input name="csrf" value="s">'
              '<input name="imagestring" value=""></form>')
    form = site.discover_form(ctx, LoginPage(broken, site.url + 'attendance.php'))
    assert solve_attendance_captcha(ctx, LoginPage(broken, site.url + 'attendance.php'), form) is False
    assert ctx.captcha_trace == {'error': 'imagehash_missing'}


def test_captcha_hint_summarizes_trace_and_submit_evidence():
    from autoptcheckin.core.models import SignResult, SignStatus
    result = SignResult(SignStatus.UNCONFIRMED, '已提交签到，但回读未找到成功或已签证据')
    assert captcha_hint(result) == ''
    result.metadata = {'captcha': {'code': 'Ab12', 'engine': 'ddddocr'},
                       'submit': {'status': 200, 'still_captcha': True, 'snippet': 'x'}}
    assert captcha_hint(result) == '最近识别=Ab12/ddddocr，提交 HTTP 200，响应仍是验证码表单'
    result.metadata = {'captcha': {'error': 'ocr_unavailable'}}
    assert captcha_hint(result) == '未取到验证码（ocr_unavailable）'


def test_unconfirmed_captcha_retry_carries_evidence_into_metadata_and_message():
    site = get_native_module(SID)
    note = {'status': 200, 'still_captcha': True, 'snippet': '验证码错误'}
    http = Http([page('未签到'), page('验证码错误', 'h2'), page('未签到', 'h3'), page('验证码错误', 'h4'),
                 page('未签到', 'h5'), page('验证码错误', 'h6')], note=note)
    result = site.signin(context(site, http))
    assert result.status == 'unconfirmed'
    assert result.metadata['captcha'] == {'code': 'Ab1234', 'engine': 'ddddocr', 'length': 6}
    assert result.metadata['submit'] == note
    assert result.message.endswith('（验证码已重试 3 次仍无成功证据；最近识别=Ab1234/ddddocr，'
                                   '提交 HTTP 200，响应仍是验证码表单）')


def test_single_attempt_captcha_failure_still_reports_the_reason():
    site = get_native_module(SID)
    # 提交后站点不再给验证码表单 → 不重试（attempts=1），识别现场仍要带出来。
    result = site.signin(context(site, Http([page('未签到'), page('验证码被拒绝', captcha=False)])))
    assert result.status == 'unconfirmed'
    assert result.metadata['captcha'] == {'code': 'Ab1234', 'engine': 'ddddocr', 'length': 6}
    assert result.message.endswith('（最近识别=Ab1234/ddddocr）')
