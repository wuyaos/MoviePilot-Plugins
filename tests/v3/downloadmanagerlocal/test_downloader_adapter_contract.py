"""公共下载器查询契约与既有字段行为：仅使用离线 fake。"""

import sys
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest


class ReadOnlyInstance:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def get_torrents(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        return self.response

    def __getattr__(self, name):
        # 所有未声明方法（包括删除、暂停、改名、标签和限速）均禁止调用。
        def forbidden(*args, **kwargs):
            raise AssertionError(f"unexpected client call: {name}")
        return forbidden


@pytest.fixture
def modules(mp_stubs):
    prefix = "app.plugins.downloadmanagerlocal."
    previous = {key: value for key, value in sys.modules.items() if key.startswith(prefix)}
    for key in previous:
        sys.modules.pop(key)
    try:
        yield SimpleNamespace(
            adapter=mp_stubs("adapter/downloader.py", "adapter.downloader"),
            fields=mp_stubs("utils/torrent_adapter.py", "utils.torrent_adapter"),
            hr=mp_stubs("modules/hr/scanner.py", "modules.hr.scanner"),
        )
    finally:
        for key in list(sys.modules):
            if key.startswith(prefix):
                sys.modules.pop(key)
        sys.modules.update(previous)


@pytest.mark.parametrize("wrapped", [False, True])
def test_read_torrents_preserves_raw_objects_and_is_readonly(modules, wrapped):
    torrents = [{"hash": "abc"}, SimpleNamespace(hashString="def")]
    instance = ReadOnlyInstance((torrents, False) if wrapped else torrents)
    result = modules.adapter.read_torrents(SimpleNamespace(instance=instance))
    assert result.success is True
    assert result.error == ""
    assert isinstance(result.items, tuple)
    assert all(actual is raw for actual, raw in zip(result.items, torrents))
    assert len(result.items) == 2
    assert instance.calls == [((), {})]
    with pytest.raises(FrozenInstanceError):
        result.success = False


@pytest.mark.parametrize("failed", [True, ["failed-id"], "private detail"])
def test_tuple_failed_discards_partial_items(modules, failed):
    instance = ReadOnlyInstance(([{"hash": "partial"}], failed))
    result = modules.adapter.read_torrents(SimpleNamespace(instance=instance))
    assert result.success is False
    assert result.items == ()
    assert result.error == "下载器查询失败"
    assert len(instance.calls) == 1


@pytest.mark.parametrize("response", [[], ([], False)])
def test_successful_empty_is_not_failure(modules, response):
    result = modules.adapter.read_torrents(SimpleNamespace(instance=ReadOnlyInstance(response)))
    assert result == modules.adapter.TorrentQueryResult(True, ())


@pytest.mark.parametrize("response", [None, (None, False), {}, "unexpected", (1, 2, 3), ({}, False)])
def test_unknown_or_none_response_is_failure_not_success_empty(modules, response):
    result = modules.adapter.read_torrents(SimpleNamespace(instance=ReadOnlyInstance(response)))
    assert result.success is False
    assert result.items == ()
    assert result.error


def test_exception_preserves_ordinary_error_without_retry(modules):
    instance = ReadOnlyInstance(error=RuntimeError("offline"))
    result = modules.adapter.read_torrents(SimpleNamespace(instance=instance))
    assert result == modules.adapter.TorrentQueryResult(False, (), "offline")
    assert len(instance.calls) == 1


@pytest.mark.parametrize("marker", [
    "http://", "https://", "password", "passwd", "token", "authorization",
    "cookie", "api_key", "apikey", "secret", "@",
])
def test_sensitive_exception_is_redacted(modules, marker):
    detail = f"failure {marker.upper()} sensitive-sentinel"
    result = modules.adapter.read_torrents(SimpleNamespace(
        instance=ReadOnlyInstance(error=RuntimeError(detail)),
    ))
    assert result == modules.adapter.TorrentQueryResult(False, (), "下载器查询失败（错误详情已脱敏）")
    assert detail not in result.error
    assert "sensitive-sentinel" not in result.error


@pytest.mark.parametrize("service", [None, SimpleNamespace(), SimpleNamespace(instance=None)])
def test_missing_instance_is_failure(modules, service):
    result = modules.adapter.read_torrents(service)
    assert result.success is False
    assert result.items == ()
    assert result.error == "下载器实例缺失"


def test_ids_none_does_not_pass_ids_keyword(modules):
    instance = ReadOnlyInstance([])
    modules.adapter.read_torrents(SimpleNamespace(instance=instance), ids=None)
    assert instance.calls == [((), {})]


def test_ids_only_queries_requested_values_once(modules):
    instance = ReadOnlyInstance([])
    ids = ("ABC", "def")
    result = modules.adapter.read_torrents(SimpleNamespace(instance=instance), ids=ids)
    assert result.success is True
    assert instance.calls == [((), {"ids": ["ABC", "def"]})]
    assert ids == ("ABC", "def")


def test_empty_ids_does_not_query_all(modules):
    instance = ReadOnlyInstance(error=AssertionError("must not query"))
    result = modules.adapter.read_torrents(SimpleNamespace(instance=instance), ids=[])
    assert result == modules.adapter.TorrentQueryResult(True, ())
    assert instance.calls == []


def test_unsupported_ids_does_not_fall_back_to_full_query(modules):
    class NoIdsInstance(ReadOnlyInstance):
        def get_torrents(self, **kwargs):
            self.calls.append(((), kwargs))
            if kwargs:
                raise TypeError("ids unsupported")
            return []

    instance = NoIdsInstance()
    result = modules.adapter.read_torrents(SimpleNamespace(instance=instance), ids=["abc"])
    assert result == modules.adapter.TorrentQueryResult(False, (), "ids unsupported")
    assert instance.calls == [((), {"ids": ["abc"]})]


@pytest.mark.parametrize("value, expected", [
    (" QBittorrent ", "qbittorrent"), ("\tTransmission\n", "transmission"),
    (None, ""), ("", ""),
])
def test_downloader_type_preserves_scanner_normalization(modules, value, expected):
    service = SimpleNamespace(type=value)
    assert modules.adapter.downloader_type(service) == expected
    assert modules.adapter.downloader_type(service) == modules.hr.downloader_type(service)
    assert modules.adapter.downloader_type(None) == ""


@pytest.mark.parametrize("dl_type, torrent", [
    ("qbittorrent", {"hash": " ABCD ", "name": "sample", "tags": " site, H&R , ,"}),
    ("transmission", SimpleNamespace(hashString=" ABCD ", name="sample", labels=[" site ", "H&R", ""])),
    ("transmission", SimpleNamespace(hash_string=" ABCD ", torrentName="sample", labels=" site,H&R")),
])
def test_existing_hash_name_label_getters_keep_current_values(modules, dl_type, torrent):
    assert modules.fields.normalize_hash(" ABCD ") == "abcd"
    assert modules.fields.get_hash(torrent, dl_type) == "abcd"
    assert modules.fields.get_torrent_name(torrent) == "sample"
    assert modules.fields.get_label(torrent, dl_type) == ["site", "H&R"]


@pytest.mark.parametrize("dl_type, field", [
    ("qbittorrent", "seeding_time"),
    ("transmission", "secondsSeeding"),
    ("transmission", "seconds_seeding"),
])
@pytest.mark.parametrize("value", [None, 0, 123])
def test_existing_hr_cumulative_time_preserves_missing_and_real_zero(modules, dl_type, field, value):
    fields = {"hash": "abc", "hashString": "abc", "completion_on": 100, "doneDate": 100}
    if value is not None:
        fields[field] = value
    torrent = fields if dl_type == "qbittorrent" else SimpleNamespace(**fields)
    snapshot = modules.hr.torrent_snapshot(torrent, "service-name", dl_type, now=1000)
    assert snapshot.downloader_seeding_time == value
    if value is None:
        assert snapshot.downloader_seeding_time is None
    else:
        assert snapshot.downloader_seeding_time is not None
    assert snapshot.seeding_time == 900


@pytest.mark.parametrize("response", [
    [{"hash": "abc"}], ([{"hash": "abc"}], False),
    (({"hash": "abc"},), False), [], ([], False),
])
def test_hr_read_torrents_preserves_list_shape_and_raw_objects(modules, response):
    instance = ReadOnlyInstance(response)
    items, error = modules.hr.read_torrents(SimpleNamespace(instance=instance))
    expected = response[0] if isinstance(response, tuple) else response
    assert isinstance(items, list)
    assert items == list(expected)
    assert all(actual is raw for actual, raw in zip(items, expected))
    assert error == ""
    assert instance.calls == [((), {})]


@pytest.mark.parametrize("response, expected_error", [
    (None, "下载器返回空响应"),
    ((None, False), "下载器返回空响应"),
    (([{"hash": "partial"}], True), "下载器查询失败"),
    ((1, 2, 3), "无法识别的返回结构"),
])
def test_hr_read_torrents_maps_query_failure(modules, response, expected_error):
    instance = ReadOnlyInstance(response)
    assert modules.hr.read_torrents(SimpleNamespace(instance=instance)) == ([], expected_error)
    assert instance.calls == [((), {})]


@pytest.mark.parametrize("detail, expected_error", [
    ("offline", "offline"),
    ("TOKEN sensitive-sentinel", "下载器查询失败（错误详情已脱敏）"),
])
def test_hr_read_torrents_preserves_safe_error_without_retry(modules, detail, expected_error):
    instance = ReadOnlyInstance(error=RuntimeError(detail))
    assert modules.hr.read_torrents(SimpleNamespace(instance=instance)) == ([], expected_error)
    assert len(instance.calls) == 1


@pytest.mark.parametrize("ids, expected_calls", [
    (None, [((), {})]),
    ([], []),
    ([123, "ABC"], [((), {"ids": ["123", "ABC"]})]),
])
def test_hr_read_torrents_normalizes_ids_without_widening_scope(modules, ids, expected_calls):
    instance = ReadOnlyInstance([])
    assert modules.hr.read_torrents(SimpleNamespace(instance=instance), ids=ids) == ([], "")
    assert instance.calls == expected_calls


def test_hr_read_torrents_unsupported_ids_does_not_retry_full_query(modules):
    class NoIdsInstance(ReadOnlyInstance):
        def get_torrents(self):
            return super().get_torrents()

    instance = NoIdsInstance([])
    items, error = modules.hr.read_torrents(SimpleNamespace(instance=instance), ids=["abc"])
    assert items == []
    assert error
    assert instance.calls == []


def test_hr_read_torrents_uses_public_query_and_falls_back_for_empty_error(modules, monkeypatch):
    calls = []

    def query(service, ids=None):
        calls.append((service, ids))
        return modules.adapter.TorrentQueryResult(False, ())

    monkeypatch.setattr(modules.hr, "_query_torrents", query)
    service = SimpleNamespace()
    assert modules.hr.read_torrents(service, ids=[123]) == ([], "下载器查询失败")
    assert calls == [(service, ["123"])]


def test_hr_downloader_type_delegates_to_public_normalization(modules, monkeypatch):
    assert modules.hr.downloader_type(None) == ""
    service = SimpleNamespace(type=" QBittorrent ")
    calls = []

    def normalize(value):
        calls.append(value)
        return "normalized"

    monkeypatch.setattr(modules.hr, "_downloader_type", normalize)
    assert modules.hr.downloader_type(service) == "normalized"
    assert calls == [service]
