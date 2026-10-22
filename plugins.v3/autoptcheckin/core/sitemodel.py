"""Native declarations with explicitly scoped page or response evidence."""
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from threading import Event
from typing import Any, Literal, Mapping, Protocol
from urllib.parse import urlsplit

from lxml import html

from .credentials import Credential, CredentialSpec
from .models import Evidence, LoginPage, LoginResult, LoginStatus, RewardSummary, SignResult, SignStatus

RecordStatus = Literal["signed", "unsigned", "unconfirmed"]


@dataclass(frozen=True)
class RecordSpec:
    """Declared evidence source; uid/date are display-only.

    page_message uses a unique XPath element and ordered substring matching.
    response_json uses a top-level field and exact scalar type/value matching.
    """
    message: str | tuple[str, ...] = ""
    status_map: Mapping[str | int | bool, Literal["signed", "unsigned"]] = field(default_factory=dict)
    uid: str | None = None
    date: str | None = None

    source: Literal["page_message", "response_json"] = "page_message"
    response_field: str | None = None

    def __post_init__(self):
        if self.source not in {"page_message", "response_json"}:
            raise ValueError("unknown record source")
        if self.source == "response_json" and not self.response_field:
            raise ValueError("response_field is required")
        if self.source == "page_message" and isinstance(self.message, str) and not self.message.strip():
            raise ValueError("message selector is required")
        if self.source == "page_message" and isinstance(self.message, tuple) and not self.message:
            raise ValueError("message selector is required")
        if any((not isinstance(key, str) or not key) if self.source == "page_message"
               else type(key) not in {str, int, bool} or key == "" for key in self.status_map):
            raise ValueError("invalid status_map key")
        if any(value not in {"signed", "unsigned"} for value in self.status_map.values()):
            raise ValueError("status_map requires nonempty keywords and signed/unsigned states")


class HttpClient(Protocol):
    """Caller supplies an authenticated, timeout-bounded client; no credential lookup here."""
    def get(self, url: str, *, referer: str | None = None) -> LoginPage: ...
    def post(self, url: str, *, data: list[tuple[str, str]] | None = None,
             json: dict | None = None, headers: dict | None = None,
             referer: str | None = None) -> LoginPage: ...
    def get_bytes(self, url: str) -> bytes: ...
    def retain_cookies(self, names: set[str]) -> None: ...


def select_text(tree, selector: str | None) -> str:
    if not selector:
        return ""
    nodes = tree.xpath(selector)
    if not isinstance(nodes, list) or len(nodes) != 1:
        return ""
    node = nodes[0]
    if isinstance(node, str):
        parent = node.getparent() if hasattr(node, "getparent") else None
        if parent is not None and parent.tag in {"html", "body"}:
            return ""
        return node.strip()
    if getattr(node, "tag", "").lower() in {"html", "body"}:
        return ""
    return (node.get("value") or node.text_content()).strip()


def page_maintenance(page: LoginPage | None) -> bool:
    """Only inspect the response body's first 2 KiB; never classify post-action reads."""
    if page is None:
        return False
    if page.status_code in {403, 502, 503}:
        return True
    prefix = page.text.encode("utf-8")[:2048].decode("utf-8", errors="ignore").casefold()
    return any(marker in prefix for marker in (
        "维护中", "站点维护", "正在维护", "站点已关闭", "网站已关闭",
        "temporarily unavailable", "site is down", "under maintenance", "site is closed",
    ))


def page_available(page: LoginPage | None) -> bool:
    return page is not None and page.status_code == 200 and bool(page.text)


def login_redirect(page: LoginPage) -> bool:
    path = urlsplit(page.url).path.lower().rstrip("/").rsplit("/", 1)[-1]
    return path in {"login", "login.php", "signin", "signin.php"} or page.status_code in {401, 403}


@dataclass
class SignContext:
    """Resources are owned by the caller, including the already-held site lock.

    page is an injected synchronous Playwright Page, ocr an injected OCR service.
    Neither is created/closed here. The HTTP client already carries credentials.
    """
    site_id: str
    credential: Credential
    http: HttpClient
    page: Any = field(default=None, repr=False)
    ocr: Any = field(default=None, repr=False)
    site_lock: Any = field(default=None, repr=False)
    cancel: Event = field(default_factory=Event, repr=False)

    get_data: Any = field(default=None, repr=False)
    save_data: Any = field(default=None, repr=False)
    public_get: Any = field(default=None, repr=False)

    def result(self, *, status: SignStatus | str, message: str = "",
               evidence: Evidence | None = None, reward: RewardSummary | None = None) -> SignResult:
        return SignResult(SignStatus(status), message, evidence, reward,
                          site_id=self.site_id, account=self.credential.uid)

    def read_record(self, page: LoginPage | None, spec: RecordSpec) -> Evidence:
        """No whole-page keyword fallback, including on missing/ambiguous selectors."""
        if not page_available(page) or login_redirect(page):
            return Evidence(status="unconfirmed")
        if spec.source == "response_json":
            try:
                payload = json.loads(page.text)
                value = payload.get(spec.response_field) if isinstance(payload, dict) else None
                # Exact scalar/type match: JSON false must not match numeric zero.
                status = next((state for key, state in spec.status_map.items()
                               if type(value) is type(key) and value == key), "unconfirmed")
                summary = str(value) if isinstance(value, (str, int, float, bool)) else ""
                return Evidence(status=status, raw_summary=summary, source="response_json")
            except (ValueError, TypeError):
                return Evidence(status="unconfirmed")
        try:
            tree = html.fromstring(page.text)
            selectors = spec.message if isinstance(spec.message, tuple) else (spec.message,)
            message = ""
            for sel in selectors:
                try:
                    message = select_text(tree, sel)
                except (ValueError, TypeError, html.etree.XPathError, html.etree.ParserError):
                    message = ""
                if message:
                    break
            status: RecordStatus = "unconfirmed"
            if message:
                status = next((state for keyword, state in spec.status_map.items()
                               if keyword in message), "unconfirmed")
            # Optional display extraction must not veto a valid message.
            values = {}
            for name in ("uid", "date"):
                try:
                    values[name] = select_text(tree, getattr(spec, name))
                except (ValueError, TypeError, html.etree.XPathError, html.etree.ParserError):
                    values[name] = ""
            return Evidence(uid=values["uid"] or None, date=values["date"],
                            status=status, raw_summary=message)
        except (ValueError, TypeError, html.etree.XPathError, html.etree.ParserError):
            return Evidence(status="unconfirmed")

    def record_result(self, page: LoginPage | None, spec: RecordSpec, *, before_submit: bool = False) -> SignResult:
        evidence = self.read_record(page, spec)
        status = {"signed": SignStatus.ALREADY if before_submit else SignStatus.SUCCESS,
                  "unsigned": SignStatus.FAILED}.get(evidence.status, SignStatus.UNCONFIRMED)
        return self.result(status=status, message=evidence.raw_summary, evidence=evidence)


class SiteModule(ABC):
    id: str = ""
    name: str = ""
    url: str = ""
    credential: CredentialSpec = CredentialSpec()
    login_capable: bool = True
    cf: bool | None = None
    record_spec: RecordSpec

    @abstractmethod
    def signin(self, ctx: SignContext) -> SignResult:
        """Perform site-specific sign-in using injected resources only."""
        raise NotImplementedError

    def parse_login(self, page: LoginPage | None) -> LoginResult:
        if page is not None and login_redirect(page):
            return LoginResult(LoginStatus.AUTH_FAILED, "页面转向登录或认证失败", site_id=self.id)
        if not page_available(page):
            return LoginResult(LoginStatus.UNCONFIRMED, "登录页面不可达", site_id=self.id)
        uid = ""
        try:
            uid = select_text(html.fromstring(page.text), self.record_spec.uid)
            if not uid:
                from ..verifiers.nexus import NexusVerifier
                uid = NexusVerifier().identity(page.text)
        except (ValueError, TypeError, html.etree.XPathError, html.etree.ParserError):
            pass
        return LoginResult(LoginStatus.LOGIN_OK, "站点页面可达", evidence=Evidence(uid=uid or None), site_id=self.id)
