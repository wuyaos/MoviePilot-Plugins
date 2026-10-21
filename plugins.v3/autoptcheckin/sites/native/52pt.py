"""52PT: V2-derived declaration; production verification remains gated."""
from ...core.bakatest import BakatestSignin
from ...core.sitemodel import RecordSpec


class Pt52(BakatestSignin):
    id = '52pt'
    name = '52PT'
    url = 'https://52pt.site/'
    attendance_path = '/bakatest.php'
    hook_implemented = True
    record_spec = RecordSpec('//*[@id="batch2-message-pending-calibration"]', {'今天已经签过到了': 'signed', '未签到': 'unsigned'})
