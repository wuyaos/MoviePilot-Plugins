# -*- coding: utf-8 -*-
"""下载器种子字段读取：非 qB 客户端返回 dict 形态时不得再走属性访问。

回归背景（2026-10-28 本地六实例矩阵）：TR/rt 宿主模块在 v3.9.0 之前返回对象、
在部分版本返回 dict，`transfer.post_transfer_process` 用 `torrent.name` 直取属性，
在 dict 形态下抛 AttributeError，表现为转移后处理每 60s 重试一次、目的端始终
「未出现种子」，tr2tr/tr2qb 等组合全灭。修复统一走 torrent_adapter.get_torrent_name。

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
_adapter = None


def _stub(name, is_package=False, **attrs):
    mod = types.ModuleType(name)
    mod.__spec__ = importlib.machinery.ModuleSpec(name, None, is_package=is_package)
    if is_package:
        mod.__path__ = []
    mod.__dict__.update(attrs)
    sys.modules[name] = mod
    return mod


def _load_real(relpath: str, name: str):
    spec = importlib.util.spec_from_file_location(name, PLUGIN / relpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _ensure_loaded():
    """进程内只桩一次、只加载一次。"""
    global _IS_LOADED, _adapter
    if _IS_LOADED:
        return
    _stub("app")
    _stub("app.sdk")
    _stub("app.sdk.logging", logger=Mock())
    _stub(PREFIX, is_package=True)
    sys.modules[PREFIX].__path__ = [str(PLUGIN)]
    _stub(f"{PREFIX}.utils", is_package=True)
    _adapter = _load_real("utils/torrent_adapter.py", f"{PREFIX}.utils.torrent_adapter")
    _IS_LOADED = True


def test_get_torrent_name_accepts_dict_and_object():
    """dict（TR/rt 部分版本）与对象（qB/rt 部分版本）两种形态都要能读出名称。"""
    _ensure_loaded()
    assert _adapter.get_torrent_name({"name": "dict 形态"}) == "dict 形态"

    obj = types.SimpleNamespace(name="对象形态")
    assert _adapter.get_torrent_name(obj) == "对象形态"

    camel = types.SimpleNamespace(torrentName="驼峰形态")
    assert _adapter.get_torrent_name(camel) == "驼峰形态"

    assert _adapter.get_torrent_name({}) == ""
    assert _adapter.get_torrent_name(None) == ""


def test_no_attribute_access_on_dict_torrents():
    """dict 种子走全部适配器读取函数都不应抛 AttributeError。"""
    _ensure_loaded()
    torrent = {
        "name": "测试种子",
        "category": "电影",
        "tags": "a,b",
        "labels": ["x"],
        "group": "电影",
        "save_path": "/downloads",
        "download_dir": "/downloads",
        "size": 1024,
        "total_size": 2048,
        "state": "downloading",
        "percent_done": 0.5,
    }
    for dl_type in ("qbittorrent", "transmission", "rtorrent"):
        assert _adapter.get_torrent_name(torrent) == "测试种子"
        assert _adapter.get_label(torrent, dl_type)
        assert _adapter.get_save_path(torrent, dl_type)
        assert _adapter.get_category(torrent, dl_type) in ("电影", "")
        assert _adapter.get_torrent_size(torrent, dl_type) >= 0
        _adapter.get_torrent_state(torrent, dl_type)
        _adapter.torrent_percent_done(torrent, dl_type)
        _adapter.torrent_is_complete(torrent, dl_type)
        _adapter.is_torrent_active(torrent, dl_type)


def test_get_category_accepts_dict_for_qbittorrent():
    """qB 分支此前直接 `torrent.get("category")`，对象形态会 AttributeError。"""
    _ensure_loaded()
    obj = types.SimpleNamespace(category="剧集")
    assert _adapter.get_category(obj, "qbittorrent") == "剧集"
    assert _adapter.get_category({"category": "电影"}, "qbittorrent") == "电影"
    assert _adapter.get_category({}, "qbittorrent") == ""


def test_service_sources_do_not_access_torrent_name_directly():
    """契约：service/ 内不得再出现直取 `.name` / `torrent.get("name")` 的形态分支。

    行为验证由本地六实例矩阵（qb2*/tr2*/rt2* 九组合）承担；本断言防止修复被回退。
    """
    offenders = []
    for path in sorted((PLUGIN / "modules").rglob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "torrent.name" in line or 'torrent.get("name"' in line:
                offenders.append(f"{path.relative_to(PLUGIN)}:{lineno}: {line.strip()}")
    assert not offenders, "存在绕过适配器的种子名称读取：\n" + "\n".join(offenders)


def test_is_torrent_active_handles_str_enum_status():
    """回归：transmission-rpc 的 Status 是 str 枚举，`.name` 是 "STOPPED"。

    v3.9.0 曾用 `str(state.name) != "stopped"` 判定，导致已暂停的 TR 种子恒被判为
    「仍活动」，转移流程在「确认源端暂停」处等满 30s 后报「源任务暂停超时」。
    """
    _ensure_loaded()
    from enum import Enum

    class Status(str, Enum):
        STOPPED = "stopped"
        SEED = "seeding"
        DOWNLOAD = "downloading"
        SEED_WAIT = "seed pending"

    assert _adapter.is_torrent_active(types.SimpleNamespace(status=Status.STOPPED), "transmission") is False
    assert _adapter.is_torrent_active(types.SimpleNamespace(status=Status.SEED), "transmission") is True
    assert _adapter.is_torrent_active(types.SimpleNamespace(status=Status.SEED_WAIT), "transmission") is True
    # 字符串形态（qB 归一后的 TR 形态）
    assert _adapter.is_torrent_active({"status": "stopped"}, "transmission") is False
    assert _adapter.is_torrent_active({"status": "seeding"}, "transmission") is True
    # 原始数字状态码：0=stopped
    assert _adapter.is_torrent_active({"status": 0}, "transmission") is False
    assert _adapter.is_torrent_active({"status": 4}, "transmission") is True
    # 读不到状态时保守判为「仍活动」
    assert _adapter.is_torrent_active({}, "transmission") is True


def test_classify_torrent_state_handles_str_enum_status():
    """状态归类同样不得被 str 枚举的 `.name` 带偏。"""
    _ensure_loaded()
    from enum import Enum

    class Status(str, Enum):
        STOPPED = "stopped"
        SEED = "seeding"

    assert _adapter.classify_torrent_state(Status.STOPPED, 0, 100) == "paused"
    assert _adapter.classify_torrent_state(Status.STOPPED, 0, 100) == "paused"
    assert _adapter.classify_torrent_state(Status.SEED, 0, 100) == "completed"


def test_get_hash_normalizes_case_for_all_clients():
    """回归：rt 回报大写哈希，直接丢给 Transmission 会 `torrent ids ... is not valid`。"""
    _ensure_loaded()
    upper = "BAA9318B435896814BF39D3131783B36F83969F0"
    lower = upper.lower()

    assert _adapter.get_hash({"hash": upper}, "qbittorrent") == lower
    assert _adapter.get_hash({"hashString": upper}, "transmission") == lower
    assert _adapter.get_hash({"hash": upper}, "rtorrent") == lower
    assert _adapter.get_hash({"hash_string": upper}, "rtorrent") == lower
    assert _adapter.get_hash(types.SimpleNamespace(hashString=upper), "transmission") == lower
    # 已经是小写则保持不变；缺失返回空串
    assert _adapter.get_hash({"hash": lower}, "qbittorrent") == lower
    assert _adapter.get_hash({}, "qbittorrent") == ""
    assert _adapter.normalize_hash(None) == ""
    assert _adapter.normalize_hash("  " + upper + " ") == lower
