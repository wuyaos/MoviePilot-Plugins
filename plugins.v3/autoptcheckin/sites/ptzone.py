# input: PTzone 站点 Cookie、UA、代理配置
# output: PTzone attendance.php POST 签到处理器
# pos: AutoPtCheckin 站点适配层，复用无验证码 POST 签到通用基类
from app.plugins.autoptcheckin.helper.attendance_post_helper import _AttendancePostHandler


class PTzone(_AttendancePostHandler):
    """PTzone 签到：attendance.php 表单无验证码，POST 即签到（繁体站点）。"""

    site_url = "ptzone.xyz"
    _signin_url = "https://ptzone.xyz/attendance.php"
    _success_texts = ["簽到成功", "签到成功", "簽到已得", "签到已得"]
    _repeat_texts = ["今天已經簽到過", "今天已经签到过", "請勿重複刷新", "已經簽到", "已经签到", "今日已簽到", "今日已签到"]
