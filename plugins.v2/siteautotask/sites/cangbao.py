"""藏宝阁站点适配。"""
import re
import time
from lxml import etree
from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType
from ..base.result import TaskResult


class CangbaoHandler(CapabilityHandler):

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

    def collect_message_feedback(self, message):
        """在消息发送后单独等待并保存该消息的系统反馈。"""
        username = self.get_username()
        if not username:
            return None
        self.wait_feedback()
        feedback = self._poll_feedback(username, message)
        if not feedback:
            return None
        self._last_message_result = feedback
        message_feedbacks = getattr(self, "_message_feedbacks", [])
        message_feedbacks.append({"message": message, "text": feedback})
        self._message_feedbacks = message_feedbacks
        return feedback

    def _poll_feedback(self, username, message=None):
        keyword = "上传量" if message and "上传" in message else "魔力" if message and "魔力" in message else None
        response = self._send_get_request(self.site_url + "/shoutbox.php")
        if not response:
            return None
        html = etree.HTML(response.text)
        if html is None:
            return None
        for row in html.xpath("//td[contains(@class, 'shoutrow')][position() <= 20]"):
            text = re.sub(r"\s+", " ", "".join(row.xpath(".//text()[not(ancestor::span[@class='date'])]")).strip())
            if not text.startswith("系统:") or f"感谢 @{username} 的支持" not in text:
                continue
            if keyword and keyword not in text:
                continue
            return text
        return None

    def get_feedback(self, message=None):
        message_feedbacks = getattr(self, "_message_feedbacks", [])
        if not message_feedbacks and self._last_message_result:
            message_feedbacks = [{"message": message, "text": self._last_message_result}]
        if not message_feedbacks:
            return None
        rewards = []
        for item in message_feedbacks:
            text = str(item["text"])
            kind = "上传量" if "上传" in text else "魔力值" if "魔力" in text else "raw_feedback"
            sent_message = item.get("message")
            description = f"“{sent_message}”：{text}" if sent_message else text
            rewards.append({
                "type": kind, "description": description,
                "amount": "", "unit": "", "is_negative": False,
            })
        return {"site": self.site_name, "message": message, "rewards": rewards}


class Tasks(BaseTask):
    def __init__(self, cookie=None):
        super().__init__(None)

    @task_info("{client_name}签到", "执行藏宝阁签到", TaskType.CHECKIN)
    def daily_checkin(self):
        return self.client.attendance()

    @task_info("{client_name}任务申领", "申领Cangbao任务", TaskType.CLAIM)
    def claim(self, task_id=None):
        return self.client.claim_task(task_id)

    @staticmethod
    def shotbox_messages():
        return ["阁主，求上传", "阁主，求魔力"]

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
