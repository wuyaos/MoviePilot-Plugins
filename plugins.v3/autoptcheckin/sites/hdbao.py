# input: HDBao 站点 Cookie、UA、代理配置
# output: HDBao attendance.php POST 签到处理器
# pos: AutoPtCheckin 站点适配层，复用无验证码 POST 签到通用基类
from app.plugins.autoptcheckin.helper.attendance_post_helper import _AttendancePostHandler


class HDBao(_AttendancePostHandler):
    """HDBao 签到：GET attendance.php 只展示表单，必须 POST 才会真正签到。"""

    site_url = "hdbao.cc"
    _signin_url = "https://hdbao.cc/attendance.php"
    _success_texts = ["签到成功", "签到已得", "获得", "连续签到"]
    _repeat_texts = ["今天已经签到过", "请勿重复刷新", "已经签到"]
