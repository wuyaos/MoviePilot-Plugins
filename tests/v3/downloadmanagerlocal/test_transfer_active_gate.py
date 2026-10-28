# -*- coding: utf-8 -*-
"""is_transfer_active 门控：v3.9.0 多任务形态（transfer_tasks 优先，废弃字段不参与）。

不使用 conftest（其 PLUGIN 常量为 parents[2]，指向错误路径；旧测试均自带加载器），
本文件自带桩注入与文件加载器，仅真实加载 utils/config.py 与 modules/transfer/tasks.py。
"""
import importlib.machinery
import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import Mock

PLUGIN = Path(__file__).resolve().parents[3] / "plugins.v3" / "downloadmanagerlocal"
PREFIX = "app.plugins.downloadmanagerlocal"

_IS_LOADED = False
_STUB_KEYS = []
_config = None


def _stub(name, is_package=False, **attrs):
    mod = types.ModuleType(name)
    mod.__spec__ = importlib.machinery.ModuleSpec(name, None, is_package=is_package)
    if is_package:
        mod.__path__ = []
    mod.__dict__.update(attrs)
    if name not in _STUB_KEYS:
        _STUB_KEYS.append(name)
    sys.modules[name] = mod
    return mod


def _load_real(relpath: str, name: str):
    spec = importlib.util.spec_from_file_location(name, PLUGIN / relpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _ensure_loaded():
    """进程内只桩一次、只加载一次（模块级缓存，多个测试共享）。"""
    global _IS_LOADED, _config
    if _IS_LOADED:
        return
    _stub("app")
    _stub("app.sdk")
    _stub("app.sdk.logging", logger=Mock())
    _stub(PREFIX, is_package=True, __path_cancelled=None)
    sys.modules[PREFIX].__path__ = [str(PLUGIN)]
    for pkg in ("modules", "modules.autoremove", "modules.failclean", "modules.hr", "core"):
        _stub(f"{PREFIX}.{pkg}", is_package=True)
    _stub(
        f"{PREFIX}.modules.autoremove.constants",
        build_remover_config_defaults=Mock(return_value={}),
    )
    _stub(
        f"{PREFIX}.modules.failclean.constants",
        build_failclean_config_defaults=Mock(return_value={}),
    )
    _stub(
        f"{PREFIX}.modules.hr.constants",
        build_hr_config_defaults=Mock(return_value={}),
    )
    _stub(f"{PREFIX}.modules.rename.service", build_rename_flat_defaults=Mock(return_value={}))
    _stub(
        f"{PREFIX}.modules.sitetag.service",
        DEFAULT_TAG_CONFIG={
            "enable": False,
            "interval_cron": "5 4 * * *",
            "enable_media_tag": False,
            "enable_tag": True,
            "enable_category": False,
            "enable_del_tags": False,
            "downloaders": [],
            "all_cat": [],
            "all_cat_rename": [],
            "rename_type": False,
            "path_rename": None,
            "catprefix": "",
            "siteprefix": "",
            "tracker_mappings_str": "",
            "custom_site_labels_str": "",
        },
    )
    _load_real("modules/transfer/tasks.py", f"{PREFIX}.modules.transfer.tasks")
    _config = _load_real("utils/config.py", f"{PREFIX}.utils.config")
    # 加载完成，还原 sys.modules（已加载模块持有桩引用，不受影响），
    # 避免污染同进程后续收集的其他测试模块。
    for key in _STUB_KEYS:
        sys.modules.pop(key, None)
    _STUB_KEYS.clear()
    _IS_LOADED = True


def _task(name="qB到TR", enabled=True, **overrides):
    base = {
        "name": name,
        "enabled": enabled,
        "from_downloader": "test-qb",
        "to_downloader": "test-tr",
        "from_path": "/downloads",
        "to_path": "/downloads",
    }
    base.update(overrides)
    return base


class _FakePlugin:
    def __init__(self, enabled=True, tasks=None, **legacy):
        self._transfer_enabled = enabled
        self._transfer_tasks = json.dumps(tasks if tasks is not None else [_task()])
        for k, v in legacy.items():
            setattr(self, k, v)


def test_active_with_enabled_task():
    _ensure_loaded()
    assert _config.is_transfer_active(_FakePlugin(enabled=True)) is True


def test_inactive_when_switch_off():
    _ensure_loaded()
    assert _config.is_transfer_active(_FakePlugin(enabled=False)) is False


def test_inactive_when_all_tasks_disabled():
    _ensure_loaded()
    assert _config.is_transfer_active(_FakePlugin(tasks=[_task(enabled=False)])) is False


def test_inactive_when_no_tasks():
    _ensure_loaded()
    assert _config.is_transfer_active(_FakePlugin(tasks=[])) is False


def test_deprecated_fromtorrentpath_not_required():
    """旧字段 _fromtorrentpath 为空时仍应就绪（v3.9.0 废弃该校验）。"""
    _ensure_loaded()
    assert _config.is_transfer_active(_FakePlugin(enabled=True, _fromtorrentpath="")) is True


def test_legacy_single_chain_fallback():
    """旧单链路键存在时经迁移视图判定就绪。"""
    _ensure_loaded()
    plugin = _FakePlugin(enabled=True, tasks=[])
    plugin._fromdownloader = "qb"
    plugin._todownloader = "tr"
    plugin._includecategory = ""
    plugin._includelabels = ""
    plugin._nolabels = ""
    plugin._transferemptylabel = True
    plugin._nopaths = ""
    plugin._frompath = "/downloads"
    plugin._topath = "/downloads"
    plugin._deletesource = False
    plugin._deleteduplicate = False
    plugin._remainoldcat = True
    plugin._remainoldtag = True
    assert _config.is_transfer_active(plugin) is True
