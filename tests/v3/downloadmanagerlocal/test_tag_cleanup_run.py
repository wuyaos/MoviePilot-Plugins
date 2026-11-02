"""run_tag_cleanup 编排契约：只读预筛 + 复查复用 + 错误合并 + 触发来源。"""
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3] / "plugins.v3" / "downloadmanagerlocal"
PREFIX = "app.plugins.downloadmanagerlocal"


@pytest.fixture
def tag_service(mp_stubs, monkeypatch):
    adapter = types.ModuleType(PREFIX + ".adapter.moviepilot")
    adapter.generate_random_tag = lambda length=10: "x"
    adapter.get_site_indexer = lambda domain: None
    adapter.get_url_domain = lambda value: ""
    adapter.list_site_dicts = lambda: []
    monkeypatch.setitem(sys.modules, adapter.__name__, adapter)
    state = types.ModuleType(PREFIX + ".model.state")
    state.SITE_TAG_STATUS_KEY = "sitetag_status"
    state.TAG_CLEANUP_STATUS_KEY = "tag_cleanup_status"
    monkeypatch.setitem(sys.modules, state.__name__, state)
    config = types.ModuleType(PREFIX + ".utils.config")
    config.observe_skip = lambda *args: False
    monkeypatch.setitem(sys.modules, config.__name__, config)
    load = mp_stubs("utils/tag_cleanup.py", "utils.tag_cleanup")
    monkeypatch.setitem(sys.modules, PREFIX + ".utils.tag_cleanup", load)
    torrent = mp_stubs("utils/torrent_adapter.py", "utils.torrent_adapter")
    monkeypatch.setitem(sys.modules, PREFIX + ".utils.torrent_adapter", torrent)
    spec = importlib.util.spec_from_file_location(PREFIX + ".modules.sitetag.service", ROOT / "modules/sitetag/service.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_run_merges_scan_errors_and_uses_execute_recheck(tag_service, monkeypatch):
    """空结果带读取失败 → code=2 不执行；有候选时 removals 只收零关联且复查由 execute 承担。"""
    service = tag_service
    calls = {}

    def fake_scan(plugin, names):
        calls["scan_names"] = list(names)
        return {"scan_id": "s1", "downloaders": [
            {"name": "qb", "tags": [
                {"tag": "empty", "count": 0, "removable": True, "hashes": []},
                {"tag": "used", "count": 3, "removable": False, "hashes": ["h"]},
            ]}],
            "errors": [{"downloader": "tr", "message": "下载器读取失败"}]}

    def fake_execute(plugin, removals, scan_id=None):
        calls["execute"] = {"removals": list(removals), "scan_id": scan_id}
        return {"code": 0, "msg": "ok", "removed": ["qb:empty"], "failed": [],
                "observed": 0, "requested": 1, "processed": 1, "truncated": False}

    monkeypatch.setattr(service, "scan_tag_candidates", fake_scan)
    monkeypatch.setattr(service, "execute_tag_cleanup", fake_execute)
    plugin = SimpleNamespace(_site_tag_config={"cleanup_downloaders": ["qb"]})

    empty = service.run_tag_cleanup(plugin, ["qb"], trigger="手动")
    assert calls["scan_names"] == ["qb"]
    assert calls["execute"]["removals"] == [{"downloader": "qb", "tag": "empty", "hashes": []}]
    assert calls["execute"]["scan_id"] == "s1"
    assert empty["code"] == 2 and empty["removed"] == ["qb:empty"]  # 有删除也有读取失败 → 部分成功
    assert empty["failed"] == [{"downloader": "tr", "tag": "", "message": "下载器读取失败"}]
    assert empty["trigger"] == "手动"


def test_run_without_candidates_reports_code2_with_errors(tag_service, monkeypatch):
    """无候选但有读取失败 → code=2、不调用执行；完全无失败 → code=0。"""
    service = tag_service
    monkeypatch.setattr(service, "scan_tag_candidates", lambda plugin, names: {
        "scan_id": "s2", "downloaders": [], "errors": [{"downloader": "tr", "message": "读取失败"}]})
    monkeypatch.setattr(service, "execute_tag_cleanup",
                        lambda *a, **k: pytest.fail("无候选不应执行"))
    plugin = SimpleNamespace(_site_tag_config={})
    result = service.run_tag_cleanup(plugin, ["qb"])
    assert result["code"] == 2 and result["removed"] == []
    assert result["msg"] == "未找到空标签；部分下载器读取失败"

    monkeypatch.setattr(service, "scan_tag_candidates", lambda plugin, names: {
        "scan_id": "s3", "downloaders": [], "errors": []})
    result = service.run_tag_cleanup(plugin, ["qb"])
    assert result["code"] == 0 and result["msg"] == "未找到空标签"


def test_run_falls_back_to_config_downloaders(tag_service, monkeypatch):
    """未显式传下载器时读 cleanup_downloaders 配置。"""
    service = tag_service
    seen = {}

    def fake_scan(plugin, names):
        seen["names"] = list(names)
        return {"scan_id": "s4", "downloaders": [], "errors": []}

    monkeypatch.setattr(service, "scan_tag_candidates", fake_scan)
    plugin = SimpleNamespace(_site_tag_config={"cleanup_downloaders": ["QB1", "QB2"]})
    service.run_tag_cleanup(plugin)
    assert seen["names"] == ["QB1", "QB2"]
