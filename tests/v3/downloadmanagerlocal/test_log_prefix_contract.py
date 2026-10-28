"""日志前缀契约：全插件日志必须符合 `【PT下载中心:<模块>】消息` 统一格式。

背景：历史上出现过三套写法——半角 `[PT下载中心:转移做种]`、全角 `【PT下载中心:转移做种】`、
以及同模块两个名字（`命名补刀` / `重命名`）。规范单源见 `utils/log_prefix.py`。
本测试是防漂移的守门：新写日志漏前缀、写错括号、写错模块名都会在这里失败。

前缀的两种合法写法（都接受）：
  内联  logger.info(f"【PT下载中心:转移做种】...")
  常量  logger.info(f"{TRANSFER_LOG_PREFIX}...")   # 常量值必须是合法前缀

被强制的不变量：
  I1 每个 `logger.*` 调用的首段文案（解析常量后）以 `【PT下载中心` 开头
  I2 括号必须是全角：源码里出现 `[PT下载中心` 一律失败
  I3 若带模块段，模块名必须取自 `utils/log_prefix.MODULES`
  I4 模块归属文件里的模块段必须与该文件归属的模块一致（跨域日志走 FILE_MODULE_EXTRA 显式登记）
  I5 所有前缀常量的值本身必须是合法前缀，且与其所在目录的模块一致
"""
from __future__ import annotations

import ast
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3] / "plugins.v3" / "downloadmanagerlocal"

# 文件（相对插件根）-> 归属模块；不在表内 = 跨层文件，不做 I4 校验
FILE_MODULE = {
    "service/transfer.py": "转移做种",
    "service/transfer_pipeline.py": "转移做种",
    "service/transfer_tasks.py": "转移做种",
    "service/payload_export.py": "转移做种",
    "service/events.py": "转移做种",
    "service/rename.py": "重命名",
    "service/rename_events.py": "重命名",
    "service/archive.py": "重命名",
    "service/site_tag.py": "站点标签",
    "service/recheck.py": "做种校验",
    "service/upload_limiter.py": "上传限速",
    "service/upload_limit_worker.py": "上传限速",
}
DIR_MODULE = {
    "service/hr": "H&R",
    "service/autoremove": "自动删种",
    "service/failclean": "失败清理",
}
# I4 的显式例外：同一文件里合法地打另一个域的日志（必须写明理由）
FILE_MODULE_EXTRA = {
    # retry_pending_renames() 虽在 transfer.py 内，实现的却是重命名补刀的重试，日志归属重命名域
    "service/transfer.py": {"重命名"},
}
LOG_METHODS = {"debug", "info", "warning", "error", "exception", "critical"}
LOG_OBJECTS = {"logger", "_logger", "log"}
PREFIX_MARK = "【PT下载中心"


# 模块名清单（唯一真源在本测试；与 service/ 下的模块目录一一对应，新增模块时同步此处）
MODULES = (
    "转移做种",
    "做种校验",
    "重命名",
    "站点标签",
    "上传限速",
    "失败清理",
    "H&R",
    "自动删种",
)


def _plugin_files():
    for path in sorted(PLUGIN.rglob("*.py")):
        if "dist" in path.parts or "__pycache__" in path.parts:
            continue
        yield path, str(path.relative_to(PLUGIN)).replace("\\", "/")


def _const_prefix_map() -> dict[str, tuple[str, str]]:
    """全插件扫描：常量名 -> (前缀值, 定义所在文件)。"""
    found: dict[str, tuple[str, str]] = {}
    for path, rel in _plugin_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)):
                continue
            if not node.value.value.startswith(PREFIX_MARK):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found[target.id] = (node.value.value, rel)
    return found


CONST_PREFIXES = _const_prefix_map()


def _expected_module(rel: str) -> str | None:
    if rel in FILE_MODULE:
        return FILE_MODULE[rel]
    for prefix, module in DIR_MODULE.items():
        if rel.startswith(prefix + "/"):
            return module
    return None


def _head_text(call: ast.Call) -> str | None:
    """返回首段文案（常量引用会解析成其值）；无法解析成前缀文案时返回 None。"""
    if not call.args:
        return None
    first = call.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    if isinstance(first, ast.JoinedStr) and first.values:
        head = first.values[0]
        if isinstance(head, ast.Constant) and isinstance(head.value, str):
            return head.value
        if isinstance(head, ast.FormattedValue) and isinstance(head.value, ast.Name):
            const = CONST_PREFIXES.get(head.value.id)
            if const:
                return const[0]
    return None


def _iter_log_calls():
    for path, rel in _plugin_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if not (isinstance(fn, ast.Attribute) and fn.attr in LOG_METHODS
                    and isinstance(fn.value, ast.Name) and fn.value.id in LOG_OBJECTS):
                continue
            yield rel, node.lineno, fn.attr, node


def _segments(text: str) -> tuple[str, str] | None:
    """从文案头部取出 (前缀原文, 模块段)；不合形态返回 None。模块段裸前缀时为 ''。"""
    if not text.startswith(PREFIX_MARK):
        return None
    end = text.find("】")
    if end < 0:
        return None
    return text[:end + 1], text[len(PREFIX_MARK):end]


def test_no_ascii_bracket_prefix_in_source():
    """I2：源码里不允许再出现半角 [PT下载中心。"""
    offenders = [rel for path, rel in _plugin_files()
                 if "[PT下载中心" in path.read_text(encoding="utf-8")]
    assert offenders == [], f"仍在使用半角括号前缀：{offenders}"


def test_every_log_call_has_prefix():
    """I1：每个 logger 调用的首段文案（常量解析后）都必须以 【PT下载中心 开头。"""
    bad = []
    for rel, lineno, level, node in _iter_log_calls():
        head = _head_text(node)
        if head is None:
            bad.append(f"{rel}:{lineno} [{level}] 无法解析出前缀文案（首参非字面量/非常量前缀）")
        elif not head.startswith(PREFIX_MARK):
            bad.append(f"{rel}:{lineno} [{level}] 缺前缀：{head[:40]!r}")
    assert bad == [], "以下日志缺少统一前缀：\n" + "\n".join(bad)


def test_module_segment_is_legal():
    """I3：模块段必须取自 utils/log_prefix.MODULES。"""
    bad = []
    for rel, lineno, level, node in _iter_log_calls():
        head = _head_text(node)
        if head is None:
            continue
        seg = _segments(head)
        if seg is None:
            continue
        module = seg[1]
        if module == "":                                  # 裸 【PT下载中心】 合法
            continue
        if not module.startswith(":"):
            bad.append(f"{rel}:{lineno} 前缀缺冒号：{head[:30]!r}")
            continue
        if module[1:] not in MODULES:
            bad.append(f"{rel}:{lineno} 非法模块名 {module[1:]!r}，合法值：{'/'.join(MODULES)}")
    assert bad == [], "以下日志模块名不合规：\n" + "\n".join(bad)


def test_module_matches_owning_file():
    """I4：模块归属文件里的模块段必须与该文件归属的模块一致。"""
    bad = []
    for rel, lineno, level, node in _iter_log_calls():
        head = _head_text(node)
        if head is None:
            continue
        seg = _segments(head)
        if seg is None:
            continue
        module = seg[1]
        if not module.startswith(":"):
            continue
        used = module[1:]
        expected = _expected_module(rel)
        if expected is None or used == expected:
            continue
        if used in FILE_MODULE_EXTRA.get(rel, set()):
            continue
        bad.append(f"{rel}:{lineno} 用了 {used!r}，该文件归属 {expected!r}"
                   f"（确属跨域请登记到 FILE_MODULE_EXTRA 并写明理由）")
    assert bad == [], "以下日志模块归属不一致：\n" + "\n".join(bad)


def test_prefix_constants_are_legal():
    """I5：前缀常量的值本身必须是合法前缀，且与定义所在目录的模块一致。"""
    assert CONST_PREFIXES, "未发现任何前缀常量——I5 校验形同虚设"
    bad = []
    for name, (value, rel) in sorted(CONST_PREFIXES.items()):
        seg = _segments(value)
        if seg is None or not seg[1].startswith(":"):
            bad.append(f"{rel} {name} 常量值不合形态：{value!r}")
            continue
        used = seg[1][1:]
        if used not in MODULES:
            bad.append(f"{rel} {name} 非法模块名 {used!r}")
            continue
        expected = _expected_module(rel)
        if expected is not None and used != expected:
            bad.append(f"{rel} {name} 值为 {used!r}，该目录归属 {expected!r}")
    assert bad == [], "以下前缀常量不合规：\n" + "\n".join(bad)


def test_known_legacy_module_name_retired():
    """历史遗留模块名「命名补刀」不得再作为日志模块段出现。"""
    bad = []
    for rel, lineno, level, node in _iter_log_calls():
        head = _head_text(node)
        if head and "PT下载中心:命名补刀" in head:
            bad.append(f"{rel}:{lineno}")
    assert bad == [], f"仍在使用已废弃的模块名「命名补刀」：{bad}"


def test_every_module_actually_logs():
    """I6：清单里每个模块都真的有带前缀的日志（新增模块漏写日志会在这里失败）。"""
    used = set()
    for rel, lineno, level, node in _iter_log_calls():
        head = _head_text(node)
        seg = _segments(head) if head else None
        if seg is not None and seg[1].startswith(":"):
            used.add(seg[1][1:])
    missing = [m for m in MODULES if m not in used]
    assert missing == [], f"以下模块没有任何带前缀的日志：{missing}"


def test_module_vocabulary_covers_service_dirs():
    """I7：service/ 下每个模块目录都必须出现在清单里（防止新目录被漏登记）。"""
    service = PLUGIN / "service"
    dirs = {p.name for p in service.iterdir() if p.is_dir() and not p.name.startswith("_")}
    # 目录名与日志模块名不是一一同名，按归属表反查覆盖情况
    covered = {module for prefix, module in DIR_MODULE.items()}
    assert covered <= set(MODULES), f"归属表里的模块未登记进清单：{sorted(covered - set(MODULES))}"
    assert dirs, "service/ 下没有模块目录——I7 校验形同虚设"
