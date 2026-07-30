"""LongPT：签到、申领、单选喊话和每日抽奖。"""
import re
from ..actions.longpt import LongPTLotteryAction
from ..core.shoutbox import Direction, ShoutboxProfile
from ..core.site import Site
from ..core.task import Chat, Checkin, Claim, Lottery
from ..core.models import TaskResult


class LongPT(Site):
    site_name = "LongPT"
    domain = "longpt.org"
    api_base = "https://longpt.org/pt-api/v1"
    shoutbox = ShoutboxProfile(
        direction=Direction.BEFORE,
        message_terms=lambda message: ["龙宝", message.split("，")[-1]],
        confirmation_wait_seconds=2,
    )
    tasks = [
        Checkin(),
        Claim(options=[
            {"id": "8", "label": "发种-简单"}, {"id": "7", "label": "发种-正常"},
            {"id": "6", "label": "发种-困难"}, {"id": "5", "label": "保种-简单"},
            {"id": "4", "label": "保种-正常"}, {"id": "2", "label": "保种-困难"},
        ]),
        Chat(options=[
            {"id": "upload", "label": "求上传", "message": "龙宝，求上传"},
            {"id": "bonus", "label": "求魔力", "message": "龙宝，求魔力"},
        ]),
        Lottery(LongPTLotteryAction()),
    ]

    def send_message(self, message):
        try:
            response = self.session.post(
                f"{self.api_base}/nexus/shoutbox/shout",
                json={"text": message}, timeout=30)
            payload = response.json()
            if payload.get("code") == 0:
                feedback = re.sub(r",?\[em\d+\]", "", payload.get("msg") or "").strip()
                return TaskResult.ok(feedback or "消息已发送", rewards=[{
                    "type": self.reward_type(feedback), "description": feedback,
                    "amount": "", "unit": "", "is_negative": False,
                }] if feedback else [])
            return TaskResult.business(payload.get("msg") or "喊话失败")
        except Exception as error:
            return TaskResult.fail(f"LongPT 喊话请求失败：{error}")
