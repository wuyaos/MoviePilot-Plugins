"""LongPT API 动作。"""
import re
from ..core.models import TaskResult


class LongPTShoutAction:
    def execute(self, site, message):
        try:
            response = site.session.post(
                f"{site.api_base}/nexus/shoutbox/shout", json={"text": message}, timeout=30)
            payload = response.json()
            if payload.get("code") == 0:
                return TaskResult.ok(payload.get("msg") or "消息已发送")
            return TaskResult.business(payload.get("msg") or "喊话失败")
        except Exception as error:
            return TaskResult.fail(f"LongPT 喊话请求失败：{error}")


class LongPTLotteryAction:
    def execute(self, site):
        try:
            response = site.get(f"{site.api_base}/lucky/pluginsPrizeReceiptRecord/join")
            if not response:
                return TaskResult.fail(site.request_error or "LongPT 抽奖请求失败")
            payload = response.json()
            if payload.get("code") in (0, -1):
                return TaskResult.idempotent(payload.get("msg") or "抽奖完成")
            return TaskResult.business(payload.get("msg") or "抽奖失败")
        except Exception as error:
            return TaskResult.fail(f"LongPT 抽奖请求失败：{error}")


def clean_feedback(text):
    return re.sub(r",?\[em\d+\]", "", text or "").strip()
