# input: DStudio 站点 Cookie、UA、代理配置
# output: DStudio attendance.php POST 签到处理器
# pos: AutoPtCheckin 站点适配层，复用无验证码 POST 签到通用基类
from app.plugins.autoptcheckin.helper.attendance_post_helper import _AttendancePostHandler


class DStudio(_AttendancePostHandler):
    """DStudio（Depth Studio）签到：attendance.php 表单无验证码，POST 即签到。"""

    site_url = "dstudio.me"
    _signin_url = "https://dstudio.me/attendance.php"
    # DStudio 经真实页面验证：未签到时存在 attendance-checkin-form，签到后表单
    # 消失并显示“签到成功”及导航栏“签到已得”。必须二次 GET 确认，避免
    # POST 响应中的奖励说明被“获得”“连续签到”等宽泛词误判为成功。
    _verify_page_state = True
    _verified_success_texts = ["签到成功", "签到已得"]
    _success_texts = ["签到成功", "签到已得", "获得", "连续签到"]
    _repeat_texts = ["今天已经签到过", "请勿重复刷新", "已经签到", "今天已签到"]
