"""统一执行链。旧适配器在逐次提交回读能力获验证前不允许接管。"""
from contextlib import contextmanager
from threading import Event, Lock
from typing import Callable
from uuid import uuid4

from .credentials import CredentialResolution
from .models import SignResult, SignStatus, LoginResult, LoginStatus
from .verification import normalize_evidence, verify_after_submit, verify_login
from ..verifiers import PageVerifier


class SiteAccountLocks:
    def __init__(self):
        self._guard = Lock()
        self._busy: set[tuple[str, str]] = set()

    @contextmanager
    def acquire(self, key: tuple[str, str]):
        with self._guard:
            acquired = key not in self._busy
            if acquired:
                self._busy.add(key)
        try:
            yield acquired
        finally:
            if acquired:
                with self._guard:
                    self._busy.remove(key)



class SignRunner:
    def __init__(self, locks: SiteAccountLocks | None = None, stop: Event | None = None,
                 history: Callable[[SignResult], object] | None = None,
                 notify: Callable[[SignResult], object] | None = None):
        self.locks = locks or SiteAccountLocks()
        self.stop = stop or Event()
        self.history, self.notify = history, notify

    def run(self, site_id: str, uid: str, business_date: str, *,
            resolve: Callable[[], CredentialResolution], fetch_page: Callable[[], str],
            verifier: PageVerifier, submit: Callable[[], tuple[bool, str]],
            read_only: bool = False, allow_page_identity: bool = False, trigger: str = "manual") -> SignResult:
        run_id = str(uuid4())

        def finish(result: SignResult) -> SignResult:
            result.site_id, result.account, result.run_id = site_id, uid, run_id
            result.metadata.setdefault("business_date", business_date)
            result.metadata["trigger"] = trigger
            result.metadata["action"] = "sign"
            result.metadata["read_only"] = read_only
            if self.history:
                self.history(result)
            if self.notify:
                self.notify(result)
            return result

        with self.locks.acquire((site_id, "" if allow_page_identity else uid)) as acquired:
            if not acquired:
                return finish(SignResult.skipped())
            if self.stop.is_set():
                return finish(SignResult(SignStatus.CANCELLED, "已停止，未提交"))
            if (not uid and not allow_page_identity) or not business_date:
                return finish(SignResult(SignStatus.UNCONFIRMED, "缺少绑定身份或业务日期，未提交"))
            try:
                auth = resolve()
            except Exception:
                return finish(SignResult(SignStatus.NETWORK_ERROR, "认证校验异常，未提交"))
            if auth.status != "valid" or auth.credential is None:
                status = (SignStatus.AUTH_FAILED if auth.status == "auth_failed" else
                          SignStatus.NETWORK_ERROR if auth.status in {"network_error", "timeout"} else SignStatus.UNCONFIRMED)
                return finish(SignResult(status, auth.reason or "认证未确认，未提交", metadata={"phase": "credentials"}))
            preflight = None
            try:
                page = fetch_page()
                if allow_page_identity:
                    uid = uid or verifier.identity(page)
                evidence = verifier.parse(page, uid, business_date)
                before = normalize_evidence(evidence, uid, business_date, True)
                preflight = verifier.preflight(page) if allow_page_identity else None
                if allow_page_identity and preflight == 'already':
                    before = SignResult(SignStatus.ALREADY, "签到前页面已签标记", evidence=evidence)
            except Exception:
                before = SignResult(SignStatus.UNCONFIRMED, "签到前页面不可达或解析异常")
            if before.confirmed or read_only:
                return finish(before)
            can_submit = (preflight == 'unsigned' if allow_page_identity
                          else before.status == SignStatus.FAILED)
            if not can_submit:
                if allow_page_identity and before.status == SignStatus.FAILED:
                    before = SignResult(SignStatus.UNCONFIRMED, '页面未提供明确可提交控件，未提交', evidence=before.evidence)
                return finish(before)
            if self.stop.is_set():
                return finish(SignResult(SignStatus.CANCELLED, "已停止，未提交"))
            submit_exception = False
            try:
                submit()
            except Exception:
                submit_exception = True
            finally:
                # 停止信号、超时和错误响应均不能取消本次提交后的回读。
                result = verify_after_submit(fetch_page, verifier, uid, business_date)
            result.metadata.update({"phase": "verification", "submit_exception": submit_exception})
            return finish(result)


    def run_login(self, site_id, uid="", *, resolve, fetch_page, verifier, trigger="manual"):
        run_id = str(uuid4())
        def finish(result):
            result.site_id, result.run_id = site_id, run_id
            result.account = uid or (result.evidence.uid if result.confirmed and result.evidence else "") or ""
            result.metadata.update(action="login", trigger=trigger)
            if self.history:
                self.history(result)
            return result
        with self.locks.acquire((site_id, "")) as acquired:
            if not acquired:
                return finish(SignResult.skipped())
            if self.stop.is_set():
                return finish(SignResult(SignStatus.CANCELLED, "已停止，未访问"))
            try:
                auth = resolve()
            except Exception:
                return finish(LoginResult(LoginStatus.UNCONFIRMED, "认证校验不可达"))
            if auth.status != "valid" or auth.credential is None:
                status = LoginStatus.AUTH_FAILED if auth.status == "auth_failed" else LoginStatus.UNCONFIRMED
                return finish(LoginResult(status, auth.reason or "认证未确认"))
            first = verify_login(fetch_page, verifier, uid)
            if first.status in (LoginStatus.LOGIN_OK, LoginStatus.AUTH_FAILED):
                return finish(first)
            return finish(verify_login(fetch_page, verifier, uid))
