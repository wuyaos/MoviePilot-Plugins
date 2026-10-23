import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[3] / "plugins.v3"))
from autoptcheckin.integrations import rousi, sunnypt
from autoptcheckin.core.models import LoginStatus


class Response:
    def __init__(self, status, payload):
        self.status_code = status
        self.text = json.dumps(payload)


class Client:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(('GET', url, kwargs))
        return next(self.responses)

    def post(self, url, **kwargs):
        self.calls.append(('POST', url, kwargs))
        return next(self.responses)


def test_rousi_claimed_today_avoids_submit():
    client = Client([Response(200, {'user': {'id': 7}, 'csrf_token': 'x'}),
                     Response(200, {'claimed_today': True})])
    assert rousi.signin(client, {}).status == 'already'
    assert [call[0] for call in client.calls] == ['GET', 'GET']


def test_rousi_signs_with_csrf_idempotency_and_headers():
    client = Client([Response(200, {'user': {'id': 7}, 'csrf_token': 'csrf'}),
                     Response(200, {'claimed_today': False}),
                     Response(200, {'success': True})])
    assert rousi.signin(client, {}).status == 'success'
    headers = client.calls[-1][2]['headers']
    assert headers['Origin'] == rousi.BASE
    assert headers['Referer'] == rousi.BASE + '/account/economy'
    assert headers['X-CSRF-Token'] == 'csrf' and headers['Idempotency-Key']


def test_rousi_refreshes_invalid_session_then_signs():
    client = Client([Response(401, {}), Response(401, {}),
                     Response(200, {'user': {'id': 7}, 'csrf_token': 'csrf'}),
                     Response(200, {'user': {'id': 7}, 'csrf_token': 'csrf'}),
                     Response(200, {'claimed_today': False}), Response(200, {'success': True})])
    result = rousi.signin(client, {'rousi_username': 'u', 'rousi_password': 'p'})
    assert result.status == 'success'
    assert client.calls[2][2]['headers']['Origin'] == rousi.BASE


def test_rousi_login_without_credentials_is_auth_failed():
    client = Client([Response(401, {})])
    assert rousi.login(client, {}).status == LoginStatus.AUTH_FAILED


def test_sunnypt_no_credentials_is_auth_failed_without_request():
    client = Client([])
    assert sunnypt.signin(client, {}).status == 'auth_failed'
    assert not client.calls


def test_sunnypt_login_validates_token_or_credentials():
    client = Client([Response(200, {'code': 0, 'data': {'token': 'jwt'}}),
                     Response(200, {'code': 0})])
    result = sunnypt.login(client, {'sunnypt_username': 'u', 'sunnypt_password': 'p'})
    assert result.status == LoginStatus.LOGIN_OK
    assert client.calls[1][2]['headers']['Authorization'] == 'Bearer jwt'


def test_sunnypt_signin_success_and_already():
    client = Client([Response(200, {'code': 0, 'msg': 'done'})])
    assert sunnypt.signin(client, {'sunnypt_token': 'jwt'}).status == 'success'
    assert client.calls[0][2]['headers']['Authorization'] == 'Bearer jwt'
    client = Client([Response(200, {'code': 400001})])
    assert sunnypt.signin(client, {'sunnypt_token': 'jwt'}).status == 'already'


def test_sunnypt_expired_token_relogs_and_retries_once():
    client = Client([Response(200, {'code': 400000}),
                     Response(200, {'code': 0, 'data': {'token': 'fresh'}}),
                     Response(200, {'code': 0, 'msg': 'ok'})])
    result = sunnypt.signin(client, {'sunnypt_username': 'u', 'sunnypt_password': 'p', 'sunnypt_token': 'old'})
    assert result.status == 'success'
    assert [call[0] for call in client.calls] == ['POST', 'POST', 'POST']
    assert client.calls[-1][2]['headers']['Authorization'] == 'Bearer fresh'


def test_sunnypt_expired_token_without_credentials_is_auth_failed():
    client = Client([Response(200, {'code': 400000})])
    assert sunnypt.signin(client, {'sunnypt_token': 'old'}).status == 'auth_failed'


def test_execute_site_routes_integration_sign_and_login(monkeypatch):
    import autoptcheckin as entry
    from autoptcheckin.core.models import SignResult, SignStatus, LoginResult, LoginStatus
    dispatched = []
    def dispatch(runner, site_id, name, info, config, action='sign', trigger='manual'):
        dispatched.append((site_id, action, info.get('cookie')))
        return LoginResult(LoginStatus.LOGIN_OK) if action == 'login' else SignResult(SignStatus.SUCCESS)
    monkeypatch.setattr(entry, 'managed_site', lambda site_id: {'cookie': 'offline-cookie'})
    monkeypatch.setattr(entry, 'run_integration', dispatch)
    plugin = entry.AutoPtCheckin()
    plugin.init_plugin({'enabled_sites': ['rousi', 'sunnypt'], 'sign_sites': ['rousi'], 'login_sites': ['sunnypt']})
    assert plugin._execute_site('rousi')['status'] == 'success'
    assert plugin._execute_site('sunnypt', action='login')['status'] == 'login_ok'
    assert dispatched == [('rousi', 'sign', 'offline-cookie'), ('sunnypt', 'login', 'offline-cookie')]


def test_yzyy_login_reuses_valid_cookie_and_relogins_on_expiry():
    from autoptcheckin.integrations import yzyy
    from autoptcheckin.core.models import LoginResult, LoginStatus

    class FakeHttp:
        def __init__(self, pages):
            self.pages = list(pages)
            self.posts = []
        def get(self, url, **kwargs):
            return self.pages.pop(0)
        def post(self, url, **kwargs):
            self.posts.append((url, kwargs.get('data')))
            return self.pages.pop(0)

    class Page:
        def __init__(self, text):
            self.text = text

    # Cookie 有效：首页含 logout → 直接 LOGIN_OK，不发登录 POST
    http = FakeHttp([Page('index action=logout 退出')])
    result = yzyy.login(http, {'yzyy_username': 'u', 'yzyy_password': 'p'})
    assert result.status == LoginStatus.LOGIN_OK and not http.posts
    # Cookie 失效：无 logout → 登录页 formhash → POST → 首页 logout → LOGIN_OK
    http = FakeHttp([Page('登录'), Page('formhash name="formhash" value="abc123"'),
                     Page('login result'), Page('action=logout 退出')])
    result = yzyy.login(http, {'yzyy_username': 'u', 'yzyy_password': 'p'})
    assert result.status == LoginStatus.LOGIN_OK and len(http.posts) == 1
    # 无账密：AUTH_FAILED
    result = yzyy.login(FakeHttp([Page('登录')]), {})
    assert result.status == LoginStatus.AUTH_FAILED
