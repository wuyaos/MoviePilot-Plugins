"""真实 curl_cffi 本地回环：SRP 双向证据、HttpOnly Cookie/JWT 恢复、HMAC 与新 GET。

此文件替代旧浏览器测试；只连接本地服务器，无真实猪猪请求。
"""
import hashlib
import hmac
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
from autoptcheckin.integrations import piggo as flow
from autoptcheckin.integrations import piggo_srp as srp
from autoptcheckin.core.models import LoginStatus, SignStatus
from autoptcheckin.sites.native.piggo import Piggo


@pytest.mark.parametrize('mode', ['today', 'checked', 'read_only', 'rejected'])
def test_http_login_restore_and_today_only(monkeypatch, tmp_path, mode):
    from curl_cffi import CurlOpt, requests
    config = {'piggo_username': 'fixture-user', 'piggo_password': 'fixture-password'}
    server = {'checked': mode == 'checked', 'login': 0, 'claim': 0, 'calendar': 0, 'errors': []}
    salt, private = bytes.fromhex('00112233445566778899aabbccddeeff'), 987654321
    H = lambda *args: hashlib.sha256(b''.join(args)).digest()
    pad = lambda n: n.to_bytes(256, 'big')
    x = int.from_bytes(H(salt, H(b'fixture-user:', hashlib.pbkdf2_hmac('sha256', b'fixture-password', salt, 210000))), 'big')
    verifier = pow(2, x, srp.N)
    k = int.from_bytes(H(bytes.fromhex(srp.N_HEX), pad(2)), 'big')
    public = (k * verifier + pow(2, private, srp.N)) % srp.N
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            self.handle_api('GET')
        def do_POST(self):
            self.handle_api('POST')
        def handle_api(self, method):
            try:
                path = self.path.removeprefix('/v1/web')
                payload = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))) or b'{}')
                cookie = None
                if path == '/auth/guest-config':
                    data = {'srp': True}
                elif path == '/auth/srp/challenge':
                    assert payload == {'username': 'fixture-user'}
                    data = {'s': salt.hex(), 'B': pad(public).hex(), 'ticket': 'fixture-ticket'}
                elif path == '/auth/srp/login':
                    server['login'] += 1
                    a = int(payload['a'], 16)
                    u = int.from_bytes(H(pad(a), pad(public)), 'big')
                    key = H(pad(pow(a * pow(verifier, u, srp.N) % srp.N, private, srp.N)))
                    xor = bytes(a ^ b for a, b in zip(H(bytes.fromhex(srp.N_HEX)), H(pad(2))))
                    m1 = H(xor, H(b'fixture-user'), salt, pad(a), pad(public), key)
                    assert hmac.compare_digest(payload['m1'], m1.hex())
                    data = {'m2': H(pad(a), m1, key).hex(), 'token': 'fixture-token', 'sign': 'a' * 64}
                    cookie = 'pigo_np_web_session=fixture-cookie; Path=/; HttpOnly'
                else:
                    assert self.headers['Authorization'] == 'Bearer fixture-token'
                    assert 'pigo_np_web_session=fixture-cookie' in self.headers.get('Cookie', '')
                    if path == '/auth/sign':
                        data = {'sign': 'a' * 64}
                    else:
                        canonical = '\n'.join((method, self.path.strip('/').lower(), self.headers['ts'], self.headers['X-Spa-Nonce']))
                        expected = hmac.new(b'a' * 64, canonical.encode(), hashlib.sha256).hexdigest()
                        assert self.headers['X-Spa-Hmac'] == expected
                        if path == '/calendar/attendance':
                            assert method == 'POST' and payload == {'ymd': '2026-11-01'}
                            server['claim'] += 1
                            if mode != 'rejected':
                                server['checked'] = True
                        else:
                            assert path == '/calendar' and method == 'GET'
                            server['calendar'] += 1
                        data = {'selected': '2026-11-01',
                                'cells': [{'ymd': '2026-11-01', 'is_today': True, 'checked': server['checked']}],
                                'detail': {'ymd': '2026-11-01', 'attendance': {'status': 'checked' if server['checked'] else 'today'}}}
                encoded = json.dumps({'code': 0, 'data': data}).encode()
                self.send_response(200)
                if cookie:
                    self.send_header('Set-Cookie', cookie)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)
            except Exception as exc:
                server['errors'].append(type(exc).__name__)
                self.send_error(500)
    http = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=http.serve_forever, daemon=True)
    thread.start()
    port = http.server_address[1]
    monkeypatch.setattr(flow, 'ORIGIN', f'http://piggo.me:{port}')
    monkeypatch.setattr(flow, 'state_path', lambda: tmp_path / 'piggo.json')
    monkeypatch.setattr(flow, 'new_session', lambda proxy: requests.Session(
        impersonate='chrome', trust_env=False,
        curl_options={CurlOpt.RESOLVE: [f'piggo.me:{port}:127.0.0.1'.encode()]}))
    try:
        login = flow.run_piggo(Piggo(), {}, config=config, action='login')
        assert login.status == LoginStatus.LOGIN_OK, login.message
        saved = json.loads((tmp_path / 'piggo.json').read_text())
        assert saved['token'] == 'fixture-token'
        assert saved['cookies'][0]['rest'].get('http_only') == 'True'
        result = flow.run_piggo(Piggo(), {}, config=config, action='sign', read_only=mode == 'read_only')
        expected = {'today': SignStatus.SUCCESS, 'checked': SignStatus.ALREADY,
                    'read_only': SignStatus.UNCONFIRMED, 'rejected': SignStatus.UNCONFIRMED}
        assert result.status == expected[mode], result.message
        assert server['login'] == 1 and server['claim'] == (1 if mode in ('today', 'rejected') else 0)
        assert server['calendar'] >= 2 and not server['errors']
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=5)
