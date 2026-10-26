"""PTTime reads its personal attendance history rather than whole-page action text."""
from datetime import datetime
from zoneinfo import ZoneInfo

from ...core.get_signin import GetSignin
from ...core.sitemodel import RecordSpec


class PTTime(GetSignin):
    id = 'pttime'
    name = 'PTTime'
    url = 'https://www.pttime.org/'
    attendance_path = '/attendance.php?type=list'
    action_path = '/attendance.php'
    action_referer = True
    use_default_message = False
    record_spec = RecordSpec('//span[starts-with(normalize-space(.),"签到日：")]', {})

    def message_spec(self):
        today = datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d')
        # The personal history labels each day explicitly; old days cannot prove today's sign-in.
        message = f'//span[normalize-space(.)="签到日：{today}"]'
        return RecordSpec(message, {f'签到日：{today}': 'signed'})
