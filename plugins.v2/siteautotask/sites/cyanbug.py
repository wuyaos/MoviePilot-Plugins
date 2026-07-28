"""大青虫(Cyanbug)站点适配。

ptautotask 独有站点，标准 NexusPHP。
注意：上游 site_name 为 "大青虫"，但 13City 也叫大青虫；
通过 domain (cyanbug.net vs 13city.org) 区分，避免 match 冲突。
任务：签到、喊话（青虫娘，无特殊反馈解析，走通用 NexusPHP 喊话）。
"""
import time

from lxml import etree

from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType
from ..base.result import TaskResult


class CyanbugHandler(CapabilityHandler):
    # 青虫娘对连续祈愿存在频率限制，给第二条魔力请求保留更长窗口。
    MESSAGE_INTERVAL = 60

    @staticmethod
    def shotbox_messages():
        return ["青虫娘，求上传", "青虫娘，求魔力"]
    @staticmethod
    def get_site_name():
        return "大青虫"

    @staticmethod
    def get_site_domain():
        return "cyanbug.net"

    def match(self) -> bool:
        return "大青虫" in self.site_name or "cyanbug" in self.domain

    def get_feedback(self, message=None):
        # 单条展开时按消息重新查询反馈，避免被后续消息覆盖。
        if message:
            self._last_message_result = self._poll_shoutbox_feedback(message)
        if not self._last_message_result:
            return None
        return {"site": self.site_name, "message": message, "rewards": [{
            "type": "raw_feedback", "description": self._last_message_result,
            "amount": "", "unit": "", "is_negative": False,
        }]}

    def _poll_shoutbox_feedback(self, message):
        """按喊话内容从 shoutbox 查找系统反馈。"""
        username = self.get_username()
        if not username:
            return None
        keyword = "上传量" if "上传" in message else "魔力值" if "魔力" in message else None
        response = self._send_get_request(self.site_url + "/shoutbox.php")
        if not response:
            return None
        html = etree.HTML(response.text or "")
        for row in html.xpath("//tr[td][position() <= 15]"):
            text = "".join(t.strip() for t in row.xpath(".//td//text()"))
            if "@" not in text or username not in text:
                continue
            if "青虫娘" not in text:
                continue
            if keyword and keyword not in text:
                continue
            return text
        return None


class Tasks(BaseTask):
    def __init__(self, cookie=None):
        super().__init__(None)

    @task_info("{client_name}签到", "执行大青虫签到", TaskType.CHECKIN)
    def daily_checkin(self):
        return self.client.attendance()


    @task_info("{client_name}喊话", "执行大青虫喊话（青虫娘）", TaskType.CHAT)
    def daily_shotbox(self):
        messages = self.client.shotbox_messages()
        results = []
        for i, msg in enumerate(messages):
            if i > 0:
                time.sleep(getattr(self.client, "message_interval", self.client.interval_cnt))
            ok, text = self.client.send_messagebox(msg)
            results.append(text if ok else f"失败: {text}")
        return TaskResult.ok("\n".join(results))
