"""梓喵（Azusa）站点任务申领适配。"""
import re

from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType
from ..utils.request import parse_json_response


class AzusaHandler(CapabilityHandler):
    @staticmethod
    def get_claim_options():
        """梓喵 task.php 页面实测的可申领任务，id 为 exam_id。"""
        return [
            {"id": "11", "label": "每日任务4（魔力+上传）"},
            {"id": "9", "label": "每日任务3（做种积分）"},
            {"id": "7", "label": "每日任务2（上传+做种积分）"},
            {"id": "6", "label": "每日任务1（发种）"},
            {"id": "15", "label": "月度任务5（发种+保种+上传）"},
            {"id": "14", "label": "月度任务4（发种）"},
            {"id": "13", "label": "月度任务3（保种+上传）"},
            {"id": "12", "label": "月度任务2（保种+上传）"},
            {"id": "8", "label": "月度任务1（发种）"},
            {"id": "10", "label": "七日任务2（发种）"},
            {"id": "5", "label": "七日任务1（保种）"},
        ]

    @staticmethod
    def get_site_name():
        return "梓喵"

    @staticmethod
    def get_site_domain():
        return "azusa.wiki"

    def match(self) -> bool:
        return "azusa.wiki" in self.domain or "梓喵" in self.site_name

    def _get_csrf_token(self):
        """梓喵领取接口要求 task.php 页面动态生成的 csrf_token。"""
        response = self._send_get_request(self.site_url + "/task.php")
        if not response:
            return ""
        match = re.search(r"csrf_token=([a-f0-9]{40})", response.text or "", re.I)
        return match.group(1) if match else ""

    def claim_task(self, task_id: str, callback=None):
        csrf_token = self._get_csrf_token()
        if not csrf_token:
            return "任务领取失败：未获取到 CSRF Token"
        response = self._send_post_request(
            f"{self.site_url}/ajax.php?csrf_token={csrf_token}",
            data={"action": "claimTask", "params[exam_id]": task_id},
        )
        if response is None:
            return "任务领取失败"
        result = parse_json_response(response, "任务领取失败")
        return result.get("msg", "未知错误")


class Tasks(BaseTask):
    def __init__(self, cookie=None):
        super().__init__(None)

    @task_info("{client_name}任务申领", "申领梓喵任务", TaskType.CLAIM)
    def claim(self, task_id=None):
        return self.client.claim_task(task_id)
