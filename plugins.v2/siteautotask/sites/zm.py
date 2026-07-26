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
        # 喊话区最新在上：反馈行在对应喊话行的上方（索引更小）。
        # 按“当前用户名 + 喊话内容”定位喊话行，再取前一行 @用户名反馈。
        response = self._send_get_request(self.site_url + "/shoutbox.php")
        if not response:
            return None
        html = etree.HTML(response.text or "")
        rows = ["".join(t.strip() for t in row.xpath(".//td//text()"))
                for row in html.xpath("//tr[td]")]
        rows = [r for r in rows if r]
        username = (self.get_username() or "").strip()
        target = (message or "").strip()
        for idx, line in enumerate(rows):
            # 跳过反馈行（含 @）
            if "@" in line:
                continue
            # 必须含当前用户名和本条喊话内容
            if username and username not in line:
                continue
            if target and target not in line:
                continue
            # 反馈在上一行
            if idx == 0:
                break
            fb = rows[idx - 1]
            if "@" not in fb or (username and f"@{username}" not in fb):
                break  # 上一行不是针对自己的反馈
            is_negative = any(k in fb for k in ("没有理", "明天再来"))
            is_reward = any(k in fb for k in ("响应", "扣减", "赠送", "电力", "魔力", "上传", "下载"))
            if "下载" in fb:
                reward_type = "下载量"
            elif "魔力" in fb:
                reward_type = "魔力"
            elif "上传" in fb:
                reward_type = "上传量"
            else:
                reward_type = "电力"
            return {"site": self.site_name, "message": message, "rewards": [{
                "type": reward_type, "description": fb,
                "amount": "", "unit": "", "is_negative": is_negative and not is_reward,
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
