"""青蛙站点（qingwapt.com）。

合并 ptautotask 的 Qingwa（Client+Tasks，含 daily_exchange）与
groupchatzone 的 QingwaHandler（含 get_feedback + buy_daily_bonus）。

关键改进：buy_daily_bonus 改用 GET /api/bonus-shop/getItems 动态匹配"每日福利"商品 id，
不再硬编码 id=28（当前仍为 28，但防未来变化）。
"""
from typing import Dict, Optional, Tuple
from urllib.parse import urljoin

from lxml import etree

from app.log import logger
from app.utils.string import StringUtils

from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType
from ..utils.request import parse_json_response


class QingwaHandler(CapabilityHandler):
    """青蛙站点处理器。"""

    def __init__(self, site_info: dict):
        super().__init__(site_info)
        self.bonusshop_api = self.site_url + "/api/bonus-shop/exchange"
        self.getitems_api = self.site_url + "/api/bonus-shop/getItems"

    @staticmethod
    def get_site_name():
        return "青蛙"

    @staticmethod
    def get_site_domain():
        return "qingwapt.com"

    def match(self) -> bool:
        return "青蛙" in self.site_name

    def send_messagebox(self, message: str = None, callback=None) -> Tuple[bool, str]:
        """发送群聊区消息（青蛙特化解析）。"""
        try:
            if not message:
                return False, "消息内容不能为空"
            cb = callback or (lambda response: " ".join(
                etree.HTML(response.text).xpath("//ul[1]/li/text()")))
            result = super().send_messagebox(message, cb)
            if result[0]:
                self._last_message_result = result[1]
                logger.info(f"青蛙：消息发送成功：{result[1]}")
            else:
                self._last_message_result = None
            return result
        except Exception as e:
            logger.error(f"青蛙：发送消息异常：{e}")
            self._last_message_result = None
            return False, str(e)

    def get_feedback(self, message: str = None) -> Optional[Dict]:
        """青蛙喊话反馈解析（"发了！"通常为 10G 上传）。"""
        if self._last_message_result:
            text = self._last_message_result
            if text == "发了！":
                text = f"{text}一般为10G！"
            return {
                "site": self.site_name,
                "message": message,
                "rewards": [{
                    "type": "青蛙",
                    "description": text,
                    "amount": "",
                    "unit": "",
                    "is_negative": False,
                }],
            }
        return None

    def buy_daily_bonus(self) -> Tuple[bool, str]:
        """每日福利购买：消耗 1 蝌蚪兑换 1000 蝌蚪。

        改进：从 getItems 动态匹配"每日福利"商品 id，不再硬编码 28。
        """
        try:
            item_id = self._get_daily_bonus_id()
            if not item_id:
                return False, "未找到每日福利商品"
            data = {"id": item_id, "amount": 1}
            response = self.session.post(self.bonusshop_api, data=data, timeout=30)
            result = parse_json_response(response, "购买请求失败")
            if result.get("success"):
                logger.info(f"青蛙：每日福利购买成功：{result.get('msg', '')}")
                return True, result.get("msg", "购买成功")
            msg = result.get("msg", "购买失败")
            # 幂等成功：今日已购买（超过限购数量）
            if any(kw in msg for kw in ("超过限购", "已购买", "已兑换")):
                logger.info(f"青蛙：每日福利今日已购买：{msg}")
                return True, f"今日已购买：{msg}"
            logger.warning(f"青蛙：每日福利购买失败：{msg}")
            return False, msg
        except Exception as e:
            logger.error(f"青蛙：每日福利购买异常：{e}")
            return False, f"购买异常: {e}"

    def _get_daily_bonus_id(self) -> Optional[str]:
        """从 getItems 动态获取每日福利商品 id。

        匹配策略：name 含"每日福利"且 b_type==bonus（蝌蚪换蝌蚪）。
        找不到时回退 id=28（向后兼容）。
        """
        try:
            response = self.session.get(self.getitems_api, timeout=15)
            result = parse_json_response(response, "获取商品列表失败")
            if isinstance(result, list):
                items = result
            elif isinstance(result, dict):
                items = result.get("data") or result.get("items") or []
            else:
                items = []
            for item in items:
                name = item.get("name", "")
                b_type = item.get("b_type", "")
                a_type = item.get("a_type", "")
                # 每日福利：1 蝌蚪换 1000 蝌蚪
                if "每日福利" in name and a_type == "bonus" and b_type == "bonus":
                    item_id = item.get("id")
                    if item_id is not None:
                        return str(item_id)
            # 回退：硬编码 28
            logger.warning("青蛙：动态匹配每日福利商品失败，回退 id=28")
            return "28"
        except Exception as e:
            logger.error(f"青蛙：获取每日福利商品 id 失败：{e}，回退 id=28")
            return "28"

    def medal_bonus(self) -> str:
        return "青蛙不支持勋章奖励"


class Tasks(BaseTask):
    """青蛙任务集合。"""

    def __init__(self, cookie: str = None):
        # cookie 仅用于兼容 BaseTask 构造，实际 client 由执行引擎注入
        super().__init__(None)

    @task_info(label="{client_name}喊话", hint="执行青蛙站点的喊话任务", task_type=TaskType.CHAT)
    def daily_shotbox(self):
        messages = ["蛙总，求上传", "蛙总，求下载"]
        results = []
        for msg in messages:
            ok, info = self.client.send_messagebox(msg)
            results.append(info)
        return "\n".join(results)

    @task_info(label="{client_name}签到", hint="执行青蛙站点签到", task_type=TaskType.CHECKIN)
    def daily_checkin(self):
        return self.client.attendance()

    @task_info(label="每日1k蝌蚪", hint="购买青蛙商店每日福利：1蝌蚪兑换1000蝌蚪", task_type=TaskType.EXCHANGE)
    def daily_exchange(self):
        ok, msg = self.client.buy_daily_bonus()
        from ..base.result import TaskResult
        return TaskResult.ok(msg) if ok else TaskResult.fail(msg)
