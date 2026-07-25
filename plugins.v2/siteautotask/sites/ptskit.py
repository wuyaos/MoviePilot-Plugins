"""Ptskit（PTS）站点适配。

喊话逻辑参考 groupchatzone 的 PtskitHandler：
- 发送后解析 magic-reward-top / shoutrow 中的系统奖励
- 识别「用户「{username}」获得魔力值」「今日已领取过」为反馈
任务合并 ptautotask 的 Ptskit：魔力值任务2 申领。
"""
from typing import Tuple
from lxml import etree
from app.log import logger

from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType
from ..base.result import TaskResult


class PtskitHandler(CapabilityHandler):
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

    def send_messagebox(self, message: str = None, callback=None) -> Tuple[bool, str]:
        if not message:
            return False, "消息内容不能为空"
        try:
            response = self._send_get_request(
                self.site_url + "/shoutbox.php",
                params={"shbox_text": message, "shout": "我喊", "sent": "yes", "type": "shoutbox"})
            if not response:
                return False, "请求失败"
            content = response.text
            username = self.get_username()
            try:
                html = etree.HTML(content)
                if html is None:
                    return False, "页面解析失败"
                # 1. 顶部系统奖励信息
                for node in html.xpath(
                        "//div[contains(@class, 'magic-reward-top') and contains(@class, 'system-msg')]"):
                    feedback = self._extract_feedback(node, username, message)
                    if feedback:
                        self._last_message_result = feedback
                        return True, feedback
                # 2. 群聊行
                for row in html.xpath("//table//tr/td[contains(@class, 'shoutrow')]"):
                    feedback = self._extract_feedback(row, username, message)
                    if feedback:
                        self._last_message_result = feedback
                        return True, feedback
                    # 自己发送的消息也算成功
                    if username and username in "".join(row.xpath(".//text()")) and message in "".join(row.xpath(".//text()")):
                        return True, "消息已发送"
                if 'name="shbox_text"' in content or 'id="shbox_text"' in content:
                    return True, "消息已发送 (未检测到特定反馈)"
            except Exception as e:
                logger.error(f"Ptskit：解析HTML失败：{e}")
                return True, "消息已发送 (解析反馈失败)"
            return True, "消息已发送 (未获得反馈)"
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
        if not self._last_message_result:
            return None
        text = str(self._last_message_result)
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

    @task_info("{client_name}魔力值任务2", "领取Ptskit魔力值任务2", TaskType.CLAIM)
    def daily_claim_task(self):
        return self.client.claim_task("12")

    @task_info("{client_name}喊话", "执行Ptskit喊话并解析魔力值反馈", TaskType.CHAT)
    def daily_shotbox(self):
        ok, msg = self.client.send_messagebox("求魔力值")
        return TaskResult.ok(msg) if ok else TaskResult.fail(msg)
