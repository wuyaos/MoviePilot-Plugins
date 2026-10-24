"""Regression coverage for attendance transport timing and Shaobaoyuan denial."""
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
from autoptcheckin.core import nexus
from autoptcheckin.core.models import LoginPage, SignStatus
from autoptcheckin.core.state_store import normalize
from autoptcheckin.sites.native.generic import build_generic_sites
from test_get_signin_c2 import context


DENIAL = '<html><head><title>403 Forbidden</title></head><body><center><h1>403 Forbidden</h1></center><hr><center>nginx</center></body></html>'


def site(site_id='shaobaoyuan'):
    obj = next(cls for cls in build_generic_sites() if cls.id == site_id)()
    obj.url = 'https://fixture.invalid/'
    return obj


def test_shaobaoyuan_nginx_denial_is_network_error_without_submission():
    obj, http = site(), Mock()
    http.get.return_value = LoginPage(DENIAL, obj.url, 200)
    result = obj.signin(context(obj, http))
    assert result.status == SignStatus.NETWORK_ERROR
    assert '站点防护页拦截' in result.message
    assert result.metadata['defer_submission'] is True
    assert normalize('sign', result.status) == 'pending'
    assert http.get.call_count == 1
    http.post.assert_not_called()


@pytest.mark.parametrize('body', [
    '<h2>unknown</h2>',
    DENIAL.replace('<title>403 Forbidden</title>', '<title>Site</title>'),
    DENIAL.replace('<h1>403 Forbidden</h1>', '<h1>Site</h1>'),
    DENIAL.replace('<center>nginx</center>', '<center>Site</center>'),
    DENIAL + '<form></form>',
    DENIAL + '<p>' + 'x' * 2048 + '</p>',
])
def test_shaobaoyuan_other_pages_keep_existing_classification(body):
    obj, http = site(), Mock()
    http.get.return_value = LoginPage(body, obj.url, 200)
    result = obj.signin(context(obj, http))
    assert result.status == SignStatus.PROTOCOL_PENDING
    http.post.assert_not_called()


def test_shaobaoyuan_normal_form_still_submits_and_rereads():
    obj, http = site(), Mock()
    obj.solve_captcha = Mock(return_value=True)
    http.get.side_effect = [LoginPage('<form method="post" action="attendance.php"><input name="token" value="fixture"></form>', obj.url), LoginPage('<h2>unknown</h2>', obj.url)]
    result = obj.signin(context(obj, http))
    assert result.status == SignStatus.UNCONFIRMED
    http.post.assert_called_once()
    assert http.get.call_count == 2


def test_nginx_detection_is_limited_to_shaobaoyuan():
    obj, http = site('bilibili'), Mock()
    http.get.return_value = LoginPage(DENIAL, obj.url, 200)
    assert obj.signin(context(obj, http)).status == SignStatus.PROTOCOL_PENDING


@pytest.mark.parametrize('response', [None, TimeoutError('private details'), LoginPage('error', 'https://fixture.invalid/', 503)])
def test_nexus_network_error_reports_front_read_elapsed_only(monkeypatch, response):
    obj, http = site('bilibili'), Mock()
    http.get.side_effect = [response]
    monkeypatch.setattr(nexus, 'monotonic', Mock(side_effect=[100.0, 120.25]))
    result = obj.signin(context(obj, http))
    assert result.status == SignStatus.NETWORK_ERROR
    assert '（20.2s）' in result.message
    assert 'private details' not in result.message
    assert http.get.call_count == 1
    http.post.assert_not_called()
