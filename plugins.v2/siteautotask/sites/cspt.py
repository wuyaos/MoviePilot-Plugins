"""财神（Cspt）站点适配。

ptautotask 独有站点，标准 NexusPHP。
任务：签到、西财神任务申领。
"""
from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType
from ..utils.request import parse_json_response


class CsptHandler(CapabilityHandler):
    @staticmethod
    def get_site_name():
        return "财神"

    @staticmethod
    def get_site_domain():
        return "cspt.top"

    def match(self) -> bool:
        return "cspt" in self.domain or self.site_name == "财神"

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

    @task_info("{client_name}签到", "执行财神签到", TaskType.CHECKIN)
    def daily_checkin(self):
        return self.client.attendance()

    @task_info("{client_name}任务领取", "领取财神西财神任务", TaskType.CLAIM)
    def daily_claim_task(self, task_id=None):
        return self.client.claim_task(task_id or "5")
