"""路径修复反例：真实检测/事务代码，下载器与 /proc 现场为隔离替身。"""
import copy
import importlib.util
import sys
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from test_transfer_pipeline import runtime, SERVICE, PREFIX


@pytest.fixture
def paths(runtime, monkeypatch, tmp_path):
    r = runtime
    spec = importlib.util.spec_from_file_location(PREFIX + '.path_repair', SERVICE / 'path_repair.py')
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, mod)
    spec.loader.exec_module(mod)
    r.paths = mod
    r.hash = 'a' * 40
    r.old = 'Album\u200e'
    r.new = 'Album'
    r.root = tmp_path
    (tmp_path / 'data' / r.new).mkdir(parents=True)
    (tmp_path / 'data' / r.new / 'track.flac').write_bytes(b'abc')
    r.source.get_torrents.return_value = ([{'hash': r.hash, 'progress': 1, 'save_path': '/data'}], None)
    r.services['target'].type = 'transmission'
    r.snapshot = {'hash': r.hash, 'download_dir': '/data', 'status': 'stopped', 'percent_done': 0, 'error': 0}
    r.target.get_torrents.side_effect = lambda **kw: ([copy.deepcopy(r.snapshot)], None)
    r.source.qbc.torrents_files.return_value = [{'index': 0, 'name': f'{r.new}/track.flac', 'size': 3}]
    r.tr_files = {0: {'name': f'{r.old}/track.flac', 'size': 3}}
    r.target.trc.get_torrent.return_value = SimpleNamespace(hashString=r.hash, get_files=lambda: copy.deepcopy(r.tr_files))
    r.target.trc.get_session.return_value = SimpleNamespace(incomplete_dir_enabled=False)
    r.target.trc._url = 'http://127.0.0.1:9091/transmission/rpc'
    r.item = {'source': 'transfer', 'source_downloader': 'source', 'source_hash': r.hash,
              'downloader': 'target', 'hash': r.hash, 'phase': 'verifying', 'created_at': time.time(),
              'delete_source_requested': True, 'skipverify': True, 'target_added': True}
    r.plugin._transfer_path_detect_enabled = True
    r.plugin._transfer_path_auto_repair = False
    r.real_process_root = mod._process_root
    monkeypatch.setattr(mod, '_process_root', lambda client: tmp_path)
    monkeypatch.setattr(r.recheck, 'ensure_seed_recheck_worker', Mock())
    def rename(torrent_hash, old, new):
        assert torrent_hash == r.hash and old == r.old and new == r.new
        # Transmission 原路径缺失：只改内部路径，不触碰真实测试文件。
        for f in r.tr_files.values():
            f['name'] = new + f['name'][len(old):]
    r.target.trc.rename_torrent_path.side_effect = rename
    return r


def test_detect_u200e_by_index_without_writes(paths):
    r = paths
    d = r.paths.diagnose(r.plugin, r.item)
    assert d['state'] == 'mismatch' and d['repairable']
    assert d['differences'][0]['target'] == 'Album\u200e/track.flac'
    assert r.paths.detect_automatic(r.plugin, r.item)
    r.target.trc.rename_torrent_path.assert_not_called()
    r.target.recheck_torrents.assert_not_called()
    r.source.delete_torrents.assert_not_called()


@pytest.mark.parametrize('change,reason', [
    ('old', '原路径'), ('part', '.part'), ('running', '暂停'),
    ('incomplete', '源任务'), ('indices', '索引'), ('size', '大小'),
    ('internal', '内部相对路径'), ('incomplete_dir', '未完成目录'),
])
def test_refuse_unsafe_candidates(paths, change, reason):
    r = paths
    if change == 'old':
        (r.root / 'data' / r.old).mkdir()
    elif change == 'part':
        (r.root / 'data' / (r.old + '.part')).write_bytes(b'x')
    elif change == 'running':
        r.snapshot['status'] = 'downloading'
    elif change == 'incomplete':
        r.source.get_torrents.return_value[0][0]['progress'] = 0.9
    elif change == 'indices':
        r.source.qbc.torrents_files.return_value[0]['index'] = 1
    elif change == 'size':
        r.tr_files[0]['size'] = 4
    elif change == 'internal':
        r.tr_files[0]['name'] = r.old + '/different.flac'
    elif change == 'incomplete_dir':
        r.target.trc.get_session.return_value.incomplete_dir_enabled = True
    d = r.paths.diagnose(r.plugin, r.item)
    assert not d['repairable'] and reason in d['reason']
    r.target.trc.rename_torrent_path.assert_not_called()


def test_remote_namespace_refused_without_credentials_in_message(paths, monkeypatch):
    r = paths
    r.target.trc._url = 'http://secret:password@192.0.2.1:9091/transmission/rpc'
    monkeypatch.setattr(r.paths.socket, 'getaddrinfo', lambda *a, **kw: [(2, 1, 6, '', ('192.0.2.1', 9091))])
    monkeypatch.setattr(r.paths, '_process_root', r.real_process_root)
    d = r.paths.diagnose(r.plugin, r.item)
    assert not d['repairable'] and '远端' in d['reason']
    assert 'password' not in str(d) and 'secret' not in str(d)


@pytest.mark.parametrize('name', ['/abs', '../x', 'a/../b', 'a//b', 'a\\b', 'a/./b', 'a\x00b'])
def test_traversal_rejected(paths, name):
    with pytest.raises(paths.paths.PathRepairBlocked):
        paths.paths.safe_relative(name)


def test_symlink_rejected(paths):
    r = paths
    candidate = r.root / 'data' / r.new / 'track.flac'
    candidate.unlink()
    try:
        candidate.symlink_to(r.root / 'outside')
    except OSError:
        pytest.skip('当前 Windows 账号无创建 symlink 权限')
    assert not r.paths.diagnose(r.plugin, r.item)['repairable']


def test_stale_token_stopped_and_observe_never_write(paths, monkeypatch):
    r = paths
    d = r.paths.diagnose(r.plugin, r.item)
    with pytest.raises(r.paths.PathRepairBlocked):
        r.paths.repair(r.plugin, r.item, 'wrong-token')
    r.plugin._event.set()
    with pytest.raises(r.paths.PathRepairBlocked):
        r.paths.repair(r.plugin, r.item, d['token'])
    r.plugin._event.clear()
    config = sys.modules['app.plugins.downloadmanagerlocal.utils.config']
    monkeypatch.setattr(config, 'observe_only', lambda *args: True)
    with pytest.raises(r.paths.PathRepairBlocked):
        r.paths.repair(r.plugin, r.item, d['token'])
    r.target.trc.rename_torrent_path.assert_not_called()
    assert not r.data


def test_manual_repair_persists_isolated_phase_rechecks_and_retains_source(paths):
    r = paths
    before = (r.root / 'data' / r.new / 'track.flac').stat()
    d = r.paths.diagnose(r.plugin, r.item)
    assert r.paths.repair(r.plugin, r.item, d['token'])['code'] == 0
    assert r.item['phase'] == 'path_repair_verifying' and not r.item['skipverify']
    r.target.recheck_torrents.assert_called_once_with(ids=[r.hash])
    # 用真实队列续办：不完整不能恢复/删源，完整后也只记校验通过、保留源。
    r.recheck.process_seed_recheck_once(r.plugin, {})
    r.source.delete_torrents.assert_not_called()
    r.target.delete_torrents.assert_not_called()
    r.target.start_torrents.assert_not_called()
    r.snapshot['status'] = 'checking'
    r.recheck.process_seed_recheck_once(r.plugin, {})
    r.snapshot.update(status='stopped', percent_done=1)
    r.recheck.process_seed_recheck_once(r.plugin, {})
    record = r.data[f'source-{r.hash}']
    assert record['path_repair_status'] == 'verified' and not record['delete_source']
    assert not r.recheck.load_seed_recheck_queue(r.plugin)
    after = (r.root / 'data' / r.new / 'track.flac').stat()
    assert before.st_size == after.st_size and before.st_mtime_ns == after.st_mtime_ns
    assert (r.root / 'data' / r.new / 'track.flac').read_bytes() == b'abc'
    r.source.delete_torrents.assert_not_called()
    r.target.delete_torrents.assert_not_called()
    r.target.start_torrents.assert_not_called()


def test_failed_rpc_and_restart_never_roll_back_or_delete(paths):
    r = paths
    d = r.paths.diagnose(r.plugin, r.item)
    r.target.trc.rename_torrent_path.side_effect = RuntimeError('password=secret')
    with pytest.raises(r.paths.PathRepairBlocked, match='保留源与目标'):
        r.paths.repair(r.plugin, r.item, d['token'])
    assert r.item['path_repair_status'] == 'blocked'
    assert 'secret' not in str(r.data)
    r.recheck.process_seed_recheck_once(r.plugin, {})
    r.target.recheck_torrents.assert_not_called()
    r.source.delete_torrents.assert_not_called()
    r.target.delete_torrents.assert_not_called()


def test_automatic_mismatch_prevents_timeout_rollback(paths):
    r = paths
    r.item['created_at'] = 0
    r.pipeline.save_transaction(r.plugin, r.item)
    r.recheck.process_seed_recheck_once(r.plugin, {})
    assert r.data[f'source-{r.hash}']['source_result'] == 'path_mismatch'
    r.target.delete_torrents.assert_not_called()
    r.source.delete_torrents.assert_not_called()
    r.target.trc.rename_torrent_path.assert_not_called()


def test_auto_repair_explicitly_enabled_uses_same_gate(paths):
    r = paths
    r.plugin._transfer_path_auto_repair = True
    assert r.paths.detect_automatic(r.plugin, r.item)
    r.target.trc.rename_torrent_path.assert_called_once()
    assert r.item['phase'] == 'path_repair_verifying'
    r.source.delete_torrents.assert_not_called()
