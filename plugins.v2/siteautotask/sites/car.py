"""财神/CARPT（Car）站点适配。

ptautotask 独有站点，标准 NexusPHP。
注意：上游 site_name 为 "CARPT"，domain 为 carpt.net。
任务：签到、天天快乐任务申领。
"""
from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType
from ..utils.request import parse_json_response


class CarHandler(CapabilityHandler):
    @staticmethod
    def get_site_name():
        return "CARPT"

    @staticmethod
    def get_site_domain():
        return "carpt.net"

    def match(self) -> bool:
        return "carpt" in self.domain or "carpt" in self.site_name.lower()

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

    @task_info("{client_name}签到", "执行CARPT签到", TaskType.CHECKIN)
    def daily_checkin(self):
        return self.client.attendance()

    @task_info("{client_name}任务领取", "领取CARPT天天快乐任务", TaskType.CLAIM)
    def daily_claim_task(self, task_id=None):
        return self.client.claim_task(task_id or "5")
