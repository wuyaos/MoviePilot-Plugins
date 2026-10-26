"""S7 真实 APScheduler Trigger + 离线宿主边界，不访问站点。"""
import asyncio
import threading
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import sys
import types

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
from autoptcheckin import AutoPtCheckin
from autoptcheckin.core.scheduler import Scheduler


BASE = dict(enabled=True, scheduler_enabled=True, cron_mode='interval', interval_hours=2, begin_hour=9, end_hour=23)


def plugin(config, data=None):
    data = {} if data is None else data
    p = AutoPtCheckin()
    p.get_data = lambda key: deepcopy(data.get(key))
    p.save_data = lambda key, value: data.update({key: deepcopy(value)})
    p.update_config = lambda value: data.update(config=deepcopy(value))
    p.init_plugin(config)
    return p


def test_cron_and_next_schedule():
    p = plugin({**BASE, 'cron_mode': 'cron', 'cron': '15 8 * * *'})
    services = p.get_service()
    assert [(s['id'], s['name']) for s in services] == [('AutoSignIn', 'PT 签到中心')]
    next_time = datetime.fromisoformat(asyncio.run(p.api_stats())['data']['next_schedule'])
    assert (next_time.hour, next_time.minute) == (8, 15)
    assert p.get_service() == services


@pytest.mark.parametrize('interval,expected', [(2, 7), (0.5, 28), (3, 4)])
def test_interval_expansion_and_persistence(monkeypatch, interval, expected):
    monkeypatch.setattr('autoptcheckin.core.scheduler.random.randint', lambda low, high: high)
    data = {}
    config = {**BASE, 'interval_hours': interval}
    p = plugin(config, data)
    services = p.get_service()
    assert len(services) == expected
    assert [s['id'] for s in services] == [f'AutoSignIn.{i}' for i in range(expected)]
    assert services[0]['name'].endswith('09:00')  # 首槽固定为开始时间（BASE begin=9）
    assert data['schedule_crons'][0] == '0 9 * * *'
    assert data['schedule_signature'].endswith(':v2')
    crons = deepcopy(data['schedule_crons'])
    monkeypatch.setattr('autoptcheckin.core.scheduler.random.randint', lambda *args: pytest.fail('reload randomized'))
    p.init_plugin(config)
    assert len(p.get_service()) == expected
    assert data['schedule_crons'] == crons
    assert len(plugin(config, data).get_service()) == expected


def test_changed_signature_rearranges(monkeypatch):
    calls = []
    monkeypatch.setattr('autoptcheckin.core.scheduler.random.randint', lambda low, high: calls.append(high) or high)
    data = {}
    p = plugin(BASE, data)
    p.get_service()
    old = data['schedule_signature']
    calls.clear()
    p.init_plugin({**BASE, 'begin_hour': 10})
    p.get_service()
    assert calls and data['schedule_signature'] != old


@pytest.mark.parametrize('config', [{}, {'enabled': True}, {'scheduler_enabled': True}])
def test_activation_gate(config):
    p = plugin(config)
    assert p.get_service() == []
    stats = asyncio.run(p.api_stats())['data']
    assert stats['next_schedule'] is None
    if not config.get('scheduler_enabled'):
        assert 'scheduler_disabled' in stats['schedule_status']


def test_config_save_preserves_existing_round_cancellation():
    p = plugin({'enabled': True})
    p._round_active = True
    p._runner.stop.set()
    p._save_config({'notify': False, 'onlyonce': True})
    assert p._runner.stop.is_set()
    assert 'onlyonce' not in p._config
    p._round_active = False


def test_scheduler_flag_does_not_enable_plugin_state():
    p = plugin({'enabled': False, 'scheduler_enabled': True, 'onlyonce': True})
    assert p.get_state() is False
    assert p.get_service() == []


def test_manual_round_reserves_before_thread_start(monkeypatch):
    p = plugin({'enabled': False, 'scheduler_enabled': False})
    pending, calls = [], []
    class DeferredThread:
        def __init__(self, target, **kwargs):
            pending.append(target)
        def start(self):
            pass
    monkeypatch.setattr(threading, 'Thread', DeferredThread)
    p._execute_all_round = lambda trigger: calls.append(trigger)
    assert asyncio.run(p.api_run_once())['success']
    assert not asyncio.run(p.api_run_once())['success']
    assert p._round_active is True
    p._save_config({"notify": False})
    assert not p._runner.stop.is_set()
    assert p._execute_all('scheduler') is None
    assert calls == []
    pending.pop()()
    assert calls == ['manual']
    assert not p._round_lock.locked()


def test_manual_thread_start_failure_releases_lock(monkeypatch):
    p = plugin({})
    class BrokenThread:
        def __init__(self, **kwargs):
            pass
        def start(self):
            raise RuntimeError('thread unavailable')
    monkeypatch.setattr(threading, 'Thread', BrokenThread)
    with pytest.raises(RuntimeError, match='thread unavailable'):
        asyncio.run(p.api_run_once())
    assert not p._round_lock.locked()


def test_immediate_run_is_not_registered():
    p = plugin({'enabled': True, 'onlyonce': True})
    assert p.get_service() == []
    assert "onlyonce" not in p._config
    assert all('once' not in service['id'] for service in p.get_service())


def test_manual_execution_does_not_use_onlyonce(monkeypatch):
    p = plugin({'enabled': True})
    calls = []
    p._execute_all_round = lambda trigger: calls.append(trigger)
    class InlineThread:
        def __init__(self, target, **kwargs):
            self.target = target
        def start(self):
            self.target()
    monkeypatch.setattr(threading, 'Thread', InlineThread)
    result = asyncio.run(p.api_run_once())
    assert result['success'] is True
    assert calls == ['manual']
    assert 'onlyonce' not in p._config
    assert not p._round_lock.locked()


def test_scheduler_and_manual_history_sources():
    p = plugin({**BASE, 'enabled_sites': ['hdsky'], 'sign_sites': ['hdsky']})
    p.get_service()[0]['func']()
    p._execute_all()  # 批次已在后台线程（API 只返回 started）；trigger 语义直接验证
    records = asyncio.run(p.api_history())['data']['items']
    assert {row['trigger'] for row in records} == {'scheduler', 'manual'}
    assert records and {row['trigger'] for row in records} == {'scheduler', 'manual'}


def test_stop_and_config_reregistration(monkeypatch):
    calls = []
    sdk = types.ModuleType('app.sdk.scheduler')
    sdk.remove_plugin_job = lambda pid: calls.append(('remove', pid))
    sdk.update_plugin_job = lambda pid: calls.append(('update', pid))
    monkeypatch.setitem(sys.modules, 'app.sdk.scheduler', sdk)
    p = plugin(BASE)
    p.get_service()
    p.stop_service()
    # 3.38 修复：stop 不再抑制注册（宿主 stop_service 置位 stop 会让 get_service
    # 永久返回空 → 服务被移除且无调度器清除 stop 的死锁）；stop 只中断在途执行。
    assert len(p.get_service()) == 7 and p._runner.stop.is_set()  # 首槽=09:00 + 6 随机槽
    p._save_config({**BASE, 'cron_mode': 'cron', 'cron': '0 9 * * *'})
    assert calls[-2:] == [('remove', 'AutoPtCheckin'), ('update', 'AutoPtCheckin')]
    assert [s['id'] for s in p.get_service()] == ['AutoSignIn']


@pytest.mark.parametrize('overrides', [{'cron_mode': 'cron', 'cron': 'bad'}, {'interval_hours': 0}, {'begin_hour': 23}, {'end_hour': 25}, {'interval_hours': 'nan'}])
def test_invalid_schedule_is_not_registered(overrides):
    p = plugin({**BASE, **overrides})
    assert p.get_service() == []
    # 4.1.0 起 init_plugin 拒绝应用非法调度配置（保留现有配置），不再进入 invalid_schedule 无任务态
    assert asyncio.run(p.api_stats())['data']['schedule_status'] != 'invalid_schedule'
    assert p.get_service() == []




def test_scheduler_runner_records_trigger_without_cookie(monkeypatch):
    monkeypatch.setattr('autoptcheckin.managed_site', lambda sid: {})
    p = plugin({**BASE, 'enabled_sites': ['hdsky'], 'sign_sites': ['hdsky']})
    p.get_service()[0]['func']()
    record = asyncio.run(p.api_history())['data']['items'][0]
    assert record['status'] == 'failed' and record['reason'] == 'auth_failed'
    assert record['trigger'] == 'scheduler'


def test_saving_config_during_running_round_does_not_cancel_it(monkeypatch):
    sdk = types.ModuleType('app.sdk.scheduler')
    sdk.remove_plugin_job = lambda pid: None
    sdk.update_plugin_job = lambda pid: None
    monkeypatch.setitem(sys.modules, 'app.sdk.scheduler', sdk)
    p = plugin(BASE)
    p._round_active = True
    p._runner.stop.clear()
    p._save_config({**BASE, 'cron_mode': 'cron', 'cron': '0 10 * * *'})
    assert p._runner.stop.is_set() is False
    assert p._running is True


@pytest.mark.parametrize('save_path', ['init', 'save'])
def test_disable_cancels_reserved_round(monkeypatch, save_path):
    p = plugin({**BASE, 'enabled_sites': ['btschool'], 'sign_sites': ['btschool']})
    pending, calls = [], []
    class DeferredThread:
        def __init__(self, target, **kwargs):
            pending.append(target)
        def start(self):
            pass
    monkeypatch.setattr(threading, 'Thread', DeferredThread)
    p._run_with_retry = lambda *a, **kw: calls.append(a)
    assert asyncio.run(p.api_run_once())['success']
    if save_path == 'init':
        p.init_plugin({**p._config, 'enabled': False})
    else:
        p._save_config({'enabled': False})
    assert p._runner.stop.is_set()
    pending.pop()()
    assert calls == []
    assert not p._round_active and not p._round_lock.locked()


def test_cancellation_during_config_write_is_not_cleared():
    p = plugin(BASE)
    p._round_active = True
    p.update_config = lambda config: p.stop_service()
    p._save_config({'notify': False})
    assert p._runner.stop.is_set()


def test_stopped_manual_request_rejected_without_clearing_cancel():
    p = plugin(BASE)
    p.stop_service()
    result = asyncio.run(p.api_run_once())
    assert result['success'] is False
    assert '停止' in result['message']
    assert p._runner.stop.is_set()
    assert not p._round_lock.locked()
