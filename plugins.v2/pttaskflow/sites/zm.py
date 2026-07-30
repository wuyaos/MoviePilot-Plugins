"""织梦：签到、喊话和邮件时间辅助方法。"""
from lxml import etree
from ..core.shoutbox import Direction, ShoutboxProfile
from ..core.site import Site
from ..core.task import Chat, Checkin


class ZM(Site):
    site_name = "织梦"
    domain = "zmpt.cc"
    message_interval = 60
    shoutbox = ShoutboxProfile(
        direction=Direction.BEFORE,
        is_feedback=lambda row, username: (
            "皮总" in row.text and f"@{username}" in row.text
            and any(x in row.text for x in ("响应", "扣减", "赠送", "没有理", "明天再来"))
        ),
        message_terms=lambda message: ["皮总", message.split("，")[-1]],
        confirmation_wait_seconds=2,
    )
    tasks = [Checkin(), Chat(messages=["皮总，求上传", "皮总，求电力"],
                             negatives=("扣减", "扣除", "失去"))]

    def get_latest_message_time(self):
        response = self.get("/messages.php")
        if not response:
            return None
        html = etree.HTML(response.text or "")
        for row in html.xpath("//tr[td[@class='rowfollow']]"):
            if not row.xpath(".//a[contains(text(), '收到来自 zmpt 赠送的')]"):
                continue
            spans = row.xpath(".//span[@title]")
            if spans and spans[0].get("title"):
                return spans[0].get("title")
        return None
