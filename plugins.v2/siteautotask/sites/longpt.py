"""LongPT 站点适配。

包含通用签到、月度任务领取、喊话反馈以及每日抽奖能力。
真实抽奖/喊话由任务开关控制，本模块测试只使用 mock。
"""
import re
import time
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType
from ..base.result import TaskResult
from .capabilities import CapabilityHandler
from ..utils.request import parse_json_response


class LongPTHandler(CapabilityHandler):

    @staticmethod
    def get_claim_options():
        """可申领任务选项，id 为站点 exam_id。"""
        return [
            {"id": "8", "label": "发种-简单"},
            {"id": "7", "label": "发种-正常"},
            {"id": "6", "label": "发种-困难"},
            {"id": "5", "label": "保种-简单"},
            {"id": "4", "label": "保种-正常"},
            {"id": "2", "label": "保种-困难"},
        ]

    MESSAGE_INTERVAL = 60  # LongPT多消息间隔秒数
    api_base = "https://longpt.org/pt-api/v1"

    @staticmethod
    def get_site_name():
        return "LongPT"

    @staticmethod
    def get_site_domain():
        return "longpt.org"

    def match(self) -> bool:
        return "longpt" in self.site_name.lower() or self.domain == "longpt.org"

    def send_messagebox(self, message=None, callback=None):
        if not message:
            return False, "消息内容不能为空"
        try:
            response = self.session.post(
                f"{self.api_base}/nexus/shoutbox/shout",
                json={"text": message},
                timeout=30,
            )
            result = parse_json_response(response, "LongPT喊话请求失败")
            if result.get("code") == 0:
                text = result.get("msg", "")
                self._last_message_result = text
                return True, text
            return False, result.get("msg", "发送失败")
        except Exception as e:
            return False, f"发送异常: {e}"

    def get_feedback(self, message=None):
        text = (self._last_message_result or "").strip()
        if not text:
            return None
        clean = re.sub(r",?\[em\d+\]", "", text).strip()
        kind = "raw_feedback"
        for keyword, reward_type in (("魔力", "魔力值"), ("上传", "上传量"), ("下载", "下载量")):
            if keyword in clean:
                kind = reward_type
                break
        return {"site": self.site_name, "message": message, "rewards": [{
            "type": kind, "description": clean, "amount": "", "unit": "", "is_negative": False,
        }]}

    def daily_lottery(self):
        try:
            response = self.session.get(
                f"{self.api_base}/lucky/pluginsPrizeReceiptRecord/join",
                timeout=30,
            )
            result = parse_json_response(response, "LongPT抽奖请求失败")
            code = result.get("code")
            message = result.get("msg", "")
            # -1 表示已经参加过，当作幂等成功
            if code in (0, -1):
                return True, message
            return False, message or "抽奖失败"
        except Exception as e:
            return False, f"抽奖异常: {e}"


class Tasks(BaseTask):
    def __init__(self, cookie=None):
        super().__init__(None)

    @task_info("{client_name}签到", "执行 LongPT 签到", TaskType.CHECKIN)
    def daily_checkin(self):
        return self.client.attendance()

    @task_info("{client_name}任务申领", "申领LongPT任务", TaskType.CLAIM)
    def claim(self, task_id=None):
        return self.client.claim_task(task_id)

    @task_info("{client_name}喊话", "执行 LongPT 喊话并获取反馈", TaskType.CHAT)
    def daily_shotbox(self):
        messages = ["龙宝，求上传", "龙宝，求魔力"]
        results = []
        for i, msg in enumerate(messages):
            if i > 0:
                time.sleep(self.client.message_interval)
            ok, text = self.client.send_messagebox(msg)
            results.append(text)
        return TaskResult.ok("\n".join(results))

    @task_info("{client_name}每日抽奖", "参加 LongPT 每日抽奖", TaskType.LOTTERY)
    def daily_lottery(self):
        ok, message = self.client.daily_lottery()
        return TaskResult.ok(message) if ok else TaskResult.fail(message)
