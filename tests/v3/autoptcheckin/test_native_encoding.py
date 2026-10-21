"""Synthetic HTTP bytes, including requests' implicit ISO-8859-1 default."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
from autoptcheckin.core.credentials import Credential
from autoptcheckin.core.native import NativeHttpClient, decode_response


def response(content, header='text/html'):
    value = requests.Response()
    value._content = content
    value.headers['Content-Type'] = header
    value.encoding = 'ISO-8859-1'
    value.status_code = 200
    value.url = 'https://fixture.invalid/'
    return value


def test_native_http_ignores_implicit_latin1(monkeypatch):
    value = response('已签到'.encode('utf-8'))
    assert value.text != '已签到'
    monkeypatch.setitem(sys.modules, 'app.sdk.config', SimpleNamespace(settings=SimpleNamespace(PROXY=None)))
    monkeypatch.setitem(sys.modules, 'app.sdk.network', SimpleNamespace(
        RequestUtils=lambda **kw: SimpleNamespace(get_res=lambda **args: value)))
    page = NativeHttpClient(Credential('managed_site', 'fixture=1'), {}).get(value.url)
    assert page.text == '已签到'


@pytest.mark.parametrize('content,header,expected', [
    ('已签到'.encode('utf-8-sig'), 'text/html', '已签到'),
    ('已签到'.encode('gbk'), 'text/html; charset=GBK', '已签到'),
    ('已签到'.encode('gbk'), 'text/html', '已签到'),
    ('café'.encode('latin-1'), 'text/html; charset="ISO-8859-1"', 'café'),
    (b'plain ASCII', 'text/html', 'plain ASCII'),
    (b'\xff', 'text/html', '\ufffd'),
    ('已签到'.encode('utf-8'), 'text/html; charset=unknown', '已签到'),
])
def test_decode_response_charset_precedence(content, header, expected):
    assert decode_response(response(content, header)) == expected
