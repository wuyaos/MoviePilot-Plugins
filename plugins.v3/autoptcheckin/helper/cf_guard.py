"""有界页面传输链；provider 必须遵守传入的秒级 timeout，不创建后台线程。"""
from dataclasses import dataclass, field
from time import monotonic
from typing import Callable, Protocol

class PageProvider(Protocol):
    def __call__(self, url: str, *, timeout: float) -> str: ...

class BrowserlessSigner(PageProvider, Protocol):
    """可选 Browserless 传输边界；阶段1不连接服务。"""

@dataclass
class GuardBudget:
    chain_seconds: float = 30
    level_seconds: float = 8
    clock: Callable[[], float] = field(default=monotonic, repr=False)
    _started: float = field(init=False, repr=False)

    def __post_init__(self):
        self._started = self.clock()

    @property
    def remaining(self) -> float:
        return max(0.0, self.chain_seconds - (self.clock() - self._started))

    def timeout(self) -> float:
        return min(self.level_seconds, self.remaining)


def _page_has_challenge(page: str) -> bool:
    text = (page or "").lower()
    return any(token in text for token in ("cf-chl", "verify you are human", "challenge-platform", "just a moment..."))

class ChallengePageProvider(Protocol):
    """命名与参考 ctx 对齐；未提供自动点击或绕过挑战实现。"""
    def _click_cf_checkbox(self, page: object, *, timeout: float) -> bool: ...
    def _wait_challenge_clear(self, page: object, *, timeout: float) -> str: ...

@dataclass(frozen=True)
class GuardResponse:
    page: str = ""
    status: str = "unconfirmed"
    level: str = ""
    attempts: tuple[str, ...] = ()

class CfGuard:
    def __init__(self, direct: PageProvider, auto_cf: PageProvider | None = None,
                 playwright: PageProvider | None = None, browserless: PageProvider | None = None,
                 enable_playwright: bool = False, enable_browserless: bool = False,
                 chain_seconds: float = 30, level_seconds: float = 8,
                 clock: Callable[[], float] = monotonic):
        self.providers = [("direct", direct), ("auto_cf", auto_cf),
                          ("playwright", playwright if enable_playwright else None),
                          ("browserless", browserless if enable_browserless else None)]
        self.chain_seconds, self.level_seconds, self.clock = chain_seconds, level_seconds, clock

    def fetch(self, url: str) -> GuardResponse:
        # 每次读取（含提交后的新页面）走相同策略，但有独立链预算。
        budget = GuardBudget(self.chain_seconds, self.level_seconds, self.clock)
        attempts = []
        for name, provider in self.providers:
            if provider is None:
                continue
            timeout = budget.timeout()
            if timeout <= 0:
                break
            attempts.append(name)
            started = self.clock()
            try:
                page = provider(url, timeout=timeout)
            except Exception:
                continue
            if self.clock() - started > timeout or budget.remaining <= 0:
                continue
            if page and not _page_has_challenge(page):
                return GuardResponse(page, "ok", name, tuple(attempts))
        return GuardResponse(attempts=tuple(attempts))
