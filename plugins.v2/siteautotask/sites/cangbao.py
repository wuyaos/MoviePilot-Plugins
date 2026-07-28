"""藏宝阁站点适配。"""
import re
import time
from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType
from ..base.result import TaskResult


class CangbaoHandler(CapabilityHandler):

    @staticmethod
    def shotbox_messages():
        return ["阁主，求上传", "阁主，求魔力"]

    @staticmethod
    def get_claim_options():
        """可申领任务选项，id 为站点 exam_id。"""
        return [
            {"id": "12", "label": "做种传奇"},
            {"id": "11", "label": "做种之光"},
            {"id": "10", "label": "做种大师"},
            {"id": "9", "label": "做种达人"},
            {"id": "8", "label": "做种新秀"},
            {"id": "6", "label": "开阁元老"},
            {"id": "5", "label": "宗师巨匠"},
            {"id": "4", "label": "护宝大师"},
            {"id": "3", "label": "持证工匠"},
            {"id": "2", "label": "宝阁学徒"},
        ]

    @staticmethod
    def get_site_name():
        return "藏宝阁"

    @staticmethod
    def get_site_domain():
        return "cangbao.ge"

    def match(self) -> bool:
        return "藏宝阁" in self.site_name or self.domain == "cangbao.ge"

    def get_feedback(self, message=None):
        """仅从本条已确认喊话上方的附近行解析系统反馈。"""
        username = self.get_username()
        keyword = "上传" if message and "上传" in message else "魔力" if message and "魔力" in message else None
        for text in self.nearby_shoutbox_rows(message):
            text = re.sub(r"\s+", " ", text).strip()
            if not text.startswith("系统:") or f"@{username}" not in text:
                continue
            negative = any(item in text for item in ("已经求过", "明天再来"))
            if keyword and keyword not in text and not negative:
                continue
            return {"site": self.site_name, "message": message, "rewards": [{
                "type": "上传量" if "上传" in text else "魔力值" if "魔力" in text else "raw_feedback",
                "description": text, "amount": "", "unit": "", "is_negative": negative,
            }]}
        return None


class Tasks(BaseTask):
    def __init__(self, cookie=None):
        super().__init__(None)

    @task_info("{client_name}签到", "执行藏宝阁签到", TaskType.CHECKIN)
    def daily_checkin(self):
        return self.client.attendance()

    @task_info("{client_name}任务申领", "申领Cangbao任务", TaskType.CLAIM)
    def claim(self, task_id=None):
        return self.client.claim_task(task_id)


    @task_info("{client_name}喊话", "执行藏宝阁喊话并获取反馈", TaskType.CHAT)
    def daily_shotbox(self):
        messages = self.client.shotbox_messages()
        results = []
        for i, msg in enumerate(messages):
            if i > 0:
                time.sleep(self.client.message_interval)
            ok, msg_text = self.client.send_messagebox(msg)
            feedback = self.client.collect_message_feedback(msg) if ok else None
            results.append(feedback or msg_text)
        return TaskResult.ok("\n".join(results))
