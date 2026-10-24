import json
import re
from .page import document, parse_record
from ..core.models import Evidence


class YaowanVerifier:
    def identity(self, page):
        match = re.search(r'"userId"\s*:\s*(\d+)', page or "")
        return match.group(1) if match and match.group(1) != "0" else ""

    def token(self, page):
        match = re.search(r'"csrfToken"\s*:\s*"([^"]+)"', page or "")
        return match.group(1) if match else ""

    def _api_state(self, page):
        match = re.search(r"<!-- forum-signin-api-state (\{.*?\}) -->", page or "")
        if not match:
            return None
        try:
            return json.loads(match.group(1))
        except (TypeError, ValueError):
            return None

    def parse(self, page, uid, business_date):
        if self.identity(page) != uid:
            return None
        state = self._api_state(page)
        if not state or str(state.get("user_id")) != uid:
            return None
        evidence, _ = parse_record(page, uid, business_date)
        if not evidence.button_text:
            return evidence
        last_checkin = str(state.get("lastCheckinTime") or "")
        if last_checkin.startswith(business_date):
            status = "已签到"
        elif state.get("canCheckIn") is True:
            status = "未签到"
        else:
            status = ""
        return Evidence(evidence.button_text, uid, business_date, status,
                        "api", "药丸用户 API 状态")
