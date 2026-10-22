"""S7 真实 APScheduler Trigger + 离线宿主边界，不访问站点。"""
import asyncio
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
    assert services[0]['name'].endswith(f'{9 + int(interval):02d}:{int(interval % 1 * 60):02d}')
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


def test_onlyonce_triggers_without_scheduler_gate():
    p = plugin({'enabled': True, 'onlyonce': True})
    once = p.get_service()
    assert len(once) == 1 and 'once' in once[0]['id']

def test_once_executes_without_scheduler_enabled():
    data = {}
    p = plugin({'enabled': True, 'onlyonce': True}, data)
    calls = []
    p._execute_all = lambda trigger: calls.append((trigger, data['config']['onlyonce']))
    services = p.get_service()
    assert [s['id'] for s in services] == ['AutoSignIn.once']
    services[0]['func']()
    assert calls == [('scheduler', False)]
    assert data['config']['onlyonce'] is False
def test_once_consumed_before_execution_and_reload():
    data = {}
    p = plugin({**BASE, 'enabled': False, 'onlyonce': True}, data)
    calls = []
    p._execute_all = lambda trigger: calls.append((trigger, data['config']['onlyonce']))
    services = p.get_service()
    assert [s['id'] for s in services] == ['AutoSignIn.once']
    assert p.get_state() is True
    assert p._next_schedule() is not None
    services[0]['func']()
    services[0]['func']()
    assert calls == [('scheduler', False)]
    assert p.get_state() is False
    assert p._next_schedule() is None
    p.init_plugin(data['config'])
    assert p.get_service() == []


def test_scheduler_and_manual_history_sources():
    p = plugin({**BASE, 'enabled_sites': ['nonpilot']})
    p.get_service()[0]['func']()
    p._execute_all()  # 批次已在后台线程（API 只返回 started）；trigger 语义直接验证
    records = asyncio.run(p.api_history())['data']['items']
    assert {row['trigger'] for row in records} == {'scheduler', 'manual'}
    assert all(row['status'] == 'skipped' for row in records)


def test_stop_and_config_reregistration(monkeypatch):
    calls = []
    sdk = types.ModuleType('app.sdk.scheduler')
    sdk.remove_plugin_job = lambda pid: calls.append(('remove', pid))
    sdk.update_plugin_job = lambda pid: calls.append(('update', pid))
    monkeypatch.setitem(sys.modules, 'app.sdk.scheduler', sdk)
    p = plugin(BASE)
    p.get_service()
    p.stop_service()
    assert p.get_service() == [] and p._next_schedule() is None
    assert p._runner.stop.is_set()
    p._save_config({**BASE, 'cron_mode': 'cron', 'cron': '0 9 * * *'})
    assert calls[-2:] == [('remove', 'AutoPtCheckin'), ('update', 'AutoPtCheckin')]
    assert [s['id'] for s in p.get_service()] == ['AutoSignIn']


@pytest.mark.parametrize('overrides', [{'cron_mode': 'cron', 'cron': 'bad'}, {'interval_hours': 0}, {'begin_hour': 23}, {'end_hour': 24}, {'interval_hours': 'nan'}])
def test_invalid_schedule_is_not_registered(overrides):
    p = plugin({**BASE, **overrides})
    assert p.get_service() == []
    assert asyncio.run(p.api_stats())['data']['schedule_status'] == 'invalid_schedule'


def test_host_timezone_once():
    scheduler = Scheduler(timezone='Asia/Shanghai')
    services = scheduler.build({'scheduler_enabled': True, 'onlyonce': True}, lambda: None)
    assert str(services[0]['trigger'].run_date.tzinfo) == 'Asia/Shanghai'


def test_scheduler_pilot_runner_records_trigger_without_cookie(monkeypatch):
    monkeypatch.setattr('autoptcheckin.managed_site', lambda sid: {})
    p = plugin({**BASE, 'enabled_sites': ['hdsky'], 'sign_sites': ['hdsky']})
    p.get_service()[0]['func']()
    record = asyncio.run(p.api_history())['data']['items'][0]
    assert record['status'] == 'auth_failed'
    assert record['trigger'] == 'scheduler'
