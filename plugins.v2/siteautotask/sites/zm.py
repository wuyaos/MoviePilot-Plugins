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
    def shotbox_messages():
        return ["皮总，求上传", "皮总，求电力"]
    @staticmethod
    def get_site_name():
        return "织梦"

    @staticmethod
    def get_site_domain():
        return "zmpt.cc"

    def match(self) -> bool:
        return "织梦" in self.site_name or "zmpt.cc" in self.domain

    def send_messagebox(self, message=None, callback=None):
        # 织梦喊话发送后由 get_feedback 重新读喊话区解析系统反馈。
        return super().send_messagebox(message, callback or (lambda response: ""))

    def wait_feedback(self):
        # 织梦电力奖励通过站内信延迟发放，需等待系统反馈生成后再读喊话区。
        import time
        time.sleep(max(0, int(self.feedback_timeout)))

    def get_feedback(self, message=None):
        # 重新读取喊话区，查找系统 @ 用户名的反馈行（如“@用户：皮总没有理你，明天再来吧”）。
        response = self._send_get_request(self.site_url + "/shoutbox.php")
        if not response:
            return None
        html = etree.HTML(response.text or "")
        for row in html.xpath("//tr[td]"):
            line = "".join(t.strip() for t in row.xpath(".//td//text()"))
            # 系统反馈含 @ 用户名；自己发的喊话不含 @。
            if "@" not in line:
                continue
            if any(k in line for k in ("皮总", "明天再来", "电力", "魔力", "上传", "没有理")):
                is_negative = "没有理" in line or "明天再来" in line
                return {"site": self.site_name, "message": message, "rewards": [{
                    "type": "电力", "description": line,
                    "amount": "", "unit": "", "is_negative": is_negative,
                }]}
        return None

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
        messages = self.client.shotbox_messages()
        results = []
        for i, msg in enumerate(messages):
            if i > 0:
                time.sleep(self.client.message_interval)
            ok, info = self.client.send_messagebox(msg)
            results.append(info)
        return "\n".join(results)
