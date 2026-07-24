"""柠檬（LemonHD）站点适配。

ptautotask 独有站点，标准 NexusPHP。
任务：签到、每日神游（免费抽奖）。
"""
from lxml import etree

from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType
from ..base.result import TaskResult


class LemonHDHandler(CapabilityHandler):
    def __init__(self, site_info: dict):
        super().__init__(site_info)
        self.lottery_url = self.site_url + "/lottery.php"

    @staticmethod
    def get_site_name():
        return "柠檬"

    @staticmethod
    def get_site_domain():
        return "lemonhd.club"

    def match(self) -> bool:
        return "柠檬" in self.site_name or "lemonhd.club" in self.domain

    def attendance(self):
        """柠檬签到页面结构特殊，需自定义解析。"""
        response = self._send_get_request(
            self.site_url + "/attendance.php",
            rt_method=lambda r: "".join(etree.HTML(r.text).xpath("//table//tr/td/text()")).strip())
        return response or "签到失败"

    def daily_lottery(self):
        """每日免费神游：POST type=0 到 lottery.php。"""
        response = self._send_post_request(self.lottery_url, data={"type": "0"})
        if response is None:
            return False, "抽奖请求失败"
        text = "".join(etree.HTML(response.text).xpath("//table/tr[1]/td[1]/text()")).strip()
        return True, text or "抽奖完成"


class Tasks(BaseTask):
    def __init__(self, cookie=None):
        super().__init__(None)

    @task_info("{client_name}签到", "执行柠檬签到", TaskType.CHECKIN)
    def daily_checkin(self):
        return self.client.attendance()

    @task_info("每日神游", "执行柠檬每日免费神游", TaskType.LOTTERY)
    def daily_lottery(self):
        ok, msg = self.client.daily_lottery()
        return TaskResult.ok(msg) if ok else TaskResult.fail(msg)
