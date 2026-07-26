"""Moment 站点适配。

groupchatzone 独有站点，喊话反馈解析型。
- 发送后从 shoutbox 解析，匹配「【{username}的女友】」格式反馈
"""
from typing import Optional, Tuple
import time
from lxml import etree
from app.log import logger

from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType
from ..base.result import TaskResult


class MomentHandler(CapabilityHandler):
    MESSAGE_INTERVAL = 120  # Moment多消息间隔秒数
    def __init__(self, site_info: dict):
        super().__init__(site_info)
        self.shoutbox_url = self.site_url + "/shoutbox.php"

    @staticmethod
    def get_site_name():
        return "Moment"

    @staticmethod
    def get_site_domain():
        return "m-team.io"

    def match(self) -> bool:
        return "moment" in self.site_name.lower()

    def send_messagebox(self, message: str = None, callback=None) -> Tuple[bool, str]:
        if not message:
            return False, "消息内容不能为空"
        try:
            ok, text = super().send_messagebox(message, callback)
            if not ok:
                return False, text
            username = self.get_username()
            if not username:
                return True, text
            self.wait_feedback()
            feedback = self._poll_feedback(username)
            if feedback:
                self._last_message_result = feedback
                return True, feedback
            return True, text
        except Exception as e:
            logger.error(f"Moment：发送消息失败：{e}")
            return False, str(e)

    def _poll_feedback(self, username: str) -> Optional[str]:
        """查找「【{username}的女友】」格式反馈。"""
        response = self._send_get_request(self.shoutbox_url)
        if not response:
            return None
        html = etree.HTML(response.text)
        if html is None:
            return None
        for row in html.xpath("//tr[td[@class='shoutrow']][position() <= 10]"):
            content = "".join(row.xpath(".//text()[not(ancestor::span[@class='date'])]")).strip()
            if f"【{username}的女友】" in content:
                return content
        return None

    def get_feedback(self, message: str = None):
        if not self._last_message_result:
            return None
        text = str(self._last_message_result)
        return {"site": self.site_name, "message": message, "rewards": [{
            "type": "raw_feedback", "description": text,
            "amount": "", "unit": "", "is_negative": False,
        }]}


class Tasks(BaseTask):
    def __init__(self, cookie=None):
        super().__init__(None)

    @task_info("{client_name}签到", "执行Moment签到", TaskType.CHECKIN)
    def daily_checkin(self):
        return self.client.attendance()

    @staticmethod
    def shotbox_messages():
        return ["茄子", "保一条"]

    @task_info("{client_name}喊话", "执行Moment喊话并解析女友反馈", TaskType.CHAT)
    def daily_shotbox(self):
        messages = self.client.shotbox_messages()
        results = []
        for i, msg in enumerate(messages):
            if i > 0:
                time.sleep(self.client.message_interval)
            ok, msg_text = self.client.send_messagebox(msg)
            results.append(msg_text)
        return TaskResult.ok("\n".join(results))
