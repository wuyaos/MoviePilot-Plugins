# input: 海棠 htpt.cc 站点 Cookie、UA、代理与 attendance.php 页面
# output: 提交 action=sign 后回读当日签到状态
# pos: AutoPtCheckin 站点适配层，处理海棠新版 button POST 表单
from app.plugins.autoptcheckin.helper.attendance_post_helper import _AttendancePostHandler


class Haitang(_AttendancePostHandler):
    """海棠签到：提交 ``action=sign``，并以回读页的“今日已签到”状态确认结果。"""

    site_url = "www.htpt.cc"
    _signin_url = "https://www.htpt.cc/attendance.php"
    _post_data = {"action": "sign"}
    _verify_page_state = True
    _success_texts = ["签到成功", "本次签到获得"]
    _repeat_texts = ["今日已签到", "今天已签到", "今天已经签到"]
    _verified_success_texts = _success_texts + _repeat_texts
