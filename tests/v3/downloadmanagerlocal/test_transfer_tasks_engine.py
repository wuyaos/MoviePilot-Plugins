"""v3.9.0 转移做种多任务引擎测试。

transfer_tasks / payload_export 真加载（仅存根 app.sdk.logging）；
transfer.py 以全存根同级依赖加载（相对导入符号全部来自 sys.modules 存根）。
"""

import importlib.machinery
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

PLUGIN = Path(__file__).resolve().parents[3] / "plugins.v3/downloadmanagerlocal"
SERVICE = PLUGIN / "modules" / "transfer"
UTILS = PLUGIN / "utils"
PREFIX = "app.plugins.downloadmanagerlocal.modules.transfer"


def _module(monkeypatch, name, **attrs):
    """替身模块，必须带 __spec__。

    只写 `types.ModuleType(name)` 会让 `__spec__` 为 None；替身一旦被写进
    sys.modules 并留在那里，测试失败时 pytest 渲染回溯会调
    `importlib.resources.files(parent)` 解析父包，抛 TypeError 变成
    INTERNALERROR，整个会话只报「no tests ran」——真实失败被掩盖。
    """
    path = attrs.pop("__path__", None)
    result = types.ModuleType(name)
    result.__spec__ = importlib.machinery.ModuleSpec(name, None, is_package=path is not None)
    if path is not None:
        result.__path__ = path
    result.__dict__.update(attrs)
    monkeypatch.setitem(sys.modules, name, result)
    return result

def _load_real(monkeypatch, name):
    spec = importlib.util.spec_from_file_location(PREFIX + "." + name, SERVICE / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, result)
    spec.loader.exec_module(result)
    return result


def _load_util(monkeypatch, name):
    """按真实路径加载 utils 子模块，供 transfer/service 的相对导入使用。"""
    full = "app.plugins.downloadmanagerlocal.utils." + name
    spec = importlib.util.spec_from_file_location(full, UTILS / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, full, result)
    spec.loader.exec_module(result)
    return result


@pytest.fixture
def tt(monkeypatch):
    """transfer_tasks 真模块。"""
    _module(monkeypatch, "app")
    _module(monkeypatch, "app.sdk")
    _module(monkeypatch, "app.sdk.logging", logger=Mock())
    return _load_real(monkeypatch, "tasks")


@pytest.fixture
def pe(monkeypatch):
    """payload_export 真模块。"""
    _module(monkeypatch, "app")
    _module(monkeypatch, "app.sdk")
    _module(monkeypatch, "app.sdk.logging", logger=Mock())
    return _load_real(monkeypatch, "payload_export")


@pytest.fixture
def tr(monkeypatch):
    """transfer.py 真模块，同级重依赖存根化。"""
    _module(monkeypatch, "app")
    _module(monkeypatch, "app.sdk")
    _module(monkeypatch, "app.sdk.logging", logger=Mock())
    _module(monkeypatch, "app.schemas", ServiceInfo=Mock())
    _module(monkeypatch, "app.schemas.types", MessageType=Mock())
    _module(monkeypatch, "app.sdk.config", settings=Mock())
    _module(monkeypatch, "app.plugins")
    _module(monkeypatch, "app.plugins.downloadmanagerlocal")
    _module(monkeypatch, "app.plugins.downloadmanagerlocal.modules",
            __path__=[str(PLUGIN / "modules")])
    _module(monkeypatch, PREFIX, __path__=[str(SERVICE)])
    _module(monkeypatch, "app.plugins.downloadmanagerlocal.adapter", __path__=[])
    _module(monkeypatch, "app.plugins.downloadmanagerlocal.adapter.moviepilot",
            is_downloader_type=Mock(return_value=False))
    _module(monkeypatch, "app.plugins.downloadmanagerlocal.utils", __path__=[str(UTILS)])
    _module(monkeypatch, "app.plugins.downloadmanagerlocal.utils.name_cleaner",
            is_dirty_renamed_torrent_name=Mock(return_value=False))
    # 适配层按真实实现加载：转移管线的跨类型状态判定依赖真实语义。
    _load_util(monkeypatch, "torrent_adapter")
    _module(monkeypatch, "app.plugins.downloadmanagerlocal.model", __path__=[])
    _module(monkeypatch, "app.plugins.downloadmanagerlocal.model.state",
            SEED_RECHECK_QUEUE_KEY="queue", record_transfer_success=Mock())
    # 真加载轻模块，供 transfer.py 的 from-import 使用
    _load_real(monkeypatch, "tasks")
    _load_real(monkeypatch, "payload_export")
    _module(monkeypatch, PREFIX + ".recheck",
            _queue_lock=Mock(), _queue_key=Mock(return_value="queue"),
            load_seed_recheck_queue=Mock(return_value={}),
            save_seed_recheck_queue=Mock(),
            ensure_seed_recheck_worker=Mock(), seed_is_checking=Mock(return_value=False),
            seed_is_ready=Mock(return_value=True), seed_is_error=Mock(return_value=False),
            seed_is_timeout=Mock(return_value=False))
    _module(monkeypatch, "app.plugins.downloadmanagerlocal.modules.rename.service",
            _get_torrent_content_name=Mock(return_value=""),
            build_rename_config=Mock(return_value={"enabled": True, "downloader": []}),
            resolve_retry_original_name=Mock(return_value=""))
    _module(monkeypatch, "app.plugins.downloadmanagerlocal.modules.sitetag.service",
            create_temporary_tag=Mock(), forget_temporary_tag=Mock(),
            release_temporary_tag=Mock())
    return _load_real(monkeypatch, "service")


def _make_plugin(**config):
    plugin = MagicMock()
    plugin._transfer_tasks = config.get("transfer_tasks", "[]")
    plugin._fromdownloader = config.get("fromdownloader", "")
    plugin._todownloader = config.get("todownloader", "")
    plugin._includecategory = config.get("includecategory", "")
    plugin._includelabels = config.get("includelabels", "")
    plugin._nolabels = config.get("nolabels", "")
    plugin._transferemptylabel = config.get("transferemptylabel", False)
    plugin._nopaths = config.get("nopaths", "")
    plugin._frompath = config.get("frompath", "")
    plugin._topath = config.get("topath", "")
    plugin._deletesource = config.get("deletesource", False)
    plugin._deleteduplicate = config.get("deleteduplicate", True)
    plugin._remainoldcat = config.get("remainoldcat", True)
    plugin._remainoldtag = config.get("remainoldtag", True)
    return plugin


class TestNormalizeTask:
    def test_valid_task_normalized(self, tt):
        task = tt._normalize_task({
            "name": "主任务", "from_downloader": "QB1", "to_downloader": "QB2",
            "from_path": "/a", "to_path": "/b",
        }, 0)
        assert task is not None
        assert task["name"] == "主任务"
        assert task["delete_duplicate"] is True

    def test_same_downloader_rejected(self, tt):
        assert tt._normalize_task({
            "from_downloader": "QB1", "to_downloader": "QB1",
            "from_path": "/a", "to_path": "/b",
        }, 0) is None

    def test_missing_path_rejected(self, tt):
        assert tt._normalize_task({
            "from_downloader": "QB1", "to_downloader": "QB2",
        }, 0) is None

    def test_defaults_filled(self, tt):
        task = tt._normalize_task({
            "from_downloader": "QB1", "to_downloader": "fnos-tr",
            "from_path": "/a", "to_path": "/b", "enabled": "yes",
        }, 0)
        assert task["enabled"] is True


class TestLoadTransferTasks:
    def test_empty_falls_back_to_legacy(self, tt):
        plugin = _make_plugin(fromdownloader="QB1", todownloader="QB2",
                              frompath="/mnt/a", topath="/mnt/b")
        tasks = tt.load_transfer_tasks(plugin)
        assert len(tasks) == 1
        assert tasks[0]["from_downloader"] == "QB1"
        assert tasks[0]["to_downloader"] == "QB2"
        assert "旧配置迁移" in tasks[0]["name"]

    def test_explicit_tasks_win(self, tt):
        payload = str([
            {"name": "T1", "from_downloader": "QB1", "to_downloader": "QB2",
             "from_path": "/a", "to_path": "/b"},
        ]).replace("'", '"')
        plugin = _make_plugin(transfer_tasks=payload,
                              fromdownloader="OLD", todownloader="OLD2")
        tasks = tt.load_transfer_tasks(plugin)
        assert len(tasks) == 1
        assert tasks[0]["name"] == "T1"

    def test_disabled_tasks_filtered(self, tt):
        payload = ('[{"name": "on", "from_downloader": "QB1", "to_downloader": "QB2",'
                   ' "from_path": "/a", "to_path": "/b", "enabled": true},'
                   ' {"name": "off", "from_downloader": "QB2", "to_downloader": "fnos-tr",'
                   ' "from_path": "/a", "to_path": "/b", "enabled": false}]')
        plugin = _make_plugin(transfer_tasks=payload)
        assert [t["name"] for t in tt.load_transfer_tasks(plugin)] == ["on"]

    def test_invalid_json_falls_back(self, tt):
        plugin = _make_plugin(transfer_tasks="{broken",
                              fromdownloader="QB1", todownloader="QB2",
                              frompath="/a", topath="/b")
        assert len(tt.load_transfer_tasks(plugin)) == 1

    def test_no_config_no_tasks(self, tt):
        assert tt.load_transfer_tasks(_make_plugin()) == []


class TestRenameGate:
    def test_post_process_skips_rename_when_disabled(self, tr, monkeypatch):
        plugin = MagicMock()
        plugin._transfer_stop_generation = 0
        plugin._event = None
        plugin._rename_enabled = True
        plugin._transfer_rename_enabled = False
        plugin._tag_enabled = False

        torrent = {"name": "old", "tags": "", "save_path": "/p", "tracker": ""}
        dl = MagicMock()
        dl.get_torrents.return_value = ([torrent], None)
        service = MagicMock()
        service.instance = dl
        service.type = "qbittorrent"
        monkeypatch.setattr(tr, "get_label", lambda t, d: [])
        monkeypatch.setattr(tr, "get_tracker_urls", lambda t, d: [])
        monkeypatch.setattr(tr, "get_save_path", lambda t, d: "/p")

        assert tr.post_transfer_process(plugin, service, "abc123") is True
        plugin._rename_torrent.assert_not_called()

    def test_post_process_renames_when_enabled(self, tr, monkeypatch):
        plugin = MagicMock()
        plugin._transfer_stop_generation = 0
        plugin._event = None
        plugin._rename_enabled = True
        plugin._transfer_rename_enabled = True
        plugin._tag_enabled = False

        torrent = {"name": "old", "tags": "", "save_path": "/p", "tracker": ""}
        dl = MagicMock()
        dl.get_torrents.return_value = ([torrent], None)
        service = MagicMock()
        service.instance = dl
        service.type = "qbittorrent"
        monkeypatch.setattr(tr, "get_label", lambda t, d: [])
        monkeypatch.setattr(tr, "get_tracker_urls", lambda t, d: [])
        monkeypatch.setattr(tr, "get_save_path", lambda t, d: "/p")

        assert tr.post_transfer_process(plugin, service, "abc123") is True
        plugin._rename_torrent.assert_called_once()

    def test_post_process_transmission_skips_rename(self, tr, monkeypatch):
        plugin = MagicMock()
        plugin._transfer_stop_generation = 0
        plugin._event = None
        plugin._rename_enabled = True
        plugin._transfer_rename_enabled = True
        plugin._tag_enabled = False

        torrent = MagicMock()
        torrent.name = "old"
        dl = MagicMock()
        dl.get_torrents.return_value = ([torrent], None)
        service = MagicMock()
        service.instance = dl
        service.type = "transmission"
        monkeypatch.setattr(tr, "get_label", lambda t, d: [])
        monkeypatch.setattr(tr, "get_tracker_urls", lambda t, d: [])
        monkeypatch.setattr(tr, "get_save_path", lambda t, d: "/p")

        assert tr.post_transfer_process(plugin, service, "abc123") is True
        plugin._rename_torrent.assert_not_called()


class TestPayloadDispatch:
    def test_qb_dispatch(self, pe):
        dl = MagicMock()
        dl.export_torrent.return_value = b"torrent-bytes"
        svc = MagicMock()
        svc.instance = dl
        result = pe.get_torrent_payloads(None, "qbittorrent", "QB1", svc, ["h" * 40])
        assert result == {"h" * 40: b"torrent-bytes"}

    def test_qb_export_none(self, pe):
        dl = MagicMock()
        dl.export_torrent.return_value = None
        svc = MagicMock()
        svc.instance = dl
        assert pe.get_torrent_payloads(None, "qbittorrent", "QB1", svc, ["h" * 40]) == {}

    def test_unsupported_type(self, pe):
        svc = MagicMock()
        assert pe.get_torrent_payloads(None, "unknown", "X", svc, ["h" * 40]) == {}


class TestValidateConfig:
    def test_validate_fails_without_tasks(self, tr):
        assert tr.validate_config(_make_plugin()) is False

    def test_validate_passes_with_legacy(self, tr):
        plugin = _make_plugin(fromdownloader="QB1", todownloader="QB2",
                              frompath="/a", topath="/b")
        assert tr.validate_config(plugin) is True


class TestRetryPendingRenamesDownloaders:
    """一键补刀的目标下载器必须与定时扫描一致：优先 rename_downloaders，回退旧单链路 todownloader。"""

    @staticmethod
    def _patch(tr, monkeypatch, *, rename_downloaders, legacy, available):
        monkeypatch.setattr(
            tr, "build_rename_config",
            lambda cfg=None: {"enabled": True, "downloader": list(rename_downloaders)},
        )
        monkeypatch.setattr(
            tr, "retry_dirty_torrent_names",
            Mock(return_value={"attempted": 0, "success": 0, "failed": 0, "skipped": 0, "errors": []}),
        )
        plugin = MagicMock()
        plugin._rename_config = {}
        plugin._todownloader = legacy
        services = {}
        for name in (list(rename_downloaders) or [legacy]):
            if not name:
                continue
            svc = MagicMock()
            svc.instance = MagicMock() if name in available else None
            services[name] = svc
        plugin.service_info = Mock(side_effect=lambda n: services.get(n))
        plugin._retry_failed_renames = Mock(return_value={"attempted": 1, "success": 1, "failed": 0})
        return plugin

    def test_uses_rename_downloaders_when_legacy_empty(self, tr, monkeypatch):
        """回归：只配 rename_downloaders、todownloader 为空时，补刀不能再报「未配置目标下载器」。"""
        plugin = self._patch(tr, monkeypatch, rename_downloaders=["QB2"], legacy="", available={"QB2"})
        result = tr.retry_pending_renames(plugin)
        plugin.service_info.assert_called_with("QB2")
        assert result["code"] == 0
        assert result["total"] == 1

    def test_falls_back_to_legacy_single_downloader(self, tr, monkeypatch):
        plugin = self._patch(tr, monkeypatch, rename_downloaders=[], legacy="QB1", available={"QB1"})
        result = tr.retry_pending_renames(plugin)
        plugin.service_info.assert_called_with("QB1")
        assert result["code"] == 0

    def test_reports_unconfigured_when_both_empty(self, tr, monkeypatch):
        plugin = self._patch(tr, monkeypatch, rename_downloaders=[], legacy="", available=set())
        result = tr.retry_pending_renames(plugin)
        assert result["code"] == 1
        assert result["msg"] == "未配置目标下载器"

    def test_reports_unavailable_when_all_missing(self, tr, monkeypatch):
        plugin = self._patch(tr, monkeypatch, rename_downloaders=["QB2", "QB3"], legacy="",
                             available=set())
        result = tr.retry_pending_renames(plugin)
        assert result["code"] == 1
        assert result["msg"] == "目标下载器不可用，已跳过补刀"

    def test_aggregates_all_available_downloaders(self, tr, monkeypatch):
        plugin = self._patch(tr, monkeypatch, rename_downloaders=["QB2", "QB3"], legacy="",
                             available={"QB2", "QB3"})
        result = tr.retry_pending_renames(plugin)
        assert plugin._retry_failed_renames.call_count == 2
        assert result["code"] == 0
        assert result["total"] == 2
        assert result["history"] == 2
