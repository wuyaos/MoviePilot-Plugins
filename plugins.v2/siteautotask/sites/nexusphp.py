"""通用 NexusPHP 站点适配。

作为最后一个 Handler 兜底，具体站点模块应放在它之前并实现更精确的 match。
"""
from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType


class NexusPHPHandler(CapabilityHandler):
    @staticmethod
    def get_site_name():
        return "NexusPHP通用"

    @staticmethod
    def get_site_domain():
        return ""

    def match(self) -> bool:
        return bool(self.site_url and self.site_name)

    def get_feedback(self, message=None):
        if not self._last_message_result:
            return None
        text = str(self._last_message_result)
        reward_type = "raw_feedback"
        for keyword, kind in (("上传", "上传量"), ("下载", "下载量"), ("魔力", "魔力值"), ("工分", "工分"), ("VIP", "VIP")):
            if keyword.lower() in text.lower():
                reward_type = kind
                break
        return {"site": self.site_name, "message": message, "rewards": [{
            "type": reward_type, "description": text, "amount": "", "unit": "", "is_negative": False,
        }]}


class Tasks(BaseTask):
    def __init__(self, cookie=None):
        super().__init__(None)

    @task_info("{client_name}签到", "执行{client_name}通用签到", TaskType.CHECKIN)
    def daily_checkin(self):
        return self.client.attendance()

    @task_info("{client_name}喊话", "执行{client_name}通用喊话", TaskType.CHAT)
    def daily_shotbox(self):
        ok, msg = self.client.send_messagebox("求上传")
        return msg if ok else f"喊话失败: {msg}"
