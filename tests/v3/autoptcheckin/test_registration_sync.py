"""4.1.0 完整注册同步：宿主任务集合在任何保存/初始化路径后必须等于当前配置。

宿主 update_plugin_job 语义 = 只追加并替换同 ID 任务（app/application/scheduling.py:238），
cron/interval 模式切换或 interval 槽数变化时旧 ID 残留会继续触发——插件侧统一走
remove_plugin_job + update_plugin_job（_sync_jobs）消除残留。
"""
import asyncio
import sys
import types
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
from autoptcheckin import AutoPtCheckin

CRON = dict(enabled=True, scheduler_enabled=True, cron_mode='cron', cron='15 8 * * *')


def make_host(monkeypatch):
    """fake 宿主任务表：remove 清本插件全部；update 按当前 get_service 追加/同 ID 替换。"""
def make_host(monkeypatch):
    """fake 宿主任务表（忠实 reconcile.py:418-428）：update = 全清后按当前 get_service
    重新注册（live once 保留属宿主内部细节，不属插件契约，不模拟）。"""
    store = {}
    holder = {}
    calls = []

    def remove(pid):
        calls.append('remove')
        store.clear()

    def update(pid):
        calls.append('update')
        store.clear()
        p = holder.get('plugin')
        for svc in (p.get_service() if p else []):
            store[f'{pid}:{svc["id"]}'] = svc
    sdk_mod = types.ModuleType('app.sdk.scheduler')
    sdk_mod.remove_plugin_job = remove
    sdk_mod.update_plugin_job = update
    app_mod = types.ModuleType('app')
    sdk_pkg = types.ModuleType('app.sdk')
    app_mod.sdk = sdk_pkg
    sdk_pkg.scheduler = sdk_mod
    monkeypatch.setitem(sys.modules, 'app', app_mod)
    monkeypatch.setitem(sys.modules, 'app.sdk', sdk_pkg)
    monkeypatch.setitem(sys.modules, 'app.sdk.scheduler', sdk_mod)
    return store, holder, calls


def make_plugin(data=None):
    data = {} if data is None else data
    p = AutoPtCheckin()
    p.get_data = lambda key: deepcopy(data.get(key))
    p.save_data = lambda key, value: data.update({key: deepcopy(value)})
    p.update_config = lambda value: data.update(config=deepcopy(value))
    return p


def test_mode_switch_leaves_no_stale_jobs(monkeypatch):
    """cron→interval 切换后旧 AutoSignIn 不残留（旧行为会继续按 8:15 触发）。"""
    monkeypatch.setattr('autoptcheckin.core.scheduler.random.randint', lambda low, high: high)
    store, holder, _ = make_host(monkeypatch)
    p = make_plugin()
    holder['plugin'] = p
    p.init_plugin(deepcopy(CRON))
    p._sync_jobs()
    assert set(store) == {'AutoPtCheckin:AutoSignIn'}

    p._save_config({**CRON, 'cron_mode': 'interval', 'interval_hours': 2, 'begin_hour': 9, 'end_hour': 11})
    ids = {svc['id'] for svc in store.values()}
    assert 'AutoSignIn' not in ids
    assert ids == {'AutoSignIn.0'}  # max(1,int((11-9)/2))=1 → 仅首槽


def test_interval_shrink_leaves_no_stale_jobs(monkeypatch):
    """interval 槽数变少后多余槽不残留（旧行为 AutoSignIn.3/.4 继续触发）。"""
    monkeypatch.setattr('autoptcheckin.core.scheduler.random.randint', lambda low, high: high)
    store, holder, _ = make_host(monkeypatch)
    p = make_plugin()
    holder['plugin'] = p
    wide = {**CRON, 'cron_mode': 'interval', 'interval_hours': 2, 'begin_hour': 9, 'end_hour': 17}
    p.init_plugin(deepcopy(wide))
    p._sync_jobs()
    assert {svc['id'] for svc in store.values()} == {f'AutoSignIn.{i}' for i in range(4)}

    p._save_config({**wide, 'begin_hour': 9, 'end_hour': 11})
    assert {svc['id'] for svc in store.values()} == {'AutoSignIn.0'}


def test_init_plugin_syncs_jobs(monkeypatch):
    """宿主保存/重载链兜底：init_plugin 完成后宿主任务=当前配置。"""
    store, holder, _ = make_host(monkeypatch)
    p = make_plugin()
    holder['plugin'] = p
    p.init_plugin(deepcopy(CRON))
    p._sync_jobs()
    assert set(store) == {'AutoPtCheckin:AutoSignIn'}

    new_cfg = {**CRON, 'cron': '30 20 * * *'}
    p.init_plugin(deepcopy(new_cfg))  # 宿主 _initialize 后必跟 _refresh_registrations；兜底等价
    p._sync_jobs()
    svc = store['AutoPtCheckin:AutoSignIn']
    assert svc['trigger'].fields[2].expressions == ['30'] or str(svc['trigger']) .find('20') >= 0


    """_sync_jobs 不显式 remove（宿主 update 自带全清+live once 保留），只调 update。"""
    store, holder, calls = make_host(monkeypatch)
    p = make_plugin()
    holder['plugin'] = p
    p.init_plugin(deepcopy(CRON))
    calls.clear()
    p._sync_jobs()
    assert calls == ['update']
    assert set(store) == {'AutoPtCheckin:AutoSignIn'}


def test_init_plugin_auto_syncs_jobs(monkeypatch):
    """关键回归：init_plugin 完成后宿主任务已自动=当前配置（不手动调 _sync_jobs）。"""
    store, holder, calls = make_host(monkeypatch)
    p = make_plugin()
    holder['plugin'] = p
    p.init_plugin(deepcopy(CRON))
    assert set(store) == {'AutoPtCheckin:AutoSignIn'}
    calls.clear()
    p.init_plugin({**CRON, 'cron': '30 20 * * *'})
    svc = store['AutoPtCheckin:AutoSignIn']
    assert calls[-1] == 'update'  # 前置 remove 来自 stop_service 既有语义（非 preserve_round 时清任务）


def test_invalid_cron_rejected_without_side_effects(monkeypatch):
    """非法 cron 拒绝保存：配置不变、宿主任务不变、返回 success=False。"""
    store, holder, _ = make_host(monkeypatch)
    p = make_plugin()
    holder['plugin'] = p
    p.init_plugin(deepcopy(CRON))
    p._sync_jobs()
    before_store = dict(store)
    before_cfg = deepcopy(p._config)

    result = asyncio.run(p.api_save_config({'cron': 'not a cron'}))

    assert result['success'] is False
    assert 'cron' in result['message']
    assert p._config == before_cfg
    assert store == before_store


def test_invalid_interval_rejected(monkeypatch):
    store, holder, _ = make_host(monkeypatch)
    p = make_plugin()
    holder['plugin'] = p
    p.init_plugin(deepcopy(CRON))

    result = asyncio.run(p.api_save_config({'cron_mode': 'interval', 'interval_hours': 0.1}))
    assert result['success'] is False

    result = asyncio.run(p.api_save_config({'cron_mode': 'interval', 'interval_hours': 2, 'begin_hour': 20, 'end_hour': 9}))
    assert result['success'] is False


def test_invalid_mode_rejected(monkeypatch):
    store, holder, _ = make_host(monkeypatch)
    p = make_plugin()
    holder['plugin'] = p
    p.init_plugin(deepcopy(CRON))
    result = asyncio.run(p.api_save_config({'cron_mode': 'weekly'}))
    assert result['success'] is False
