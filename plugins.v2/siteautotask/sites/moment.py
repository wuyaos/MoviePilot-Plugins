"""Moment 站点适配。

groupchatzone 独有站点，喊话反馈解析型。
- 发送后从 shoutbox 解析，匹配「【{username}的女友】」格式反馈
"""
from typing import Tuple
import time
from app.log import logger

from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType
from ..base.result import TaskResult


class MomentHandler(CapabilityHandler):

    @staticmethod
    def shotbox_messages():
        return ["茄子", "保一条"]
    MESSAGE_INTERVAL = 120  # Moment多消息间隔秒数
    # 兼容旧 Handler 独立调用；生产确认路径使用 shoutbox_profile().direction。
    FEEDBACK_ROWS_BOTH = True

    def shoutbox_profile(self):
        from ..base.shoutbox import FeedbackDirection, ShoutboxProfile
        return ShoutboxProfile(
            path="/shoutbox.php",
            row_xpath="//td[contains(@class, 'shoutrow')]",
            direction=FeedbackDirection.BOTH,
            is_feedback=lambda row, username: f"【{username}的女友】" in row.text,
            message_terms=lambda message: [message],
            confirmation_wait_seconds=2,
        )

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
            # 发送后的确认与反馈完全由引擎读取的 Profile 快照负责。
            return super().send_messagebox(message, callback)
        except Exception as e:
            logger.error(f"Moment：发送消息失败：{e}")
            return False, str(e)


    def get_feedback(self, message: str = None):
        # 反馈已由 Profile 在确认快照中关联（女友反馈可能在本条上方或下方）。
        observation = getattr(self, "_chat_observation", None)
        text = observation.feedback.text if observation and observation.feedback else ""
        if not text:
            return None
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
