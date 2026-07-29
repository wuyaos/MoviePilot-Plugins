"""PTLGS 站点适配。

喊话逻辑参考 groupchatzone 的 PtlgsHandler：
- 发送后轮询 shoutbox，匹配「黑丝娘」对 @用户名 的反馈
- 识别奖赏/获得/损失/明天再来吧
- 损失反馈标记 is_negative

任务合并 ptautotask 的 Lgs：签到、喊话（黑丝娘 求上传/求工分）。
"""
import time
from typing import Dict, Optional, Tuple

from app.log import logger

from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType
from ..base.result import TaskResult


class PtlgsHandler(CapabilityHandler):

    @staticmethod
    def shotbox_messages():
        return ["黑丝娘，求工分", "黑丝娘，求上传"]
    def __init__(self, site_info: dict):
        super().__init__(site_info)
        self.shoutbox_url = self.site_url + "/shoutbox.php"

    @staticmethod
    def get_site_name():
        return "PTLGS"

    @staticmethod
    def get_site_domain():
        return "ptlgs.org"

    def match(self) -> bool:
        return "ptlgs" in self.site_name.lower() or "ptlgs.org" in self.domain

    def shoutbox_profile(self):
        from ..base.shoutbox import FeedbackDirection, ShoutboxProfile
        return ShoutboxProfile(
            path="/shoutbox.php?type=shoutbox",
            row_xpath="//td[contains(@class, 'shoutrow')]",
            direction=FeedbackDirection.BEFORE,
            is_feedback=lambda row, username: "黑丝娘" in row.text and f"@{username}" in row.text
            and any(key in row.text for key in ("奖赏", "获得", "损失", "明天再来")),
            message_terms=lambda message: ["黑丝娘", message.split("，")[-1]],
            confirmation_wait_seconds=2,
        )

    def send_messagebox(self, message: str = None, callback=None) -> Tuple[bool, str]:
        if not message:
            return False, "消息内容不能为空"
        try:
            # 发送后的确认与反馈完全由引擎读取的 Profile 快照负责。
            return super().send_messagebox(message, callback)
        except Exception as e:
            logger.error(f"PTLGS：发送消息失败：{e}")
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
        return {
            "site": self.site_name, "message": message,
            "rewards": [{
                "type": reward_type, "description": text,
                "amount": "", "unit": "",
                "is_negative": "损失" in text,
            }],
        }


class Tasks(BaseTask):
    def __init__(self, cookie=None):
        super().__init__(None)

    @task_info("{client_name}签到", "执行PTLGS签到", TaskType.CHECKIN)
    def daily_checkin(self):
        return self.client.attendance()


    @task_info("{client_name}喊话", "执行PTLGS喊话并解析黑丝娘反馈", TaskType.CHAT)
    def daily_shotbox(self):
        messages = self.client.shotbox_messages()
        results = []
        for i, msg in enumerate(messages):
            if i > 0:
                time.sleep(self.client.message_interval)
            ok, text = self.client.send_messagebox(msg)
            results.append(text)
        return TaskResult.ok("\n".join(results))
