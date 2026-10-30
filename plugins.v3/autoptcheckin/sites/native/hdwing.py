"""HDWinG：首页右上角 AJAX 签到（plugin_sign-in.php?cmd=signin，x-csrf 头）。"""
import json
import re
from urllib.parse import urljoin

from ...core.models import SignResult, SignStatus
from ...core.sitemodel import RecordSpec, SignContext, SiteModule


class Hdwing(SiteModule):
    id = "hdwing"
    name = "HDWinG"
    url = "https://hdwing.org/"
    # 签到入口在首页右上角（do_signin AJAX），无独立 attendance 页面。
    attendance_path = "/"
    record_spec = RecordSpec('//a[contains(@onclick, "do_signin")]', {})

    def signin(self, ctx: SignContext) -> SignResult:
        page = ctx.http.get(urljoin(self.url, "/index.php"))
        text = (page.text or "") if page is not None else ""
        if not text:
            return ctx.result(status=SignStatus.NETWORK_ERROR, message="签到页面不可达：空响应")
        # 已签证据：按钮变为「已签到」或 do_signin 入口消失。
        if "已签到" in text and "do_signin" not in text:
            return ctx.result(status=SignStatus.ALREADY, message="HDWinG 今日已签到（首页已签标记）")
        csrf = re.search(r"meta\s+name=['\"]x-csrf['\"]\s+content=['\"]([^'\"]+)", text)
        if not csrf:
            return ctx.result(status=SignStatus.UNCONFIRMED, message="未取到 x-csrf，无法提交 AJAX 签到")
        resp = ctx.http.post(urljoin(self.url, "/plugin_sign-in.php?cmd=signin"),
                             data={"csrf": csrf.group(1)},
                             headers={"Referer": urljoin(self.url, "/index.php"),
                                      "X-Requested-With": "XMLHttpRequest"})
        state = None
        try:
            state = (json.loads(resp.text or "{}") or {}).get("state")
        except Exception:
            pass
        # 无条件回读首页核实真实状态（按钮/已签标记），不轻信提交回执。
        page2 = ctx.http.get(urljoin(self.url, "/index.php"))
        text2 = (page2.text or "") if page2 is not None else ""
        if "已签到" in text2 and "do_signin" not in text2:
            return ctx.result(status=SignStatus.ALREADY, message="提交后首页已签标记")
        if state == "success":
            return ctx.result(status=SignStatus.SUCCESS, message="签到成功")
        return ctx.result(status=SignStatus.UNCONFIRMED, message=f"提交回执 state={state}")
