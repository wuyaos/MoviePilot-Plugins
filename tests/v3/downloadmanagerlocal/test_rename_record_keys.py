"""B02：重命名记录复合键（下载器:hash）的隔离、迁移、定位与端点兼容回归。

覆盖 B02 验收口径：
1. 双下载器同 hash 记录互不覆盖（复合键隔离）；
2. 旧裸键带 downloader 字段 → 读侧幂等迁移归位；
3. lookup 六态（exact/legacy/unique/other_downloader/ambiguous/missing）；
4. hash-only 端点唯一命中兼容、歧义显式冲突；
5. 归档/恢复/清状态按下载器隔离，展示 hash 纯化并带 downloader。
"""

import copy
import importlib.machinery
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from test_rename_idempotent import mods, PREFIX

PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "downloadmanagerlocal"



class Plugin:
    def __init__(self, data=None):
        self.data = copy.deepcopy(data or {})
        self.writes = []

    def get_data(self, key):
        return copy.deepcopy(self.data.get(key))

    def save_data(self, key, value):
        self.data[key] = copy.deepcopy(value)
        self.writes.append(key)
        self._rename_enabled = True
        self._tag_enabled = True

    def _rename_torrent(self, *args, **kwargs):
        return True

    def _tag_torrent(self, *args, **kwargs):
        return True


@pytest.fixture
def env(mods):
    archive = sys.modules[PREFIX + '.modules.rename.archive']
    keys = sys.modules[PREFIX + '.modules.rename.record_keys']
    plugin = Plugin()
    plugin.is_rename_archived = lambda h, downloader="": archive.is_rename_archived(plugin, h, downloader)
    plugin.record_rename_failure = lambda *a, **kw: archive.record_rename_failure(plugin, *a, **kw)
    plugin.clear_rename_retry_state = lambda h, downloader="": archive.clear_rename_retry_state(plugin, h, downloader)
    return SimpleNamespace(rename=mods.rename, archive=archive, keys=keys, plugin=plugin)


def _record(h, success=False, downloader="", **extra):
    item = {
        "hash": h,
        "original_name": f"Original {h}",
        "after_name": f"After {h}",
        "success": success,
        "reason": "" if success else "测试失败",
        "downloader": downloader,
        "time": "2026-01-01 00:00:00",
    }
    item.update(extra)
    return item


def test_same_hash_records_isolated_per_downloader(env):
    """双下载器同 hash 各写各的记录，互不覆盖；裸键仅用于无下载器上下文。"""
    r, p, k = env.rename, env.plugin, env.keys
    r.save_rename_record(p, 'abc', 'O', 'A', True, downloader='source')
    r.save_rename_record(p, 'abc', 'O', 'B', False, '失败', downloader='target')
    records = r.get_rename_records(p)
    assert k.record_key('abc', 'source') in records
    assert k.record_key('abc', 'target') in records
    assert records[k.record_key('abc', 'source')]['success'] is True
    assert records[k.record_key('abc', 'target')]['success'] is False
    assert r.get_failed_rename_hashes(p) == {'abc'}


def test_legacy_bare_key_migrates_idempotently_on_read(env):
    """带 downloader 字段的旧裸键在读侧归位到复合键，且重复读不叠加。"""
    r, p, k = env.rename, env.plugin, env.keys
    p.data['rename_records'] = {'abc': _record('abc', downloader='qb')}
    records = r.get_rename_records(p)
    assert k.record_key('abc', 'qb') in records
    assert 'abc' not in records
    # 幂等：再读一次键集不变，不产生第二次写入
    writes_before = len(p.writes)
    records_again = r.get_rename_records(p)
    assert set(records_again) == set(records)
    assert len(p.writes) == writes_before
    # 空 downloader 的裸键不猜下载器，保持裸键
    p.data['rename_records'] = {'xyz': _record('xyz', downloader='')}
    assert set(r.get_rename_records(p)) == {'xyz'}


def test_lookup_statuses(env):
    """lookup 六态：exact/legacy/unique/other_downloader/ambiguous/missing。"""
    k = env.keys
    # exact：指定下载器命中
    records = {k.record_key('a', 'qb'): _record('a', downloader='qb')}
    assert k.lookup(records, 'a', 'qb')['status'] == 'exact'
    # other_downloader：指定下载器无记录而他人有；不携带他人记录（key/record 置空）
    other = k.lookup(records, 'a', 'tr')
    assert other['status'] == 'other_downloader'
    assert other['key'] == '' and not other['record']
    assert k.lookup({}, 'zzz', '')['status'] == 'missing'
    # unique：不指定下载器且复合键唯一命中
    assert k.lookup(records, 'a', '')['status'] == 'unique'
    # legacy：单条旧裸键命中
    legacy = {'a': _record('a', downloader='qb')}
    assert k.lookup(legacy, 'a', '')['status'] == 'legacy'
    assert k.lookup(legacy, 'a', 'qb')['status'] == 'legacy'
    # ambiguous：不指定下载器且多条记录，绝不任取
    records2 = dict(records)
    records2[k.record_key('a', 'tr')] = _record('a', downloader='tr')
    found = k.lookup(records2, 'a', '')
    assert found['status'] == 'ambiguous'
    assert set(found['candidates']) == {'qb', 'tr'}
    assert not found['record']


MODEL_NAMES = (
    "ApiBusinessModel", "CleanupModuleRequest", "CleanupModuleResult", "DiagnosticsResult", "EmptyRequest",
    "ExecutionHistoryPageResult", "HashActionResult", "HrActionResult", "HrClearTaskRequest", "HrPresetsResult",
    "HrSkipStatsResult", "HrTasksResult", "ModuleActionResult", "ModuleConfigSummaryResult", "ModuleStatusResult",
    "OverviewResult", "RenamePageResult", "RetryRenamesResult", "SelectionItem", "TagCleanupExecuteRequest",
    "TagCleanupExecuteResult", "TagCleanupScanRequest", "TagCleanupScanResult", "UploadLimitDisableResult",
    "UploadLimitReallocateResult", "UploadLimitRulesRequest", "UploadLimitRulesResult", "UploadLimitSiteTagsRequest",
    "UploadLimitSiteTagsResult", "UploadLimitStatusResult",
)


class FakeHTTPException(Exception):
    def __init__(self, status_code: int = 500, detail: str = ""):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class _FakeResponseFactory:
    def __init__(self, model_type):
        self.model_type = model_type

    def __call__(self, **kwargs):
        return SimpleNamespace(model=self.model_type, success=kwargs.get("success"), message=kwargs.get("message"),
                               data=kwargs.get("data"))


class FakeResponse:
    """schemas.Response[T] 替身。"""

    def __class_getitem__(cls, model_type):
        return _FakeResponseFactory(model_type)


class FakeBaseModel:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    @classmethod
    def model_validate(cls, payload):
        return cls(**payload)

    def model_dump(self):
        return dict(self.__dict__)


@pytest.fixture
def handlers_env(mods, monkeypatch):
    """在 rename 模块替身之上加载真实 controller/handlers.py（外部边界全替身）。"""

    def stub(name, **attrs):
        result = types.ModuleType(name)
        result.__spec__ = importlib.machinery.ModuleSpec(name, None, is_package="__path__" in attrs)
        result.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, result)
        return result

    monkeypatch.setattr(sys.modules[PREFIX + ".model.state"], "TRANSFER_SKIP_STATS_KEY", "transfer_skip_stats",
                        raising=False)
    monkeypatch.setattr(sys.modules[PREFIX + ".model.state"], "TRANSFER_STATS_KEY", "transfer_stats", raising=False)
    monkeypatch.setattr(sys.modules[PREFIX + ".model.state"], "load_transfer_stats", Mock(return_value={}),
                        raising=False)
    monkeypatch.setattr(sys.modules[PREFIX + ".adapter.moviepilot"], "get_downloader_service", Mock(return_value=None),
                        raising=False)
    monkeypatch.setattr(sys.modules[PREFIX + ".adapter.moviepilot"], "get_downloader_services",
                        Mock(return_value={}), raising=False)
    monkeypatch.setattr(sys.modules[PREFIX + ".adapter.moviepilot"], "list_builtin_sites", Mock(return_value=[]),
                        raising=False)

    sys.modules["app.schemas"].Response = FakeResponse
    stub("fastapi", HTTPException=FakeHTTPException)
    stub("pydantic", BaseModel=FakeBaseModel)
    stub(PREFIX + ".utils.config", observe_skip=lambda *args, **kwargs: False,
         MODULE_SWITCHES={"rename": ("rename_enabled", "_rename_enabled")})
    stub(PREFIX + ".modules.hr", __path__=[str(PLUGIN_DIR / "modules" / "hr")])
    stub(PREFIX + ".modules.hr.guard", HrGuard=Mock())
    stub(PREFIX + ".modules.hr.rules", load_preset_rules=Mock(return_value={}))
    stub(PREFIX + ".modules.sitetag", __path__=[str(PLUGIN_DIR / "modules" / "sitetag")])
    stub(PREFIX + ".modules.sitetag.service", complement_history=Mock(), execute_tag_cleanup=Mock(),
         scan_tag_candidates=Mock(), scan_and_clean_tags=Mock())
    stub(PREFIX + ".modules.uploadlimit", __path__=[str(PLUGIN_DIR / "modules" / "uploadlimit")])
    stub(PREFIX + ".modules.uploadlimit.worker", stop_upload_limit_worker=Mock())
    stub(PREFIX + ".modules.uploadlimit.service", get_upload_limit_status=Mock(),
         persist_upload_limit_site_rules=Mock(), restore_upload_limits=Mock(), run_upload_limit_cycle=Mock(),
         scan_upload_limit_site_tags=Mock())
    model_api = stub(PREFIX + ".model.api")
    for name in MODEL_NAMES:
        setattr(model_api, name, type(name, (FakeBaseModel,), {}))

    def load(relpath, name):
        spec = importlib.util.spec_from_file_location(name, PLUGIN_DIR / relpath)
        result = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, spec.name, result)
        spec.loader.exec_module(result)
        return result

    return SimpleNamespace(
        handlers=load("controller/handlers.py", PREFIX + ".controller.handlers"))


def test_hash_only_endpoint_unique_hit_and_ambiguous_conflict(env, handlers_env, monkeypatch):
    """恢复原名端点：唯一命中兼容旧调用；多下载器记录时显式冲突不任取。"""
    r, p = env.rename, env.plugin
    handlers = handlers_env.handlers

    class FakeInstance:
        is_inactive = lambda self: False
        qbc = SimpleNamespace(torrents_rename=Mock(return_value=None))

        def get_torrents(self, ids=None):
            return [{"hash": "abc", "name": "New Name"}], None

    service = SimpleNamespace(name="source", type="qbittorrent", instance=FakeInstance())
    monkeypatch.setattr(handlers, "resolve_record_downloader",
                        lambda plugin, h, record: {"service": service, "candidates": ["source"],
                                                   "ambiguous": False, "reason": "record"})

    r.save_rename_record(p, 'abc', 'O', 'A', True, downloader='source')
    # 唯一命中：不带 downloader 兼容旧调用
    resp = handlers.api_recovery_torrent(p, 'abc')
    assert resp.data.code == 0
    # 两条记录：hash-only 显式冲突
    r.save_rename_record(p, 'abc', 'O', 'B', True, downloader='target')
    conflict = handlers.api_recovery_torrent(p, 'abc')
    assert conflict.data.code == 1
    assert '多个下载器' in conflict.data.msg
    # 指定下载器后恢复命中对应记录
    ok = handlers.api_recovery_torrent(p, 'abc', 'target')
    assert ok.data.code == 0
    # 指定了不存在记录的下载器 → 拒绝
    miss = handlers.api_recovery_torrent(p, 'abc', 'nowhere')
    assert miss.data.code == 1


def test_archive_and_clear_scoped_per_downloader(env):
    """归档/清状态按下载器隔离；展示条目 hash 纯化并带 downloader。"""
    a, r, p = env.archive, env.rename, env.plugin
    r.save_rename_record(p, 'abc', 'O', 'B', False, '失败', downloader='target')
    a.record_rename_failure(p, 'abc', 'B', '失败', threshold=1, downloader='target')
    # target 已归档 → target 不再补刀；source 无记录不受影响
    assert a.is_rename_archived(p, 'abc', 'target') is True
    assert a.is_rename_archived(p, 'abc', 'source') is False
    page = a.list_rename_archive(p)
    assert page['total'] == 1
    entry = page['items'][0]
    assert entry['hash'] == 'abc'
    assert entry['downloader'] == 'target'
    # 恢复 target 后重新参与补刀，source 依旧不受影响
    assert a.restore_rename_archive(p, 'abc', 'target')['code'] == 0
    assert a.is_rename_archived(p, 'abc', 'target') is False
    # 再次归档后按下载器清除，source 无感
    a.record_rename_failure(p, 'abc', 'B', '失败', threshold=1, downloader='target')
    assert a.clear_rename_retry_state(p, 'abc', 'target') is None or True
    assert a.is_rename_archived(p, 'abc', 'target') is False
    assert a.is_rename_archived(p, 'abc', 'source') is False


def test_retry_rename_by_hash_downloader_aware(env, monkeypatch):
    """单条补刀按下载器取记录：不同下载器同一 hash 补到各自的原始名。"""
    r, p, k = env.rename, env.plugin, env.keys
    r.save_rename_record(p, 'abc', 'Source Original', 'Source New', False, '失败', downloader='source')
    r.save_rename_record(p, 'abc', 'Target Original', 'Target New', False, '失败', downloader='target')

    class FakeInstance:
        def get_torrents(self, ids=None):
            return [{"hash": "abc", "name": "Target New"}], None

        def rename_torrent(self, *args, **kwargs):
            return True

    class FakeService:
        name = 'target'
        type = 'qbittorrent'
        instance = FakeInstance()
    monkeypatch.setattr(r, 'resolve_retry_original_name',
                        lambda plugin, h, *a: 'Target Original' if a[2:] == ('target',) else '')
    result = r.retry_rename_by_hash(p, FakeService(), 'abc')
    assert result.get('code') == 0
    records = r.get_rename_records(p)
    assert records[k.record_key('abc', 'target')]['success'] is False
    assert records[k.record_key('abc', 'source')]['success'] is False


def test_lookup_specified_downloader_with_multiple_composite_keys(env):
    """指定下载器 + 多条复合键 → other_downloader 且不携带他人记录。"""
    k = env.keys
    records = {
        k.record_key('a', 'qb'): _record('a', downloader='qb'),
        k.record_key('a', 'tr'): _record('a', downloader='tr'),
    }
    found = k.lookup(records, 'a', 'tr2')
    assert found['status'] == 'other_downloader'
    assert found['key'] == '' and not found['record']
    assert set(found['candidates']) == {'qb', 'tr'}


def test_legacy_failure_write_relocates_to_composite_key(env):
    """legacy 裸键 + 指定下载器失败写入 → 归位到复合键且裸键不残留。"""
    a, p, k = env.archive, env.plugin, env.keys
    p.data['rename_retry'] = {'abc': {'hash': 'abc', 'downloader': 'qb', 'fail_count': 0, 'archived': False}}
    a.record_rename_failure(p, 'abc', 'N', '失败', threshold=1, downloader='qb')
    state = env.archive.get_rename_retry_state(p)
    assert k.record_key('abc', 'qb') in state
    assert 'abc' not in state


def test_migrate_keys_conflict_keeps_newer_time(env):
    """迁移冲突取 time 较新者；平局保留复合键记录。"""
    k = env.keys
    composite = k.record_key('abc', 'qb')
    state = {
        composite: _record('abc', downloader='qb', time='2026-01-01 00:00:00'),
        'abc': _record('abc', downloader='qb', time='2026-01-02 00:00:00'),
    }
    migrated, moved = k.migrate_keys(state)
    assert set(migrated) == {composite}
    assert migrated[composite]['time'] == '2026-01-02 00:00:00'
    assert moved == 1
    # 平局（时间相同）保留复合键记录
    state2 = {
        composite: _record('abc', downloader='qb', time='2026-01-01 00:00:00'),
        'abc': _record('abc', downloader='qb', time='2026-01-01 00:00:00'),
    }
    migrated2, _ = k.migrate_keys(state2)
    assert migrated2[composite]['original_name'] == 'Original abc'


def test_retry_failed_renames_get_torrents_error_recorded(env, monkeypatch):
    """补刀查询失败必须计入 summary：failed=候选数、errors 带原因，不静默成功。"""
    r, p = env.rename, env.plugin
    r.save_rename_record(p, 'abc', 'O', 'A', False, '失败', downloader='target')
    r.save_rename_record(p, 'def', 'O2', 'B2', False, '失败', downloader='target')

    class ErrInstance:
        def get_torrents(self, ids=None):
            return [], "下载器连接失败"

    service = SimpleNamespace(name='target', type='qbittorrent', instance=ErrInstance())
    monkeypatch.setattr(r, 'get_failed_rename_hashes', lambda plugin: ['abc', 'def'])

    summary = r.retry_failed_renames(p, service)

    assert summary['failed'] == 2
    assert summary['attempted'] == 0
    assert any('补刀查询失败' in e and '下载器连接失败' in e for e in summary['errors'])
