"""大青虫(Cyanbug)站点适配。

ptautotask 独有站点，标准 NexusPHP。
注意：上游 site_name 为 "大青虫"，但 13City 也叫大青虫；
通过 domain (cyanbug.net vs 13city.org) 区分，避免 match 冲突。
任务：签到、喊话（青虫娘，无特殊反馈解析，走通用 NexusPHP 喊话）。
"""
import time

from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType
from ..base.result import TaskResult


class CyanbugHandler(CapabilityHandler):
    @staticmethod
    def get_site_name():
        return "大青虫"

    @staticmethod
    def get_site_domain():
        return "cyanbug.net"

    def match(self) -> bool:
        return "大青虫" in self.site_name or "cyanbug" in self.domain

    def get_feedback(self, message=None):
        if not self._last_message_result:
            return None
        return {"site": self.site_name, "message": message, "rewards": [{
            "type": "raw_feedback", "description": self._last_message_result,
            "amount": "", "unit": "", "is_negative": False,
        }]}


class Tasks(BaseTask):
    def __init__(self, cookie=None):
        super().__init__(None)

    @task_info("{client_name}签到", "执行大青虫签到", TaskType.CHECKIN)
    def daily_checkin(self):
        return self.client.attendance()

    @task_info("{client_name}喊话", "执行大青虫喊话（青虫娘）", TaskType.CHAT)
    def daily_shotbox(self):
        messages = ("青虫娘，求上传", "青虫娘，求魔力")
        results = []
        for i, msg in enumerate(messages):
            if i > 0:
                time.sleep(self.client.interval_cnt)
            ok, text = self.client.send_messagebox(msg)
            results.append(text if ok else f"失败: {text}")
        return TaskResult.ok("\n".join(results))
