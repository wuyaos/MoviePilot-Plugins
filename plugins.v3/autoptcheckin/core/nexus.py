"""Native Nexus form flow. Submission replies never replace a fresh message read."""
from dataclasses import dataclass, replace
from urllib.parse import urljoin, urlsplit

from lxml import html

from .models import Evidence, LoginPage, LoginStatus, SignResult, SignStatus
from .sitemodel import RecordSpec, SignContext, SiteModule, page_available


@dataclass
class SigninForm:
    action: str
    data: list[tuple[str, str]]
    referer: str | None = None


class NexusSignin(SiteModule):
    attendance_path: str = "/attendance.php"
    success_texts: tuple[str, ...] = ()
    pre_read_spec: RecordSpec | None = None
    signed_marker: str | None = None

    def read_before(self, ctx: SignContext, page: LoginPage | None) -> SignResult:
        if page_available(page) and self.parse_login(page).status != LoginStatus.AUTH_FAILED:
            if self.signed_marker:
                nodes = html.fromstring(page.text).xpath(self.signed_marker)
                if len(nodes) == 1:
                    return ctx.result(status=SignStatus.ALREADY,
                                      evidence=Evidence(status="signed"))
        spec = self.pre_read_spec or self.message_spec()
        # A homepage is not the action response; never parse its JSON as a receipt.
        if spec.source == "response_json":
            return ctx.result(status=SignStatus.UNCONFIRMED, evidence=Evidence(status="unconfirmed"))
        return ctx.record_result(page, spec, before_submit=True)

    def read_after(self, ctx: SignContext, page: LoginPage | None) -> SignResult:
        if self.signed_marker:
            result = self.read_before(ctx, page)
            if result.status == SignStatus.ALREADY:
                result.status = SignStatus.SUCCESS
                return result
        return ctx.record_result(page, self.message_spec())

    def message_spec(self) -> RecordSpec:
        # Explicit mappings keep priority, including overlapping unsigned keywords.
        states = dict(self.record_spec.status_map)
        for text in self.success_texts:
            states.setdefault(text, "signed")
        return replace(self.record_spec, status_map=states)

    def discover_form(self, ctx: SignContext, page: LoginPage) -> SigninForm | None:
        """Only an unambiguous POST form on the attendance page is eligible.

        Other sites can override discovery; never guess among multiple forms.
        """
        if self.record_spec.source == "response_json":
            return None
        tree = html.fromstring(page.text)
        base_url = page.url or urljoin(self.url, self.attendance_path)
        forms = [form for form in tree.forms if form.method.upper() == "POST"]
        attendance_url = urljoin(self.url, self.attendance_path)
        candidates = [form for form in forms
                      if urlsplit(urljoin(base_url, form.get("action") or base_url)).path
                      == urlsplit(attendance_url).path]
        if len(candidates) != 1:
            return None
        form = candidates[0]
        action = urljoin(base_url, form.get("action") or base_url)
        if urlsplit(action)[:2] != urlsplit(self.url)[:2]:
            return None
        data = list(form.form_values())
        buttons = form.xpath('.//input[@type="submit" and not(@disabled)] | '
                             './/button[not(@type) or @type="submit"][not(@disabled)]')
        if len(buttons) > 1:
            return None
        if buttons and buttons[0].get("name"):
            data.append((buttons[0].get("name"), buttons[0].get("value", "")))
        return SigninForm(action, data)

    def solve_captcha(self, ctx: SignContext, page: LoginPage, form: SigninForm) -> bool:
        """No captcha by default; override to fill form using ctx.ocr/ctx.page."""
        return True

    def submit(self, ctx: SignContext, form: SigninForm) -> None:
        """Override for two-step sites; the outer flow still always re-reads."""
        kwargs = {"referer": form.referer} if form.referer else {}
        ctx.http.post(form.action, data=form.data, **kwargs)

    def signin(self, ctx: SignContext) -> SignResult:
        if ctx.cancel.is_set():
            return ctx.result(status=SignStatus.CANCELLED, message="任务已取消")
        attendance_url = urljoin(self.url, self.attendance_path)
        try:
            page = ctx.http.get(attendance_url)
            login = self.parse_login(page)
            if login.status == LoginStatus.AUTH_FAILED:
                return ctx.result(status=SignStatus.AUTH_FAILED, message=login.message)
            if not page_available(page):
                return ctx.result(status=SignStatus.UNCONFIRMED, message="签到页面不可达")
            before = self.read_before(ctx, page)
            if before.status == SignStatus.ALREADY:
                return before
            form = self.discover_form(ctx, page)
            if form is None:
                return ctx.result(status=SignStatus.UNCONFIRMED, message="未发现唯一签到表单",
                                  evidence=before.evidence)
            if not self.solve_captcha(ctx, page, form):
                return ctx.result(status=SignStatus.UNCONFIRMED, message="验证码未解决，未提交")
        except Exception:
            return ctx.result(status=SignStatus.UNCONFIRMED, message="签到前读或表单解析未确认")
        if ctx.cancel.is_set():
            return ctx.result(status=SignStatus.CANCELLED, message="任务已取消，未提交")
        try:
            self.submit(ctx, form)
        except Exception:
            # A timeout may occur after the server accepted the action. Never retry.
            pass
        finally:
            # Also run after cancellation during the action or any submission exception.
            try:
                fresh = ctx.http.get(attendance_url)
            except Exception:
                fresh = None
        return self.read_after(ctx, fresh)
