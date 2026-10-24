"""Sanitized structural excerpts from the 3.20 calibration, never live requests."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / "plugins.v3"))

import pytest

from autoptcheckin.core.models import LoginPage
from autoptcheckin.core.registry import get_native_module
from test_get_signin_c2 import Http, context, signed, before, actions


SIGNED = {
    'audiences': '<h1 class="attendance-hero__title">每日签到</h1><h2 class="attendance-card__title">今天已签到</h2>',
    'baozi': '<a class="userbar__bonus-hint userbar__bonus-hint--attended" href="attendance.php">[签到已得3000, 补签卡: 1]</a>',
    'discfan': '<a href="attendance.php">[簽到已得300, 補簽卡: 1]</a><h2>簽到成功</h2>',
    'ptfans': '<h2>签到成功</h2><h2>签到勋章</h2><a href="attendance.php">[签到已得435, 补签卡: 1]</a>',
    'tu88': '<a href="attendance.php">[簽到已得145, 補簽卡: 0]</a>',
    'lpbits': '<a href="attendance.php">[Attend got: 290, card: 0]</a>',
    'ptzone': '<a href="attendance.php">[簽到已得660, 補簽卡: 1]</a>',
}


@pytest.mark.parametrize('sid', SIGNED)
@pytest.mark.parametrize('state', ['signed', 'unsigned', 'unknown'])
def test_calibrated_page_states(sid, state):
    site = get_native_module(sid)
    text = SIGNED[sid] if state == 'signed' else '<a href="attendance.php">签到</a>' if state == 'unsigned' else '<main>maintenance</main>'
    page = LoginPage(text, site.url + 'attendance.php')
    ctx = context(site, None)
    # No unsigned production message was observed: absence stays unknown, never failed.
    assert site.read_before(ctx, page).status == ('already' if state == 'signed' else 'unconfirmed')
    assert site.read_after(ctx, page).status == ('success' if state == 'signed' else 'unconfirmed')


def test_haitang_primary_form_excludes_calendar_duplicate():
    site = get_native_module('haitang')
    primary = '<form method="post" action="attendance.php"><input name="action" value="sign"><button type="submit"><b>立即签到（连续第 2 天）</b></button></form>'
    calendar = '<form method="post" action="attendance.php"><input name="action" value="sign"><button type="submit" class="att-link">签到</button></form>'
    page = LoginPage(primary + calendar, site.url + 'attendance.php')
    form = site.discover_form(None, page)
    assert form.data == [('action', 'sign')]
    assert site.discover_form(None, LoginPage(primary * 2, page.url)) is None
    http = Http(site, '<span><b>今日已签到</b></span>', initial=page.text)
    assert site.signin(context(site, http)).status == 'success'
    assert len(actions(http)) == 1 and http.reads == 2


@pytest.mark.parametrize('fresh,expected', [('signed', 'success'), ('entry', 'unconfirmed'), ('blocked', 'unconfirmed')])
def test_btschool_inverse_entry_requires_authenticated_homepage(fresh, expected):
    site = get_native_module('btschool')
    text = signed('btschool') if fresh == 'signed' else before('btschool') if fresh == 'entry' else '<title>403 Forbidden</title>'
    http = Http(site, text)
    assert site.signin(context(site, http)).status == expected
    assert len(actions(http)) == 1 and http.reads == 2
    blocked = Http(site, '', initial='<title>403 Forbidden</title>')
    assert site.signin(context(site, blocked)).status == 'protocol_pending'
    assert not actions(blocked)


def test_pttime_history_today_not_old_day_or_whole_page_text():
    site = get_native_module('pttime')
    yesterday = (datetime.now(ZoneInfo('Asia/Shanghai')) - timedelta(days=1)).strftime('%Y%m%d')
    for text in [f'<span class="ml10">签到日：{yesterday}</span>', '<p>拒绝访问：已签到，无需再签</p>', '<body>签到成功</body>']:
        assert site.read_before(context(site, None), LoginPage(text, site.url + site.attendance_path)).status == 'unconfirmed'
    assert site.read_before(context(site, None), LoginPage(signed('pttime'), site.url + site.attendance_path)).status == 'already'
    http = Http(site, signed('pttime'))
    assert site.signin(context(site, http)).status == 'success'
    assert http.calls[0][1].endswith('?type=list') and http.calls[-1][1].endswith('?type=list')
    assert len(actions(http)) == 1


def test_retrotoon_claim_ignores_timezone_form():
    site = get_native_module('retrotoon')
    claim = '<form method="post"><input name="csrf_token" value="fixture"><input type="submit" name="claim" value="Claim Daily Reward"></form>'
    timezone = '<form id="tz-detect" method="post" action="attendance.php"><input name="csrf_token" value="fixture"><input name="set_tz" value="1"><input name="tz"></form>'
    page = LoginPage(claim + timezone, site.url + 'attendance.php')
    assert dict(site.discover_form(None, page).data) == {'csrf_token': 'fixture', 'claim': 'Claim Daily Reward'}
    assert site.discover_form(None, LoginPage(claim * 2 + timezone, page.url)) is None


def test_slow_and_headful_cloak_declarations_are_preserved():
    yema = get_native_module('yema')
    piggo = get_native_module('piggo')
    vclib = get_native_module('vclib')
    assert yema.slow is True and yema.slow_timeout == 90000
    assert piggo.headful is True and vclib.headful is True


def test_yema_signin_capability_and_login_are_enabled():
    site = get_native_module('yema')
    assert site.signin_capable is True
    assert site.login_capable is True
    assert site.cloak_steps == ['altcha', 'sign_button']
