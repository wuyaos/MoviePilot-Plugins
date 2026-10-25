"""PTzone: V2-derived declaration; production verification remains gated."""
from ...core.nexus import NexusSignin
from ...core.sitemodel import RecordSpec


class PTzone(NexusSignin):
    verified = True
    id = 'ptzone'
    name = 'PTzone'
    url = 'https://ptzone.xyz/'
    attendance_path = '/attendance.php'
    record_spec = RecordSpec('//*[@id="batch2-message-pending-calibration"]', {'簽到成功': 'signed', '签到成功': 'signed', '簽到已得': 'signed', '签到已得': 'signed', '今天已經簽到過': 'signed', '今天已经签到过': 'signed', '請勿重複刷新': 'signed', '已經簽到': 'signed', '已经签到': 'signed', '今日已簽到': 'signed', '今日已签到': 'signed', '未签到': 'unsigned'})
    signed_marker = '//a[@href="attendance.php" and contains(.,"簽到已得")]'
