"""Offline regression: a live sync browser may expose a running event loop.

The fake enforces thread affinity rather than allowing browser calls on any
thread. No network, browser installation or credentials are used.
"""
import asyncio
import importlib
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
entry = importlib.import_module('autoptcheckin')
cloak = importlib.import_module('autoptcheckin.core.cloak')
native = importlib.import_module('autoptcheckin.core.native')


def test_round_browser_lifecycle_stays_on_actor_thread(monkeypatch):
    live = set()
    opened = []
    closed = []

    class Page:
        url = 'https://fixture.invalid/'

        def __init__(self, context):
            self.context = context

        def content(self):
            self.context.check()
            return 'fixture'

    class Context:
        def __init__(self):
            self.owner = threading.get_ident()
            live.add(self.owner)
            opened.append(self.owner)

        def check(self):
            if threading.get_ident() != self.owner:
                raise RuntimeError('Cannot switch to a different thread')

        def new_page(self):
            self.check()
            return Page(self)

        def cookies(self, url):
            self.check()
            return []

        def close(self):
            self.check()
            live.remove(self.owner)
            closed.append(self.owner)

    def running_loop():
        if threading.get_ident() in live:
            return object()
        raise RuntimeError('no running event loop')

    monkeypatch.setattr(asyncio, 'get_running_loop', running_loop)
    monkeypatch.setattr(cloak, 'launch_context', lambda **kwargs: Context())
    p = entry.AutoPtCheckin.__new__(entry.AutoPtCheckin)
    p._config = {'site_browserless': ['fixture-a', 'fixture-b']}
    p._runner = SimpleNamespace(stop=threading.Event())
    p._recompute_track_states = Mock()
    p._track_store = lambda: SimpleNamespace(rollover=lambda: None)
    p._due_for = lambda action: ['fixture-a', 'fixture-b'] if action == 'sign' else []
    p._notify_round = Mock()

    @native.off_loop
    def execute(site_id, action, trigger):
        site = SimpleNamespace(id=site_id, url='https://fixture.invalid/')
        client = cloak.CloakHttpClient(SimpleNamespace(cookies={}), {}, site)
        try:
            return {'status': 'success', 'message': client.page_snapshot()[0]}
        finally:
            client.close()

    p._run_with_retry = execute
    assert p._execute_all_round('scheduler') == [{'status': 'success', 'message': 'fixture'},
                                                 {'status': 'success', 'message': 'fixture'}]
    assert len(opened) == 2
    assert closed == opened
    assert not live
    assert all(owner != threading.get_ident() for owner in opened)
    assert list(p._last_round_results) == [('fixture-a', 'sign'), ('fixture-b', 'sign')]
