"""猪猪新版 HTTP 声明与当日日历判据；会话执行见 integrations/piggo.py。"""
from ...core.credentials import CredentialSpec
from ...core.models import SignStatus
from ...core.sitemodel import RecordSpec, SiteModule


def calendar_today(payload):
    """今日、选中日期、详情日期一致，且两处 checked 状态一致才确认。"""
    if not isinstance(payload, dict):
        return None
    selected, detail, cells = payload.get('selected'), payload.get('detail'), payload.get('cells')
    if not isinstance(selected, str) or not isinstance(detail, dict) or not isinstance(cells, list):
        return None
    today = [cell for cell in cells if isinstance(cell, dict) and cell.get('is_today') is True]
    if len(today) != 1 or today[0].get('ymd') != selected or detail.get('ymd') != selected:
        return None
    attendance = detail.get('attendance')
    if not isinstance(attendance, dict) or attendance.get('status') not in ('checked', 'today'):
        return None
    if today[0].get('checked') is not (attendance['status'] == 'checked'):
        return None
    return {'date': selected, 'status': attendance['status']}


class Piggo(SiteModule):
    id = 'piggo'
    name = '猪猪'
    url = 'https://piggo.me/'
    credential = CredentialSpec(kind='password', cookie_sources=())
    login_capable = True
    emulate = False
    headful = False
    record_spec = RecordSpec('', {})

    def signin(self, ctx):
        # 原生入口对该站分派到 HTTP 会话集成，不得退回旧页/空 Cookie 通道。
        return ctx.result(status=SignStatus.UNCONFIRMED, message='请通过猪猪 HTTP 会话通道执行')
