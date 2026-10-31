"""重命名记录的复合键：下载器 + hash（B02）。

存储键统一为 ``<downloader>:<hash>``，下载器未知（旧记录、缺下载器上下文）时退化为
裸 ``<hash>`` 以兼容旧数据。hash 为十六进制、不含冒号，因此按**最后一个**冒号切分
即可同时兼容下载器名自身含冒号的情形。

旧记录迁移（读侧触发、幂等、不扫真实下载器）：

- 带非空 ``downloader`` 字段的裸键记录 → 归位到 ``<downloader>:<hash>``；
- ``downloader`` 为空的裸键记录 → **不猜下载器**，保持裸键，由 :func:`lookup` 按
  「同 hash 唯一命中可用、多条命中视为歧义」处理；
- 目标键已存在时不叠加：取 ``time`` 较新的一条，时间相同保留复合键记录，
  避免迁移用旧数据覆盖新写入。

对外展示字段（``hash``/``original_name``/``after_name``/``success``/``reason``/
``downloader``/``time``）不因改键而变化。
"""

from __future__ import annotations

from datetime import datetime

RECORD_KEY_SEPARATOR = ":"

TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def record_key(torrent_hash: str, downloader: str = "") -> str:
    """按下载器身份生成存储键；下载器为空时退化为裸 hash。"""
    hash_text = str(torrent_hash or "").strip()
    if not hash_text:
        return ""
    downloader_text = str(downloader or "").strip()
    if not downloader_text or RECORD_KEY_SEPARATOR in hash_text:
        return hash_text
    return f"{downloader_text}{RECORD_KEY_SEPARATOR}{hash_text}"


def split_record_key(key) -> tuple[str, str]:
    """拆出 (downloader, hash)；裸键的 downloader 为空串。"""
    text = str(key or "")
    downloader, separator, torrent_hash = text.rpartition(RECORD_KEY_SEPARATOR)
    if not separator:
        return "", text
    return downloader, torrent_hash


def downloader_of_key(key) -> str:
    """取键内记录的下载器名（裸键为空串）。"""
    return split_record_key(key)[0]


def hash_of_key(key) -> str:
    """取键内记录的种子 hash。"""
    return split_record_key(key)[1]


def entries_for_hash(state, torrent_hash) -> list[tuple[str, dict]]:
    """列出同一 hash 的全部 (key, item)，按 key 排序保证结果稳定。"""
    hash_text = str(torrent_hash or "").strip()
    if not hash_text or not isinstance(state, dict):
        return []
    return sorted(
        (
            (key, item)
            for key, item in state.items()
            if isinstance(item, dict) and hash_of_key(key) == hash_text
        ),
        key=lambda pair: str(pair[0]),
    )


def lookup(state, torrent_hash, downloader: str = "") -> dict:
    """按 (hash, downloader) 定位一条记录。

    返回 ``{"key", "record", "status", "candidates"}``，``status`` 取值：

    - ``exact``：复合键精确命中该下载器；
    - ``legacy``：只有一条裸键记录（下载器未知），唯一命中可视为该下载器；
    - ``unique``：哈希只对应一条复合键记录（下载器未指定时唯一命中）；
    - ``other_downloader``：该下载器无记录，但同 hash 在其它下载器有记录；
    - ``ambiguous``：同 hash 多条记录且无法定位到具体下载器，**绝不任取**；
    - ``missing``：无任何记录。
    """
    hash_text = str(torrent_hash or "").strip()
    result = {"key": "", "record": {}, "status": "missing", "candidates": []}
    if not hash_text or not isinstance(state, dict):
        return result

    downloader_text = str(downloader or "").strip()
    if downloader_text:
        exact = record_key(hash_text, downloader_text)
        item = state.get(exact)
        if isinstance(item, dict):
            return {"key": exact, "record": item, "status": "exact", "candidates": [downloader_text]}

    matches = entries_for_hash(state, hash_text)
    if not matches:
        return result

    candidates = [name for name, _ in (split_record_key(key) for key, _ in matches)]
    candidate_names = [name for name in candidates if name]
    if len(matches) == 1 and not downloader_of_key(matches[0][0]):
        key, item = matches[0]
        return {"key": key, "record": item, "status": "legacy", "candidates": []}
    if len(matches) == 1:
        if downloader_text:
            # 指定下载器无记录：不把其它下载器的记录当作命中（key/record 置空）
            return {"key": "", "record": {}, "status": "other_downloader", "candidates": candidate_names}
        key, item = matches[0]
        return {"key": key, "record": item, "status": "unique", "candidates": candidate_names}
    if downloader_text:
        return {"key": "", "record": {}, "status": "other_downloader", "candidates": candidate_names}
    return {"key": "", "record": {}, "status": "ambiguous", "candidates": candidate_names}

def needs_migration(state) -> bool:
    """是否仍有可归位的裸键记录（带 downloader 字段但键未带下载器）。"""
    if not isinstance(state, dict):
        return False
    for key, item in state.items():
        if not isinstance(item, dict):
            continue
        downloader, torrent_hash = split_record_key(key)
        if downloader or not torrent_hash:
            continue
        if str(item.get("downloader") or "").strip():
            return True
    return False


def migrate_keys(state) -> tuple[dict, int]:
    """把裸键记录归位到复合键；返回 (新状态, 归位条数)，重复执行结果不变。"""
    if not isinstance(state, dict):
        return {}, 0
    result: dict = {}
    pending: list[tuple[str, dict]] = []
    for key, item in state.items():
        if not isinstance(item, dict):
            result[key] = item
            continue
        downloader, torrent_hash = split_record_key(key)
        if not downloader and torrent_hash and str(item.get("downloader") or "").strip():
            pending.append((key, item))
            continue
        result[key] = item
    moved = 0
    for key, item in pending:
        target = record_key(hash_of_key(key), item.get("downloader"))
        existing = result.get(target)
        if isinstance(existing, dict):
            result[target] = _newer_record(existing, item)
        else:
            result[target] = item
        moved += 1
    return result, moved


def _newer_record(current: dict, candidate: dict) -> dict:
    """冲突时取时间较新的一条；时间相同保留原（复合键）记录。"""
    if _time_value(candidate) > _time_value(current):
        return candidate
    return current


def _time_value(item: dict) -> str:
    text = str(item.get("time") or item.get("last_failed_at") or item.get("archived_at") or "")
    try:
        return datetime.strptime(text, TIME_FORMAT).strftime("%Y%m%d%H%M%S")
    except Exception:
        return text


__all__ = (
    "RECORD_KEY_SEPARATOR",
    "downloader_of_key",
    "entries_for_hash",
    "hash_of_key",
    "lookup",
    "migrate_keys",
    "needs_migration",
    "record_key",
    "split_record_key",
)
