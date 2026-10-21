"""One action receipt plus an unconditional safe-page read; never retry the action."""
from urllib.parse import urljoin

from .models import LoginStatus, SignStatus
from .nexus import NexusSignin, SigninForm
from .sitemodel import page_available


class ApiSignin(NexusSignin):
    action_path = ""

    def discover_form(self, ctx, page):
        return SigninForm(urljoin(self.url, self.action_path), [])

    def perform_action(self, ctx, form):
        return ctx.http.get(form.action)

    def receipt_result(self, ctx, receipt):
        return ctx.record_result(receipt, self.record_spec)

    def signin(self, ctx):
        if ctx.cancel.is_set():
            return ctx.result(status=SignStatus.CANCELLED)
        safe_url = urljoin(self.url, self.attendance_path)
        try:
            page = ctx.http.get(safe_url)
            if self.parse_login(page).status == LoginStatus.AUTH_FAILED:
                return ctx.result(status=SignStatus.AUTH_FAILED)
            if not page_available(page):
                return ctx.result(status=SignStatus.UNCONFIRMED)
            before = self.read_before(ctx, page)
            if before.status == SignStatus.ALREADY:
                return before
            form = self.discover_form(ctx, page)
            if form is None or not self.solve_captcha(ctx, page, form):
                return ctx.result(status=SignStatus.UNCONFIRMED, message="动作参数未确认，未提交")
        except Exception:
            return ctx.result(status=SignStatus.UNCONFIRMED, message="动作前读未确认")
        if ctx.cancel.is_set():
            return ctx.result(status=SignStatus.CANCELLED)
        receipt = None
        try:
            receipt = self.perform_action(ctx, form)
        except Exception:
            pass
        finally:
            try:
                fresh = ctx.http.get(safe_url)
            except Exception:
                fresh = None
        try:
            reread = self.read_before(ctx, fresh)
        except Exception:
            reread = ctx.result(status=SignStatus.UNCONFIRMED)
        if reread.status == SignStatus.ALREADY:
            reread.status = SignStatus.SUCCESS
            return reread
        return self.receipt_result(ctx, receipt)
