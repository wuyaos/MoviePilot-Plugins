# -*- coding: utf-8 -*-
"""重命名模块配置契约与候选剪枝规则。

回归背景（2026-10-28 本地模块测试）：
- 一键补刀读的下载器来源曾与定时扫描不一致（补刀走 legacy `_todownloaders`、扫描走
  `rename_downloaders`），已在 `modules/transfer/service.py` 统一到 `build_rename_config`；
  本文件锁住「扁平 rename_* 键 → 嵌套配置」的映射契约，防止再次走偏。
- 「原始发布名候选置信度过低，跳过自动补刀」这条剪枝决定补刀是否会去调媒体识别，
  用 `_score_original_name_candidate` 的相对序锁定。

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
_rename = None


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
    global _IS_LOADED, _rename
    if _IS_LOADED:
        return
    _stub("app")
    _stub("app.sdk")
    _stub("app.sdk.logging", logger=Mock())
    _stub("app.sdk.media", MetaBase=object, MetaInfo=object, resolve_media_identity=Mock())
    _stub("app.schemas")
    _stub("app.schemas.types", MediaType=Mock(), MessageType=Mock())
    _stub("app.modules", is_package=True)
    _stub("app.modules.filemanager", is_package=True)
    _stub("app.modules.filemanager.transhandler", TransHandler=Mock())
    _stub("bencode", bdecode=Mock())
    _stub(PREFIX, is_package=True)
    sys.modules[PREFIX].__path__ = [str(PLUGIN)]
    for pkg in ("utils", "model", "modules", "modules.rename", "modules.hr", "adapter"):
        _stub(f"{PREFIX}.{pkg}", is_package=True)
    _stub(f"{PREFIX}.adapter.moviepilot", get_download_history_by_hash=Mock(return_value=None))

    _load_real("utils/name_cleaner.py", f"{PREFIX}.utils.name_cleaner")
    _load_real("utils/tag_cleanup.py", f"{PREFIX}.utils.tag_cleanup")
    _load_real("utils/torrent_adapter.py", f"{PREFIX}.utils.torrent_adapter")
    _load_real("modules/hr/constants.py", f"{PREFIX}.modules.hr.constants")
    _load_real("model/state.py", f"{PREFIX}.model.state")
    _load_real("modules/rename/archive.py", f"{PREFIX}.modules.rename.archive")
    _rename = _load_real("modules/rename/service.py", f"{PREFIX}.modules.rename.service")
    _IS_LOADED = True


# ────────────────────────── 扁平键契约 ──────────────────────────


def test_every_flat_key_maps_to_nested_config():
    """RENAME_FLAT_CONFIG_KEYS 的每个扁平键都必须能写进嵌套配置（补刀/扫描共用同一份）。"""
    _ensure_loaded()
    flat_keys = dict(_rename.RENAME_FLAT_CONFIG_KEYS)
    defaults = _rename.DEFAULT_RENAME_CONFIG
    payload = {}
    for nested, flat in flat_keys.items():
        default = defaults[nested]
        if isinstance(default, bool):
            payload[flat] = not default
        elif isinstance(default, list):
            payload[flat] = [" test-qb "]
        elif isinstance(default, int):
            payload[flat] = 7
        else:
            payload[flat] = "SENTINEL"
    cfg = _rename.build_rename_config(payload)
    for nested, flat in flat_keys.items():
        assert nested in cfg, f"{flat} 未映射到 {nested}"
        assert cfg[nested] not in (None, "", [], {}), f"{flat} → {nested} 值丢失：{cfg[nested]!r}"
    assert cfg["enabled"] is not defaults["enabled"]
    assert cfg["downloader"] == ["test-qb"]
    assert cfg["event_debounce_seconds"] == 7
    assert cfg["cron"] == "SENTINEL"
    assert all(flat.startswith("rename_") for flat in flat_keys.values())


def test_flat_key_wins_over_nested_key():
    """扁平键与嵌套键同时出现时以扁平键为准（宿主配置页写的是扁平键）。"""
    _ensure_loaded()
    cfg = _rename.build_rename_config({"rename_enabled": False, "enabled": True})
    assert cfg["enabled"] is False


def test_defaults_survive_missing_and_bad_values():
    """缺键走默认值；downloader 归一化；debounce 非法值回落默认。"""
    _ensure_loaded()
    base = _rename.build_rename_config({})
    assert base["enabled"] is _rename.DEFAULT_RENAME_CONFIG["enabled"]
    assert base["event_debounce_seconds"] == _rename.DEFAULT_RENAME_CONFIG["event_debounce_seconds"]

    cleaned = _rename.build_rename_config(
        {"rename_downloaders": [" test-qb ", "", None, "test-qb"], "rename_event_debounce_seconds": -3}
    )
    assert cleaned["downloader"] == ["test-qb"]
    # 非法（含非正）值不回落默认，而是钳到最小正值 1
    assert cleaned["event_debounce_seconds"] == 1


# ────────────────────────── 过滤链 ──────────────────────────


def test_filters_pass_when_no_rule_configured():
    _ensure_loaded()
    ok, reason = _rename.passes_rename_filters({}, "abc", ["x"], "/downloads/a")
    assert ok is True and reason == ""


def test_exclude_dir_blocks_first():
    _ensure_loaded()
    cfg = _rename.build_rename_config({"rename_exclude_dirs": "/downloads/keep\n/downloads/skip"})
    ok, reason = _rename.passes_rename_filters(cfg, "abc", [], "/downloads/skip/movie")
    assert ok is False and "排除目录" in reason


def test_hash_whitelist_only_allows_listed():
    _ensure_loaded()
    cfg = _rename.build_rename_config({"rename_hash_white_list": "AAA, bbb"})
    assert _rename.passes_rename_filters(cfg, "bbb", [], "/d")[0] is True
    ok, reason = _rename.passes_rename_filters(cfg, "ccc", [], "/d")
    assert ok is False and "白名单" in reason


def test_exclude_and_include_tags():
    _ensure_loaded()
    cfg = _rename.build_rename_config(
        {"rename_exclude_tags": "已重命名", "rename_include_tags": "站点A"}
    )
    ok, reason = _rename.passes_rename_filters(cfg, "h", ["已重命名"], "/d")
    assert ok is False and "排除标签" in reason

    ok, reason = _rename.passes_rename_filters(cfg, "h", ["站点B"], "/d")
    assert ok is False and "包含标签" in reason

    assert _rename.passes_rename_filters(cfg, "h", ["站点A"], "/d")[0] is True


# ────────────────────────── 候选剪枝 ──────────────────────────


def test_path_name_candidate_strips_media_suffix():
    _ensure_loaded()
    assert _rename._path_name_candidate("Movie.Name.2024.mkv") == "Movie.Name.2024"
    assert _rename._path_name_candidate("D:\\dl\\Show.S01E02.mp4") == "Show.S01E02"
    assert _rename._path_name_candidate("D:\\dl\\pack.torrent") == "pack"
    assert _rename._path_name_candidate("D:\\dl\\folder/") == "folder"
    assert _rename._path_name_candidate("") == ""


def test_release_name_outranks_polluted_and_bare_names():
    """带发布特征的名字得分更高；纯占位名（如 dml-batch-01.bin）得分最低 → 会被剪枝。"""
    _ensure_loaded()
    score = _rename._score_original_name_candidate
    release = score("Some.Movie.2024.1080p.WEB-DL.H264-GROUP")
    plain = score("dml-batch-01.bin")
    assert release > plain, f"发布名 {release} 应高于占位名 {plain}"
    assert score("") <= plain
