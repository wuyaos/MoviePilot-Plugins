"""Maintenance classification is limited to safe pre-action response prefixes."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[3] / "plugins.v3"))

from contextlib import nullcontext
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from autoptcheckin.core import native
from autoptcheckin.core.api_signin import ApiSignin
from autoptcheckin.core.custom import CustomNexusSignin
from autoptcheckin.core.get_signin import GetSignin
from autoptcheckin.core.models import LoginPage, SignStatus
from autoptcheckin.core.nexus import NexusSignin
from autoptcheckin.core.registry import discover_sites, get_native_module
from autoptcheckin.core.sitemodel import page_maintenance
from test_sign_status import URL, site
from test_get_signin_c2 import context


PAGES = [
    LoginPage(text, URL) for text in ('维护中', '站点维护', '正在维护', '站点已关闭',
                                    'Temporarily Unavailable', 'SITE IS DOWN', 'Under Maintenance')
]

# 2026-10-23 用户裁决：维护只认响应体文案；HTTP 403/502/503/404 一律归站点不可达。
HTTP_ERROR_PAGES = [LoginPage('denied', URL, code) for code in (403, 502, 503, 404)]


@pytest.mark.parametrize('kind', [NexusSignin, GetSignin, ApiSignin, CustomNexusSignin])
@pytest.mark.parametrize('page', PAGES)
def test_maintenance_pre_read_never_submits(kind, page):
    obj, http = site(kind), Mock()
    http.get.return_value = page
    result = obj.signin(context(obj, http))
    assert result.status == SignStatus.MAINTENANCE
    assert result.message == '维护中/已关闭'
    assert http.get.call_count == 1
    http.post.assert_not_called()


@pytest.mark.parametrize('page', HTTP_ERROR_PAGES)
def test_http_errors_are_network_error_not_maintenance(page):
    obj, http = site(NexusSignin), Mock()
    http.get.return_value = page
    result = obj.signin(context(obj, http))
    assert result.status == SignStatus.NETWORK_ERROR
    http.post.assert_not_called()


@pytest.mark.parametrize('page', PAGES)
def test_native_verify_maintenance_recorded_once(monkeypatch, page):
    monkeypatch.setattr(native, 'cookiecloud_candidate', lambda url: SimpleNamespace(credential=None))
    obj, http = site(NexusSignin), Mock()
    http.get.return_value = page
    runner = SimpleNamespace(locks=SimpleNamespace(acquire=lambda key: nullcontext(True)),
                             stop=Event(), history=Mock(), notify=None)
    result = native.run_native(runner, obj, {'url': obj.url, 'cookie': 'synthetic'},
                               read_only=True, context_factory=lambda *args: context(obj, http))
    assert result.status == SignStatus.MAINTENANCE
    runner.history.assert_called_once_with(result)
    assert http.get.call_count == 1


@pytest.mark.parametrize('prefix', ['x' * 2048, '中' * 683])
def test_maintenance_text_outside_first_2kib_is_ignored(prefix):
    assert not page_maintenance(LoginPage(prefix + '维护中', URL))
    assert page_maintenance(LoginPage('x' * (2048 - len('维护中'.encode('utf-8'))) + '维护中', URL))


@pytest.mark.parametrize('error', [TimeoutError('private'), OSError('DNS lookup failed')])
def test_transport_exception_remains_network_error(error):
    obj, http = site(NexusSignin), Mock()
    http.get.side_effect = error
    assert obj.signin(context(obj, http)).status == SignStatus.NETWORK_ERROR
    http.post.assert_not_called()


def test_post_submit_maintenance_is_still_unconfirmed():
    obj, http = site(NexusSignin), Mock()
    http.get.side_effect = [LoginPage('<form method="post"><input name="submit" value="sign"></form>', URL),
                            LoginPage('维护中', URL, 503)]
    result = obj.signin(context(obj, http))
    assert result.status == SignStatus.UNCONFIRMED
    http.post.assert_called_once()
    assert http.get.call_count == 2


@pytest.mark.parametrize('site_id', ['phoenixpt'])
def test_closed_sites_registry_signin_not_applicable(site_id):
    row = next(row for row in discover_sites()['sites'] if row['id'] == site_id)
    assert row['signin_applicable'] is False
    assert row['signin_capable'] is False


@pytest.mark.parametrize('site_id', ['phoenixpt'])
def test_closed_sites_signin_skips_without_request(site_id):
    obj, http = get_native_module(site_id), Mock()
    assert obj.signin(context(obj, http)).status == SignStatus.SKIPPED
    assert not http.mock_calls
