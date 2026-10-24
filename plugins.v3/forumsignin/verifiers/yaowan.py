import json
import re
from ..core.models import Evidence

# Flarum 签到是纯 API 站点：判定只信 /api/users/{uid} 状态，页面按钮/记录行不适用于药丸。
BUTTON_TOKEN = "api-state"


class YaowanVerifier:
    def identity(self, page):
        match = re.search(r'"userId"\s*:\s*(\d+)', page or "")
        return match.group(1) if match and match.group(1) != "0" else ""

    def token(self, page):
        match = re.search(r'"csrfToken"\s*:\s*"([^"]+)"', page or "")
        return match.group(1) if match else ""

    def api_state(self, page):
        match = re.search(r"<!-- forum-signin-api-state (\{.*?\}) -->", page or "")
        if not match:
            return None
        try:
            return json.loads(match.group(1))
        except (TypeError, ValueError):
            return None

    def judge(self, page, uid, business_date):
        """API 状态判定；state 缺失或字段无法识别时 status 留空，由 normalize 归为 unconfirmed。

        字段名以官方/V2 在线实现为准（canCheckin），兼容历史注入样本的大写变体。
        """
        state = self.api_state(page) or {}
        last_checkin = str(state.get("lastCheckinTime") or "")
        can_checkin = state.get("canCheckin", state.get("canCheckIn"))
        if last_checkin.startswith(business_date):
            status = "已签到"
        elif can_checkin is True:
            status = "未签到"
        else:
            status = ""
        total = state.get("totalContinuousCheckIn")
        note = f"已签到 {total} 天" if isinstance(total, int) and total > 0 else ""
        return Evidence(BUTTON_TOKEN, uid, business_date, status, "api", "药丸用户 API 状态", note)
