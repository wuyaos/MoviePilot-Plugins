"""CHDBits: V2-derived declaration; production verification remains gated."""
from ...core.bakatest import BakatestSignin
from ...core.sitemodel import RecordSpec


class CHDBits(BakatestSignin):
    id = 'chdbits'
    name = 'CHDBits'
    url = 'https://ptchdbits.co/'
    attendance_path = '/bakatest.php'
    hook_implemented = True
    record_spec = RecordSpec('//*[@id="batch2-message-pending-calibration"]', {'今天已经签过到了': 'signed', '未签到': 'unsigned'})
