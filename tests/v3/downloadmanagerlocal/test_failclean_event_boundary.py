"""整理失败事件的删除边界反例：媒体库/远端/根目录/缺身份不能绕过保护。"""
import pytest
from test_failclean_scan import fc, _failed_event  # noqa: F401


@pytest.mark.parametrize('kind', ['outside', 'traversal', 'remote', 'root', 'missing_roots'])
def test_transfer_failure_rejects_untrusted_source(fc, tmp_path, kind):
    download = tmp_path / 'downloads'
    download.mkdir()
    source = tmp_path / 'media.mkv'
    source.write_bytes(b'keep')
    fc.dir_state['paths'] = [str(download)]
    event = _failed_event(source)
    if kind == 'traversal':
        event.event_data['fileitem']['path'] = str(download / '..' / source.name)
    elif kind == 'remote':
        event.event_data['fileitem'].update(path=str(download / 'remote.mkv'), storage='aliyundrive')
    elif kind == 'root':
        event.event_data['fileitem']['path'] = str(download)
    elif kind == 'missing_roots':
        fc.dir_state['paths'] = []
    result = fc.build().handle_transfer_failed(event)
    assert result['deleted'] == 0
    assert result['skipped'] is True
    assert source.exists()
    assert fc.recorder.deleted_items == []
    assert fc.recorder.history_deleted == []
    assert fc.recorder.events_sent == []


def test_transfer_failure_without_hash_or_history_never_deletes(fc, tmp_path):
    source = tmp_path / 'unknown.mkv'
    source.write_bytes(b'keep')
    result = fc.build().handle_transfer_failed(_failed_event(source, download_hash=''))
    assert result['skipped'] is True
    assert source.exists()
    assert fc.recorder.deleted_items == []


@pytest.mark.parametrize('protected', [False, True])
def test_missing_event_hash_recovers_history_identity_before_guard(fc, tmp_path, protected):
    source = tmp_path / 'known.mkv'
    source.write_bytes(b'keep')
    fc.history_state['hash'] = 'history-hash'
    fc.guard_state['skip'] = protected
    result = fc.build().handle_transfer_failed(_failed_event(source, download_hash=''))
    assert result['hash'] == 'history-hash'
    assert result['deleted'] == (0 if protected else 1)
    assert source.exists() == protected
