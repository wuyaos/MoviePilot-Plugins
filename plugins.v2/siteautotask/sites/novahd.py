"""NovaHD 站点适配。

ptautotask 独有站点，标准 NexusPHP。
任务：签到、保种任务申领。
"""
from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType
from ..utils.request import parse_json_response


class NovaHDHandler(CapabilityHandler):

    @staticmethod
    def get_claim_options():
        """可申领任务选项，id 为站点 exam_id。"""
        return [
            {"id": "3", "label": "保种任务"},
            {"id": "2", "label": "转种任务"},
        ]

    @staticmethod
    def get_site_name():
        return "NovaHD"

    @staticmethod
    def get_site_domain():
        return "novahd.top"

    def match(self) -> bool:
        return "novahd" in self.domain or "novahd" in self.site_name.lower()

    def claim_task(self, task_id: str, callback=None):
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

    @task_info("{client_name}签到", "执行NovaHD签到", TaskType.CHECKIN)
    def daily_checkin(self):
        return self.client.attendance()

    @task_info("{client_name}任务申领", "申领NovaHD任务", TaskType.CLAIM)
    def claim(self, task_id=None):
        return self.client.claim_task(task_id)

