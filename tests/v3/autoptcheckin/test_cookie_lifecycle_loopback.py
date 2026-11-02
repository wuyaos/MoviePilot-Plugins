"""Real transports and loopback servers only; synthetic cookies, no external accounts."""
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from types import ModuleType, SimpleNamespace

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
from autoptcheckin.core.credentials import Credential
from autoptcheckin.core.models import LoginResult
from autoptcheckin.core.native import NativeHttpClient, persist_cookie_result


@pytest.fixture
def loopback(monkeypatch):
    # Exercise NativeHttpClient's RequestUtils boundary using a real requests.Session.
    class RequestUtils:
        def __init__(self, session, **options):
            self.session, self.options = session, options

        def get_res(self, url, **kwargs):
            return self.session.get(url, cookies=self.options['cookies'], timeout=3, **kwargs)

    sdk = ModuleType('app.sdk'); sdk.__path__ = []
    app = ModuleType('app'); app.__path__ = []; app.sdk = sdk
    config = ModuleType('app.sdk.config'); config.settings = SimpleNamespace(PROXY=None)
    network = ModuleType('app.sdk.network'); network.RequestUtils = RequestUtils
    for name, module in [('app', app), ('app.sdk', sdk), ('app.sdk.config', config), ('app.sdk.network', network)]:
        monkeypatch.setitem(sys.modules, name, module)
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            seen.append((self.path, self.headers.get('Cookie', '')))
            redirect = None
            cookies = []
            if self.path == '/rotate':
                cookies = ['sid=fresh; Path=/']
            elif self.path == '/delete':
                cookies = ['sid=; Max-Age=0; Path=/']
            elif self.path == '/redirect':
                cookies = ['sid=redirected; Path=/']
                redirect = '/echo'
            elif self.path == '/private/set':
                cookies = ['sid=private; Path=/private']
            elif self.path == '/cross':
                redirect = f'http://localhost:{self.server.server_port}/foreign'
            elif self.path == '/foreign':
                cookies = ['foreign=other-host; Path=/', 'sid=foreign; Path=/']
            self.send_response(302 if redirect else 200)
            if redirect:
                self.send_header('Location', redirect)
            for value in cookies:
                self.send_header('Set-Cookie', value)
            self.end_headers()
            self.wfile.write(b'fixture')

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = Thread(target=server.serve_forever, daemon=True); worker.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', seen
    finally:
        server.shutdown(); server.server_close(); worker.join(timeout=5)
        assert not worker.is_alive()


@pytest.fixture(params=['requests', 'cffi'])
def client(request, loopback):
    base, seen = loopback
    # Ignore machine proxy settings for these loopback-only tests.
    session = requests.Session(); session.trust_env = False
    with NativeHttpClient(Credential('fixture', 'sid=initial; keep=unchanged'),
                          {'url': base, 'impersonate': request.param == 'cffi'}, session=session) as http:
        yield http, base, seen
    session.close()


def test_replacement_is_sent_once_and_persisted(client):
    http, base, seen = client
    http.get(base + '/rotate'); http.get(base + '/echo')
    assert seen[-1][1].count('sid=') == 1
    assert 'sid=fresh' in seen[-1][1]
    assert http.cookies == {'sid': 'fresh', 'keep': 'unchanged'}
    data = {}
    persist_cookie_result(LoginResult('login_ok'), http, 'fixture', 'stored_cookie', data.get, data.__setitem__)
    assert 'sid=fresh' in data['cookies.table']['fixture']['cookie']


def test_deletion_does_not_resurrect_initial_cookie(client):
    http, base, seen = client
    http.get(base + '/rotate'); http.get(base + '/delete'); http.get(base + '/echo')
    assert 'sid=' not in seen[-1][1]
    assert http.cookies == {'keep': 'unchanged'}
    data = {}
    persist_cookie_result(LoginResult('login_ok'), http, 'fixture', 'stored_cookie', data.get, data.__setitem__)
    assert data['cookies.table']['fixture']['cookie'] == 'keep=unchanged'


def test_redirect_cookie_replaces_initial_without_duplicate(client):
    http, base, seen = client
    http.get(base + '/redirect'); http.get(base + '/echo')
    assert all(cookie.count('sid=') == 1 and 'sid=redirected' in cookie
               for path, cookie in seen if path == '/echo')
    assert http.cookies['sid'] == 'redirected'


def test_private_path_cookie_stays_private_and_is_not_flattened(client):
    http, base, seen = client
    http.get(base + '/private/set'); http.get(base + '/private/echo'); http.get(base + '/echo')
    private = next(cookie for path, cookie in seen if path == '/private/echo')
    assert 'sid=private' in private
    assert 'sid=private' not in seen[-1][1] and 'sid=initial' in seen[-1][1]
    # The flat cross-round table can represent root cookies only, never widen private ones.
    assert http.cookies == {'sid': 'initial', 'keep': 'unchanged'}


def test_foreign_redirect_cookie_never_leaks_to_site_or_table(client):
    http, base, seen = client
    http.get(base + '/cross'); http.get(base + '/echo')
    assert 'sid=' not in next(cookie for path, cookie in seen if path == '/foreign')
    assert 'foreign=' not in seen[-1][1]
    assert http.cookies == {'sid': 'initial', 'keep': 'unchanged'}


def test_browser_removal_is_respected_by_next_http_submit_session(client):
    from autoptcheckin.core.cloak import CloakHttpClient
    http, base, seen = client
    http.get(base + '/rotate')
    browser = object.__new__(CloakHttpClient)
    browser.http, browser.url = http, base + '/private/page'
    class Context:
        def cookies(self, url):
            assert url == base + '/'
            return [{'name': 'keep', 'value': 'unchanged', 'domain': '127.0.0.1', 'path': '/'},
                    {'name': 'private', 'value': 'not-root', 'domain': '127.0.0.1', 'path': '/private'}]
    browser.session = SimpleNamespace(context=Context())
    browser._sync_cookies()
    http.get(base + '/echo')
    assert http.cookies == {'keep': 'unchanged'}
    assert 'sid=' not in seen[-1][1] and 'private=' not in seen[-1][1]


def test_explicit_cookie_rotation_and_retain_keep_scoped_session(client):
    http, base, seen = client
    http.get(base + '/echo')
    http.cookies['sid'] = 'explicitly-refreshed'
    http.get(base + '/echo')
    assert seen[-1][1].count('sid=') == 1 and 'sid=explicitly-refreshed' in seen[-1][1]
    http.retain_cookies({'keep'})
    http.get(base + '/echo')
    assert seen[-1][1] == 'keep=unchanged'
