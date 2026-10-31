"""自动删种 scanner 委托公共只读适配层：只读查询、失败语义与类型归一口径。"""

import sys
from types import SimpleNamespace

import pytest


class ReadOnlyInstance:
    """只允许 get_torrents 的下载器客户端假实现，记录调用参数。"""

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
            scanner=mp_stubs("modules/autoremove/scanner.py", "modules.autoremove.scanner"),
        )
    finally:
        for key in list(sys.modules):
            if key.startswith(prefix):
                sys.modules.pop(key)
        sys.modules.update(previous)


# --- 成功路径：保持 list 形态与原始对象身份，全量查询不传 ids ---


@pytest.mark.parametrize(
    "response",
    [
        [{"hash": "abc"}],
        ([{"hash": "abc"}], False),
    ],
)
def test_read_torrents_preserves_list_shape_and_raw_objects(modules, response):
    instance = ReadOnlyInstance(response)
    items, error = modules.scanner.read_torrents(instance)
    expected = response[0] if isinstance(response, tuple) else response
    assert isinstance(items, list)
    assert items == list(expected)
    assert all(actual is raw for actual, raw in zip(items, expected))
    assert error == ""
    # 全量查询：ids=None 时公共层调用 instance.get_torrents() 不传 ids 参数。
    assert instance.calls == [((), {})]


def test_read_torrents_wraps_instance_and_queries_full_scope(modules, monkeypatch):
    captured = {}

    def query(service, ids=None):
        captured["service"] = service
        captured["ids"] = ids
        return modules.adapter.TorrentQueryResult(True, ("a",))

    monkeypatch.setattr(modules.scanner, "_query_torrents", query)
    instance = ReadOnlyInstance([])
    assert modules.scanner.read_torrents(instance) == (["a"], "")
    assert captured["ids"] is None
    assert captured["service"].instance is instance


# --- 失败路径：委托适配层语义，None / 非 list 不再当成功空 ---


@pytest.mark.parametrize(
    "response, expected_error",
    [
        (None, "下载器返回空响应"),
        ((None, False), "下载器返回空响应"),
        ({"unexpected": "dict"}, "无法识别的返回结构"),
        ("unexpected", "无法识别的返回结构"),
        (([{"hash": "partial"}], True), "下载器查询失败"),
    ],
)
def test_read_torrents_maps_query_failure(modules, response, expected_error):
    instance = ReadOnlyInstance(response)
    assert modules.scanner.read_torrents(instance) == ([], expected_error)
    assert instance.calls == [((), {})]


@pytest.mark.parametrize(
    "detail, expected_error",
    [
        ("offline", "offline"),
        ("TOKEN sensitive-sentinel", "下载器查询失败（错误详情已脱敏）"),
    ],
)
def test_read_torrents_preserves_safe_error_without_retry(modules, detail, expected_error):
    instance = ReadOnlyInstance(error=RuntimeError(detail))
    assert modules.scanner.read_torrents(instance) == ([], expected_error)
    assert len(instance.calls) == 1


def test_read_torrents_falls_back_when_adapter_error_empty(modules, monkeypatch):
    def query(service, ids=None):
        return modules.adapter.TorrentQueryResult(False, ())

    monkeypatch.setattr(modules.scanner, "_query_torrents", query)
    assert modules.scanner.read_torrents(ReadOnlyInstance([])) == ([], "下载器查询失败")


# --- downloader_type 委托公共层归一口径 ---


@pytest.mark.parametrize(
    "value, expected",
    [
        (" QBittorrent ", "qbittorrent"),
        ("\tTransmission\n", "transmission"),
        (None, ""),
        ("", ""),
    ],
)
def test_downloader_type_preserves_scanner_normalization(modules, value, expected):
    assert modules.scanner.downloader_type(SimpleNamespace(type=value)) == expected
    assert modules.scanner.downloader_type(None) == ""


def test_downloader_type_delegates_to_public_normalization(modules, monkeypatch):
    service = SimpleNamespace(type=" QBittorrent ")
    calls = []

    def normalize(value):
        calls.append(value)
        return "normalized"

    monkeypatch.setattr(modules.scanner, "_downloader_type", normalize)
    assert modules.scanner.downloader_type(service) == "normalized"
    assert calls == [service]
