"""Actual curl_cffi transport against loopback only; no remote sites or accounts."""
import json
import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from types import ModuleType, SimpleNamespace
from urllib.parse import parse_qs
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
from autoptcheckin.core.native import NativeHttpClient
from autoptcheckin.core.credentials import Credential


def test_actual_cffi_preserves_body_headers_and_redirect_image_session(monkeypatch):
    from curl_cffi import requests
    assert requests.Session.__module__.startswith('curl_cffi.')
    sdk = ModuleType('app.sdk'); sdk.__path__ = []
    app = ModuleType('app'); app.__path__ = []; app.sdk = sdk
    config = ModuleType('app.sdk.config'); config.settings = SimpleNamespace(PROXY=None)
    network = ModuleType('app.sdk.network')
    network.RequestUtils = Mock(side_effect=AssertionError('No standard HTTP fallback'))
    sdk.config = config; sdk.network = network
    for name, module in [('app', app), ('app.sdk', sdk), ('app.sdk.config', config), ('app.sdk.network', network)]:
        monkeypatch.setitem(sys.modules, name, module)
    seen = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            seen.append(('GET', self.path, dict(self.headers), b''))
            if self.path == '/form':
                self.send_response(302)
                self.send_header('Location', '/landing')
                self.send_header('Set-Cookie', 'flow=one; Path=/')
                self.end_headers()
            else:
                self.send_response(200)
                if self.path == '/image':
                    self.send_header('Set-Cookie', 'image=fresh; Path=/')
                self.end_headers(); self.wfile.write(b'image' if self.path == '/image' else b'fixture')
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
            seen.append(('POST', self.path, dict(self.headers), body))
            self.send_response(201); self.end_headers(); self.wfile.write(b'{"accepted":true}')
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = Thread(target=server.serve_forever, daemon=True); worker.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with NativeHttpClient(Credential('fixture', 'sid=fixture'), {'url': base, 'impersonate': True}) as http:
            page = http.get(base + '/form')
            assert page.url == base + '/landing' and http.cookies['flow'] == 'one'
            assert http.get_bytes(base + '/image', referer=page.url) == b'image'
            http.post(base + '/claim', data=[('claim', '1'), ('tag', 'a'), ('tag', 'b')],
                      headers={'X-CSRF-Token': 'fixture'}, referer=page.url)
            http.post(base + '/claim', json={'mode': 'fixed'}, headers={'X-CSRF-Token': 'fixture'})
        form, payload = [row for row in seen if row[0] == 'POST']
        assert parse_qs(form[3].decode()) == {'claim': ['1'], 'tag': ['a', 'b']}
        assert form[2]['X-CSRF-Token'] == 'fixture' and form[2]['Referer'] == base + '/landing'
        assert 'flow=one' in form[2]['Cookie'] and 'image=fresh' in form[2]['Cookie']
        assert json.loads(payload[3]) == {'mode': 'fixed'}
        assert payload[2]['X-CSRF-Token'] == 'fixture'
        image = next(row for row in seen if row[1] == '/image')
        assert image[2]['Referer'] == base + '/landing' and 'flow=one' in image[2]['Cookie']
        network.RequestUtils.assert_not_called()
    finally:
        server.shutdown(); server.server_close(); worker.join(timeout=5)
        assert not worker.is_alive()
