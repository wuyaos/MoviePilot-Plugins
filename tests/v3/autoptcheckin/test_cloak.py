import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / "plugins.v3"))
cloak = importlib.import_module("autoptcheckin.core.cloak")


class Context:
    def __init__(self): self.calls = []
    def new_page(self): return object()
    def add_cookies(self, cookies): self.calls.append(cookies)
    def storage_state(self, path): self.calls.append(path)
    def close(self): self.calls.append("closed")


def test_cloak_session_launch_cookie_and_resource_cleanup(monkeypatch, tmp_path):
    context = Context()
    seen = {}
    def launch(**kwargs):
        seen.update(kwargs)
        return context
    monkeypatch.setattr(cloak, "launch_context", launch)
    state = tmp_path / "state.json"
    state.write_text("{}")
    with cloak.CloakSession(state=state, cookie="sid=abc; x=y", url="https://pt.example/"):
        pass
    assert seen == {"headless": True, "humanize": True, "locale": "zh-CN", "storage_state": str(state)}
    assert context.calls[0] == [
        {"name": "sid", "value": "abc", "domain": "pt.example", "path": "/"},
        {"name": "x", "value": "y", "domain": "pt.example", "path": "/"},
    ]
    assert context.calls[-1] == "closed"


class _Body:
    def __init__(self, page): self.page = page
    def inner_text(self): return next(self.page.bodies)


class _Page:
    def __init__(self, titles, bodies):
        self.titles = iter(titles)
        self.bodies = iter(bodies)
        self.waits = []
    def title(self): return next(self.titles)
    def locator(self, selector):
        assert selector == "body"
        return _Body(self)
    def wait_for_timeout(self, milliseconds): self.waits.append(milliseconds)


def test_slider_waits_until_gate_page_redirects():
    page = _Page(["滑动认证", "Farmm :: 签到"], ["拖动滑块验证", "签到已得325"])
    assert cloak._wait_for_slider_page_exit(page) is True
    assert page.waits == [1500, 2000]


def test_slider_wait_reports_gate_timeout_without_stability_wait():
    page = _Page(["滑动认证"] * 16, ["拖动滑块验证"] * 16)
    assert cloak._wait_for_slider_page_exit(page) is False
    assert page.waits == [1500] * 16


class _Token:
    def __init__(self, values): self.values = iter(values)
    def count(self): return 1
    def input_value(self): return next(self.values)


class _TurnstilePage:
    def __init__(self, values):
        self.token = _Token(values)
        self.waits = []
    def locator(self, selector):
        assert selector == 'input[name="cf-turnstile-response"]'
        return type('FirstLocator', (), {'first': self.token})()
    def wait_for_timeout(self, milliseconds): self.waits.append(milliseconds)


def test_turnstile_waits_for_token_before_continuing():
    page = _TurnstilePage(['', '', 'token-value'])
    session = type('Session', (), {'page': page})()
    assert cloak.run_page_action(session, ['human_verify']) == [('human_verify', 'turnstile-ok')]
    assert page.waits == [1500, 1500, 8000]


def test_turnstile_timeout_is_reported_without_submission():
    page = _TurnstilePage([''] * 40)
    session = type('Session', (), {'page': page})()
    assert cloak.run_page_action(session, ['human_verify']) == [('human_verify', 'turnstile-timeout')]
    assert page.waits == [1500] * 40 + [8000]


def test_piggo_round_site_opens_headful_cloak_without_vclib(monkeypatch):
    from types import SimpleNamespace
    from autoptcheckin import AutoPtCheckin
    from autoptcheckin.core import cloak

    opened = []
    class FakeSession:
        def __init__(self, **kwargs): opened.append(kwargs)
        def __enter__(self): return self
        def close(self): pass

    monkeypatch.setattr(cloak, 'CloakSession', FakeSession)
    plugin = AutoPtCheckin()
    plugin._config = {'site_browserless': ['piggo', 'yema']}
    plugin._recompute_track_states = lambda: None
    plugin._track_store = lambda: SimpleNamespace(rollover=lambda: None)
    plugin._due_for = lambda action: ['piggo', 'yema'] if action == 'sign' else []
    def execute(site_id, *args):
        client = cloak.CloakHttpClient(
            SimpleNamespace(cookies={}), {},
            SimpleNamespace(id=site_id, url='https://fixture.invalid/'))
        client.close()
    plugin._run_with_retry = execute
    plugin._notify_round = lambda *args: None
    plugin._execute_all()
    assert [options['headless'] for options in opened] == [False, True]


def test_cloak_http_client_actor_binds_browser_to_dedicated_thread(monkeypatch):
    """独立会话的 playwright 操作全部在专属 actor 线程执行，调用方线程身份无关。"""
    import threading
    from types import SimpleNamespace
    from autoptcheckin.core import cloak

    seen_threads = []

    class FakeSession:
        def __init__(self, **kwargs):
            seen_threads.append(('open', threading.get_ident()))
            self.closed = False
            self.context = SimpleNamespace(cookies=lambda url: [])
            self.page = SimpleNamespace(content=lambda: '<html/>', url='https://fixture.invalid/',
                                         wait_for_timeout=lambda ms: seen_threads.append(('wait', threading.get_ident())))
        def __enter__(self): return self
        def goto(self, url):
            seen_threads.append(('goto', threading.get_ident()))
            return SimpleNamespace(status=200)
        def close(self):
            seen_threads.append(('close', threading.get_ident()))
            self.closed = True
    fake_context = SimpleNamespace(cookies=lambda url: [])
    monkeypatch.setattr(cloak, 'CloakSession', FakeSession)

    caller = threading.get_ident()
    client = cloak.CloakHttpClient(SimpleNamespace(cookies={}), {'url': 'https://fixture.invalid/'},
                                   SimpleNamespace(id='anthelion', url='https://fixture.invalid/'))
    page = client.get('https://fixture.invalid/')
    client.close()
    assert page.status_code == 200 and client.session.closed
    browser_ops = [ident for op, ident in seen_threads]
    assert browser_ops and set(browser_ops) == {browser_ops[0]}, '所有浏览器操作必须同一线程'
    assert browser_ops[0] != caller, '浏览器操作不得在调用方线程执行'


def test_cloak_http_client_actor_reraises_exception_from_browser_thread(monkeypatch):
    """actor 线程内的异常在调用方线程原样重抛（类型与消息保留）。"""
    from types import SimpleNamespace
    from autoptcheckin.core import cloak

    class FakeSession:
        def __init__(self, **kwargs): self.page = SimpleNamespace(content=lambda: '', url='', wait_for_timeout=lambda ms: None)
        def __enter__(self): return self
        def goto(self, url): raise RuntimeError('It looks like you are using Playwright Sync API inside the asyncio loop')
        def close(self): pass
    monkeypatch.setattr(cloak, 'CloakSession', FakeSession)
    client = cloak.CloakHttpClient(SimpleNamespace(cookies={}), {'url': 'https://fixture.invalid/'},
                                   SimpleNamespace(id='anthelion', url='https://fixture.invalid/'))
    try:
        client.get('https://fixture.invalid/')
        raise AssertionError('应当重抛异常')
    except RuntimeError as exc:
        assert 'asyncio loop' in str(exc)
    finally:
        client.close()


def test_actor_run_page_action_and_open_failure_recover_pool(monkeypatch):
    """P1-2/P2 回归：页面动作经 actor 线程执行；_open 失败回收 actor 线程。"""
    import threading
    from types import SimpleNamespace
    from autoptcheckin.core import cloak

    seen = []

    class FakeSession:
        def __init__(self, **kwargs):
            self.context = SimpleNamespace(cookies=lambda url: [])
            self.page = SimpleNamespace(content=lambda: '<html>ok</html>', url='https://fixture.invalid/',
                                        wait_for_timeout=lambda ms: seen.append(('wait', threading.get_ident())))
        def __enter__(self): return self
        def goto(self, url): return SimpleNamespace(status=200)
        def close(self): pass
    monkeypatch.setattr(cloak, 'CloakSession', FakeSession)
    monkeypatch.setattr(cloak, 'run_page_action', lambda session, steps: seen.append(('action', threading.get_ident())) or [['sign_button', 'clicked']])

    caller = threading.get_ident()
    client = cloak.CloakHttpClient(SimpleNamespace(cookies={}), {'url': 'https://fixture.invalid/'},
                                   SimpleNamespace(id='yema', url='https://fixture.invalid/'))
    try:
        result = client.run_page_action(['sign_button'])
        assert result == [['sign_button', 'clicked']]
        content, url = client.page_snapshot()
        assert content == '<html>ok</html>'
        assert seen and {ident for _, ident in seen} == {seen[0][1]}, '动作与快照必须同线程'
        assert seen[0][1] != caller, '页面动作不得在调用方线程执行'
    finally:
        client.close()

    # _open 失败：actor 线程被回收（不泄漏非 daemon 线程）
    before = threading.active_count()

    class BoomSession:
        def __init__(self, **kwargs): raise RuntimeError('browser launch failed')
    monkeypatch.setattr(cloak, 'CloakSession', BoomSession)
    try:
        cloak.CloakHttpClient(SimpleNamespace(cookies={}), {'url': 'https://fixture.invalid/'},
                              SimpleNamespace(id='yema', url='https://fixture.invalid/'))
        raise AssertionError('应当重抛构造异常')
    except RuntimeError as exc:
        assert 'launch failed' in str(exc)
    import time
    deadline = time.time() + 2
    while threading.active_count() > before and time.time() < deadline:
        time.sleep(0.05)
    assert threading.active_count() <= before, '构造失败后 actor 线程应被 shutdown 回收'
