"""GGPT 站点适配。

勋章购买型站点（疯狂星期四勋章，7天有效）。
- 站点框架：NexusPHP
- 访问地址：https://gamegamept.com
- 勋章购买：POST /ajax.php action=buyMedal params[medal_id]=35
- 过期检测：访问 medal.php，找 data-id="35" 按钮，可点击=已过期，disabled"已经购买"=有效
- 简化迁移自独立插件 ggptmedalbuyer（舍弃到期检测/定时器/历史记录）
"""
import json
from lxml import etree
from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType
from ..base.result import TaskResult


class GgptHandler(CapabilityHandler):
    MEDAL_ID = "35"
    MEDAL_NAME = "疯狂星期四"

    @staticmethod
    def get_site_name():
        return "GGPT"

    @staticmethod
    def get_site_domain():
        return "gamegamept.com"

    def match(self) -> bool:
        return "ggpt" in self.site_name.lower() or "gamegamept.com" in self.domain

    def _is_medal_expired(self) -> bool:
        """检查勋章是否已过期（按钮可点击=已过期）。"""
        response = self._send_get_request(self.site_url + "/medal.php")
        if not response:
            return True  # 页面读不到，按已过期处理，尝试购买
        html = etree.HTML(response.text)
        # 找 data-id="35" 的按钮，disabled 或 value 含"已经购买"=仍有效
        btn = html.xpath(f'//input[@data-id="{self.MEDAL_ID}"]')
        if not btn:
            return True  # 找不到按钮，可能页面结构变化或已过期，尝试购买
        disabled = btn[0].get("disabled") is not None
        value = (btn[0].get("value") or "").strip()
        if disabled or "已经购买" in value or "已购买" in value:
            return False  # 仍有效
        return True  # 按钮可点击，已过期

    def buy_medal(self, medal_id: str = None) -> tuple:
        """购买勋章，返回 (success, message)。"""
        medal_id = medal_id or self.MEDAL_ID
        if not self._is_medal_expired():
            return True, f"勋章未过期，跳过续购"
        response = self._send_post_request(
            self.site_url + "/ajax.php",
            data={"action": "buyMedal", "params[medal_id]": medal_id})
        if not response:
            return False, "购买请求失败：无响应"
        try:
            payload = json.loads(response.text)
        except Exception:
            return False, f"购买勋章响应解析失败：{response.text[:100]}"
        msg = payload.get("message") or payload.get("msg") or payload.get("info") or "无返回信息"
        if payload.get("ret") in (0, "0"):
            return True, f"购买成功：{msg}"
        if any(kw in str(msg) for kw in ("已经购买", "已拥有", "已购买", "already")):
            return True, f"已拥有：{msg}"
        return False, str(msg)


class Tasks(BaseTask):
    def __init__(self, cookie=None):
        super().__init__(None)

    @task_info("{client_name}签到", "执行GGPT签到", TaskType.CHECKIN)
    def daily_checkin(self):
        return self.client.attendance()

    @task_info("购买疯狂星期四勋章", "过期时购买GGPT疯狂星期四勋章(7天有效)", TaskType.MEDAL)
    def buy_medal(self):
        ok, msg = self.client.buy_medal()
        return TaskResult.ok(msg) if ok else TaskResult.fail(msg)
