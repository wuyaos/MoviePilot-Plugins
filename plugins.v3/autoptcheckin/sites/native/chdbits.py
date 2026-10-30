"""CHDBits: V2-derived declaration; production verification remains gated."""
from ...core.bakatest import BakatestSignin
from ...core.sitemodel import RecordSpec


class CHDBits(BakatestSignin):
    id = 'chdbits'
    name = 'CHDBits'
    url = 'https://ptchdbits.co/'
    attendance_path = '/bakatest.php'
    # 答题类：误答有账号风险，仅保留模拟登录（配置/数据卡 ⚠ 徽标）。
    signin_capable = False
    signin_note = '答题类签到不建议使用（误答有账号风险），仅保留模拟登录'
    login_notice = 'CHDBits 为答题类签到，误答有账号风险，建议仅人工登录'
    record_spec = RecordSpec('', {'今天已经签过到了': 'signed', '未签到': 'unsigned'})
