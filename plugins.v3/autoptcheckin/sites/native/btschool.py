"""BTSchool: V2-derived declaration; production verification remains gated."""
from ...core.get_signin import GetSignin
from ...core.sitemodel import RecordSpec


class BTSchool(GetSignin):
    id = 'btschool'
    name = 'BTSchool'
    url = 'https://pt.btschool.club/'
    attendance_path = '/'
    hook_implemented = True
    action_path = '/index.php?action=addbonus'
    record_spec = RecordSpec('//*[@id="batch2-message-pending-calibration"]', {})
    # V2 infers success from absence of 每日签到; absence alone is not positive evidence.
