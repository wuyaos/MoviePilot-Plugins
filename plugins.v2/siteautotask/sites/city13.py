"""13City（大青虫）站点适配。

喊话逻辑参考 groupchatzone 的 ThirteenCityHandler：
- 发送前校验/自动购买「诸神赐福」勋章，避免被扣啤酒瓶
- 发送后校验群聊区是否出现自己的消息
- 解析「掌管啤酒瓶的神」对 @用户名 的反馈为啤酒瓶奖励

任务合并 ptautotask 的 City13：每日/每月做种任务申领。
"""
import json
from typing import Optional, Tuple
from urllib.parse import urljoin
from lxml import etree

from app.log import logger

from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType
from ..base.result import TaskResult


class City13Handler(CapabilityHandler):
    BLESSING_MEDAL_NAME = "诸神赐福"
    BLESSING_MEDAL_ID = "11"
    BLESSING_BOT_NAME = "掌管啤酒瓶的神"

    def __init__(self, site_info: dict):
        super().__init__(site_info)
        self.index_url = self.site_url + "/index.php"
        self.shoutbox_url = self.site_url + "/shoutbox.php?type=shoutbox"
        self.medal_url = self.site_url + "/medal.php?q=&sort=category"
        self._blessing_status = {
            "auto_buy_enabled": bool(site_info.get("thirteencity_auto_buy_blessing", False)),
            "medal_status": "未检查",
            "purchase_status": "未触发",
        }

    @staticmethod
    def get_site_name():
        return "13City"

    @staticmethod
    def get_site_domain():
        return "13city.org"

    def match(self) -> bool:
        return "13city" in self.site_name.lower() or "13city.org" in self.domain

    def send_messagebox(self, message: str = None, callback=None) -> Tuple[bool, str]:
        if not message:
            return False, "消息内容不能为空"
        try:
            # 1. 勋章校验/自动购买
            blessing_ok, blessing_msg = self._ensure_blessing_medal()
            if not blessing_ok:
                self._last_message_result = blessing_msg
                return False, blessing_msg

            # 2. 获取用户名
            username = self.get_username()
            if not username:
                return False, "获取13City用户名失败"

            # 3. 发送喊话
            ok, text = self._send_shout_message(message)
            if not ok:
                self._last_message_result = text
                return False, text

            # 4. 校验群聊区是否出现自己的消息
            if not self._message_exists_in_shoutbox(username, message):
                logger.warning(f"13City：喊话请求已返回，但群聊区未发现用户消息：{username} {message}")
                return False, "13City群聊区未显示发送的喊话消息"

            # 5. 等待系统反馈生成后解析（掌管啤酒瓶的神对 @username 的回复）
            self.wait_feedback()
            feedback = self._poll_feedback(username)
            result = (True, feedback) if feedback else (True, "消息已发送")
            self._last_message_result = result[1] if result[0] else None
            return result
        except Exception as e:
            logger.error(f"13City：发送消息失败：{e}")
            return False, str(e)

    def _send_shout_message(self, message: str) -> Tuple[bool, str]:
        try:
            response = self.session.get(
                self.site_url + "/shoutbox.php",
                params={"shbox_text": message, "shout": "我喊", "sent": "yes", "type": "shoutbox"},
                headers={"Referer": self.index_url},
                timeout=(3.05, 15),
            )
            response.raise_for_status()
            return True, response.text
        except Exception as e:
            logger.error(f"13City：发送喊话失败：{e}")
            return False, "发送13City喊话失败"

    def _message_exists_in_shoutbox(self, username: str, message: str) -> bool:
        response = self._send_get_request(self.shoutbox_url)
        if not response:
            return False
        html = etree.HTML(response.text)
        if html is None:
            return False
        rows = html.xpath("//tr[td[contains(@class, 'shoutrow')]][position() <= 20]")
        expected = f"{username} {message}"
        for row in rows:
            content = self._extract_row_text(row)
            if expected in " ".join(content.split()):
                return True
        return False

    def _poll_feedback(self, username: str) -> Optional[str]:
        response = self._send_get_request(self.shoutbox_url)
        if not response:
            return None
        html = etree.HTML(response.text)
        if html is None:
            return None
        rows = html.xpath("//tr[td[contains(@class, 'shoutrow')]][position() <= 20]")
        for row in rows:
            content = self._extract_row_text(row)
            if self._is_feedback_message(content, username):
                return content
        return None

    def _extract_row_text(self, row) -> str:
        return "".join(row.xpath(".//text()[not(ancestor::span[@class='date'])]")).strip()

    def _is_feedback_message(self, content: str, username: str) -> bool:
        if not content or f"@{username}" not in content:
            return False
        return self.BLESSING_BOT_NAME in content and any(
            kw in content for kw in ("听到了你的愿望", "你今天求过啤酒瓶了", "啤酒瓶"))

    def get_feedback(self, message: str = None) -> Optional[dict]:
        if not self._last_message_result:
            return None
        text = str(self._last_message_result)
        reward_type = "啤酒瓶" if "啤酒瓶" in text else "raw_feedback"
        return {
            "site": self.site_name, "message": message,
            "blessing_status": self._blessing_status,
            "rewards": [{
                "type": reward_type, "description": text,
                "amount": "", "unit": "", "is_negative": False,
            }],
        }

    def buy_blessing_medal(self) -> Tuple[bool, str]:
        """暴露为任务的诸神赐福勋章自动购买（喊话前联动）。"""
        ok, msg = self._ensure_blessing_medal(auto_buy=True)
        return ok, msg

    def _ensure_blessing_medal(self, auto_buy: bool = False) -> Tuple[bool, str]:
        """检查/购买诸神赐福勋章。

        :param auto_buy: True=未拥有时自动购买（buy_blessing 任务）；False=只检查不买（喊话前）
        """
        self._blessing_status = {
            "auto_buy_enabled": auto_buy,
            "medal_status": "检查中", "purchase_status": "未触发",
        }
        page = self._fetch_medal_page()
        if page is None:
            if not auto_buy:
                self._blessing_status["medal_status"] = "无法确认"
                self._blessing_status["purchase_status"] = "未开启自动购买"
                return True, "未校验勋章状态，继续执行喊话"
            self._blessing_status["medal_status"] = "检查失败"
            self._blessing_status["purchase_status"] = "检查失败"
            return False, "获取13City勋章页面失败"
        if self._has_blessing_medal(page):
            self._blessing_status["medal_status"] = "已拥有诸神赐福"
            self._blessing_status["purchase_status"] = "无需购买"
            return True, f"已拥有{self.BLESSING_MEDAL_NAME}勋章"
        if not auto_buy:
            self._blessing_status["medal_status"] = "未拥有诸神赐福"
            self._blessing_status["purchase_status"] = "未开启自动购买"
            return True, f"未拥有{self.BLESSING_MEDAL_NAME}勋章，继续执行喊话"
        self._blessing_status["purchase_status"] = "尝试自动购买"
        ok, msg = self._buy_blessing_medal(page)
        if not ok:
            self._blessing_status["purchase_status"] = f"购买失败: {msg}"
            return False, msg
        page = self._fetch_medal_page()
        if page is None or not self._has_blessing_medal(page):
            self._blessing_status["purchase_status"] = "已购买，未检测到勋章"
            return False, f"购买{self.BLESSING_MEDAL_NAME}后未检测到勋章"
        self._blessing_status["medal_status"] = "已拥有诸神赐福"
        self._blessing_status["purchase_status"] = "自动购买成功"
        return True, msg

    def _fetch_medal_page(self) -> Optional[str]:
        response = self._send_get_request(self.medal_url)
        return response.text if response else None

    def _has_blessing_medal(self, page_text: str) -> bool:
        html = etree.HTML(page_text)
        if html is None:
            return False
        for card in self._find_blessing_medal_cards(html):
            if "purchased" in (card.xpath("string(@class)") or "").split():
                return True
            buy_text = "".join(card.xpath(
                ".//div[contains(@class, 'medal-action')]//button[contains(@class, 'buy')]//text()")).strip()
            if buy_text in ("已经购买", "已购买"):
                return True
        return False

    def _buy_blessing_medal(self, page_text: str) -> Tuple[bool, str]:
        if not self._can_buy_blessing_medal(page_text):
            return False, f"{self.BLESSING_MEDAL_NAME}当前不可购买"
        response = self._send_post_request(
            self.site_url + "/ajax.php",
            data={"action": "buyMedal", "params[medal_id]": self.BLESSING_MEDAL_ID})
        if not response:
            return False, f"购买{self.BLESSING_MEDAL_NAME}失败"
        try:
            payload = json.loads(response.text)
        except Exception:
            return False, f"购买{self.BLESSING_MEDAL_NAME}响应解析失败"
        if payload.get("ret") != 0:
            return False, payload.get("msg") or f"购买{self.BLESSING_MEDAL_NAME}失败"
        return True, payload.get("msg") or f"已自动购买{self.BLESSING_MEDAL_NAME}勋章"

    def _can_buy_blessing_medal(self, page_text: str) -> bool:
        html = etree.HTML(page_text)
        if html is None:
            return False
        buttons = []
        for card in self._find_blessing_medal_cards(html):
            buttons.extend(card.xpath(
                f".//button[contains(@class, 'buy') and @data-id='{self.BLESSING_MEDAL_ID}']"))
        if not buttons:
            return False
        if buttons[0].xpath("@disabled"):
            return False
        return "购买" in "".join(buttons[0].xpath(".//text()")).strip()

    def _find_blessing_medal_cards(self, html) -> list:
        cards = html.xpath(
            f"//div[contains(@class, 'medal-card')]"
            f"[.//button[contains(@class, 'buy') and @data-id='{self.BLESSING_MEDAL_ID}']]")
        if cards:
            exact = []
            for card in cards:
                name = "".join(card.xpath(".//div[contains(@class, 'medal-name')]//text()")).strip()
                if name == self.BLESSING_MEDAL_NAME:
                    exact.append(card)
            return exact or cards
        return html.xpath(
            f"//div[contains(@class, 'medal-card')]"
            f"[.//div[contains(@class, 'medal-name') and normalize-space(text())='{self.BLESSING_MEDAL_NAME}']]")

    @staticmethod
    def get_claim_options():
        """可申领任务选项，id 为站点 exam_id。"""
        return [
            {"id": "2", "label": "每日做种"},
            {"id": "6", "label": "每月做种"},
        ]


class Tasks(BaseTask):
    def __init__(self, cookie=None):
        super().__init__(None)

    @task_info("{client_name}签到", "执行13City签到", TaskType.CHECKIN)
    def daily_checkin(self):
        return self.client.attendance()

    @task_info("{client_name}任务申领", "申领13City做种任务", TaskType.CLAIM)
    def claim(self, task_id=None):
        return self.client.claim_task(task_id)

    @task_info("{client_name}喊话", "执行13City喊话并解析啤酒瓶反馈", TaskType.CHAT)
    def daily_shotbox(self):
        ok, msg = self.client.send_messagebox("掌管啤酒瓶的神请赐予我啤酒瓶")
        return TaskResult.ok(msg) if ok else TaskResult.fail(msg)

    @task_info("诸神赐福勋章", "喊话前自动购买13City诸神赐福勋章，关闭则只检查不买", TaskType.CHECKIN)
    def buy_blessing(self):
        ok, msg = self.client.buy_blessing_medal()
        return TaskResult.ok(msg) if ok else TaskResult.fail(msg)
