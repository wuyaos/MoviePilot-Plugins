"""躺平（tangpt）双通道适配回归：签到页改 Turnstile 后云签/仿真并存。

站点实测（2026-11-11）：attendance.php 为隐藏 cf-turnstile-response + 立即签到提交，
非交互自动出 token；传统 imagehash 验证码已移除，HTTP 通道拿不到 token 无法提交。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))

from autoptcheckin.core import cloudsign, siteconf
from autoptcheckin.core.registry import get_native_module


class FakeResp:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

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


# ---- 能力与声明 ----

def test_cloud_rule_registered():
    assert 'tangpt' in cloudsign.CLOUD_SITES
    assert cloudsign.enabled('tangpt')
    rule = cloudsign.CLOUD_RULES['tangpt']
    assert rule['path'] == '/attendance.php'
    assert rule['submit'] == 'auto'
    assert rule['verify'] == '/attendance.php'
    assert rule['success'] and rule['already']


def test_declaration_is_page_action_emulate():
    site = get_native_module('tangpt')
    assert site is not None
    assert tuple(getattr(site, 'cloak_steps', ())) == ('human_verify', 'sign_button')
    assert getattr(site, 'attendance_path', '') == '/attendance.php'
    assert bool(getattr(site, 'emulate', False)) is True
    assert bool(getattr(site, 'headful', False)) is True


def test_dual_channels_coexist():
    # 未选云签：声明 emulate 默认走本地仿真
    flags = siteconf.resolve('tangpt', {'site_cloudsign': []}, declared_emulate=True)
    assert flags['emulate'] and flags['cloudsign_capable'] and not flags['cloudsign_selected']
    # 选中云签：两通道能力并存，由 site_cloudsign 选择分流
    flags = siteconf.resolve('tangpt', {'site_cloudsign': ['tangpt']}, declared_emulate=True)
    assert flags['emulate'] and flags['cloudsign_capable'] and flags['cloudsign_selected']


# ---- 云签编排（与 c18 同款离线 BQL 桩）----

def test_sign_already_in_stage1_skips_stage2(bql):
    calls = bql([FakeResp({'data': {'solve': {'token': ''}, 'after': {'html': '今日已签到'}}})])
    result = cloudsign.sign('tangpt', 'https://www.tangpt.top/', 'a=1', {'browserless_token': 'tk'})
    assert result.status == 'success' and '已签到' in result.message
    assert len(calls) == 1


def test_sign_two_stage_success_hits_verify(bql):
    calls = bql([
        FakeResp({'data': {'solve': {'token': '0.tk'}, 'session': {'browserQLEndpoint':
                   'https://production-sfo.browserless.io/e/s1/chromium/bql'}, 'after': {'html': '待签到'}}}),
        FakeResp({'data': {'verifyPage': {'html': '签到成功'}, 'after': {'html': ''}}}),
    ])
    result = cloudsign.sign('tangpt', 'https://www.tangpt.top/', 'a=1', {'browserless_token': 'tk'})
    assert (result.status, result.message) == ('success', '云签成功')
    assert len(calls) == 2
    assert calls[1]['payload']['variables']['verifyUrl'] == 'https://www.tangpt.top/attendance.php'


def test_sign_solve_failure_is_protocol_pending(bql):
    bql([FakeResp({'data': {'solve': {'token': ''}, 'after': {'html': '待签到'}}})])
    result = cloudsign.sign('tangpt', 'https://www.tangpt.top/', 'a=1', {'browserless_token': 'tk'})
    assert result.status == 'protocol_pending'
