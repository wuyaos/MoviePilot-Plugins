"""自由农场（FreeFarm）站点适配。

ptautotask 独有站点，标准 NexusPHP。domain 为 0ff.cc。
任务：签到、每周做种任务申领。
"""
from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType
from ..utils.request import parse_json_response


class FreeFarmHandler(CapabilityHandler):

    @staticmethod
    def get_claim_options():
        """可申领任务选项，id 为站点 exam_id。"""
        return [
            {"id": "12", "label": "做种积分"},
            {"id": "11", "label": "发种增量"},
            {"id": "9", "label": "下载增量"},
        ]

    @staticmethod
    def get_site_name():
        return "自由农场"

    @staticmethod
    def get_site_domain():
        return "0ff.cc"

    def match(self) -> bool:
        return "0ff.cc" in self.domain or "自由农场" in self.site_name

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

    @task_info("{client_name}签到", "执行自由农场签到", TaskType.CHECKIN)
    def daily_checkin(self):
        return self.client.attendance()

    @task_info("{client_name}任务申领", "申领FreeFarm任务", TaskType.CLAIM)
    def claim(self, task_id=None):
        return self.client.claim_task(task_id)

