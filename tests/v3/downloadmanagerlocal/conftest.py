"""V3 插件测试共享 stub 环境。

MP 宿主模块（app.*）在测试环境不存在，用带 __spec__ 的包替身注入 sys.modules，
再按 spec_from_file_location 加载插件真实源码（相对导入挂到
app.plugins.downloadmanagerlocal 假包下）。
"""

import importlib
import importlib.machinery
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import Mock

import pytest

PLUGIN = Path(__file__).resolve().parents[3] / "plugins.v3" / "downloadmanagerlocal"
PREFIX = "app.plugins.downloadmanagerlocal"


@pytest.fixture
def mp_stubs(monkeypatch):
    """注入 MP 宿主替身，返回 load(relpath, name) 加载器。"""

    def module(name, **attrs):
        """带 __spec__ 的包替身（pytest 断言重写要求 spec 非 None）。"""
        path = attrs.pop("__path__", None)
        result = types.ModuleType(name)
        result.__spec__ = importlib.machinery.ModuleSpec(
            name, None, is_package=path is not None
        )
        if path is not None:
            result.__path__ = path
        result.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, result)
        return result

    module("app")
    module("app.sdk")
    module("app.plugins")
    module(PREFIX, __path__=[str(PLUGIN)])
    module("app.sdk.logging", logger=Mock())
    module("app.application")
    module("app.application.torrent")
    module("app.application.torrent.download", TorrentHelper=Mock())
    module("app.db")
    module("app.db.oper")
    module("app.db.oper.downloadhistory", DownloadHistoryOper=Mock())
    module("app.db.oper.site", SiteOper=Mock())
    module("app.modules.qbittorrent", Qbittorrent=type("Qbittorrent", (), {}))
    module("app.modules.transmission", Transmission=type("Transmission", (), {}))
    module("app.sdk.network", RequestUtils=Mock(), SitesHelper=Mock())
    module("app.sdk.services", DownloaderHelper=Mock())
    module("app.sdk.utilities", StringUtils=Mock())
    module("app.sdk.media", MetaBase=object, MetaInfo=Mock, resolve_media_identity=Mock())
    module("app.sdk.config", settings=Mock())
    module("app.modules")
    module("app.modules.filemanager")
    module("app.modules.filemanager.transhandler", TransHandler=Mock())
    module("app.schemas")
    module("app.schemas.types", MediaType=Mock(), MessageType=Mock())
    module("bencode", bdecode=Mock(), bencode=Mock())
    module("requests", post=Mock(), get=Mock())

    def load(relpath: str, name: str):
        spec = importlib.util.spec_from_file_location(
            PREFIX + "." + name, PLUGIN / relpath
        )
        result = importlib.util.module_from_spec(spec)
        sys.modules[PREFIX + "." + name] = result
        spec.loader.exec_module(result)
        return result

    return load
