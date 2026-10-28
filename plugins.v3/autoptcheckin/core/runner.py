"""执行链共享资源：站点锁、停止信号、历史与通知回调。"""
from contextlib import contextmanager
from threading import Event, Lock
from typing import Callable

from .models import SignResult


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
