"""插件本地 SQLite 后端（autoptcheckin.db）：records/kv 两表、迁移与标记。"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))

from autoptcheckin.core.history import HistoryStore, IconCacheDB, open_local_db


def test_db_backend_append_list_and_retention(tmp_path):
    now = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
    db = tmp_path / 'autoptcheckin.db'
    store = HistoryStore(db_path=db, clock=lambda: now)
    for days, status in ((15, 'success'), (14, 'success'), (1, 'failed'), (0, 'success')):
        store.append({'time': (now - timedelta(days=days)).isoformat(), 'site': 'fixture', 'status': status})
    # append 顺手清理：15 天前的行已删，14 天边界保留
    assert store.list()['total'] == 3
    assert [item['status'] for item in store.list(page=1, size=2)['items']] == ['success', 'failed']
    assert store.list(page=99)['items'] == []
    store.close()
    # 重开连接数据仍在（持久性）
    reopened = HistoryStore(db_path=db, clock=lambda: now)
    assert reopened.list()['total'] == 3


def test_db_backend_today_counts_and_clear_today(tmp_path):
    now = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
    store = HistoryStore(db_path=tmp_path / 'autoptcheckin.db', clock=lambda: now)
    store.append({'time': (now - timedelta(hours=1)).isoformat(), 'site': 'fixture', 'status': 'success'})
    store.append({'time': (now - timedelta(days=1)).isoformat(), 'site': 'fixture', 'status': 'failed'})
    assert store.today_counts() == dict(success=1, signed=0, failed=0, unconfirmed=0)
    assert store.clear_today() == 1
    assert store.list()['total'] == 1


def test_import_json_skips_expired_and_persists(tmp_path):
    now = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
    db = tmp_path / 'autoptcheckin.db'
    store = HistoryStore(db_path=db, clock=lambda: now)
    legacy = [{'time': (now - timedelta(days=100)).isoformat(), 'site': 'old', 'status': 'success'},
              {'time': (now - timedelta(days=1)).isoformat(), 'site': 'fresh', 'status': 'success'},
              {'time': 'garbage', 'site': 'bad', 'status': 'success'}]
    assert store.import_json(db, legacy) == 1
    assert store.list()['total'] == 1 and store.list()['items'][0]['site'] == 'fresh'


def test_icon_cache_roundtrip_and_migration(tmp_path):
    db = tmp_path / 'autoptcheckin.db'
    icons = IconCacheDB(db)
    icons.put_many({'hdsky': 'data:image/png;base64,AAA', 'vclib': ''})
    assert icons.all() == {'hdsky': 'data:image/png;base64,AAA', 'vclib': ''}
    # 迁移导入覆盖同 key
    assert icons.import_json(db, {'hdsky': 'new'}) == 1
    assert icons.all()['hdsky'] == 'new'
    assert icons.get_flag('migrated:localstore') is None
    icons.set_flag('migrated:localstore')
    assert icons.get_flag('migrated:localstore') == '1'
    # 与 records 表同库互不干扰
    store = HistoryStore(db_path=db, clock=lambda: datetime(2026, 10, 20, tzinfo=timezone.utc))
    store.append({'site': 'fixture', 'status': 'success'})
    assert store.list()['total'] == 1
    assert set(icons.all()) == {'hdsky', 'vclib'}


def test_migrate_local_store_moves_host_keys(tmp_path, monkeypatch):
    """宿主 plugindata 的 history/icon/按日 key → 本地库，源 key 删除，标记置位。"""
    import autoptcheckin as module

    data = {'history.records': [{'time': '2026-10-19T12:00:00+00:00', 'site': 'fixture', 'status': 'success'}],
            'icon.cache': {'hdsky': 'AAA'},
            '7月29日': '[{"site": "legacy"}]', '10月25日': '[{"site": "legacy2"}]'}
    deleted = []
    plugin = module.AutoPtCheckin.__new__(module.AutoPtCheckin)  # 跳过 __init__，手工装配
    plugin.get_data = lambda key: data.get(key)
    plugin.del_data = lambda key: deleted.append(key) or data.pop(key, None)
    plugin.get_data_path = lambda: tmp_path
    from autoptcheckin.core.history import HistoryStore, IconCacheDB
    plugin._history = HistoryStore()
    plugin._icons = IconCacheDB(None)
    plugin._migrate_local_store()
    assert plugin._history.list()['total'] == 1
    assert plugin._icons.all() == {'hdsky': 'AAA'}
    assert 'history.records' in deleted and 'icon.cache' in deleted
    assert 'history.records' not in data and '7月29日' not in data and '10月25日' not in data
    # 标记置位：db 落盘
    assert IconCacheDB(tmp_path / 'autoptcheckin.db').get_flag('migrated:localstore') == '1'
    # 二次调用直接短路（不再删任何 key）
    plugin._migrate_local_store()
    assert deleted.count('history.records') == 1
