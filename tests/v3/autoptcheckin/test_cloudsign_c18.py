"""云签引擎（BQL）离线单测：endpoint 规范化 / 结果分类 / 两段编排 / run_native 分流。"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))

import requests

from autoptcheckin.core import cloudsign, native
from autoptcheckin.core.cloudsign import CloudResult
from autoptcheckin.core.credentials import Credential, CredentialSpec
from autoptcheckin.core.models import SignStatus
from autoptcheckin.core.models import SignResult, SignStatus
from autoptcheckin.core.registry import get_native_module, shield_of
from autoptcheckin.core.runner import SignRunner


# ---- endpoint 规范化 ----

def test_bql_endpoint_normalization():
    assert cloudsign.bql_endpoint('https://production-sfo.browserless.io', 'tk') == \
        'https://production-sfo.browserless.io/stealth/bql?token=tk'
    assert cloudsign.bql_endpoint('http://192.168.1.10:3000', '') == 'http://192.168.1.10:3000/stealth/bql'
    assert cloudsign.bql_endpoint('http://192.168.1.10:3000/stealth', 'tk') == \
        'http://192.168.1.10:3000/stealth/bql?token=tk'
    # 已是完整端点（自建 /chromium/bql）原样保留，只补 token
    assert cloudsign.bql_endpoint('http://cb.local:3000/chromium/bql', 'tk') == \
        'http://cb.local:3000/chromium/bql?token=tk'
    assert cloudsign.bql_endpoint('', 'tk') == f'https://production-sfo.browserless.io/stealth/bql?token=tk'
    with pytest.raises(cloudsign.CloudSignError):
        cloudsign.bql_endpoint('ftp://x', 'tk')


def test_session_endpoint_keeps_path_and_appends_token():
    base = 'https://production-sfo.browserless.io/e/abc-123/chromium/bql'
    assert cloudsign.session_endpoint(base, 'tk') == base + '?token=tk'
    assert cloudsign.session_endpoint(base, '') == base
    assert cloudsign.session_endpoint('', 'tk') == ''


# ---- 配置矩阵与 Cookie 解析 ----

def test_enabled_and_configured():
    assert cloudsign.enabled('audiences') and cloudsign.enabled('vclib') and cloudsign.enabled('ourbits')
    assert not cloudsign.enabled('52pt') and not cloudsign.enabled('hdsky')
    assert not cloudsign.configured({})
    assert not cloudsign.configured({'browserless_url': cloudsign.DEFAULT_BROWSERLESS_URL, 'browserless_token': ''})
    assert cloudsign.configured({'browserless_token': 'tk'})
    assert cloudsign.configured({'browserless_url': 'http://cb.local:3000'})


def test_cookie_objects_parses_header():
    items = cloudsign.cookie_objects('a=1; b= 2 ; broken', 'https://audiences.me/attendance.php')
    assert items == [{'name': 'a', 'value': '1', 'domain': 'audiences.me', 'path': '/', 'secure': True},
                     {'name': 'b', 'value': '2', 'domain': 'audiences.me', 'path': '/', 'secure': True}]
    assert cloudsign.cookie_objects('', 'https://audiences.me/') == []
    assert cloudsign.cookie_objects('a=1', 'not-a-url') == []


# ---- 结果分类 ----

def test_classify_priority_success_before_already():
    rule = cloudsign.CLOUD_RULES['audiences']
    # 成功页常带「已连续签到 N 天」，必须先判成功
    assert cloudsign._classify('签到成功 已连续签到 3 天', rule) == 'success'
    assert cloudsign._classify('今日已签到', rule) == 'already'
    assert cloudsign._classify('完成人机验证即可领取今日爆米花奖励', rule) == 'pending'
    assert cloudsign._classify('<html>nothing</html>', rule) == 'unknown'


# ---- BQL 请求层错误映射 ----

class FakeResp:
    def __init__(self, payload=None, status=200):
        self.payload, self.status_code = payload, status

    def json(self):
        if self.status_code != 200:
            raise ValueError
        return self.payload


@pytest.fixture
def bql(monkeypatch):
    calls = []

    def install(responses):
        def fake_post(url, json=None, timeout=None):
            calls.append({'url': url, 'payload': json, 'timeout': timeout})
            resp = responses.pop(0)
            if isinstance(resp, Exception):
                raise resp
            return resp
        monkeypatch.setattr(cloudsign.requests, 'post', fake_post)
        return calls
    return install


def test_sign_auto_two_stage_success(bql):
    calls = bql([
        FakeResp({'data': {'solve': {'token': '0.turnstile-tk'}, 'session': {'browserQLEndpoint':
                   'https://production-sfo.browserless.io/e/s1/chromium/bql'}, 'after': {'html': '待签到'}}}),
        FakeResp({'data': {'verifyPage': {'html': '签到成功'}, 'after': {'html': ''}}}),
    ])
    result = cloudsign.sign('audiences', 'https://audiences.me', 'a=1', {'browserless_token': 'tk'})
    assert (result.status, result.message) == ('success', '云签成功')
    assert len(calls) == 2
    # 第二段必须打到 reconnect 返回的会话地址（同浏览器复用），并带 token
    assert calls[1]['url'].startswith('https://production-sfo.browserless.io/e/s1/')
    assert calls[1]['url'].endswith('token=tk')
    # Cookie 必须注入云签会话（setCookies 经 cookies(cookies:$cookies) 步骤）
    assert calls[0]['payload']['variables']['cookies'][0]['name'] == 'a'
    assert 'cookies(cookies:$cookies)' in calls[0]['payload']['query']
    assert 'session:reconnect' in calls[0]['payload']['query']
    # 注入脚本 evaluate 超时 = 脚本预算 + 余量
    assert calls[1]['payload']['variables']['autoTimeout'] == 30000 + cloudsign.INJECT_STEP_MARGIN_MS


def test_sign_auto_already_in_stage1_skips_stage2(bql):
    calls = bql([FakeResp({'data': {'solve': {'token': ''}, 'after': {'html': '今日已签到'}}})])
    result = cloudsign.sign('audiences', 'https://audiences.me', 'a=1', {'browserless_token': 'tk'})
    assert result.status == 'success' and '已签到' in result.message
    assert len(calls) == 1


def test_sign_solve_failure_is_protocol_pending(bql):
    bql([FakeResp({'data': {'solve': {'token': ''}, 'after': {'html': '待签到'}}})])
    result = cloudsign.sign('audiences', 'https://audiences.me', 'a=1', {'browserless_token': 'tk'})
    assert result.status == 'protocol_pending'
    assert 'solve 失败' in result.message


def test_sign_click_mode_already(bql):
    # mua_xloli 两段式：第一段 solve 后页面回读已签即返回，不再等提交表单。
    calls = bql([FakeResp({'data': {'solve': {'token': '0.tk'}, 'session': {}, 'after': {'html': '今天已经签到'}}})])
    result = cloudsign.sign('mua_xloli', 'https://mua.xloli.cc', 'a=1', {'browserless_token': 'tk'})
    assert result.status == 'success' and '已签到' in result.message
    assert len(calls) == 1


def test_sign_failed_definitive_after_submit(bql):
    bql([
        FakeResp({'data': {'solve': {'token': '0.tk'}, 'session': {}, 'after': {'html': '待签到'}}}),
        FakeResp({'data': {'verifyPage': {'html': '<div>站点公告</div>'},
                           'autoDiag': '{"token": true, "post": 200, "still": false}',
                           'response': 'null', 'after': {'html': ''}}}),
    ])
    result = cloudsign.sign('audiences', 'https://audiences.me', 'a=1', {'browserless_token': 'tk'})
    assert result.status == 'failed'
    assert '未确认签到' in result.message


def test_sign_bql_step_error_does_not_abort_readback(bql):
    # BQL 官方语义：失败步骤不中止 mutation，errors[] 与 data 并存。
    # evaluate 撞导航（audiences 凌晨竞态）后 verifyPage 回读仍可仲裁出已签。
    bql([
        FakeResp({'data': {'solve': {'token': '0.tk'}, 'session': {}, 'after': {'html': '待签到'}}}),
        FakeResp({'data': {'verifyPage': {'html': '<div>今日已签到，明天再来</div>'},
                           'autoDiag': None, 'response': 'null', 'after': None},
                 'errors': [{'message': 'Protocol error (Runtime.evaluate): Inspected target navigated or closed',
                             'path': ['submit']}]}),
    ])
    result = cloudsign.sign('audiences', 'https://audiences.me', 'a=1', {'browserless_token': 'tk'})
    assert result.status == 'success' and '已签到' in result.message


def test_sign_bql_step_error_appended_to_failed_message(bql):
    bql([
        FakeResp({'data': {'solve': {'token': '0.tk'}, 'session': {}, 'after': {'html': '待签到'}}}),
        FakeResp({'data': {'verifyPage': {'html': '<div>站点公告</div>'},
                           'autoDiag': None, 'response': 'null', 'after': None},
                 'errors': [{'message': 'Inspected target navigated or closed', 'path': ['submit']}]}),
    ])
    result = cloudsign.sign('audiences', 'https://audiences.me', 'a=1', {'browserless_token': 'tk'})
    assert result.status == 'failed'
    assert 'BQL步骤失败' in result.message and 'submit' in result.message


def test_sign_solve_error_reported_in_pending_message(bql):
    bql([FakeResp({'data': {'solve': None, 'after': {'html': '待签到'}},
                   'errors': [{'message': 'solve timed out', 'path': ['solve']}]}),
         ])
    result = cloudsign.sign('audiences', 'https://audiences.me', 'a=1', {'browserless_token': 'tk'})
    assert result.status == 'protocol_pending'
    assert 'solve 失败' in result.message and 'solve timed out' in result.message




def _solve_timeout_response(html="Cloudflare challenge"):
    return FakeResp({
        "data": {"solve": None, "after": {"html": html}, "session": {}},
        "errors": [{"message": "Captcha solving timed out after 40000 ms", "path": ["solve"]}],
    })


def test_ourbits_solve_timeout_returns_already_from_each_attempt_readback(bql):
    calls = bql([_solve_timeout_response("今日已签到")])
    result = cloudsign.sign('ourbits', 'https://ourbits.club', 'a=1', {'browserless_token': 'tk'})
    assert result.status == 'success' and '已签到' in result.message
    assert len(calls) == 1
    assert calls[0]['payload']['variables']['solveTimeout'] == 60000
    assert calls[0]['timeout'] >= 75


def test_ourbits_retries_only_solve_then_submits_once(bql):
    calls = bql([
        _solve_timeout_response(),
        FakeResp({'data': {'solve': {'token': '0.turnstile-tk'},
                          'session': {'browserQLEndpoint': 'https://production-sfo.browserless.io/e/retry/chromium/bql'},
                          'after': {'html': '待签到'}}}),
        FakeResp({'data': {'verifyPage': {'html': '签到成功'}, 'after': {'html': ''}}}),
    ])
    result = cloudsign.sign('ourbits', 'https://ourbits.club', 'a=1', {'browserless_token': 'tk'})
    assert result.status == 'success'
    assert len(calls) == 3
    assert [call['payload']['variables']['solveTimeout'] for call in calls[:2]] == [60000, 90000]
    assert 'solve:solve(' in calls[0]['payload']['query']
    assert 'solve:solve(' in calls[1]['payload']['query']
    assert 'autoSubmit' in calls[2]['payload']['query']
    assert calls[2]['payload']['variables']['autoTimeout'] == 30000 + cloudsign.INJECT_STEP_MARGIN_MS


def test_ourbits_stops_after_three_solve_timeouts_without_submitting(bql):
    calls = bql([_solve_timeout_response() for _ in range(3)])
    result = cloudsign.sign('ourbits', 'https://ourbits.club', 'a=1', {'browserless_token': 'tk'})
    assert result.status == 'protocol_pending'
    assert '已尝试 3 次' in result.message
    assert len(calls) == 3
    assert [call['payload']['variables']['solveTimeout'] for call in calls] == [60000, 90000, 120000]
    assert all('solve:solve(' in call['payload']['query'] for call in calls)


def test_ourbits_retries_next_budget_when_bql_request_times_out(bql):
    calls = bql([
        requests.exceptions.Timeout('slow'),
        FakeResp({
            'data': {
                'solve': {'token': '0.turnstile-tk'},
                'session': {'browserQLEndpoint': 'https://production-sfo.browserless.io/e/retry/chromium/bql'},
                'after': {'html': '待签到'},
            },
        }),
        FakeResp({'data': {'verifyPage': {'html': '签到成功'}, 'after': {'html': ''}}}),
    ])
    result = cloudsign.sign('ourbits', 'https://ourbits.club', 'a=1', {'browserless_token': 'tk'})
    assert result.status == 'success'
    assert [call['payload']['variables']['solveTimeout'] for call in calls[:2]] == [60000, 90000]
    assert calls[0]['timeout'] < calls[1]['timeout']


def test_ourbits_reports_attempts_when_every_bql_request_times_out(bql):
    calls = bql([requests.exceptions.Timeout('slow') for _ in range(3)])
    result = cloudsign.sign('ourbits', 'https://ourbits.club', 'a=1', {'browserless_token': 'tk'})
    assert result.status == 'network_error'
    assert '已尝试 3 次，未提交' in result.message
    assert len(calls) == 3
    assert all('solve:solve(' in call['payload']['query'] for call in calls)


def test_ourbits_does_not_retry_bql_auth_error(bql):
    calls = bql([FakeResp(status=401)])
    result = cloudsign.sign('ourbits', 'https://ourbits.club', 'a=1', {'browserless_token': 'tk'})
    assert result.status == 'network_error'
    assert '鉴权' in result.message
    assert len(calls) == 1


def test_ourbits_does_not_retry_non_timeout_solve_error(bql):
    calls = bql([FakeResp({
        'data': {'solve': None, 'after': {'html': 'Cloudflare challenge'}, 'session': {}},
        'errors': [{'message': 'solver returned no token', 'path': ['solve']}],
    })])
    result = cloudsign.sign('ourbits', 'https://ourbits.club', 'a=1', {'browserless_token': 'tk'})
    assert result.status == 'protocol_pending'
    assert '已尝试 1 次' in result.message
    assert len(calls) == 1

def test_sign_http_errors_map_to_network_error_and_never_leak_token(monkeypatch):
    token = 'secret-token-xyz'
    urls = []

    def post(url, json=None, timeout=None):
        urls.append(url)
        return FakeResp(status=401)
    monkeypatch.setattr(cloudsign.requests, 'post', post)
    result = cloudsign.sign('audiences', 'https://audiences.me', 'a=1', {'browserless_token': token})
    assert result.status == 'network_error'
    assert '鉴权' in result.message and token not in result.message
    assert any('token=' in u for u in urls)


def test_sign_timeout_is_transient_network_error(bql):
    bql([requests.exceptions.Timeout('boom')])
    result = cloudsign.sign('vclib', 'https://v.cb.land', 'a=1', {'browserless_token': 'tk'})
    assert result.status == 'network_error'
    assert '超时' in result.message


def test_inject_script_contains_token_and_diag():
    script = cloudsign.inject_script('0.abc', cloudsign.CLOUD_RULES['vclib'])
    assert '0.abc' in script
    assert '__ptsignin_auto' in script and '__ptsignin_response' in script
    assert 'cf-turnstile-response' in script
    assert 'fetch(' in script  # 同源表单兜底 POST


# ---- run_native 云签分流 ----

@pytest.fixture
def storage(monkeypatch):
    data = {'cookies.table': {'audiences': {'cookie': 'session=stored', 'source': 'refreshed', 'updated': 'old'},
                              'hdsky': {'cookie': 'session=stored', 'source': 'refreshed', 'updated': 'old'}}}
    runner = SignRunner()
    runner.get_data = data.get
    runner.save_data = data.__setitem__
    runner.del_data = lambda key: data.pop(key, None)
    return runner, data


def module_namespace(site_id, **overrides):
    real = get_native_module(site_id)
    attrs = {k: getattr(real, k) for k in dir(real) if not k.startswith('__')}
    attrs.pop('id', None)
    attrs.pop('signin', None)
    return SimpleNamespace(id=site_id, **attrs, **overrides)


def cloud_site(site_id='audiences'):
    return module_namespace(site_id, signin=lambda ctx: pytest.fail('本地仿真不应被执行'))


@pytest.mark.parametrize('url', ['http://cb.local:3000', 'https://bql.internal.invalid/stealth/bql'])
def test_native_self_hosted_without_token_executes_cloud(storage, monkeypatch, url):
    runner, _ = storage
    calls = []
    def sign(*args):
        calls.append(args)
        return CloudResult('success', 'ok')
    monkeypatch.setattr(native.cloudsign, 'sign', sign)
    result = native.run_native(runner, cloud_site(), {'cookie': 'session=stored'},
                               config={'site_cloudsign': ['audiences'], 'browserless_url': url})
    assert result.status == SignStatus.SUCCESS
    assert len(calls) == 1


def test_run_native_routes_to_cloudsign_when_configured(storage, monkeypatch):
    runner, data = storage
    site = cloud_site()
    seen = {}

    def fake_sign(site_id, base_url, cookie, config):
        seen.update(id=site_id, url=base_url, cookie=cookie, config=config)
        return CloudResult('success', '云签成功')
    monkeypatch.setattr(native.cloudsign, 'sign', fake_sign)
    result = native.run_native(runner, site, {'cookie': 'session=managed'},
                               config={'browserless_token': 'tk', 'site_cloudsign': ['audiences']})
    assert result.status == SignStatus.SUCCESS
    assert result.metadata['transport'] == 'cloud'
    assert seen['id'] == 'audiences' and seen['cookie'] == 'session=stored' and seen['config']['browserless_token'] == 'tk'


def test_run_native_fails_explicitly_when_selected_without_token(storage, monkeypatch):
    """用户已选云签但缺配置：待处理，不计失败且不回退本地仿真。"""
    runner, data = storage
    site = cloud_site()
    monkeypatch.setattr(native.cloudsign, 'sign', lambda *a, **k: pytest.fail('缺 token 不应发起云签'))
    monkeypatch.setattr(native, 'native_cloak_client', lambda site, http, info, config: http)
    result = native.run_native(runner, site, {'cookie': 'session=stored'},
                               config={'site_cloudsign': ['audiences']})
    assert result.status == SignStatus.PROTOCOL_PENDING
    assert 'browserless_token' in result.message
    assert result.metadata['transport'] == 'cloud'

def test_missing_cloud_config_is_pending_without_same_round_retry(storage, monkeypatch):
    from autoptcheckin import AutoPtCheckin
    from autoptcheckin.core.state_store import PENDING
    plugin = AutoPtCheckin()
    plugin.init_plugin({'enabled_sites': ['audiences'], 'sign_sites': ['audiences'],
                        'site_cloudsign': ['audiences'], 'retry_count': 3})
    runner, _ = storage
    runner.history = plugin._record_result
    calls = []
    monkeypatch.setattr(native.cloudsign, 'sign', lambda *a, **kw: pytest.fail('must not request BQL'))
    def execute(*args, **kwargs):
        calls.append(1)
        result = native.run_native(runner, cloud_site(), {}, config=plugin._config)
        return {'status': result.status}
    monkeypatch.setattr(plugin, '_execute_site', execute)
    plugin._run_with_retry('audiences', 'sign', 'manual')
    assert calls == [1]
    assert plugin._track_store().state_of('audiences', 'sign') == PENDING



def test_run_native_keeps_local_emulation_without_token(storage, monkeypatch):
    runner, data = storage
    calls = []
    site = module_namespace('audiences', signin=lambda ctx: calls.append(1) or SignResult('success'))
    monkeypatch.setattr(native.cloudsign, 'sign', lambda *a, **k: pytest.fail('未选云签不应走云签'))
    monkeypatch.setattr(native, 'native_cloak_client', lambda site, http, info, config: http)
    result = native.run_native(runner, site, {'cookie': 'session=stored'}, config={})
    assert result.status == SignStatus.SUCCESS and calls


def test_shield_field_from_cloak_steps():
    assert shield_of(get_native_module('audiences')) == 'cloud'
    assert shield_of(get_native_module('mua_xloli')) == 'cloud'
    assert shield_of(get_native_module('vclib')) == 'cloud'
    # 52pt 2026-10-28 转 signin_capable=False 并去掉仿真声明（站点入口下线）。
    assert shield_of(get_native_module('52pt')) is None
    assert shield_of(get_native_module('yema')) == 'emulate'
    assert shield_of(get_native_module('hdsky')) is None


def test_registry_sites_carry_shield():
    from autoptcheckin.core.registry import get_registry
    rows = {row['id']: row for row in get_registry()['sites']}
    assert rows['audiences']['shield'] == 'cloud'
    assert rows['52pt']['shield'] is None
    assert rows['hdsky']['shield'] is None


def test_vclib_pending_words_require_full_phrase():
    # 2026-10-26 词表收紧回归：单「验证」/「人机」不再误判 pending（站点公告误伤实况），
    # 仅完整人机验证引导短语命中。
    rule = cloudsign.CLOUD_RULES['vclib']
    assert cloudsign._classify('<div>邮箱验证帮助</div>', rule) == 'unknown'
    assert cloudsign._classify('<div>安全验证设置</div>', rule) == 'unknown'
    assert cloudsign._classify('<div>请完成人机验证后签到</div>', rule) == 'pending'
