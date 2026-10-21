import re
from .page import parse_record

class YaowanVerifier:
    def identity(self, page):
        match = re.search(r'"userId"\s*:\s*(\d+)', page)
        return match.group(1) if match and match.group(1) != "0" else ""

    def token(self, page):
        match = re.search(r'"csrfToken"\s*:\s*"([^"]+)"', page)
        return match.group(1) if match else ""

    def parse(self, page, uid, business_date):
        if self.identity(page) != uid:
            return None
        return parse_record(page, uid, business_date)[0]
