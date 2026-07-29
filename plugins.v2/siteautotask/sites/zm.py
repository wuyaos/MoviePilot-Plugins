"""织梦站点适配。

织梦的奖励反馈依赖邮件/群聊区，单独模块化，避免污染通用 NexusPHP 执行流程。
"""
import time
from lxml import etree
from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType


class ZmHandler(CapabilityHandler):
    # 皮总对连续请求的接受窗口高于全局默认，实测 30 秒后第二条仍可能不入区。
    MESSAGE_INTERVAL = 60

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

    def shoutbox_profile(self):
        from ..base.shoutbox import FeedbackDirection, ShoutboxProfile
        return ShoutboxProfile(
            path="/shoutbox.php?type=shoutbox",
            row_xpath="//td[contains(@class, 'shoutrow')]",
            direction=FeedbackDirection.BEFORE,
            is_feedback=lambda row, username: "皮总" in row.text and f"@{username}" in row.text
            and any(key in row.text for key in ("响应", "扣减", "赠送", "没有理", "明天再来")),
            message_terms=lambda message: ["皮总", message.split("，")[-1]],
            confirmation_wait_seconds=2,
        )

    def get_feedback(self, message=None):
        """从确认快照关联的皮总反馈解析实际奖励类型。"""
        observation = getattr(self, "_chat_observation", None)
        feedback = observation.feedback.text if observation and observation.feedback else ""
        if not feedback:
            return None
        is_negative = any(key in feedback for key in ("没有理", "明天再来"))
        if is_negative:
            reward_type = "raw_feedback"
        elif "下载" in feedback:
            reward_type = "下载量"
        elif "魔力" in feedback:
            reward_type = "魔力值"
        elif "上传" in feedback:
            reward_type = "上传量"
        elif "电力" in feedback:
            reward_type = "电力"
        else:
            reward_type = "raw_feedback"
        return {"site": self.site_name, "message": message, "rewards": [{
            "type": reward_type, "description": feedback,
            "amount": "", "unit": "", "is_negative": is_negative,
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
        messages = self.client.shotbox_messages()
        results = []
        for i, msg in enumerate(messages):
            if i > 0:
                time.sleep(self.client.message_interval)
            ok, info = self.client.send_messagebox(msg)
            results.append(info)
        return "\n".join(results)
