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
        evidence, row = parse_record(page, uid, business_date)
        if self.SIGNED_MESSAGE not in (page or ""):
            return evidence
        return evidence.__class__(evidence.button_text, evidence.uid, evidence.date,
                                  "已签到", evidence.source, evidence.raw_summary)

    def reward(self, page, uid, business_date):
        return reward_from_row(parse_record(page, uid, business_date)[1])
