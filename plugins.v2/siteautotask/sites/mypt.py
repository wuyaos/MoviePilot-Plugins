"""myPT 站点适配。

勋章续购型站点，支持多勋章选择。
- 站点框架：NexusPHP
- 访问地址：https://mypt.cc
- 勋章购买：POST /ajax.php action=buyMedal id={medal_id}
- 过期检测：访问 medal.php，找 data-id="N" 按钮，可点击=已过期，disabled"已经购买"=有效
- 简化迁移自独立插件 myptmedalbuyer（舍弃到期检测/定时器/历史记录）
"""
import json
from lxml import etree
from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType
from ..base.result import TaskResult


class MyptHandler(CapabilityHandler):
    # 可选勋章列表（id, 名称, 有效期, 魔力加成, 价格）
    MEDALS = [
        {"id": "8", "label": "VIP（30天）"},
        {"id": "7", "label": "白金（365天）"},
        {"id": "6", "label": "铂金（365天）"},
        {"id": "5", "label": "黄金（365天）"},
        {"id": "4", "label": "钻石（365天）"},
        {"id": "3", "label": "至尊（365天）"},
    ]
    # 勋章续购支持多选（一次购买多个勋章）
    CLAIM_MULTIPLE = True

    @staticmethod
    def get_site_name():
        return "myPT"

    @staticmethod
    def get_site_domain():
        return "mypt.cc"

    def match(self) -> bool:
        return "mypt" in self.site_name.lower() or "mypt.cc" in self.domain

    @staticmethod
    def get_claim_options():
        """可购买勋章选项，复用 CLAIM 下拉机制。"""
        return [{"id": m["id"], "label": m["label"]} for m in MyptHandler.MEDALS]

    def _medal_purchase_state(self, medal_id: str):
        """返回 expired、active 或 unavailable，避免购买站点已下架的历史勋章。"""
        response = self._send_get_request(self.site_url + "/medal.php")
        if not response:
            return "unavailable"
        html = etree.HTML(response.text)
        btn = html.xpath(f'//input[@data-id="{medal_id}"]') if html is not None else []
        if not btn:
            return "unavailable"
        disabled = btn[0].get("disabled") is not None
        value = (btn[0].get("value") or "").strip()
        if "需要更多魔力值" in value:
            return "insufficient"
        return "active" if disabled or "已经购买" in value or "已购买" in value else "expired"

    def buy_medal(self, medal_id=None) -> tuple:
        """购买勋章，返回检查结果、消息和实际购买成功的 ID。"""
        if isinstance(medal_id, (list, tuple)):
            if not medal_id:
                return False, "未选择勋章，跳过续购", []
            results = [self._buy_one(str(mid)) for mid in medal_id]
            all_ok = all(result[0] for result in results)
            messages = "; ".join(result[1] for result in results)
            purchased_ids = [purchased_id for _, _, ids in results for purchased_id in ids]
            return all_ok, messages, purchased_ids
        return self._buy_one(medal_id)

    def _buy_one(self, medal_id: str) -> tuple:
        """购买单个勋章，返回检查结果、名称化消息和实际购买成功 ID。"""
        if not medal_id:
            return False, "未选择勋章，跳过续购", []
        medal_name = next(
            (medal["label"].split("（", 1)[0] for medal in self.MEDALS if medal["id"] == medal_id),
            f"勋章 {medal_id}",
        )
        state = self._medal_purchase_state(medal_id)
        if state == "active":
            return True, f"{medal_name}勋章未过期，跳过续购", []
        if state == "unavailable":
            return True, f"{medal_name}勋章当前不可购买，跳过续购", []
        if state == "insufficient":
            return True, f"{medal_name}勋章魔力不足，跳过续购", []
        response = self._send_post_request(
            self.site_url + "/ajax.php",
            data={"action": "buyMedal", "params[medal_id]": medal_id})
        if not response:
            return False, f"{medal_name}勋章购买请求失败：无响应", []
        try:
            payload = json.loads(response.text)
        except Exception:
            return False, f"{medal_name}勋章购买响应解析失败：{response.text[:100]}", []
        msg = payload.get("message") or payload.get("msg") or payload.get("info") or "无返回信息"
        if payload.get("ret") in (0, "0") or payload.get("success") is True:
            return True, f"{medal_name}勋章购买成功：{msg}", [str(medal_id)]
        if any(kw in str(msg) for kw in ("已经购买", "已拥有", "已购买", "already", "未到期")):
            return True, f"{medal_name}勋章已拥有：{msg}", []
        return False, f"{medal_name}勋章购买失败：{msg}", []


class Tasks(BaseTask):
    def __init__(self, cookie=None):
        super().__init__(None)

    @task_info("{client_name}签到", "执行myPT签到", TaskType.CHECKIN)
    def daily_checkin(self):
        return self.client.attendance()

    @task_info("{client_name}勋章续购", "过期时续购myPT勋章", TaskType.MEDAL)
    def buy_medal(self, medal_id=None):
        ok, msg, purchased_ids = self.client.buy_medal(medal_id)
        return TaskResult.ok(msg, purchased_medal_ids=purchased_ids) if ok else TaskResult.fail(msg)
