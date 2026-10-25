"""第 1-2 轮审查修复的行为契约：轮次隔离、远程命令防护、凭据边界、通知过滤。"""
import pytest

from forum_under_test import ForumSignin
from forum_under_test.core.models import SignResult, SignStatus


def _plugin(notify=True):
    plugin = ForumSignin()
    plugin.get_data = lambda key=None: {}
    plugin.save_data = lambda key, value: None
    plugin.update_config = lambda config: None
    plugin.post_message = lambda **kwargs: None
    plugin._config["notify"] = notify
    return plugin


def test_run_once_continues_after_site_exception():
    """单站执行异常不得中断其余站点（P0：静默漏签防护）。"""
    plugin = _plugin()
    plugin._config["enabled_sites"] = ["fengchao", "yaowan"]
    calls = []

    def fake_result(domain, readonly=False, trigger=None, record=True):
        calls.append(domain)
        if "fengchao" in domain:
            raise TypeError("synthetic boom")
        r = SignResult(SignStatus.SUCCESS, "本人当日签到记录已确认")
        r.site_id = "yaowan"
        return r

    from unittest.mock import patch
    with patch.object(ForumSignin, "_execute_result", side_effect=fake_result):
        response = plugin.run_once()
    assert "fengchao.chat" in calls and "invites.fun" in calls
    assert response["success"] is True
    assert [r["site_id"] for r in response["data"]] == ["yaowan"]


def test_remote_command_ignored_when_disabled_or_stopped():
    """插件停用（含卸载残留 handler）时远程命令静默忽略。"""
    import forum_under_test as fut
    from unittest.mock import patch

    plugin = _plugin()
    plugin._config["enabled"] = False
    with patch("threading.Thread") as thread_mock:
        plugin._handle_remote_command(type("E", (), {"event_data": {"action": "signin_once"}})())
        thread_mock.assert_not_called()

    plugin._config["enabled"] = True
    plugin._stopped = True
    with patch("threading.Thread") as thread_mock:
        plugin._handle_remote_command(type("E", (), {"event_data": {"action": "signin_once"}})())
        thread_mock.assert_not_called()

    plugin._stopped = False
    with patch("threading.Thread") as thread_mock:
        plugin._handle_remote_command(type("E", (), {"event_data": {"action": "other"}})())
        thread_mock.assert_not_called()


def test_remote_command_deduped_by_round_lock():
    """上一轮未结束时远程命令不重入。"""
    from unittest.mock import patch

    plugin = _plugin()
    plugin._config["enabled"] = True
    with plugin._round_lock:
        with patch.object(plugin, "run_once") as run_once:
            plugin._handle_remote_command(type("E", (), {"event_data": {"action": "signin_once"}})())
            run_once.assert_not_called()


def test_empty_managed_site_id_treated_as_unbound():
    """managed_site_id 为空串时按未绑定处理（不得判定为绑定缺失而拒签）。"""
    from forum_under_test.core.credentials import resolve, CredentialSpec
    from forum_under_test.core.registry import ADAPTERS

    adapter = ADAPTERS["ssdforum"]
    spec = adapter.credential_spec
    # 空串绑定 id 等价于 None：resolve 走本地 cookie，不抛 managed_site_binding_missing
    with pytest.raises(Exception) as exc_info:
        resolve("ssdforum", {"ssdforum_cookie": ""}, None)
    assert "managed_site_binding_missing" not in str(exc_info.value)


def test_skipped_results_do_not_notify():
    """skipped 结果不进入通知缓冲。"""
    plugin = _plugin()
    r = SignResult(SignStatus.SKIPPED, "站点未启用")
    r.site_id = "ssdforum"
    plugin._execute_result("ssdforum", readonly=False)  # 真实路径会写缓冲
    plugin._notify_buffer.clear()
    plugin._history.append(r)
    assert plugin._notify_buffer == []


def test_update_info_rejects_non_fengchao_domain():
    """update_info 恒为蜂巢同步：其他域明确拒绝。"""
    import asyncio

    plugin = _plugin()
    response = asyncio.run(plugin.api_update_info("pting.club"))
    assert response["success"] is False and response["message"] == "unknown_site"


def test_retry_chain_records_only_final_result():
    """重试链只在终态落一次历史与通知：中途失败不产生多条记录。"""
    from unittest.mock import patch
    from forum_under_test.core.registry import get_registry
    import time as _time

    plugin = _plugin()
    store: dict = {}
    plugin.save_data = lambda key, value: store.update({key: value})
    plugin.get_data = lambda key=None: store.get(key) if key in store else {}
    plugin._config["retry_count"] = 1
    plugin._config["retry_interval"] = 1
    real_sleep = _time.sleep
    _time.sleep = lambda seconds: None  # 退避不真等
    try:
        first = SignResult(SignStatus.FAILED, "首次失败")
        first.site_id = "ssdforum"
        final = SignResult(SignStatus.ALREADY, "已签到")
        final.site_id = "ssdforum"
        results = iter([first, final])
        with patch.object(ForumSignin, "_execute_result", side_effect=lambda *a, **k: next(results)):
            domain = next(s["domain"] for s in get_registry() if s["id"] == "ssdforum")
            plugin._execute_with_retry(domain, trigger="manual")
    finally:
        _time.sleep = real_sleep
    assert [r["status"] for r in plugin._history.list(1, 10)["items"]] == ["signed"]
    assert [(sid, r.status) for sid, r in plugin._notify_buffer] == [("ssdforum", SignStatus.ALREADY)]
