import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))

import pytest

def test_run_isolated_works_from_running_loop_thread():
    # qnap 实况等价环境：调用线程正在运行事件循环（宿主调度线程）时同步调用
    # run_isolated——worker 新线程无 running loop，Sync Playwright 可靠启动。
    from autoptcheckin.core.cloak import run_isolated

    async def scenario():
        asyncio.get_running_loop()  # 当前线程确有 running loop
        return run_isolated(lambda: "isolated" if not _running_loop() else "leaked")

    assert asyncio.run(scenario()) == "isolated"


def _running_loop():
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


def test_run_isolated_propagates_result_and_exception():
    from autoptcheckin.core.cloak import run_isolated

    assert run_isolated(lambda: 42) == 42
    with pytest.raises(ValueError, match="synthetic"):
        run_isolated(lambda: (_ for _ in ()).throw(ValueError("synthetic")))


def test_browser_login_launch_error_maps_to_unconfirmed(monkeypatch):
    # browser_login 站：run_isolated 内 launch_context 失败，异常透传后由
    # native 外层归类 UNCONFIRMED（qnap 00:46 mteam 同族路径的 FileList 版）。
    from types import SimpleNamespace
    import unittest.mock as mock

    from autoptcheckin.core import cloak, native
    from autoptcheckin.core.credentials import CredentialSpec
    from autoptcheckin.core.runner import SignRunner

    def broken_launch(**kwargs):
        raise RuntimeError("Playwright Sync API inside the asyncio loop.")

    runner = SignRunner()
    runner.get_data = lambda key: pytest.fail("browser_login 分支不应读 Cookie 表")
    site = SimpleNamespace(id="filelist", url="https://filelist.io/",
                           credential=CredentialSpec(kind="cookie"),
                           browser_login=True)
    with mock.patch.object(cloak, "launch_context", broken_launch):
        result = native.run_native_login(runner, site, {"cookie": "session=synthetic"})
    assert result.status == "unconfirmed"
    assert "浏览器登录核验异常" in result.message


def test_off_loop_wrapped_login_survives_loop_thread(monkeypatch):
    # Anthelion qnap 实况：宿主在带 running loop 的线程调用 run_native_login
    # （@off_loop 包装）→ 自动挪 run_isolated 线程执行，结果正常回传线程边界。
    from types import SimpleNamespace
    from autoptcheckin.core import native
    from autoptcheckin.core.credentials import CredentialSpec
    from autoptcheckin.core.models import LoginPage, LoginResult, LoginStatus
    from autoptcheckin.core.runner import SignRunner
    data = {}
    runner = SignRunner()
    runner.get_data = data.get
    runner.save_data = data.__setitem__
    site = SimpleNamespace(id='fixture', url='https://fixture.invalid/', credential=CredentialSpec(),
                           parse_login=lambda *a, **k: LoginResult(LoginStatus.LOGIN_OK))
    monkeypatch.setattr(native.NativeHttpClient, 'get',
                        lambda self, url: LoginPage('success', url))

    async def scenario():
        asyncio.get_running_loop()  # 当前线程确有 running loop（宿主等价环境）
        return native.run_native_login(runner, site, {'cookie': 'session=managed'})

    assert asyncio.run(scenario()).status == 'login_ok'
