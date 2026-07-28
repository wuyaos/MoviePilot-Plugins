"""LuckPT 站点适配。

groupchatzone 独有站点，喊话反馈解析型。
- 采用非标准 DIV+Flex 布局（wish-bubble-system / chat-message-container）
- 优先解析许愿池系统反馈：@username 幸运池听到了你的愿望...
- 其次解析聊天区 @username 的回复
"""
from typing import Optional, Tuple
from lxml import etree
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

    def send_messagebox(self, message: str = None, callback=None) -> Tuple[bool, str]:
        if not message:
            return False, "消息内容不能为空"
        try:
            ok, text = super().send_messagebox(message, callback)
            if not ok or getattr(self, "_chat_confirmation_in_progress", False):
                return ok, text
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
            logger.error(f"LuckPT：发送消息失败：{e}")
            return False, str(e)

    def _poll_feedback(self, username: str) -> Optional[str]:
        """优先解析许愿池系统反馈，其次解析聊天区。"""
        response = getattr(self, "_last_shoutbox_snapshot", None) or self._send_get_request(self.shoutbox_url)
        if not response:
            return None
        html = etree.HTML(response.text)
        if html is None:
            return None
        # 1. 许愿池系统反馈
        for node in html.xpath("//div[contains(@class, 'wish-bubble-system')]//div[contains(@class, 'wish-content')]"):
            text = "".join(node.xpath(".//text()")).strip()
            if f"@{username}" in text:
                return text
        # 2. 聊天区 @username 回复
        for container in html.xpath("//div[contains(@class, 'chat-message-container')][position() <= 10]"):
            content_nodes = container.xpath(".//div[contains(@class, 'chat-content')]")
            if not content_nodes:
                continue
            content = "".join(content_nodes[0].xpath(".//text()")).strip()
            if f"@{username}" in content:
                return content
        return None

    def get_feedback(self, message: str = None):
        username = self.get_username()
        if username:
            feedback = self._poll_feedback(username)
            if feedback:
                self._last_message_result = feedback
        if not self._last_message_result:
            return None
        text = str(self._last_message_result)
        reward_type = "raw_feedback"
        if "幸运星" in text:
            reward_type = "幸运星"
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
