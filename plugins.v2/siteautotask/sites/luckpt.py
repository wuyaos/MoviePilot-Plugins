"""LuckPT 站点适配。

groupchatzone 独有站点，喊话反馈解析型。
- 采用非标准 DIV+Flex 布局（wish-bubble-system / chat-message-container）
- 优先解析许愿池系统反馈：@username 幸运池听到了你的愿望...
- 其次解析聊天区 @username 的回复
"""
from typing import Tuple
from app.log import logger

from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType
from ..base.result import TaskResult


class LuckptHandler(CapabilityHandler):
    def __init__(self, site_info: dict):
        super().__init__(site_info)
        self.shoutbox_url = self.site_url + "/shoutbox.php"

    @staticmethod
    def get_site_name():
        return "LuckPT"

    @staticmethod
    def get_site_domain():
        return "luckpt.de"

    def match(self) -> bool:
        return "luckpt" in self.site_name.lower() or "幸运" in self.site_name or "luckpt" in self.domain

    def shoutbox_profile(self):
        from ..base.shoutbox import FeedbackDirection, ShoutboxProfile
        return ShoutboxProfile(
            path="/shoutbox.php?type=shoutbox",
            row_xpath="//div[contains(@class, 'chat-message-container')]",
            direction=FeedbackDirection.EXTERNAL,
            external_feedback_xpath="//div[contains(@class, 'wish-bubble-system')]//div[contains(@class, 'wish-content')]",
            is_feedback=lambda row, username: f"@{username}" in row.text,
            message_terms=lambda message: [message],
            confirmation_wait_seconds=2,
        )

    def send_messagebox(self, message: str = None, callback=None) -> Tuple[bool, str]:
        if not message:
            return False, "消息内容不能为空"
        try:
            return super().send_messagebox(message, callback)
        except Exception as e:
            logger.error(f"LuckPT：发送消息失败：{e}")
            return False, str(e)


    def get_feedback(self, message: str = None):
        observation = getattr(self, "_chat_observation", None)
        text = observation.feedback.text if observation and observation.feedback else ""
        if not text:
            return None
        reward_type = "幸运星" if "幸运星" in text else "raw_feedback"
        for kw, kind in (("上传", "上传量"), ("下载", "下载量"), ("魔力", "魔力值")):
            if kw in text:
                reward_type = kind
                break
        return {"site": self.site_name, "message": message, "rewards": [{
            "type": reward_type, "description": text,
            "amount": "", "unit": "", "is_negative": False,
        }]}


class Tasks(BaseTask):
    def __init__(self, cookie=None):
        super().__init__(None)

    @task_info("{client_name}签到", "执行LuckPT签到", TaskType.CHECKIN)
    def daily_checkin(self):
        return self.client.attendance()

    @task_info("{client_name}喊话", "执行LuckPT喊话并解析许愿池反馈", TaskType.CHAT)
    def daily_shotbox(self):
        ok, msg = self.client.send_messagebox("幸运池祈愿")
        if not ok:
            return TaskResult.fail(msg)
        return TaskResult.ok(msg or "消息已发送，未解析到反馈")
