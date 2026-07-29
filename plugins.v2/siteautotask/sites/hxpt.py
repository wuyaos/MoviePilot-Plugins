"""好学（Hxpt）站点适配。

groupchatzone 独有站点，喊话反馈解析型。
- 发送后带 ajax_chat 参数轮询 shoutbox
- 查找 @用户名 的消息，检查上一行是否为"系统提示："
- 解析火花奖励类型
"""
import time
from typing import Optional, Tuple
from lxml import etree
from app.log import logger

from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType
from ..base.result import TaskResult
from ..utils.request import parse_json_response


class HxptHandler(CapabilityHandler):
    @staticmethod
    def get_claim_options():
        """好学 task.php 页面实测的可申领任务。"""
        return [
            {"id": "2", "label": "精进研习社"},
            {"id": "4", "label": "测（管理组任务）"},
        ]

    def __init__(self, site_info: dict):
        super().__init__(site_info)
        self.shoutbox_url = self.site_url + "/shoutbox.php"

    @staticmethod
    def get_site_name():
        return "好学"

    @staticmethod
    def get_site_domain():
        return "haoxue.net"

    def match(self) -> bool:
        return "好学" in self.site_name or "haoxue" in self.domain

    def shoutbox_profile(self):
        """好学仅 AJAX 流返回真实喊话记录，不能使用通用 shoutbox URL。"""
        from ..base.shoutbox import FeedbackDirection, ShoutboxProfile
        return ShoutboxProfile(
            path="/shoutbox.php?ajax_chat=1&type=",
            row_xpath="//td[contains(@class, 'shoutrow')]",
            direction=FeedbackDirection.BEFORE,
            # 好学的有效结果不一定含“火花”，如“明天再继续”也是本条学习反馈。
            is_feedback=lambda row, _username: "系统提示：" in row.text,
            retry_on_unconfirmed=False,
            message_terms=lambda _message: ["好好学习", "天天向上"],
            confirmation_wait_seconds=2,
        )

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
            logger.error(f"好学：发送消息失败：{e}")
            return False, str(e)

    def _poll_feedback(self, username: str) -> Optional[str]:
        """带 ajax_chat 参数轮询，查找 @用户名 消息的上一行系统提示。"""
        response = self._send_get_request(self.shoutbox_url, params={
            "ajax_chat": "1", "type": "", "t": str(int(time.time() * 1000))})
        if not response:
            return None
        html = etree.HTML(response.text)
        if html is None:
            return None
        rows = html.xpath("//tr[td[@class='shoutrow']][position() <= 10]")
        for i, row in enumerate(rows):
            content = " ".join(" ".join(row.xpath(
                ".//text()[not(ancestor::span[@class='date'])]")).split())
            if f"@{username}" in content or username in content:
                if i > 0:
                    prev = " ".join(" ".join(rows[i - 1].xpath(
                        ".//text()[not(ancestor::span[@class='date'])]")).split())
                    if "系统提示：" in prev:
                        return prev
        return None

    def claim_task(self, task_id: str):
        response = self._send_post_request(
            self.site_url + "/ajax.php",
            data={"action": "claimTask", "params[exam_id]": task_id},
        )
        if response is None:
            return "任务领取失败"
        return parse_json_response(response, "任务领取失败").get("msg", "未知错误")

    def get_feedback(self, message: str = None):
        observation = getattr(self, "_chat_observation", None)
        if message and observation and observation.feedback:
            self._last_message_result = observation.feedback.text
        if not self._last_message_result:
            return None
        text = str(self._last_message_result)
        reward_type = "火花" if "火花" in text else "raw_feedback"
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

    @task_info("{client_name}签到", "执行好学签到", TaskType.CHECKIN)
    def daily_checkin(self):
        return self.client.attendance()

    @task_info("{client_name}喊话", "执行好学喊话并解析火花反馈", TaskType.CHAT)
    def daily_shotbox(self):
        ok, msg = self.client.send_messagebox("好好学习天天向上")
        return TaskResult.ok(msg) if ok else TaskResult.fail(msg)

    @task_info("{client_name}任务申领", "申领好学任务", TaskType.CLAIM)
    def claim(self, task_id=None):
        return self.client.claim_task(task_id)
