"""Offline V2-style round notification rendering."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
from autoptcheckin.core.notify import format_round_notifications


def test_notify_sign_header_counts_round_entries_only():
    """头部计数只取 round_entries；entries 里的旧待办（含已签此前）只进明细，不补本轮数字。"""
    rendered = format_round_notifications({
        'sign': {'total': 66, 'executed': 3, 'next': 65, 'entries': [
            ('Done', {'status': 'success', 'message': '签到成功'}),
            ('Fail', {'status': 'failed', 'message': '403 Forbidden'}),
            ('Pend', {'status': 'pending', 'reason': 'network_error', 'message': 'HTTP 502'}),
            ('Old', {'status': 'signed', 'reason': 'already_signed'}),
        ], 'round_entries': [
            ('Done', {'status': 'success', 'message': '签到成功'}),
            ('Fail', {'status': 'failed', 'message': '403 Forbidden'}),
            ('Pend', {'status': 'pending', 'reason': 'network_error', 'message': 'HTTP 502'}),
        ]},
        'login': {'total': 4, 'executed': 2, 'next': 2, 'entries': [
            ('LoginOk', {'status': 'login_ok', 'message': '页面可达'}),
            ('LoginUn', {'status': 'unconfirmed', 'message': '登录页面不可达'}),
        ], 'round_entries': [
            ('LoginOk', {'status': 'login_ok', 'message': '页面可达'}),
            ('LoginUn', {'status': 'unconfirmed', 'message': '登录页面不可达'}),
        ]},
    })
    assert len(rendered) == 2
    track, title, text = rendered[0]
    assert title == '【PT 签到中心】'
    assert text.splitlines()[:3] == ['全部签到: 66',
                                     '本次签到: 3（成功 1 · 失败 1 · 待处理 1）',
                                     '下轮待执行: 65']
    # 旧待办（已签此前）只入明细，不改变本轮成功计数
    assert '【Old】此前已签' in text
    assert text.index('—— ✅ 已完成 ——') < text.index('—— ❌ 失败 ——') < text.index('—— ⏳ 待处理 ——')
    assert '【Done】签到成功' in text
    assert '【Fail】签到失败，403 Forbidden' in text
    # pending 按 reason 显示网络诊断
    assert '【Pend】网络请求失败或超时' in text and '（HTTP 502）' in text
    login_text = rendered[1][2]
    assert login_text.splitlines()[:3] == ['全部登录: 4',
                                           '本次登录: 2（成功 1 · 失败 0 · 待处理 1）',
                                           '下轮待执行: 2']
    assert '【LoginOk】模拟登录成功，页面可达' in login_text
    assert '【LoginUn】模拟登录结果未确认，请人工核验（登录页面不可达）' in login_text


def test_notify_signed_keeps_reward_message_and_plain_text():
    """signed 必须保留 message（奖励/诊断证据）；纯文本契约与分轨两条消息不可回退。"""
    rendered = format_round_notifications({
        'sign': {'total': 4, 'executed': 4, 'next': 0, 'entries': [
            ('Reward', {'status': 'signed', 'message': '已连续签到142天，本次签到获得715个憨豆'}),
            ('Dedup', {'status': 'signed', 'message': '签到成功，获得50魔力', 'reward': '50 魔力'}),
            ('Empty', {'status': 'signed'}),
            ('Prior', {'status': 'signed', 'reason': 'already_signed',
                       'message': '页面显示今日已签，未重复提交'}),
        ], 'round_entries': [
            ('Reward', {'status': 'signed', 'message': '已连续签到142天，本次签到获得715个憨豆'}),
            ('Dedup', {'status': 'signed', 'message': '签到成功，获得50魔力', 'reward': '50 魔力'}),
            ('Empty', {'status': 'signed'}),
            ('Prior', {'status': 'signed', 'reason': 'already_signed',
                       'message': '页面显示今日已签，未重复提交'}),
        ]},
        'login': {'total': 1, 'executed': 0, 'next': 1, 'entries': [], 'round_entries': []},
    })
    assert len(rendered) == 2
    sign_text, login_text = rendered[0][2], rendered[1][2]
    assert sign_text.splitlines()[:3] == ['全部签到: 4',
                                          '本次签到: 4（成功 4 · 失败 0 · 待处理 0）',
                                          '下轮待执行: 0']
    # 与 success 同一套去重：message 已含「签到成功」原样回显，否则补前缀；奖励证据不丢
    assert '【Reward】签到成功，已连续签到142天，本次签到获得715个憨豆' in sign_text
    assert '【Dedup】签到成功，获得50魔力' in sign_text
    # 空 message 保留已签语义；already_signed 保留诊断 message
    assert '【Empty】今日已签到' in sign_text
    assert '【Prior】此前已签，页面显示今日已签，未重复提交' in sign_text
    # 纯文本契约：不出现 HTML 标签
    assert '<' not in sign_text and '<' not in login_text


def test_notify_legacy_values_compat():
    """旧 success/already/auth_failed 及失败组保持既有语义，认证失败必须带认证消息。"""
    rendered = format_round_notifications({
        'sign': {'total': 4, 'executed': 3, 'next': 1, 'entries': [
            ('Fresh', {'status': 'success', 'message': '已签到，魔力值+10'}),
            ('Already', {'status': 'already'}),
            ('Dead', {'status': 'auth_failed'}),
            ('Keyed', {'status': 'auth_failed', 'credential': 'password'}),
        ], 'round_entries': [
            ('Fresh', {'status': 'success', 'message': '已签到，魔力值+10'}),
            ('Already', {'status': 'already'}),
            ('Dead', {'status': 'auth_failed'}),
            ('Keyed', {'status': 'auth_failed', 'credential': 'password'}),
        ]},
        'login': {'total': 1, 'executed': 1, 'next': 0, 'entries': [
            ('NoAuth', {'status': 'auth_failed', 'message': '重定向到登录页'})],
            'round_entries': [
                ('NoAuth', {'status': 'auth_failed', 'message': '重定向到登录页'})]},
    })
    text = rendered[0][2]
    assert text.splitlines()[:3] == ['全部签到: 4',
                                     '本次签到: 4（成功 2 · 失败 2 · 待处理 0）',
                                     '下轮待执行: 1']
    assert '【Fresh】签到成功，已签到，魔力值+10' in text
    assert '【Already】今日已签到' in text
    assert '【Dead】签到失败，Cookie 已失效' in text
    assert '【Keyed】签到失败，认证失败' in text
    login_lines = rendered[1][2].splitlines()
    assert '—— ❌ 失败 ——' in login_lines and '—— ⏳ 待处理 ——' not in login_lines
    assert login_lines[login_lines.index('—— ❌ 失败 ——') + 1] == '【NoAuth】模拟登录认证失败（重定向到登录页）'


def test_notify_pending_reason_variants_and_unknown_status():
    """pending 按约定 reason 精确细分网络/维护/协议/结果未知；未命中保留原 message；未知 status 不武断算明确失败。"""
    rendered = format_round_notifications({
        'sign': {'total': 6, 'executed': 6, 'next': 6, 'entries': [
            ('Net', {'status': 'pending', 'reason': 'network_error'}),
            ('Maint', {'status': 'pending', 'reason': 'maintenance'}),
            ('Proto', {'status': 'pending', 'reason': 'protocol_pending', 'message': '云签验证超时'}),
            ('Mystery', {'status': 'pending', 'reason': 'result_unknown'}),
            ('Weird', {'status': 'pending', 'message': '回读页面无法解析'}),
            ('Legacy', {'status': 'mystery_status', 'message': '协议返回异常'}),
        ], 'round_entries': [
            ('Net', {'status': 'pending', 'reason': 'network_error'}),
            ('Maint', {'status': 'pending', 'reason': 'maintenance'}),
            ('Proto', {'status': 'pending', 'reason': 'protocol_pending', 'message': '云签验证超时'}),
            ('Mystery', {'status': 'pending', 'reason': 'result_unknown'}),
            ('Weird', {'status': 'pending', 'message': '回读页面无法解析'}),
            ('Legacy', {'status': 'mystery_status', 'message': '协议返回异常'}),
        ]},
    })
    text = rendered[0][2]
    assert '本次签到: 6（成功 0 · 失败 0 · 待处理 6）' in text
    assert '【Net】网络请求失败或超时，本轮未确认，稍后自动重试' in text
    assert '【Maint】站点维护中/已关闭，本轮跳过' in text
    assert '【Proto】提交前置条件未满足，本轮未提交（云签验证超时）' in text
    assert '【Mystery】结果未知，待下轮重试' in text
    # 未命中约定 reason：不编造原因，原样保留 message
    assert '【Weird】回读页面无法解析' in text
    # 未知 status 归待处理且保留 message，不算失败
    assert '【Legacy】协议返回异常' in text and '—— ❌ 失败 ——' not in text


def test_notify_hides_empty_sections_but_keeps_zero_counts():
    """空分节隐藏；本轮计数为 0 时头部三行仍完整显示。"""
    rendered = format_round_notifications({
        'sign': {'total': 2, 'executed': 0, 'next': 1, 'entries': [
            ('Old', {'status': 'network_error', 'message': '旧轮超时'})],
            'round_entries': []},
    })
    text = rendered[0][2]
    assert text.splitlines()[:3] == ['全部签到: 2',
                                     '本次签到: 0（成功 0 · 失败 0 · 待处理 0）',
                                     '下轮待执行: 1']
    assert '—— ✅ 已完成 ——' not in text and '—— ❌ 失败 ——' not in text
    assert '—— ⏳ 待处理 ——' in text
    assert '【Old】网络请求失败或超时，本轮未确认，稍后自动重试（旧轮超时）' in text


def test_notify_lock_busy_cancel_and_disabled_not_executed():
    """锁忙/取消/门控禁用没有执行结论：不进明细，不进本轮三项。"""
    rendered = format_round_notifications({
        'sign': {'total': 4, 'executed': 0, 'next': 3, 'entries': [
            ('Busy', {'status': 'skipped', 'state': 'pending'}),
            ('Gated', {'status': 'skipped', 'state': 'disabled', 'reason': 'site_disabled'}),
            ('Stopped', {'status': 'cancelled'}),
        ], 'round_entries': [
            ('Busy', {'status': 'skipped', 'state': 'pending'}),
            ('Gated', {'status': 'skipped', 'state': 'disabled', 'reason': 'site_disabled'}),
            ('Stopped', {'status': 'cancelled'}),
        ]},
    })
    assert len(rendered) == 1
    text = rendered[0][2]
    assert text.splitlines()[:3] == ['全部签到: 4',
                                     '本次签到: 0（成功 0 · 失败 0 · 待处理 0）',
                                     '下轮待执行: 3']
    for name in ('Busy', 'Gated', 'Stopped'):
        assert f'【{name}】' not in text
    assert '—— ✅ 已完成 ——' not in text and '—— ❌ 失败 ——' not in text and '—— ⏳ 待处理 ——' not in text


def test_notify_skips_all_zero_track():
    """本轮零执行 + 无明细 + 无待执行队列的轨道整条不发（「全部 X」是启用站点数，恒 >0）。"""
    rendered = format_round_notifications({
        'sign': {'total': 131, 'executed': 0, 'next': 0, 'entries': [], 'round_entries': []},
        'login': {'total': 131, 'executed': 0, 'next': 0, 'entries': [], 'round_entries': []},
    })
    assert rendered == []


def test_notify_keeps_track_with_leftover_details_only():
    """本轮没跑但还有当日残留明细时仍发该轨（明细就是这一轨的话说）。"""
    rendered = format_round_notifications({
        'login': {'total': 5, 'executed': 0, 'next': 0, 'entries': [
            ('Old', {'status': 'login_ok', 'message': '页面可达'}),
        ], 'round_entries': []},
    })
    assert len(rendered) == 1
    assert '【Old】模拟登录成功，页面可达' in rendered[0][2]


def test_notify_skips_empty_track_next_to_active_track():
    """一轨有执行、另一轨三零：只有有话说的那条发出去。"""
    rendered = format_round_notifications({
        'sign': {'total': 20, 'executed': 1, 'next': 0, 'entries': [
            ('Done', {'status': 'success', 'message': '签到成功'}),
        ], 'round_entries': [
            ('Done', {'status': 'success', 'message': '签到成功'}),
        ]},
        'login': {'total': 131, 'executed': 0, 'next': 0, 'entries': [], 'round_entries': []},
    })
    assert [track for track, _, _ in rendered] == ['sign']
