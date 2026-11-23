"""躺平（tangpt）nexus HTTP 通道回归。

站点实测（2026-11-23）：attendance.php 未签表单已无 Turnstile（sitekey 空、
仅「立即签到」submit），2026-11-11 适配的表单内嵌 Turnstile 已被站点移除——
solve 无 widget 可解，11-21/23 连续「未获取到 token」。tangpt 退出云签，
转 nexus HTTP 声明（ourbits 同款 status_map）。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))

from autoptcheckin.core import cloudsign, siteconf
from autoptcheckin.core.registry import get_native_module

DECLARATIONS = Path(__file__).parents[3] / 'plugins.v3' / 'autoptcheckin' / 'sites' / 'native' / 'generic_sites.json'


def _tangpt_declaration() -> dict:
    rows = json.loads(DECLARATIONS.read_text(encoding='utf-8'))
    return next(r for r in rows if r['id'] == 'tangpt')


# ---- 云签退出 ----

def test_tangpt_removed_from_cloud_sign():
    assert 'tangpt' not in cloudsign.CLOUD_SITES
    assert not cloudsign.enabled('tangpt')
    assert 'tangpt' not in cloudsign.CLOUD_RULES
    result = cloudsign.sign('tangpt', 'https://www.tangpt.top/', 'a=1', {'browserless_token': 'tk'})
    assert result.status == 'network_error'
    assert '云签未适配' in result.message


def test_siteconf_no_cloud_capability():
    flags = siteconf.resolve('tangpt', {'site_cloudsign': ['tangpt']}, declared_emulate=False)
    assert not flags['cloudsign_capable']
    assert not flags['cloudsign_selected']
    # 归一化会把残留选择剔除（__init__ 归一化用 CLOUD_SITES 过滤）


# ---- nexus 声明 ----

def test_declaration_is_nexus_http():
    row = _tangpt_declaration()
    assert row['protocol'] == 'nexus'
    assert row['attendance_path'] == '/attendance.php'
    assert not row.get('emulate')
    assert not row.get('headful')
    assert not row.get('cloak_steps')
    assert row['status_map'].get('签到成功') == 'signed'
    assert row['status_map'].get('今天已经签到过') == 'signed'
    assert row['status_map'].get('未签到') == 'unsigned'


def test_native_module_has_no_cloak_steps():
    site = get_native_module('tangpt')
    assert site is not None
    assert not tuple(getattr(site, 'cloak_steps', ()) or ())
    assert getattr(site, 'attendance_path', '') == '/attendance.php'
    assert bool(getattr(site, 'emulate', False)) is False
