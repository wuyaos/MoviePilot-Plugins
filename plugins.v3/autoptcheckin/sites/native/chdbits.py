"""CHDBits: V2-derived declaration; production verification remains gated."""
from ...core.bakatest import BakatestSignin
from ...core.sitemodel import RecordSpec


class CHDBits(BakatestSignin):
    id = 'chdbits'
    name = 'CHDBits'
    url = 'https://ptchdbits.co/'
    attendance_path = '/bakatest.php'
    hook_implemented = True
    # 答题类：误答有账号风险，仅保留模拟登录（配置/数据卡 ⚠ 徽标）。
    login_notice = 'CHDBits 为答题类签到，误答有账号风险，建议仅人工登录'
    record_spec = RecordSpec('//*[@id="batch2-message-pending-calibration"]', {'今天已经签过到了': 'signed', '未签到': 'unsigned'})
