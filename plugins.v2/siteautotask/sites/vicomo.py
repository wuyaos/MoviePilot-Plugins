"""Vicomo（象站）站点适配。

喊话逻辑参考 groupchatzone 的 VicomoHandler：
- 发送后读取站内信列表，取第二条作为反馈（象草奖励）
- 标记已读，避免重复处理

任务合并 ptautotask 的 Vicomo：签到、喊话、每日打 Boss（周一/三单挑、周二/四团战、周五-日世界 Boss）。
"""
import datetime
import re
import time
from typing import Optional, Tuple
from lxml import etree

from app.log import logger

from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType
from ..base.result import TaskResult
from ..utils.content_filter import ContentFilter


class VicomoHandler(CapabilityHandler):
    def __init__(self, site_info: dict):
        super().__init__(site_info)
        self.vs_boss_url = self.site_url + "/customgame.php?action=exchange"

    @staticmethod
    def get_site_name():
        return "象站"

    @staticmethod
    def get_site_domain():
        return "ptvicomo.net"

    def match(self) -> bool:
        return "象站" in self.site_name or "ptvicomo.net" in self.domain

    def send_messagebox(self, message: str = None, callback=None) -> Tuple[bool, str]:
        if not message:
            return False, "消息内容不能为空"
        try:
            # groupchatzone：发送时丢弃即时返回，转而读取站内信
            ok, _ = super().send_messagebox(message, lambda response: "")
            if not ok:
                return False, "发送消息失败"
            message_list = self.client_message_list()
            if not message_list:
                return False, "获取消息列表失败"
            feedback = message_list[1].get("topic", "") if len(message_list) > 1 else ""
            if len(message_list) > 1:
                self.set_message_read(message_list[1].get("id", ""))
            self._last_message_result = feedback
            return True, feedback
        except Exception as e:
            logger.error(f"Vicomo 发送消息失败: {e}")
            return False, str(e)

    def client_message_list(self):
        return self.get_message_list()

    def get_feedback(self, message: str = None):
        text = self._last_message_result or "消息发送成功"
        return {
            "site": self.site_name, "message": message,
            "rewards": [{
                "type": "象草", "description": text,
                "amount": "", "unit": "", "is_negative": False,
            }],
        }

    def vs_boss(self) -> Optional[str]:
        """执行一次打 Boss。

        按星期决定战斗类型，参考 ptautotask：
        - 周一/三：1v1 锋芒交错
        - 周二/四：5v5 龙与凤的抗衡
        - 周五/六/日：世界 Boss 对抗 Sysrous
        """
        weekday = datetime.date.today().weekday()
        if weekday in (0, 2):
            vs_data = ("option=1&vs_member_name=0&submit="
                       "%E9%94%8B%E8%8A%92%E4%BA%A4%E9%94%99+-+1v1")
        elif weekday in (1, 3):
            vs_data = ("option=1&vs_member_name=0%2C1%2C2%2C3%2C4&submit="
                       "%E9%BE%99%E4%B8%8E%E5%87%A4%E7%9A%84%E6%8A%97%E8%A1%A1+-+%E5%9B%A2%E6%88%98+5v5")
        else:
            vs_data = ("option=1&vs_member_name="
                       "0%2C1%2C2%2C3%2C4%2C5%2C6%2C7%2C8%2C9%2C10%2C11%2C12%2C13%2C14%2C15%2C16"
                       "&submit=%E4%B8%96%E7%95%8Cboss+-+%E5%AF%B9%E6%8A%97Sysrous")
        try:
            self.session.headers.update({
                "Content-Type": "application/x-www-form-urlencoded",
                "Pragma": "no-cache",
            })
            response = self.session.post(self.vs_boss_url, data=vs_data, timeout=(3.05, 15))
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Vicomo 打Boss请求失败: {e}")
            return None

        # 提取签到信息
        match = ContentFilter.re_get_match(response, r"\[签到已得(\d+), 补签卡: (\d+)\]")
        if match:
            logger.info(f"Vicomo 签到已得: {match.group(1)}, 补签卡: {match.group(2)}")

        # 提取战斗结果重定向 URL
        match = ContentFilter.re_get_match(response, r"window\.location\.href\s*=\s*'([^']+战斗结果[^']+)'")
        if not match:
            logger.info("Vicomo 未找到战斗结果重定向 URL")
            return None
        redirect_url = match.group(1)
        try:
            battle_response = self.session.get(redirect_url, timeout=(3.05, 15))
            battle_response.raise_for_status()
        except Exception as e:
            logger.error(f"Vicomo 战斗结果页请求失败: {e}")
            return None
        html = ContentFilter.lxml_get_html(battle_response)
        if not html.xpath('//*[@id="battleMsgInput"]'):
            return None
        results = html.xpath('//*[@id="battleResultStringLastShow"]/div[2]/text()')
        return results[0].strip() if results else None


class Tasks(BaseTask):
    def __init__(self, cookie=None):
        super().__init__(None)

    @task_info("{client_name}签到", "执行象站签到", TaskType.CHECKIN)
    def daily_checkin(self):
        return self.client.attendance()

    @task_info("{client_name}喊话", "执行象站喊话并解析象草反馈", TaskType.CHAT)
    def daily_shotbox(self):
        ok, msg = self.client.send_messagebox("小象求象草")
        return TaskResult.ok(msg) if ok else TaskResult.fail(msg)

    @task_info("{client_name}打Boss", "执行象站每日打Boss任务", TaskType.GENERIC)
    def daily_vs_boss(self):
        results = []
        for _ in range(3):
            result = self.client.vs_boss()
            if result:
                results.append(result)
            time.sleep(10)
        return TaskResult.ok("\n".join(results)) if results else TaskResult.fail("未获得战斗结果")
