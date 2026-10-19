# input: 海棠 htpt.cc 站点 Cookie、UA、代理与 attendance.php 页面
# output: 提交 action=sign 后回读当日签到状态
# pos: AutoPtCheckin 站点适配层，处理海棠新版 button POST 表单
from lxml import etree

from app.log import logger
from app.plugins.autoptcheckin.helper.attendance_post_helper import _AttendancePostHandler
from app.utils.site import SiteUtils


class Haitang(_AttendancePostHandler):
    """海棠签到：提交 ``action=sign``，并以当日单元格状态确认结果。"""

    site_url = "www.htpt.cc"
    _signin_url = "https://www.htpt.cc/attendance.php"
    _post_data = {"action": "sign"}
    _verify_page_state = True
    _success_texts = ["签到成功", "本次签到获得"]
    _repeat_texts = ["今日已签到", "今天已签到", "今天已经签到"]
    _verified_success_texts = _success_texts + _repeat_texts

    def _verify_attendance_page(self, site, response, before_post: bool):
        if response and response.status_code == 200:
            html_text = response.text or ""
            if SiteUtils.is_logged_in(html_text) and "login.php" not in html_text:
                html = etree.HTML(html_text)
                today_signed = bool(html is not None and html.xpath(
                    '//td[contains(concat(" ",normalize-space(@class)," ")," att-today ") '
                    'and contains(concat(" ",normalize-space(@class)," ")," att-signed ")]'
                ))
                if today_signed:
                    if before_post:
                        logger.info(f"{site} 今日已签到")
                        return True, "今日已签到"
                    logger.info(f"{site} 签到成功（已回读今日状态）")
                    return True, "签到成功"
        return super()._verify_attendance_page(site, response, before_post)
