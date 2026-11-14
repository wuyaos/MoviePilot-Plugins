"""ColaPT（colapt.com）：自建 SPA，JSON API 每周签到。

协议（2026-10/11 实测）：
- GET /api/v1/me → session.csrf_token（Cookie 会话；401 = Cookie 失效；CSRF 服务端可能轮换，现取不缓存）
- GET /api/v1/me/cola → today（ColaToday：logged_in/login_earned，每日登录状态）、week.checkin_amount（>0 = 本周已签）、
  week.next_start（下周一 0 点）、rules.daily_login_reward（每日登录奖励数，<=0 = 站点关闭）
- POST /api/v1/me/cola/daily-login（Origin + X-CSRF-Token + JSON body）→ 200 {earned,balance,currency:"cola"}；
  「每天打开站点 +3」由前端显式 claim 领取，纯 GET 探活不发放；spec 未定义 409，前端防重依据 today.logged_in，
  claim 失败前端静默降级——插件同样只降级为消息片段，不阻断每周签到
- POST /api/v1/me/cola/checkin（Origin + X-CSRF-Token + JSON body）→ 200 {balance,currency,earned}；
  提交回执须经 GET /api/v1/me/cola 回读确证（week.checkin_amount>0 才算成功，不猜 200 空回执）；
  409 = cola_checkin_done
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
        # 只读探测：today（每日登录状态）与 week（每周签到）在同一 /me/cola 响应里。
        cola = self._json(ctx.http.get(urljoin(self.url, "/api/v1/me/cola")))
        daily = self._claim_daily_login(ctx, csrf, cola)
        week = (cola.get("week") or {})
        amount = week.get("checkin_amount") or 0
        if amount:
            return ctx.result(status=SignStatus.ALREADY,
                              message=self._join(daily, f"本周已签到（+{amount}），下周一 0 点可再签"))
        resp = ctx.http.post(urljoin(self.url, "/api/v1/me/cola/checkin"), json={},
                             headers={"Origin": self.url.rstrip("/"),
                                      "X-CSRF-Token": csrf,
                                      "Accept": "application/json",
                                      "Referer": urljoin(self.url, "/account/cola")})
        code = resp.status_code if resp is not None else 0
        body = self._json(resp)
        if code == 409 or (body.get("error") or {}).get("code") == "cola_checkin_done":
            return ctx.result(status=SignStatus.ALREADY, message=self._join(daily, "本周已经签过到了"))
        if code == 200:
            earned, balance = body.get("earned"), body.get("balance")
            # 提交回执必须经回读确证：GET /api/v1/me/cola 本周计数 >0 才算成功；
            # 响应缺业务字段、回读不可达或计数未增长都按未确认，不猜成功。
            week = (self._json(ctx.http.get(urljoin(self.url, "/api/v1/me/cola"))).get("week") or {})
            amount = week.get("checkin_amount") or 0
            if not amount:
                return ctx.result(status=SignStatus.UNCONFIRMED,
                                  message=self._join(daily, "签到回执未确认（回读未见本周签到计数）"))
            detail = f"获得 {earned} 个核子可乐" if earned is not None else f"本周已签到（+{amount}）"
            if balance is not None:
                detail += f"（余额 {balance}）"
            return ctx.result(status=SignStatus.SUCCESS, message=self._join(daily, detail))
        if code in (401, 403):
            return ctx.result(status=SignStatus.NETWORK_ERROR,
                              message=self._join(daily, f"签到被拒绝（HTTP {code}，CSRF 或会话失效）"))
        return ctx.result(status=SignStatus.UNCONFIRMED,
                          message=self._join(daily, f"签到回执未确认（HTTP {code}）"))

    def _claim_daily_login(self, ctx: SignContext, csrf: str, cola: dict) -> str:
        """每日登录奖励（POST /api/v1/me/cola/daily-login，前端 operationId claimColaDailyLogin）。

        「每天打开站点 +3」由前端显式 POST claim 领取，纯 GET 探活不发放。
        已领判定优先 today.logged_in（前端同款防重依据；spec 未定义 409，不把
        重复 POST 的具体错误码当主判据，409 仅作状态竞争兜底）。claim 失败
        静默降级为消息片段（前端 catch 同款），不阻断每周签到主流程。
        返回消息片段字符串（空串 = 无需展示）。
        """
        today = cola.get("today") or {}
        if today.get("logged_in"):
            earned = today.get("login_earned") or 0
            return f"每日登录 +{earned}" if earned else "每日登录已领取"
        if not (cola.get("rules") or {}).get("daily_login_reward", 0):
            return ""
        resp = ctx.http.post(urljoin(self.url, "/api/v1/me/cola/daily-login"), json={},
                             headers={"Origin": self.url.rstrip("/"),
                                      "X-CSRF-Token": csrf,
                                      "Accept": "application/json",
                                      "Referer": urljoin(self.url, "/account/cola")})
        code = resp.status_code if resp is not None else 0
        if code == 200:
            earned = self._json(resp).get("earned") or 0
            return f"每日登录 +{earned}" if earned else "每日登录已处理（未获得新增奖励）"
        if code == 409:
            return "每日登录已领取"
        return f"每日登录奖励未确认（HTTP {code}）"

    @staticmethod
    def _join(*parts: str) -> str:
        return "；".join(p for p in parts if p)

    @staticmethod
    def _json(page):
        try:
            return json.loads(getattr(page, "text", "") or "{}") or {}
        except Exception:
            return {}
