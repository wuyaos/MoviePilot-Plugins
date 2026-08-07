# input: 慕雪阁站点 Cookie、UA、代理配置
# output: 慕雪阁 attendance.php POST 签到处理器
# pos: AutoPtCheckin 站点适配层，复用无验证码 POST 签到通用基类
from app.plugins.autoptcheckin.helper.attendance_post_helper import _AttendancePostHandler


class Muxuege(_AttendancePostHandler):
    """慕雪阁签到：attendance.php 表单无验证码，POST「立即签到」即签到。"""

    site_url = "pt.muxuege.org"
    _signin_url = "https://pt.muxuege.org/attendance.php"
    _success_texts = ["签到成功", "签到已得", "获得", "连续签到"]
    _repeat_texts = ["今天已经签到过", "请勿重复刷新", "已经签到", "今天已签到"]
    # 经真实页面验证：POST 后签到表单消失并显示「签到成功/第 N 次签到」
    _verify_page_state = True
    _verified_success_texts = ["签到成功", "签到已得", "连续签到", "本次签到获得"]
