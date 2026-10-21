"""海胆: V2-derived declaration; production verification remains gated."""
from ...core.get_signin import GetSignin
from ...core.sitemodel import RecordSpec


class HaiDan(GetSignin):
    id = 'haidan'
    name = '海胆'
    url = 'https://www.haidan.cc/'
    attendance_path = '/index.php'
    hook_implemented = True
    action_path = '/signin.php'
    record_spec = RecordSpec('//input[@value="已经打卡"]', {'已经打卡': 'signed'})

