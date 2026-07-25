"""蟹黄堡（Crabpt）站点适配。

ptautotask 独有站点，标准 NexusPHP。
任务：签到、保种魔王任务申领、力争全勤任务申领。
"""
from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType
from ..utils.request import parse_json_response


class CrabptHandler(CapabilityHandler):

    @staticmethod
    def get_claim_options():
        """可申领任务选项，id 为站点 exam_id。"""
        return [
            {"id": "16", "label": "转种员专属任务"},
            {"id": "15", "label": "保种员专属2"},
            {"id": "14", "label": "保种员专属1"},
            {"id": "12", "label": "保种魔王"},
            {"id": "11", "label": "力争全勤奖"},
            {"id": "10", "label": "每月任务2"},
            {"id": "9", "label": "每月任务1"},
            {"id": "2", "label": "test转种项目"},
        ]

    @staticmethod
    def get_site_name():
        return "蟹黄堡"

    @staticmethod
    def get_site_domain():
        return "crabpt.vip"

    def match(self) -> bool:
        return "蟹黄堡" in self.site_name or "crabpt.vip" in self.domain

    def claim_task(self, task_id: str, callback=None):
        """蟹黄堡任务申领返回 JSON，统一解析 msg。"""
        response = self._send_post_request(
            self.site_url + "/ajax.php",
            data={"action": "claimTask", "params[exam_id]": task_id})
        if response is None:
            return "申领失败"
        result = parse_json_response(response, "申领失败")
        return result.get("msg", "未知错误")


class Tasks(BaseTask):
    def __init__(self, cookie=None):
        super().__init__(None)

    @task_info("{client_name}签到", "执行蟹黄堡签到", TaskType.CHECKIN)
    def daily_checkin(self):
        return self.client.attendance()

    @task_info("{client_name}任务申领", "申领Crabpt任务", TaskType.CLAIM)
    def claim(self, task_id=None):
        return self.client.claim_task(task_id)

