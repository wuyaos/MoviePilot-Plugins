"""织梦站点适配。

织梦的奖励反馈依赖邮件/群聊区，单独模块化，避免污染通用 NexusPHP 执行流程。
"""
import time
from lxml import etree
from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType


class ZmHandler(CapabilityHandler):
    @staticmethod
    def get_site_name():
        return "织梦"

    @staticmethod
    def get_site_domain():
        return "zmpt.cc"

    def match(self) -> bool:
        return "织梦" in self.site_name or "zmpt.cc" in self.domain

    def send_messagebox(self, message=None, callback=None):
        # 织梦需要等待站点处理喊话，不主动伪造成功反馈。
        return super().send_messagebox(message, callback or (lambda response: ""))

    def get_feedback(self, message=None):
        if not self._last_message_result:
            return None
        return {"site": self.site_name, "message": message, "rewards": [{
            "type": "电力", "description": self._last_message_result,
            "amount": "", "unit": "", "is_negative": False,
        }]}

    def get_latest_message_time(self):
        def extract(response):
            html = etree.HTML(response.text)
            for row in html.xpath("//tr[td[@class='rowfollow']]"):
                if not row.xpath(".//a[contains(text(), '收到来自 zmpt 赠送的')]"):
                    continue
                spans = row.xpath(".//span[@title]")
                if spans and spans[0].get("title"):
                    return spans[0].get("title")
            return None
        return self._send_get_request(self.site_url + "/messages.php", rt_method=extract)


class Tasks(BaseTask):
    def __init__(self, cookie=None):
        super().__init__(None)

    @task_info("{client_name}签到", "执行织梦签到", TaskType.CHECKIN)
    def daily_checkin(self):
        return self.client.attendance()

    @task_info("{client_name}喊话", "执行织梦喊话并等待奖励反馈", TaskType.CHAT)
    def daily_shotbox(self):
        messages = ["皮总，求上传", "皮总，求电力"]
        results = []
        for i, msg in enumerate(messages):
            if i > 0:
                time.sleep(self.client.message_interval)
            ok, info = self.client.send_messagebox(msg)
            results.append(info)
        return "\n".join(results)
