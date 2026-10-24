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
    title, text = rendered[0]
    assert title == '【站点自动签到】'
    assert text.splitlines()[:4] == ['全部签到: 4', '本次签到: 3', '成功: 2', '失败（下次签到）: 2']
    # 逐站行只显示本轮实际执行的站点，未执行的（今日已签）不出现
    assert '【已签站】' not in text
    assert text.index('【Done】') < text.index('【Already】') < text.index('【Failed】')
    assert '【Failed】签到失败，Cookie 已失效' in text
    assert rendered[1][0] == '【站点自动登录】'
    assert '【Login】模拟登录成功，页面可达' in rendered[1][1]
