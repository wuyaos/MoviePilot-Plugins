import re
from .page import document, parse_record, reward_from_row

class SSDForumVerifier:
    def identity(self, page):
        links = document(page).xpath('//a[@title="访问我的空间"]/@href')
        match = re.search(r'(?:uid=|space-uid-)(\d+)', links[0]) if links else None
        return match.group(1) if match else ""

    def token(self, page):
        values = document(page).xpath('//input[@name="formhash"]/@value')
        return values[0] if values else ""

    def parse(self, page, uid, business_date):
        if self.identity(page) != uid:
            return None
        return parse_record(page, uid, business_date)[0]

    def reward(self, page, uid, business_date):
        if self.identity(page) != uid:
            return None
        return reward_from_row(parse_record(page, uid, business_date)[1])
