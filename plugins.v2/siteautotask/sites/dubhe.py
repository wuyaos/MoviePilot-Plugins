"""天枢（Dubhe）站点适配。

groupchatzone 独有站点，喊话反馈解析型。
- 发送后从 shoutbox 解析，匹配用户名在内容中的回复
- 验证回复与请求类型匹配（求魔力→魔力值，求上传→上传量）
"""
from typing import Dict, Optional, Tuple
import time
from app.log import logger

from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType
from ..base.result import TaskResult


class DubheHandler(CapabilityHandler):

    @staticmethod
    def shotbox_messages():
        return ["天枢娘，求魔力", "天枢娘，求上传"]
    def __init__(self, site_info: dict):
        super().__init__(site_info)
        self.shoutbox_url = self.site_url + "/shoutbox.php"

    @staticmethod
    def get_site_name():
        return "天枢"

    @staticmethod
    def get_site_domain():
        return "dubhe.to"

    def match(self) -> bool:
        return "天枢" in self.site_name or "dubhe" in self.domain

    def shoutbox_profile(self):
        from ..base.shoutbox import FeedbackDirection, ShoutboxProfile
        return ShoutboxProfile(
            path="/shoutbox.php?type=shoutbox",
            row_xpath="//td[contains(@class, 'shoutrow')]",
            direction=FeedbackDirection.BEFORE,
            message_terms=lambda message: ["天枢", message.split("，")[-1]],
            confirmation_wait_seconds=2,
        )

    def send_messagebox(self, message: str = None, callback=None) -> Tuple[bool, str]:
        if not message:
            return False, "消息内容不能为空"
        try:
            return super().send_messagebox(message, callback)
        except Exception as e:
            logger.error(f"天枢：发送消息失败：{e}")
            return False, str(e)


    def get_feedback(self, message: str = None) -> Optional[Dict]:
        observation = getattr(self, "_chat_observation", None)
        text = observation.feedback.text if observation and observation.feedback else ""
        if not text:
            return None
        reward_type = "raw_feedback"
        for kw, kind in (("上传", "上传量"), ("下载", "下载量"), ("魔力", "魔力值"),
                          ("工分", "工分"), ("vip", "VIP")):
            if kw in text.lower():
                reward_type = kind
                break
        return {"site": self.site_name, "message": message, "rewards": [{
            "type": reward_type, "description": text,
            "amount": "", "unit": "", "is_negative": False,
        }]}


class Tasks(BaseTask):
    def __init__(self, cookie=None):
        super().__init__(None)

    @task_info("{client_name}签到", "执行天枢签到", TaskType.CHECKIN)
    def daily_checkin(self):
        return self.client.attendance()


    @task_info("{client_name}喊话", "执行天枢喊话并解析反馈", TaskType.CHAT)
    def daily_shotbox(self):
        messages = self.client.shotbox_messages()
        results = []
        for i, msg in enumerate(messages):
            if i > 0:
                time.sleep(self.client.message_interval)
            ok, text = self.client.send_messagebox(msg)
            results.append(text)
        return TaskResult.ok("\n".join(results))
