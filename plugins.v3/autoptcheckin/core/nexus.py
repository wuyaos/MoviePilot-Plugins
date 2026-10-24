"""Native Nexus form flow. Submission replies never replace a fresh message read."""
from dataclasses import dataclass, replace
from urllib.parse import urljoin, urlsplit

from lxml import html

from .models import Evidence, LoginPage, LoginStatus, SignResult, SignStatus
from .sitemodel import RecordSpec, SignContext, SiteModule, page_available, page_maintenance


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
                if nodes:
                    return ctx.result(status=SignStatus.ALREADY,
                                      evidence=Evidence(status="signed"))
        spec = self.pre_read_spec or self.message_spec()
        # A homepage is not the action response; never parse its JSON as a receipt.
        if spec.source == "response_json":
            return ctx.result(status=SignStatus.UNCONFIRMED, evidence=Evidence(status="unconfirmed"))
        return ctx.record_result(page, spec, before_submit=True)

    @staticmethod
    def _with_steps(result: SignResult, steps, ctx: "SignContext | None" = None) -> SignResult:
        # 动作站 steps 明细/提交异常进 metadata（空则不动）；MP 日志 INFO/WARNING 不落盘，
        # history/响应 metadata 是 qnap 上唯一的动作诊断通道。
        meta = result.metadata or {}
        if steps:
            meta = {**meta, "page_action": steps}
        if ctx is not None:
            err = getattr(ctx, "cloak_submit_error", None)
            if err:
                meta = {**meta, "submit_error": err}
        if meta != (result.metadata or {}):
            result.metadata = meta
        return result

    def read_after(self, ctx: SignContext, page: LoginPage | None) -> SignResult:
        steps = getattr(ctx, "cloak_steps_result", None)
        if self.signed_marker:
            result = self.read_before(ctx, page)
            if result.status == SignStatus.ALREADY:
                result.status = SignStatus.SUCCESS
            return self._with_steps(result, steps, ctx)
        return self._with_steps(ctx.record_result(page, self.message_spec()), steps, ctx)
    # NexusPHP 标准结构默认消息选择器（占位站自动回退，命中即用；全部未命中仍 unconfirmed）
    DEFAULT_MESSAGE_XPATHS = (
        '//h1[contains(.,"签到") or contains(.,"打卡")]',
        '//h2[contains(.,"签到") or contains(.,"打卡")]',
        '//h3[contains(.,"签到") or contains(.,"打卡")]',
        '//div[contains(@class,"alert") or contains(@class,"layui-layer")]',
        '//div[contains(@id,"msg") or contains(@class,"message")]',
        '//td[contains(@class,"text") and contains(text(),"签到")]',
        '//table[contains(@class,"t1")]//tr[1]',
        '//div[@id="main"]//font[contains(text(),"签到")]',
    )
    # 已签判据是词表：出现在唯一消息元素里即视为已签；新词只加列表，不再逐条写映射。
    SIGNED_TEXTS = (
        '签到成功', '已签到', '今天已经签到', '已经签到', '今天已签到',
        '連續簽到', '连续签到', '签到已得', '簽到已得',
        '請勿重複刷新', '请勿重复刷新', '您今天已经签到过了',
        '打卡成功', '已打卡', '簽到成功', '已簽到', '今天已打卡', '已經簽到', '請勿重複',
    )
    UNSIGNED_TEXTS = ('未签到', '未簽到')
    DEFAULT_STATUS_MAP = {**{text: 'signed' for text in SIGNED_TEXTS},
                          **{text: 'unsigned' for text in UNSIGNED_TEXTS}}

    def message_spec(self) -> RecordSpec:
        spec = self.record_spec
        # batch2 占位 → 回退 NexusPHP 默认选择器链（保留站点已有确证关键词并合并默认集）
        placeholder = isinstance(spec.message, str) and 'batch2-message-pending-calibration' in spec.message
        if getattr(self, "use_default_message", True) and (
                placeholder or (isinstance(spec.message, tuple) and not spec.message)):
            states = dict(self.DEFAULT_STATUS_MAP)
            states.update({k: v for k, v in spec.status_map.items() if v != 'signed' or k not in states})
            for text in self.success_texts:
                states.setdefault(text, "signed")
            return RecordSpec(message=self.DEFAULT_MESSAGE_XPATHS, status_map=states,
                              uid=spec.uid, date=spec.date, source="page_message")
        # Explicit mappings keep priority, including overlapping unsigned keywords.
        states = dict(spec.status_map)
        for text in self.success_texts:
            states.setdefault(text, "signed")
        return replace(spec, status_map=states)

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
        except Exception as exc:
            return ctx.result(status=SignStatus.NETWORK_ERROR, message=f"签到页面不可达：{type(exc).__name__}")
        try:
            if page_maintenance(page):
                return ctx.result(status=SignStatus.MAINTENANCE, message="维护中/已关闭")
            login = self.parse_login(page)
            if login.status == LoginStatus.AUTH_FAILED:
                return ctx.result(status=SignStatus.AUTH_FAILED, message=login.message)
            if not page_available(page):
                code = page.status_code if page is not None else 0
                detail = f"HTTP {code}" if code else "网络超时/无响应"
                return ctx.result(status=SignStatus.NETWORK_ERROR, message=f"签到页面不可达：{detail}")
            if getattr(page, 'status_code', 200) and page.status_code >= 400:
                # 2026-10-24 用户裁决口径：403/404/5xx 一律站点不可达，不进入表单/判定流程。
                return ctx.result(status=SignStatus.NETWORK_ERROR, message=f"站点不可达：HTTP {page.status_code}")
            before = self.read_before(ctx, page)
            if before.status == SignStatus.ALREADY:
                return before
            if before.metadata.get('reason') == 'identity_conflict':
                return before
            # 页面动作站（cloak_steps）不是 NexusPHP 表单协议：动作链自身负责验证和点击，
            # 因此直接进入 submit hook，保留统一的无条件回读与异常不重试语义。
            if getattr(self, "cloak_steps", None):
                form = SigninForm(attendance_url, [])
            else:
                if getattr(self, "protocol_pending", False):
                    return ctx.result(status=SignStatus.PROTOCOL_PENDING, message="滑动验证码协议待适配，未提交",
                                      evidence=before.evidence)
                form = self.discover_form(ctx, page)
                if form is None:
                    # CF JS 挑战页可达但返回 200：挑战页无表单，归不可达而非协议待适配。
                    low = (page.text or '')[:20000].lower()
                    if 'just a moment' in low or 'challenge-platform' in low or '__cf_chl' in low:
                        return ctx.result(status=SignStatus.NETWORK_ERROR, message="CF 盾拦截：页面为浏览器挑战页")
                    return ctx.result(status=SignStatus.PROTOCOL_PENDING, message="未发现唯一签到表单",
                                      evidence=before.evidence)
                if not self.solve_captcha(ctx, page, form):
                    return ctx.result(status=SignStatus.PROTOCOL_PENDING, message="验证码未解决，未提交")
        except Exception:
            return ctx.result(status=SignStatus.PROTOCOL_PENDING, message="签到前读或表单解析未确认")
        if ctx.cancel.is_set():
            return ctx.result(status=SignStatus.CANCELLED, message="任务已取消，未提交")
        try:
            self.submit(ctx, form)
        except Exception as exc:
            # A timeout may occur after the server accepted the action. Never retry.
            # 异常进 metadata（截断），qnap 日志不落盘时 history 是唯一诊断通道。
            ctx.cloak_submit_error = f"{type(exc).__name__}: {exc}"[:300]
        finally:
            # Also run after cancellation during the action or any submission exception.
            try:
                fresh = ctx.http.get(attendance_url)
            except Exception:
                fresh = None
        return self.read_after(ctx, fresh)
