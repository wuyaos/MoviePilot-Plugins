"""`utils/path.py:convert_save_path` 的边界契约。

背景：转移任务里 `from_path` / `to_path` 不同（源下载器根目录 ≠ 目的下载器根目录）时，
`modules/transfer/service.py:431` 调它把源任务的 `save_path` 映射成目的端的保存路径；
映射失败（返回空）会整条任务判 fail+1。

2026-10-28 排查发现该函数**零测试覆盖**，且当时全部 e2e 用例都是
`/downloads` → `/downloads`（同路径），等于「路径映射」这条真实分支从未被验证。
本文件补纯函数层边界；端到端（真容器、真落盘位置）由
`D:/work/tmp/dml-test/path_case.py` 覆盖。

契约（按实现逐条固化，防止后续重构静默改变语义）：
  C1 任一入参为空 → 原样返回 `save_path`（不猜、不改）
  C2 `save_path` 等于 `from_root`（容忍尾部斜杠差异）→ 返回 `to_root`（**原样**，末尾斜杠保留）
  C3 在 `from_root` 之下 → 前缀替换 + 相对段拼接（`from_root`/`to_root` 的尾部斜杠都不影响结果）
  C4 不在 `from_root` 下 → 原样返回（不做映射，避免把无关路径搬进目的端根目录）
  C5 `/downloads` 与 `/downloads2` 这种「前缀相同但不是子目录」必须判为 C4
  C6 `to_root` 为 Windows 风格且不含 `/` 时用 `\\` 分隔；`save_path` 的 `\\` 先归一为 `/`
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[3] / "plugins.v3" / "downloadmanagerlocal"

_spec = importlib.util.spec_from_file_location(
    "dml_utils_path", PLUGIN / "utils" / "path.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
convert_save_path = _mod.convert_save_path


# ---------------------------------------------------------------- C1 空入参

@pytest.mark.parametrize("save_path,from_root,to_root", [
    ("", "/downloads", "/media"),
    ("/downloads/a", "", "/media"),
    ("/downloads/a", "/downloads", ""),
    ("", "", ""),
])
def test_c1_empty_arg_returns_save_path(save_path, from_root, to_root):
    assert convert_save_path(save_path, from_root, to_root) == save_path


# ------------------------------------------------- C2 save_path 等于源根目录

@pytest.mark.parametrize("save_path", ["/downloads", "/downloads/"])
def test_c2_equal_root_returns_to_root(save_path):
    assert convert_save_path(save_path, "/downloads", "/media") == "/media"


def test_c2_returns_to_root_verbatim_keeping_trailing_slash():
    """C2 分支返回的是 `to_root` **原样**（与 C3 不同：C3 会 rstrip 后拼接）。"""
    assert convert_save_path("/downloads", "/downloads", "/media/") == "/media/"


def test_c2_tolerates_trailing_slash_on_from_root():
    assert convert_save_path("/downloads", "/downloads/", "/media") == "/media"


def test_c2_root_to_root():
    assert convert_save_path("/", "/", "/media") == "/media"


# ------------------------------------------------------------- C3 子目录映射

def test_c3_nested_prefix_replaced():
    assert convert_save_path("/downloads/movie/xxx", "/downloads", "/media") == "/media/movie/xxx"


def test_c3_trailing_slashes_do_not_leak():
    """`from_root` / `to_root` 的尾部斜杠都不能产生 `//` 或丢失分隔符。"""
    assert convert_save_path("/downloads/a/b", "/downloads/", "/media/") == "/media/a/b"


def test_c3_deep_nesting():
    assert (convert_save_path("/downloads/a/b/c/d", "/downloads", "/media/dst")
            == "/media/dst/a/b/c/d")


def test_c3_internal_slash_normalized_from_backslash_source():
    """`save_path` 里的 `\\` 先归一为 `/`，才能与 `from_root` 比较。"""
    assert (convert_save_path("\\downloads\\a\\b", "/downloads", "/media")
            == "/media/a/b")


# --------------------------------------------------------- C4 不在源根目录下

@pytest.mark.parametrize("save_path", [
    "/other/a",                    # 完全不相干
    "/media/a",                    # 等于目的根（不该再被映射一次）
    "/download/a",                 # 少一个字符的近似名
])
def test_c4_outside_root_returned_unchanged(save_path):
    assert convert_save_path(save_path, "/downloads", "/media") == save_path


def test_c5_sibling_prefix_is_not_a_subdir():
    """`/downloads2` 以 `/downloads` 开头但**不是**其后代，必须原样返回。"""
    assert convert_save_path("/downloads2/a", "/downloads", "/media") == "/downloads2/a"


def test_c5_twin_root_not_mapped():
    assert convert_save_path("/downloads-archive/a", "/downloads", "/media") == "/downloads-archive/a"


# ----------------------------------------------------- C6 Windows 风格 to_root

def test_c6_backslash_separator_when_to_root_is_windows_style():
    """`to_root` 含 `\\` 且不含 `/` → 输出用 `\\` 分隔（同一媒体库映射到 Windows 挂载点）。"""
    assert (convert_save_path("/downloads/a/b", "/downloads", "D:\\media")
            == "D:\\media\\a\\b")


def test_c6_backslash_to_root_trailing_slash_stripped():
    assert (convert_save_path("/downloads/a", "/downloads", "D:\\media\\")
            == "D:\\media\\a")


def test_c6_mixed_to_root_uses_forward_slash():
    """`to_root` 同时含 `/` 与 `\\` → 走 `/` 分支（判定条件是 `'\\' in to_root and '/' not in to_root`）。"""
    assert (convert_save_path("/downloads/a", "/downloads", "D:/media\\x")
            == "D:/media\\x/a")
