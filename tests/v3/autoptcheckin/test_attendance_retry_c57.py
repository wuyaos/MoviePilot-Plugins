"""C57: 验证码站「识别+提交」有界重试（合成页面，不发真实请求，不调真实 OCR）。"""
import sys
from pathlib import Path
from unittest.mock import Mock


sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
from autoptcheckin.core.credentials import Credential
from autoptcheckin.core.models import LoginPage
from autoptcheckin.core.nexus import NexusSignin
from autoptcheckin.core.registry import get_native_module
from autoptcheckin.core.sitemodel import RecordSpec, SignContext

SID = 'kelu'


def page(message, hash_value='h1', captcha=True):
    """签到页：消息节点 + 可选 NexusPHP 验证码表单（imagehash/imagestring/image.php）。"""
    form = ''
    if captcha:
        form = ('<form method="post" action="attendance.php">'
                '<input name="csrf" value="synthetic">'
                f'<input name="imagehash" value="{hash_value}">'
                f'<img src="image.php?action=regimage&amp;imagehash={hash_value}">'
                '<input name="imagestring" value=""><button>签到</button></form>')
    return f'<div class="alert">{message}</div>{form}'


def rejected(hash_value='h2'):
    """提交被拒：站点重新给出未签到的验证码表单，没有任何已签/成功证据。"""
    return page('验证码错误', hash_value)


class Http:
    def __init__(self, pages):
        self.pages, self.calls = iter(pages), []

    def get(self, url):
        self.calls.append(('get', url))
        return LoginPage(next(self.pages), url)

    def post(self, url, *, data, referer=None):
        self.calls.append(('post', url, list(data), referer))
        return LoginPage('已提交', url)

    @property
    def posts(self):
        return [call for call in self.calls if call[0] == 'post']


def context(site, http, ocr=None):
    return SignContext(site.id, Credential('managed_site', 'synthetic'), http,
                       ocr=ocr or Mock(return_value='Ab1234'))


def test_captcha_retry_submits_again_after_an_unsolved_attempt():
    site = get_native_module(SID)
    http = Http([page('未签到'), rejected(), page('未签到', 'h3'), page('签到成功')])
    result = site.signin(context(site, http))
    assert result.status == 'success'
    assert len(http.posts) == 2
    assert [call[0] for call in http.calls] == ['get', 'post', 'get', 'get', 'post', 'get']
    assert result.metadata['signin_attempts'] == 2


def test_captcha_retry_is_bounded_and_reports_the_attempt_count():
    site = get_native_module(SID)
    pages = [page('未签到'), rejected(), page('未签到', 'h3'), rejected('h4'),
             page('未签到', 'h5'), rejected('h6')]
    result = site.signin(context(site, Http(pages)))
    assert result.status == 'unconfirmed'
    assert result.message == ('已提交签到，但回读未找到成功或已签证据（页面提示：验证码错误）'
                              '（验证码已重试 3 次仍无成功证据；最近识别=Ab1234/ddddocr）')
    assert result.metadata['signin_attempts'] == 3


def test_successful_first_attempt_records_no_attempt_metadata():
    site = get_native_module(SID)
    http = Http([page('未签到'), page('签到成功', captcha=False)])
    result = site.signin(context(site, http))
    assert result.status == 'success'
    assert 'signin_attempts' not in (result.metadata or {})
    assert len(http.posts) == 1


def test_already_signed_page_is_never_submitted_again():
    site = get_native_module(SID)
    http = Http([page('未签到'), page('今天已经签到', captcha=False)])
    result = site.signin(context(site, http))
    assert result.status == 'success'
    assert len(http.posts) == 1


def test_explicit_unsigned_answer_is_not_retried_at_site_level():
    """回读明确拿到「未签到」时结果归 FAILED，当场重试由 runner 的 retry_count 负责。"""
    site = get_native_module(SID)
    http = Http([page('未签到'), page('未签到', 'h3')])
    result = site.signin(context(site, http))
    assert result.status == 'failed'
    assert len(http.posts) == 1
    assert 'signin_attempts' not in (result.metadata or {})


def test_cancel_before_submit_stops_the_retry_loop():
    site = get_native_module(SID)
    ctx = context(site, Http([page('未签到'), rejected()]))
    ctx.cancel.set()
    result = site.signin(ctx)
    assert result.status == 'cancelled'
    assert result.message == '任务已取消'


class ActionSite(NexusSignin):
    id = 'fixture-action'
    name = 'Fixture Action'
    url = 'https://fixture.invalid/'
    attendance_path = '/attendance.php'
    record_spec = RecordSpec('batch2-message-pending-calibration', {})
    cloak_steps = ('sign_button',)

    def submit(self, ctx, form):
        """合成替身：真实页面动作站由 CloakBrowser 会话提交，不走 http POST。"""


def test_page_action_sites_keep_a_single_attempt():
    site = ActionSite()
    http = Http([page('未签到'), rejected()])
    result = site.signin(context(site, http))
    assert result.status == 'unconfirmed'
    assert http.posts == []
    assert [call[0] for call in http.calls] == ['get', 'get']
    assert 'signin_attempts' not in (result.metadata or {})


def test_captcha_attempts_defaults_to_three():
    assert NexusSignin().captcha_attempts == 3
