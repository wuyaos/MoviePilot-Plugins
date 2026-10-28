# -*- coding: utf-8 -*-
"""站点标签打标的三态契约（True / None / False）。

回归背景（2026-10-28 用户裁决）：「无法识别站点」属可接受情形，算 warning，不能拉低补刀成功率。
因此 `modules/sitetag/service.py:tag_torrent` 的返回值从布尔改成三态：

- `True`  已打上标签，或标签已存在（幂等）
- `None`  站点未识别 —— 跳过，**不计失败**（调用侧记 warning）
- `False` **写入失败**（下载器报错）—— 调用侧记 failure

调用侧对应关系（本文件不覆盖，由各自模块的用例覆盖）：
- `modules/rename/service.py` 补刀：`False` → `summary["errors"]`，`None` → `summary["warnings"]`
- `modules/transfer/service.py` 转移后打标：`False` → logger.error，`None` → logger.warning

不使用 conftest（其 PLUGIN 常量为 parents[2]，指向错误路径），本文件自带桩注入。
"""
import importlib.machinery
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import Mock

PLUGIN = Path(__file__).resolve().parents[3] / "plugins.v3" / "downloadmanagerlocal"
PREFIX = "app.plugins.downloadmanagerlocal"

_IS_LOADED = False
_site_tag = None
_logger = Mock()
_stubs = {}


def _stub(name, is_package=False, **attrs):
    mod = types.ModuleType(name)
    mod.__spec__ = importlib.machinery.ModuleSpec(name, None, is_package=is_package)
    if is_package:
        mod.__path__ = []
    mod.__dict__.update(attrs)
    sys.modules[name] = mod
    _stubs[name] = mod
    return mod


def _load_real(relpath: str, name: str):
    spec = importlib.util.spec_from_file_location(name, PLUGIN / relpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _fake_domain(value: str) -> str:
    """粗粒度等价 get_url_domain：去掉协议与路径、端口。"""
    text = (value or "").split("://")[-1].split("/")[0]
    return text.split(":")[0].lower()


def _ensure_loaded():
    global _IS_LOADED, _site_tag
    if _IS_LOADED:
        return
    global _logger
    _logger = Mock()
    _stub("app")
    _stub("app.sdk")
    _stub("app.sdk.config", settings=types.SimpleNamespace(TZ="Asia/Shanghai"))
    _stub("app.sdk.logging", logger=_logger)
    _stub(PREFIX, is_package=True)
    sys.modules[PREFIX].__path__ = [str(PLUGIN)]
    _stub(PREFIX + ".adapter", is_package=True)
    _stub(PREFIX + ".adapter.moviepilot",
          generate_random_tag=Mock(return_value="TMP_TAG"),
          get_site_indexer=Mock(return_value={}),
          get_url_domain=_fake_domain,
          list_site_dicts=Mock(return_value=[]))
    _stub(PREFIX + ".utils", is_package=True)
    _stub(PREFIX + ".utils.tag_cleanup",
          TEMP_TAG_PREFIX="TMP_",
          classify_tag=Mock(return_value="user"),
          is_auto_removable=Mock(return_value=False),
          normalize_tags=lambda tags: list(tags or []))
    _stub(PREFIX + ".utils.torrent_adapter",
          get_hash=Mock(return_value=""),
          get_label=Mock(return_value=""),
          get_torrent_name=Mock(return_value=""))
    _site_tag = _load_real("modules/sitetag/service.py", PREFIX + ".modules.sitetag.service")
    _IS_LOADED = True


def _module(name):
    _ensure_loaded()
    return sys.modules[name]


def _plugin(**attrs):
    base = {
        "_tracker_mappings": {},
        "_custom_site_labels": {},
        "_tag_siteprefix": "\U0001F3E0",
    }
    base.update(attrs)
    return types.SimpleNamespace(**base)


def _dl(**attrs):
    attrs.setdefault("set_torrents_tag", Mock())
    return types.SimpleNamespace(**attrs)


TRACKER = "udp://tracker.dml-test.local:6969/announce"


def test_unknown_site_returns_none_not_false():
    """站点库与自定义映射都没有该域名 → None（warning 语义），且不调用下载器写入。"""
    _ensure_loaded()
    adapter = _module(PREFIX + ".adapter.moviepilot")
    adapter.list_site_dicts.return_value = []
    _logger.reset_mock()
    dl = _dl()
    plugin = _plugin()

    result = _site_tag.tag_torrent(plugin, dl, "qbittorrent", "hash-unknown", [], [TRACKER])

    assert result is None
    assert result is not False, "未识别站点必须与写入失败区分开，否则会被计入补刀失败"
    assert dl.set_torrents_tag.call_count == 0
    assert _logger.warning.call_count >= 1
    assert any("无法识别站点" in str(c) for c in _logger.warning.call_args_list)
    assert _logger.error.call_count == 0, "未识别站点是 warning，不应记 error"


def test_known_site_tags_and_returns_true():
    """站点库能解析出站点 → 打「前缀+站点名」标签并返回 True。"""
    _ensure_loaded()
    adapter = _module(PREFIX + ".adapter.moviepilot")
    adapter.list_site_dicts.return_value = [
        {"domain": "https://tracker.dml-test.local", "name": "DML-CUSTOM"},
    ]
    dl = _dl()
    result = _site_tag.tag_torrent(_plugin(), dl, "qbittorrent", "hash-known", [], [TRACKER])
    assert result is True
    dl.set_torrents_tag.assert_called_once_with(ids="hash-known", tags=["\U0001F3E0DML-CUSTOM"])


def test_custom_site_label_mapping_wins_when_site_unknown():
    """站点库未收录但自定义映射命中 → 仍返回 True（3.8.5 自定义站点能力不回归）。"""
    _ensure_loaded()
    adapter = _module(PREFIX + ".adapter.moviepilot")
    adapter.list_site_dicts.return_value = []
    dl = _dl()
    plugin = _plugin(_custom_site_labels={"tracker.dml-test.local": "CUSTOM"})
    result = _site_tag.tag_torrent(plugin, dl, "qbittorrent", "hash-custom", [], [TRACKER])
    assert result is True
    dl.set_torrents_tag.assert_called_once_with(ids="hash-custom", tags=["\U0001F3E0CUSTOM"])


def test_existing_tag_is_idempotent_true():
    """标签已存在 → True，且不重复写入。"""
    _ensure_loaded()
    adapter = _module(PREFIX + ".adapter.moviepilot")
    adapter.list_site_dicts.return_value = [
        {"domain": "tracker.dml-test.local", "name": "DML-CUSTOM"},
    ]
    dl = _dl()
    result = _site_tag.tag_torrent(
        _plugin(), dl, "qbittorrent", "hash-idem", ["\U0001F3E0DML-CUSTOM"], [TRACKER])
    assert result is True
    assert dl.set_torrents_tag.call_count == 0


def test_write_failure_returns_false():
    """下载器写入抛错 → False（失败语义），并记 error。"""
    _ensure_loaded()
    adapter = _module(PREFIX + ".adapter.moviepilot")
    adapter.list_site_dicts.return_value = [
        {"domain": "tracker.dml-test.local", "name": "DML-CUSTOM"},
    ]
    _logger.reset_mock()
    dl = _dl(set_torrents_tag=Mock(side_effect=RuntimeError("boom")))
    result = _site_tag.tag_torrent(_plugin(), dl, "qbittorrent", "hash-fail", [], [TRACKER])
    assert result is False
    assert _logger.error.call_count == 1
