"""D1 generated declarations exercise the same offline consumer paths as C1-C4."""
import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
from autoptcheckin.core.api_signin import ApiSignin
from autoptcheckin.core.get_signin import GetSignin
from autoptcheckin.core.registry import get_native_module, discover_sites
from autoptcheckin.sites.native import generic
import test_attendance_captcha_c1 as c1
import test_get_signin_c2 as c2
import test_post_api_signin_c34 as c34

CAPTCHA = c1.IDS
GET = 'haidan hdcity hdupt'.split()  # hhanclub 动作页即结果页，单列
POST = ['hdarea', 'nexushd']


@pytest.mark.parametrize('sid', CAPTCHA)
@pytest.mark.parametrize('state', ['success', 'already', 'unconfirmed'])
def test_generic_captcha_three_states(sid, state):
    site = get_native_module(sid)
    pages = [c1.message('今日已簽到')] if state == 'already' else [c1.form_page(), c1.message('簽到已得') if state == 'success' else '<main>签到成功</main>']
    http, ocr = c1.Http(pages), Mock(return_value='Ab1234')
    assert site.signin(c1.context(site, http, ocr)).status == state
    assert site.solve_captcha.__func__ is generic._solve_captcha
    assert [c[0] for c in http.calls] == (['get'] if state == 'already' else ['get', 'post', 'get'])
    if state == 'already':
        ocr.assert_not_called()
    else:
        assert http.calls[1][3] == site.url + 'attendance.php'
        assert dict(http.calls[1][2]) == dict(csrf='synthetic', imagehash='fixture-hash', imagestring='Ab1234')
        assert sum(key == 'imagestring' for key, _ in http.calls[1][2]) == 1


@pytest.mark.parametrize('sid', GET)
@pytest.mark.parametrize('state', ['signed', 'unsigned', 'unknown'])
def test_generic_get_three_states(sid, state):
    site = get_native_module(sid)
    assert isinstance(site, GetSignin)
    fresh = c2.signed(sid) if state == 'signed' else c2.message('未签到') if state == 'unsigned' else '<main>签到成功</main>'
    http = c2.Http(site, fresh)
    expected = 'success' if state == 'signed' and sid != 'btschool' else 'failed' if state == 'unsigned' and sid not in {'btschool', 'haidan'} else 'unconfirmed'
    assert site.signin(c2.context(site, http)).status == expected
    assert len(c2.actions(http)) == 1 and http.reads == 2
    assert http.calls[0][1] == http.calls[-1][1]
    if sid == 'hhanclub':
        assert c2.actions(http)[0][2] == site.url


@pytest.mark.parametrize('state', ['already', 'success', 'unconfirmed'])
def test_hhanclub_visit_signin(state):
    """Same URL for pre-read, action and readback: fixtures follow call order."""
    site = get_native_module('hhanclub')
    signed = '<p class="register-now-info register-info">已连续签到142天，本次签到获得715个憨豆。</p>'
    unsigned = '<main>今日可签到</main>'
    pages = [signed] if state == 'already' else [unsigned, signed, signed if state == 'success' else unsigned]
    http = Mock()
    from autoptcheckin.core.models import LoginPage
    http.get.side_effect = [LoginPage(text, site.url + 'attendance.php') for text in pages]
    assert site.signin(c2.context(site, http)).status == state
    assert http.get.call_count == (1 if state == 'already' else 3)
    assert all(call.args == (site.url + 'attendance.php',) for call in http.get.call_args_list)
    if state != 'already':
        assert http.get.call_args_list[1].kwargs == {'referer': site.url}
    http.post.assert_not_called()


@pytest.mark.parametrize('sid', POST)
@pytest.mark.parametrize('state', ['signed', 'unsigned', 'unknown'])
def test_generic_static_post_three_states(sid, state):
    site = get_native_module(sid)
    fresh = c34.signed(sid) if state == 'signed' else c34.message('未签到') if state == 'unsigned' else '<main>签到成功</main>'
    http = c34.Http(site, fresh=fresh)
    assert site.signin(c34.context(site, http)).status == {'signed': 'success', 'unsigned': 'failed', 'unknown': 'unconfirmed'}[state]
    assert len(http.actions) == 1 and http.reads == 2
    assert http.actions[0][0] == 'post'
    assert dict(http.actions[0][2]['data']) == ({'action': 'sign_in'} if sid == 'hdarea' else {'action': 'post', 'content': ''})
    form = site.discover_form(None, None)
    form.data.append(('extra', 'value'))
    assert ('extra', 'value') not in site.discover_form(None, None).data


def generate(monkeypatch, tmp_path, **fields):
    path = tmp_path / 'declarations.json'
    path.write_text(json.dumps([dict(id='d1_fixture', name='Fixture', url='https://fixture.invalid/', **fields)]), encoding='utf-8')
    monkeypatch.setattr(generic, '_DECLARATIONS', path)
    # Factory publishes classes for registry discovery; restore its namespace after test.
    monkeypatch.setattr(generic, 'GenericD1_Fixture', None, raising=False)
    return generic.build_generic_sites()[0]()


@pytest.mark.parametrize('mapping,value,expected', [
    ({'1': 'signed'}, '1', 'success'), ({'1': 'signed'}, 1, 'unconfirmed'),
    ([[0, 'signed']], 0, 'success'), ([[0, 'signed']], False, 'unconfirmed'),
    ([[True, 'signed'], [False, 'unsigned']], True, 'success'),
    ([[True, 'signed'], [False, 'unsigned']], False, 'failed'),
    ([[True, 'signed']], 1, 'unconfirmed'),
])
@pytest.mark.parametrize('action_error', [False, True])
def test_generic_response_json_exact_types_and_safe_readback(monkeypatch, tmp_path, mapping, value, expected, action_error):
    site = generate(monkeypatch, tmp_path, safe_read_path='/', action_path='/action',
                    response_json={'field': 'status', 'status_map': mapping})
    assert isinstance(site, ApiSignin)
    http = c34.Http(site, receipt=TimeoutError() if action_error else json.dumps({'status': value}))
    assert site.signin(c34.context(site, http)).status == ('unconfirmed' if action_error else expected)
    assert len(http.actions) == 1 and http.reads == 2
    assert http.actions[0][1] == 'https://fixture.invalid/action'
    assert http.calls[0][1] == http.calls[-1][1] == site.url


def test_generic_login_only_is_skipped_and_registry_honors_capability(monkeypatch, tmp_path):
    site = generate(monkeypatch, tmp_path, signin_capable=False)
    http = Mock()
    result = site.signin(c1.context(site, http, None))
    assert result.status == 'skipped' and result.metadata['reason'] == 'signin_not_applicable'
    assert not http.mock_calls
    row = next(row for row in discover_sites()['sites'] if row['id'] == site.id)
    assert not row['signin_capable']


def test_generic_kelu_variants_and_btschool_opt_out():
    kelu = get_native_module('kelu')
    for text in ['签到成功', '簽到成功', '签到已得', '簽到已得', '今天已經簽到過', '今日已簽到']:
        assert kelu.record_spec.status_map[text] == 'signed'
    site = get_native_module('btschool')
    assert site.use_default_message is False and not site.message_spec().status_map


@pytest.mark.parametrize('sid', CAPTCHA + GET + POST)
def test_generic_migrated_module_removed(sid):
    assert not generic._DECLARATIONS.with_name(sid + '.py').exists()
    assert get_native_module(sid).__module__ == generic.__name__


@pytest.mark.parametrize('fields', [{'action_get': '/attendance.php'}, {'action_path': '/action', 'response_json': {'field': 'status', 'status_map': {'ok': 'signed'}}}])
def test_generic_action_requires_explicit_safe_read_path(monkeypatch, tmp_path, fields):
    with pytest.raises(KeyError, match='safe_read_path'):
        generate(monkeypatch, tmp_path, **fields)


def test_generic_response_json_rejects_colliding_keys(monkeypatch, tmp_path):
    with pytest.raises(ValueError, match='colliding'):
        generate(monkeypatch, tmp_path, safe_read_path='/', action_path='/action',
                 response_json={'field': 'status', 'status_map': [[0, 'signed'], [False, 'unsigned']]})


def test_generic_success_text_override(monkeypatch, tmp_path):
    site = generate(monkeypatch, tmp_path, success_texts=['fixture success'])
    assert site.message_spec().status_map['fixture success'] == 'signed'


def test_cloak_action_readback_prefers_stashed_landing_page(monkeypatch):
    site = get_native_module('pt_0ff')
    landing = '<h2>签到已得100</h2>'

    class Page:
        url = site.url
        def content(self): return landing

    class Session:
        page = Page()

    class Http:
        session = Session()
        def run_page_action(self, steps):
            from autoptcheckin.core import cloak as _cloak
            return _cloak.run_page_action(self.session, list(steps))

        def page_snapshot(self):
            return (self.session.page.content(), self.session.page.url)
        def get(self, *args, **kwargs):
            from autoptcheckin.core.models import LoginPage
            return LoginPage('<html>滑动认证 拖动滑块验证</html>', site.url, 200)

    # run_page_action is imported locally from core.cloak.
    from autoptcheckin.core import cloak
    monkeypatch.setattr(cloak, 'run_page_action', lambda session, steps: None)
    result = site.signin(c1.context(site, Http(), None))
    assert result.status == 'success', result.evidence
    assert result.message == '签到已得100'



def test_vclib_cloak_human_verify_chain(monkeypatch):
    site = get_native_module('vclib')
    assert site.emulate is True and site.cloak_steps == ['human_verify', 'sign_button']

    class Page:
        url = site.url + '/attendance.php'
        def content(self): return '<div class="ant-message">签到成功</div>'
        def goto(self, *a, **k): return None
        def wait_for_timeout(self, *a, **k): return None
        def wait_for_load_state(self, *a, **k): return None
        def inner_text(self): return ''

    class Session:
        page = Page()

    class Http:
        session = Session()
        def run_page_action(self, steps):
            from autoptcheckin.core import cloak as _cloak
            return _cloak.run_page_action(self.session, list(steps))

        def page_snapshot(self):
            return (self.session.page.content(), self.session.page.url)
        def get(self, *a, **k):
            from autoptcheckin.core.models import LoginPage
            return LoginPage('<main>attendance 表单</main>', site.url + '/attendance.php', 200)

    from autoptcheckin.core import cloak
    steps = []
    def fake_action(session, step_list):
        steps.extend(step_list)
        session.page.__class__.content = lambda self: '<div class="ant-message">签到成功</div>'
    monkeypatch.setattr(cloak, 'run_page_action', fake_action)
    result = site.signin(c1.context(site, Http(), None))
    assert steps == ['human_verify', 'sign_button']
    assert result.status.value in ('success', 'already')


def test_yema_signin_executable_and_52pt_declared_uncapable(monkeypatch):
    rows = {row['id']: row for row in json.loads(generic._DECLARATIONS.read_text(encoding='utf-8'))}
    assert rows['yema']['signin_capable'] is True
    # 52pt 2026-10-28 用户裁决转显式无签到能力（站点入口整体下线+公告反脚本条款）：仅登录。
    assert rows['52pt']['signin_capable'] is False
    assert rows['pt_0ff']['signin_capable'] is True
    assert rows['piggo']['cloak_entry_path'] == '/'
    assert 'emulate' not in rows['kamept']
    from autoptcheckin.core import cloak
    monkeypatch.setattr(cloak, 'run_page_action', lambda session, steps: None)
    # 52pt 声明已转 False，仅验证注册表与模块一致；执行层 skipped 由通用 not_supported 分支覆盖（b17）。
    site = get_native_module('yema')
    assert site.signin_capable is True
    entry = next(row for row in discover_sites()['sites'] if row['id'] == 'yema')
    assert entry['signin_capable'] is True
    site_52 = get_native_module('52pt')
    assert site_52.signin_capable is False
    entry_52 = next(row for row in discover_sites()['sites'] if row['id'] == '52pt')
    assert entry_52['signin_capable'] is False

    class Page:
        url = site.url
        def content(self):
            # yema：Ant 按钮态即证据。
            return '<button class="ant-btn">已签到，明日继续</button>'
        def goto(self, *args, **kwargs): return None
        def wait_for_timeout(self, *args, **kwargs): return None
        def wait_for_load_state(self, *args, **kwargs): return None
        def inner_text(self): return ''

    class Session:
        page = Page()

    class Http:
        session = Session()
        def run_page_action(self, steps):
            from autoptcheckin.core import cloak as _cloak
            return _cloak.run_page_action(self.session, list(steps))

        def page_snapshot(self):
            return (self.session.page.content(), self.session.page.url)

        def get(self, *args, **kwargs):
            from autoptcheckin.core.models import LoginPage
            return LoginPage(self.session.page.content(), site.url, 200)

    result = site.signin(c1.context(site, Http(), None))
    # yema 按钮态映射 signed（回读判已签，SUCCESS/ALREADY 均表示证据成立）。
    assert result.message == '已签到，明日继续' and str(result.status).endswith(('success', 'already')), \
        f'yema: {result.status} | {result.message} | {result.evidence}'
