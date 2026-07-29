"""Ptskit（PTS）站点适配。

喊话逻辑参考 groupchatzone 的 PtskitHandler：
- 发送后解析 magic-reward-top / shoutrow 中的系统奖励
- 识别「用户「{username}」获得魔力值」「今日已领取过」为反馈
任务合并 ptautotask 的 Ptskit：魔力值任务2 申领。
"""
from typing import Tuple
from app.log import logger

from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType
from ..base.result import TaskResult


class PtskitHandler(CapabilityHandler):

    @staticmethod
    def get_claim_options():
        """可申领任务选项，id 为站点 exam_id。"""
        return [
            {"id": "15", "label": "永久邀请奖励"},
            {"id": "14", "label": "魔力值奖励3"},
            {"id": "13", "label": "魔力值奖励1"},
            {"id": "12", "label": "魔力值任务2"},
        ]

    def __init__(self, site_info: dict):
        super().__init__(site_info)
        self.shoutbox_url = self.site_url + "/shoutbox.php?type=shoutbox"

    @staticmethod
    def get_site_name():
        return "Ptskit"

    @staticmethod
    def get_site_domain():
        return "ptskit.org"

    def match(self) -> bool:
        return "pts" in self.site_name.lower() or "ptskit" in self.domain

    def shoutbox_profile(self):
        from ..base.shoutbox import FeedbackDirection, ShoutboxProfile
        return ShoutboxProfile(
            path="/shoutbox.php?type=shoutbox",
            row_xpath="//td[contains(@class, 'shoutrow')]",
            direction=FeedbackDirection.EXTERNAL,
            external_feedback_xpath="//div[contains(@class, 'magic-reward-top') and contains(@class, 'system-msg')]",
            is_feedback=lambda row, username: f"用户「{username}」" in row.text,
            message_terms=lambda message: [message],
            confirmation_wait_seconds=2,
        )

    def send_messagebox(self, message: str = None, callback=None) -> Tuple[bool, str]:
        if not message:
            return False, "消息内容不能为空"
        try:
            response = self._send_get_request(
                self.site_url + "/shoutbox.php",
                params={"shbox_text": message, "shout": "我喊", "sent": "yes", "type": "shoutbox"})
            if not response:
                return False, "请求失败"
            return True, "消息已发送"
        except Exception as e:
            logger.error(f"Ptskit：发送消息失败：{e}")
            return False, str(e)

    def _extract_feedback(self, node, username: str, message: str):
        text = "".join(node.xpath(".//text()[not(ancestor::span[@class='date'])]")).strip()
        if not username or f"用户「{username}」" not in text:
            return None
        if "获得" in text and "魔力值" in text:
            return text.replace("[系统]", "").strip()
        if "今日已领取过" in text:
            return text.replace("[系统]", "").strip()
        return None

    def get_feedback(self, message: str = None):
        observation = getattr(self, "_chat_observation", None)
        text = observation.feedback.text if observation and observation.feedback else ""
        if not text:
            return None
        text = text.replace("[系统]", "").strip()
        reward_type = "魔力值" if "魔力值" in text else "raw_feedback"
        return {"site": self.site_name, "message": message, "rewards": [{
            "type": reward_type, "description": text,
            "amount": "", "unit": "", "is_negative": False,
        }]}


class Tasks(BaseTask):
    def __init__(self, cookie=None):
        super().__init__(None)

    @task_info("{client_name}签到", "执行Ptskit签到", TaskType.CHECKIN)
    def daily_checkin(self):
        return self.client.attendance()

    @task_info("{client_name}任务申领", "申领Ptskit任务", TaskType.CLAIM)
    def claim(self, task_id=None):
        return self.client.claim_task(task_id)

    @task_info("{client_name}喊话", "执行Ptskit喊话并解析魔力值反馈", TaskType.CHAT)
    def daily_shotbox(self):
        ok, msg = self.client.send_messagebox("「短剧第一站」")
        return TaskResult.ok(msg) if ok else TaskResult.fail(msg)
