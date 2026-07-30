"""藏宝阁：签到、任务申领、双消息喊话。"""
from ..core.shoutbox import ChatRow, Direction, Observation, ShoutboxProfile, parse_snapshot
from ..core.site import Site
from ..core.task import Chat, Checkin, Claim


class Cangbao(Site):
    site_name = "藏宝阁"
    domain = "cangbao.ge"
    message_interval = 60
    shoutbox = ShoutboxProfile(
        direction=Direction.BOTH,
        window_size=20,
        is_feedback=lambda row, username: "系统:" in row.text and f"@{username}" in row.text,
        message_terms=lambda message: ["阁主", message.split("，")[-1]],
        confirmation_wait_seconds=2,
    )
    tasks = [
        Checkin(),
        Claim(options=[
            {"id": "12", "label": "做种传奇"}, {"id": "11", "label": "做种之光"},
            {"id": "10", "label": "做种大师"}, {"id": "9", "label": "做种达人"},
            {"id": "8", "label": "做种新秀"}, {"id": "6", "label": "开阁元老"},
            {"id": "5", "label": "宗师巨匠"}, {"id": "4", "label": "护宝大师"},
            {"id": "3", "label": "持证工匠"}, {"id": "2", "label": "宝阁学徒"},
        ]),
        Chat(messages=["阁主，求上传", "阁主，求魔力"]),
    ]

    def extract_feedback(self, html, username, message):
        rows, reason = parse_snapshot(html, self.shoutbox)
        if reason:
            return Observation(False, False, reason=reason, retry_allowed=False)
        target = next((row for row in rows if row.source == "row" and username in row.text
                       and all(term in row.text for term in ("阁主", message.split("，")[-1]))), None)
        if not target:
            return Observation(True, False, reason="喊话区未出现当前用户消息")
        reward_term = "上传量" if "上传" in message else "魔力值" if "魔力" in message else ""
        candidates = sorted((row for row in rows if row.source == "row" and row.index != target.index),
                            key=lambda row: abs(row.index - target.index))
        for row in candidates[:20]:
            text = row.text
            if "系统:" not in text or f"@{username}" not in text:
                continue
            if "已经求过奖励" in text or "明天再来" in text or not reward_term or reward_term in text:
                return Observation(True, True, feedback=ChatRow(row.index, text, row.age_seconds, row.source))
        return Observation(True, True, reason="未解析到反馈")
