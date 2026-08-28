"""LuckPT 站点适配。

groupchatzone 独有站点，喊话反馈解析型。
- 采用非标准 DIV+Flex 布局（wish-bubble-system / chat-message-container）
- 优先解析许愿池系统反馈：@username 幸运池听到了你的愿望...
- 其次解析聊天区 @username 的回复
- 勋章中心分类奖励：medal_collection.php 的 claim-reward 按钮经
  POST ajax.php action=claimMedalCategoryReward 领取（bonus_daily 每日可领）
"""
from typing import Tuple
from app.log import logger

from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType
from ..base.result import TaskResult
from ..utils.request import parse_json_response


class LuckptHandler(CapabilityHandler):
    def __init__(self, site_info: dict):
        super().__init__(site_info)
        self.shoutbox_url = self.site_url + "/shoutbox.php"

    @staticmethod
    def get_site_name():
        return "LuckPT"

    @staticmethod
    def get_site_domain():
        return "luckpt.de"

    def match(self) -> bool:
        return "luckpt" in self.site_name.lower() or "幸运" in self.site_name or "luckpt" in self.domain

    def shoutbox_profile(self):
        from ..base.shoutbox import FeedbackDirection, ShoutboxProfile
        return ShoutboxProfile(
            path="/shoutbox.php?type=shoutbox",
            row_xpath="//div[contains(@class, 'chat-message-container')]",
            direction=FeedbackDirection.EXTERNAL,
            external_feedback_xpath="//div[contains(@class, 'wish-bubble-system')]//div[contains(@class, 'wish-content')]",
            is_feedback=lambda row, username: f"@{username}" in row.text,
            message_terms=lambda message: [message],
            confirmation_wait_seconds=2,
        )

    def send_messagebox(self, message: str = None, callback=None) -> Tuple[bool, str]:
        if not message:
            return False, "消息内容不能为空"
        try:
            return super().send_messagebox(message, callback)
        except Exception as e:
            logger.error(f"LuckPT：发送消息失败：{e}")
            return False, str(e)


    def get_feedback(self, message: str = None):
        observation = getattr(self, "_chat_observation", None)
        text = observation.feedback.text if observation and observation.feedback else ""
        if not text:
            return None
        reward_type = "幸运星" if "幸运星" in text else "raw_feedback"
        for kw, kind in (("上传", "上传量"), ("下载", "下载量"), ("魔力", "魔力值")):
            if kw in text:
                reward_type = kind
                break
        return {"site": self.site_name, "message": message, "rewards": [{
            "type": reward_type, "description": text,
            "amount": "", "unit": "", "is_negative": False,
        }]}

    def _find_claimable_medal_rewards(self):
        """读取勋章中心可领取奖励按钮，返回 [(category, type, label)]。"""
        from lxml import etree

        response = self._send_get_request(self.site_url + "/medal_collection.php")
        if not response:
            return None
        html = etree.HTML(response.text or "")
        if html is None:
            return []
        buttons = html.xpath(
            '//button[contains(concat(" ", normalize-space(@class), " "), " claim-reward ")'
            ' and not(@disabled)]'
        )
        rewards = []
        for btn in buttons:
            category = (btn.get("data-category") or "").strip()
            reward_type = (btn.get("data-type") or "").strip()
            label = (btn.get("data-reward-label") or "").strip()
            if category and reward_type:
                rewards.append((category, reward_type, label or reward_type))
        return rewards

    def claim_medal_rewards(self):
        """领取勋章中心全部可领取的分类奖励。

        页面按钮由 JS 经 ``POST ajax.php`` 发送
        ``action=claimMedalCategoryReward`` + ``params[category_id]`` +
        ``params[reward_type]``，响应 ``ret == 0`` 表示成功。
        """
        rewards = self._find_claimable_medal_rewards()
        if rewards is None:
            return False, "读取勋章中心失败"
        if not rewards:
            return True, "无可领取的勋章奖励"

        claimed, failed = [], []
        for category, reward_type, label in rewards:
            response = self._send_post_request(
                self.site_url + "/ajax.php",
                data={
                    "action": "claimMedalCategoryReward",
                    "params[category_id]": category,
                    "params[reward_type]": reward_type,
                },
            )
            payload = parse_json_response(response, "领取响应解析失败") if response else {"success": False, "msg": "领取请求失败"}
            msg = str(payload.get("msg") or payload.get("message") or "无返回信息")
            if payload.get("ret") in (0, "0"):
                claimed.append(f"{label}(分类{category})")
            elif any(kw in msg for kw in ("已经领取", "已领取", "已经购买", "已拥有")):
                claimed.append(f"{label}(分类{category}·已领取)")
            else:
                failed.append(f"{label}: {msg}")
        if failed:
            return False, "；".join(failed)
        return True, "领取成功：" + "、".join(claimed)


class Tasks(BaseTask):
    def __init__(self, cookie=None):
        super().__init__(None)

    @task_info("{client_name}签到", "执行LuckPT签到", TaskType.CHECKIN)
    def daily_checkin(self):
        return self.client.attendance()

    @task_info("{client_name}喊话", "执行LuckPT喊话并解析许愿池反馈", TaskType.CHAT)
    def daily_shotbox(self):
        ok, msg = self.client.send_messagebox("幸运池祈愿")
        if not ok:
            return TaskResult.fail(msg)
        return TaskResult.ok(msg or "消息已发送，未解析到反馈")

    @task_info("{client_name}勋章奖励领取", "领取LuckPT勋章中心可领取的分类奖励", TaskType.MEDAL)
    def claim_medal_reward(self):
        ok, msg = self.client.claim_medal_rewards()
        return TaskResult.ok(msg) if ok else TaskResult.fail(msg)
