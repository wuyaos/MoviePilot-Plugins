"""Offline V2-style round notification rendering."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
from autoptcheckin.core.notify import format_round_notifications


def test_notify_round_separates_tracks_and_orders_sign_results():
    rendered = format_round_notifications({
        'sign': {'total': 4, 'executed': 3, 'next': 2, 'entries': [
            ('Failed', {'status': 'auth_failed', 'message': 'bad'}),
            ('Done', {'status': 'success', 'message': '已签到', 'reward': ''}),
            ('Already', {'status': 'signed'}),
        ]},
        'login': {'total': 2, 'executed': 1, 'next': 0, 'entries': [
            ('Login', {'status': 'login_ok', 'message': '页面可达'})]},
    })
    assert len(rendered) == 2
    track, title, text = rendered[0]
    assert title == '【PT 签到中心】'
    assert text.splitlines()[:4] == ['全部签到: 4', '本次签到: 3', '成功: 2', '失败（下次签到）: 2']
    # 逐站行只显示本轮实际执行的站点，未执行的（今日已签）不出现
    assert '【已签站】' not in text
    assert text.index('【Done】') < text.index('【Already】') < text.index('【Failed】')
    assert '【Failed】签到失败，Cookie 已失效' in text
    assert rendered[1][1] == '【PT 签到中心】'
    assert '【Login】模拟登录成功，页面可达' in rendered[1][2]


def test_notify_pending_entries_carry_diagnostic_message():
    rendered = format_round_notifications({
        'sign': {'total': 3, 'executed': 0, 'next': 2, 'entries': [
            ('Yema', {'status': 'network_error', 'message': '签到页面不可达：网络超时/无响应'}),
            ('Sbao', {'status': 'protocol_pending', 'message': '未发现唯一签到表单'}),
        ]},
        'login': {'total': 1, 'executed': 0, 'next': 1, 'entries': [
            ('Dic', {'status': 'unconfirmed', 'message': '登录页面不可达'})]},
    })
    sign_text = rendered[0][2]
    assert '【Yema】网络请求失败或超时，本轮未确认，稍后自动重试（签到页面不可达：网络超时/无响应）' in sign_text
    assert '【Sbao】验证码/协议未适配，未提交（未发现唯一签到表单）' in sign_text
    login_text = rendered[1][2]
    assert '【Dic】模拟登录结果未确认，请人工核验（登录页面不可达）' in login_text


def test_build_rich_blocks_structure_and_icons():
    from autoptcheckin.core.notify import build_rich_blocks

    blocks = build_rich_blocks({
        'sign': {'total': 3, 'executed': 2, 'next': 1, 'entries': [
            ('Gamma', {'status': 'failed', 'message': '立即签到'}),
            ('Alpha', {'status': 'success', 'message': '获得 50 魅力'}),
            ('Beta', {'status': 'already'}),
        ]},
        'login': {'total': 1, 'executed': 1, 'next': 0, 'entries': [
            ('Dic', {'status': 'unconfirmed', 'message': '登录页面不可达'})]},
    })
    sign = blocks['sign']
    # 计数行（无标题）+ 分节标题（无正文）+ 逐站行（标题=图标+站名）
    assert sign[0] == {'title': None, 'text': '全部签到: 3 · 本次签到: 2 · 成功: 2 · 失败（下次签到）: 1'}
    assert sign[1] == {'title': '签到明细', 'text': None}
    # 排序：成功 → 已签 → 失败；图标按 bucket
    assert [(b['title'], b['text']) for b in sign[2:]] == [
        ('✅ Alpha', '签到成功，获得 50 魅力'),
        ('✔️ Beta', '今日已签到'),
        ('❌ Gamma', '签到失败，立即签到'),
    ]
    assert blocks['login'][0]['text'] == '全部模拟登录: 1 · 本次模拟登录: 1 · 成功: 0 · 失败（下次模拟登录）: 1'
    assert blocks['login'][2] == {'title': '⏳ Dic', 'text': '模拟登录结果未确认，请人工核验（登录页面不可达）'}


def test_build_rich_blocks_skips_empty_tracks():
    from autoptcheckin.core.notify import build_rich_blocks

    assert build_rich_blocks({'sign': {'total': 0, 'executed': 0, 'next': 0, 'entries': []}}) == {}
    assert build_rich_blocks({}) == {}
