"""PTTime: V2-derived declaration; production verification remains gated."""
from ...core.get_signin import GetSignin
from ...core.sitemodel import RecordSpec


class PTTime(GetSignin):
    id = 'pttime'
    name = 'PTTime'
    url = 'https://www.pttime.org/'
    attendance_path = '/'
    hook_implemented = True
    action_path = '/attendance.php'
    record_spec = RecordSpec('//*[@id="batch2-message-pending-calibration"]', {'签到成功': 'signed', '已签到': 'signed', '无需再签': 'signed', '未签到': 'unsigned'})
    # GET attendance.php signs; homepage is the only pre-read in this declaration.
