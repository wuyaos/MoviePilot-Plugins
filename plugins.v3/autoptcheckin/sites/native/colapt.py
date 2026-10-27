"""ColaPT（colapt.com）：自建 SPA，JSON API 每周签到。

协议（2026-10 实测）：
- GET /api/v1/me → session.csrf_token（Cookie 会话；401 = Cookie 失效）
- GET /api/v1/me/cola → week.checkin_amount（>0 = 本周已签）、week.next_start（下周一 0 点）
- POST /api/v1/me/cola/checkin（Origin + X-CSRF-Token + JSON body）→ 200 {balance,currency,earned}；
- POST /api/v1/me/cola/checkin（Origin + X-CSRF-Token + JSON body）→ 200 {balance,currency,earned}；
  提交回执须经 GET /api/v1/me/cola 回读确证（week.checkin_amount>0 才算成功，不猜 200 空回执）；
  409 = cola_checkin_done；CSRF 服务端可能轮换，故每次签到现取不缓存。
"""
import json
from urllib.parse import urljoin

from ...core.models import SignResult, SignStatus
from ...core.sitemodel import RecordSpec, SignContext, SiteModule


class Colapt(SiteModule):
    id = "colapt"
    name = "可乐PT"
    url = "https://www.colapt.com/"
    attendance_path = "/account/cola"
    hook_implemented = True
    record_spec = RecordSpec('//button[contains(@class,"cola-checkin")]',
                             {"本周已签": "signed"})

    def signin(self, ctx: SignContext) -> SignResult:
        me = ctx.http.get(urljoin(self.url, "/api/v1/me"))
        if me is not None and me.status_code in (401, 403):
            return ctx.result(status=SignStatus.NETWORK_ERROR,
                              message="登录状态不可用（/api/v1/me 401，Cookie 可能失效）")
        csrf = (self._json(me).get("session") or {}).get("csrf_token") or ""
        if not csrf:
            return ctx.result(status=SignStatus.NETWORK_ERROR, message="未取到 CSRF token，无法提交签到")
        # 只读探测：本周已签直接跳过，不发提交请求（零副作用）。
        week = (self._json(ctx.http.get(urljoin(self.url, "/api/v1/me/cola"))).get("week") or {})
        amount = week.get("checkin_amount") or 0
        if amount:
            return ctx.result(status=SignStatus.ALREADY,
                              message=f"本周已签到（+{amount}），下周一 0 点可再签")
        resp = ctx.http.post(urljoin(self.url, "/api/v1/me/cola/checkin"), json={},
                             headers={"Origin": self.url.rstrip("/"),
                                      "X-CSRF-Token": csrf,
                                      "Accept": "application/json",
                                      "Referer": urljoin(self.url, "/account/cola")})
        code = resp.status_code if resp is not None else 0
        body = self._json(resp)
        if code == 409 or (body.get("error") or {}).get("code") == "cola_checkin_done":
            return ctx.result(status=SignStatus.ALREADY, message="本周已经签过到了")
        if code == 200:
            earned, balance = body.get("earned"), body.get("balance")
            # 提交回执必须经回读确证：GET /api/v1/me/cola 本周计数 >0 才算成功；
            # 响应缺业务字段、回读不可达或计数未增长都按未确认，不猜成功。
            week = (self._json(ctx.http.get(urljoin(self.url, "/api/v1/me/cola"))).get("week") or {})
            amount = week.get("checkin_amount") or 0
            if not amount:
                return ctx.result(status=SignStatus.UNCONFIRMED,
                                  message="签到回执未确认（回读未见本周签到计数）")
            detail = f"获得 {earned} 个核子可乐" if earned is not None else f"本周已签到（+{amount}）"
            if balance is not None:
                detail += f"（余额 {balance}）"
            return ctx.result(status=SignStatus.SUCCESS, message=detail)
            return ctx.result(status=SignStatus.NETWORK_ERROR,
                              message=f"签到被拒绝（HTTP {code}，CSRF 或会话失效）")
        return ctx.result(status=SignStatus.UNCONFIRMED, message=f"签到回执未确认（HTTP {code}）")

    @staticmethod
    def _json(page):
        try:
            return json.loads(getattr(page, "text", "") or "{}") or {}
        except Exception:
            return {}
