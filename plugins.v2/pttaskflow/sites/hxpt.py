"""好学：签到、AJAX 喊话与任务申领（FluxTorrent API 版）。"""
from ..actions.checkin import FluxTorrentCheckin
from ..core.models import TaskResult
from ..core.shoutbox import Direction, ShoutboxProfile
from ..core.site import Site
from ..core.task import Chat, Checkin, Claim


class HxPT(Site):
    site_name = "好学"
    domain = "haoxue.net"
    domain_aliases = ("hxpt.org",)
    shoutbox = ShoutboxProfile(
        path="/shoutbox.php?ajax_chat=1&type=",
        direction=Direction.BEFORE,
        is_feedback=lambda row, _username: "系统提示：" in row.text,
        message_terms=lambda _message: ["好好学习", "天天向上"],
        # 站点疲劳态回执是「丢失 N 火花」，negatives 缺「丢失」会把亏损记成成功。
        # 站点疲劳态回执是「丢失 N 火花」，negatives 由 Chat 任务声明（见 tasks）。
        retry_on_unconfirmed=False,
        confirmation_wait_seconds=3,
    )
    tasks = [
        Checkin(action=FluxTorrentCheckin()),
        Chat(messages=["好好学习天天向上"],
             negatives=("扣减", "扣除", "失去", "丢失")),
        # 任务商店（GET /api/v1/tasks）：id=2 本月发布 5 枚种子、id=3 字幕翻译志愿行。
        # id=1 做种研习社本人已领且名额满；晋升档（4-9）需费用/资格，不放进默认项。
        Claim(options=[
            {"id": "2", "label": "本月发布 5 枚种子"},
            {"id": "3", "label": "字幕翻译志愿行"},
        ]),
    ]

    def send_message(self, message):
        # 好学的确认入口与普通 NexusPHP 不同；发送仍使用兼容的 shoutbox endpoint。
        return super().send_message(message)

    def claim_task(self, task_id: str) -> TaskResult:
        """任务商店申领：POST /api/v1/tasks/claim {"task_id": int}。

        旧 NexusPHP exam 接口（ajax.php claimTask）在新版已不存在。
        """
        try:
            body = {"task_id": int(str(task_id).strip())}
        except ValueError:
            return TaskResult.fail(f"非法任务 ID：{task_id}")
        response = self.post("/api/v1/tasks/claim", json=body)
        if not response:
            return TaskResult.fail(self.request_error or "任务申领请求失败")
        try:
            payload = response.json()
        except Exception:
            return TaskResult.fail("任务申领响应不是 JSON")
        if not isinstance(payload, dict):
            return TaskResult.fail("任务申领响应格式异常")
        message = str(payload.get("message") or payload.get("msg") or "申领完成")
        if payload.get("code") in (0, "0"):
            data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
            reward = data.get("reward")
            return TaskResult.ok(f"申领成功（奖励 {reward}）" if reward is not None else message)
        if any(term in message for term in (
                "已领取", "已经领取", "重复", "进行中", "名额", "上限", "资格")):
            return TaskResult.idempotent(message)
        return TaskResult.business(message)
