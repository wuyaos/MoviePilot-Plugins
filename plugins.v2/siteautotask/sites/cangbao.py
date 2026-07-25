"""藏宝阁站点适配。"""
import re
from lxml import etree
from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType
from ..base.result import TaskResult


class CangbaoHandler(CapabilityHandler):
    @staticmethod
    def get_site_name():
        return "藏宝阁"

    @staticmethod
    def get_site_domain():
        return "cangbao.ge"

    def match(self) -> bool:
        return "藏宝阁" in self.site_name or self.domain == "cangbao.ge"

    def send_messagebox(self, message=None, callback=None):
        """发送后轮询系统反馈；不阻塞过长，失败时仍保留发送结果。"""
        callback = callback or (lambda response: " ".join(etree.HTML(response.text).xpath("//tr[1]/td//text()")))
        result = super().send_messagebox(message, callback)
        if not result[0]:
            return result
        username = self.get_username()
        if not username:
            return result
        self.wait_feedback()
        feedback = self._poll_feedback(username, message)
        if feedback:
            self._last_message_result = feedback
            return True, feedback
        return result

    def _poll_feedback(self, username, message=None):
        keyword = "上传量" if message and "上传" in message else None
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
        if not self._last_message_result:
            return None
        text = str(self._last_message_result)
        kind = "上传量" if "上传" in text else "魔力值" if "魔力" in text else "raw_feedback"
        return {"site": self.site_name, "message": message, "rewards": [{
            "type": kind, "description": text, "amount": "", "unit": "", "is_negative": False,
        }]}


class Tasks(BaseTask):
    def __init__(self, cookie=None):
        super().__init__(None)

    @task_info("{client_name}任务领取", "领取藏宝阁做种传奇任务", TaskType.CLAIM)
    def daily_claim_task(self):
        return self.client.claim_task("12")

    @task_info("{client_name}签到", "执行藏宝阁签到", TaskType.CHECKIN)
    def daily_checkin(self):
        return self.client.attendance()

    @task_info("{client_name}喊话", "执行藏宝阁喊话并获取反馈", TaskType.CHAT)
    def daily_shotbox(self):
        ok, msg = self.client.send_messagebox("求上传")
        return TaskResult.ok(msg) if ok else TaskResult.fail(msg)
