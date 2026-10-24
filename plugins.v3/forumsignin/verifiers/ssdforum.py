import re
from .page import document, parse_record, reward_from_row


class SSDForumVerifier:
    SIGNED_MESSAGE = "您今天已经签到过了"

    def identity(self, page):
        links = document(page).xpath('//a[@title="访问我的空间"]/@href')
        match = re.search(r'(?:uid=|space-uid-)(\d+)', links[0]) if links else None
        return match.group(1) if match else ""

    def token(self, page):
        values = document(page).xpath('//input[@name="formhash"]/@value')
        return values[0] if values else ""

    def parse(self, page, uid, business_date):
        """行在场以行为基础、文案确认状态；已签视图无行时凭文案合成；无行但表单可交互按未签提交复核。"""
        text = page or ""
        evidence, row = parse_record(text, uid, business_date)
        signed = self.SIGNED_MESSAGE in text
        if signed and row is not None:
            return evidence.__class__(evidence.button_text or "已签文案", evidence.uid or uid,
                                      evidence.date or business_date, "已签到",
                                      evidence.source, evidence.raw_summary)
        if signed and row is None:
            return evidence.__class__("已签文案", uid, business_date, "已签到", "page",
                                      "站点返回已签提示")
        if row is None and evidence.button_text and self.token(text):
            return evidence.__class__(evidence.button_text, uid, business_date, "未签到",
                                      evidence.source, "无本人当日行，表单可提交")
        return evidence
    def reward(self, page, uid, business_date):
        return reward_from_row(parse_record(page, uid, business_date)[1])
