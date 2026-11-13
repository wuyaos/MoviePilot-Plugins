"""同步客户端内部文件路径；不清洗字符、不移动文件、不取得删源许可。

Transmission rename-path 可能改磁盘，只有本机 RPC socket 对应进程的
/proc/<pid>/root 可直接核验时才允许修复。远端或容器隔离无法证明时拒绝。
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import socket
import stat
import sys
import time
from urllib.parse import urlsplit

from ...adapter.downloader import read_torrents
from ...utils.torrent_adapter import get_save_path, get_torrent_state, torrent_is_complete


class PathRepairBlocked(ValueError):
    pass


def field(value, *names, default=None):
    for name in names:
        result = value.get(name) if isinstance(value, dict) else getattr(value, name, None)
        if result is not None:
            return result
    return default


def safe_relative(name):
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        raise PathRepairBlocked("文件路径无效")
    parts = name.split("/")
    if any(p in ("", ".", "..") for p in parts) or PurePosixPath(name).is_absolute():
        raise PathRepairBlocked("文件路径越界或含非规范片段")
    return name


def read_files(service, torrent_hash):
    """仅查询指定 hash，按客户端文件索引对齐，不能按清洗后的名称猜测。"""
    if service.type == "qbittorrent":
        files = service.instance.qbc.torrents_files(torrent_hash=torrent_hash)
        rows = [(int(field(f, "index")), safe_relative(field(f, "name")), int(field(f, "size"))) for f in files]
    elif service.type == "transmission":
        torrent = service.instance.trc.get_torrent(torrent_hash, arguments=["hashString", "files"])
        if str(field(torrent, "hashString", "hash_string", default="")).lower() != torrent_hash.lower():
            raise PathRepairBlocked("文件列表返回的种子身份不一致")
        raw = torrent.get_files()
        rows = [(int(i), safe_relative(field(f, "name")), int(field(f, "size", "length"))) for i, f in raw.items()]
    else:
        raise PathRepairBlocked("当前仅支持 qB/Transmission 来源与 Transmission 目标")
    rows.sort()
    if not rows or [r[0] for r in rows] != list(range(len(rows))) or any(r[2] < 0 for r in rows):
        raise PathRepairBlocked("文件索引不完整或大小无效")
    names = [r[1] for r in rows]
    # casefold 仅用于拒绝冲突，绝不据此建立文件映射。
    if len({n.casefold() for n in names}) != len(names):
        raise PathRepairBlocked("文件名存在大小写或重名冲突")
    return rows


def _one(plugin, service, torrent_hash):
    result = read_torrents(service, [torrent_hash])
    if not result.success or len(result.items) != 1:
        raise PathRepairBlocked("无法唯一读取源/目标任务")
    task = result.items[0]
    if str(plugin.get_hash(task, service.type) or "").lower() != torrent_hash.lower():
        raise PathRepairBlocked("源/目标 infohash 不一致")
    return task


def _process_root(client):
    """证明 RPC 直连本机 Transmission 进程，不把容器可见路径当作远端现场。"""
    url = getattr(client, "_url", None)
    if not isinstance(url, str):
        raise PathRepairBlocked("无法核实 RPC 地址对应的文件现场")
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    try:
        # 不能以一次 DNS 恰好解析到回环地址来证明 RPC 始终直连本机。
        if host != "localhost" and not ipaddress.ip_address(host).is_loopback:
            raise ValueError("not loopback")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        addresses = {ipaddress.ip_address(x[4][0]) for x in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
        local = addresses and all(a.is_loopback for a in addresses)
    except (OSError, ValueError):
        local = False
    if not local:
        raise PathRepairBlocked("远端文件现场无法确认：仅提供路径检测，不允许修复")
    inodes = set()
    for table in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            for line in Path(table).read_text().splitlines()[1:]:
                fields = line.split()
                address_hex, port_hex = fields[1].rsplit(":", 1)
                address_bytes = b"".join(int(address_hex[i:i + 8], 16).to_bytes(4, sys.byteorder)
                                         for i in range(0, len(address_hex), 8))
                listener = ipaddress.ip_address(address_bytes)
                same_endpoint = listener in addresses or (listener.is_unspecified and any(
                    a.version == listener.version for a in addresses))
                if fields[3] == "0A" and int(port_hex, 16) == port and same_endpoint:
                    inodes.add(fields[9])
        except FileNotFoundError:
            continue
    roots = []
    for proc in Path("/proc").glob("[0-9]*"):
        try:
            if "transmission" not in Path(os.readlink(proc / "exe")).name.lower():
                continue
            if any(os.readlink(fd) in {f"socket:[{i}]" for i in inodes} for fd in (proc / "fd").iterdir()):
                roots.append(proc / "root")
        except (OSError, PermissionError):
            continue
    if len(roots) != 1:
        raise PathRepairBlocked("无法唯一确认本机 Transmission 进程及其磁盘命名空间")
    return roots[0]


def _real_path(root, absolute, relative="", *, missing=False):
    if not isinstance(absolute, str) or not absolute.startswith("/") or ".." in absolute.split("/"):
        raise PathRepairBlocked("目标保存目录无效")
    path = root
    parts = list(PurePosixPath(absolute).parts[1:]) + (safe_relative(relative).split("/") if relative else [])
    for index, part in enumerate(parts):
        path = path / part
        try:
            info = path.lstat()
        except FileNotFoundError:
            if missing:
                return None
            raise PathRepairBlocked("源端现用文件在目标文件现场不存在") from None
        if stat.S_ISLNK(info.st_mode):
            raise PathRepairBlocked("路径含符号链接，拒绝自动推断实际文件")
        if index < len(parts) - 1 and not stat.S_ISDIR(info.st_mode):
            raise PathRepairBlocked("路径中间片段不是目录")
    return path


def _disk_guard(client, directory, source_files, old_root):
    session = client.get_session()
    if field(session, "incomplete_dir_enabled", "incomplete-dir-enabled") is not False:
        raise PathRepairBlocked("启用了独立未完成目录或无法确认其状态，拒绝推断实际路径")
    root = _process_root(client)
    # rename-path 对旧文件、目录和 .part 都可能实际改名，必须全部不存在。
    if _real_path(root, directory, old_root, missing=True) is not None or _real_path(root, directory, old_root + ".part", missing=True) is not None:
        raise PathRepairBlocked("目标原路径或 .part 已存在，修复可能改动磁盘，拒绝执行")
    for _, name, size in source_files:
        path = _real_path(root, directory, name)
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_size != size:
            raise PathRepairBlocked("源端现用文件在目标现场的类型或大小不匹配")


def diagnose(plugin, item):
    """返回有限的只读诊断；完整文件列表只留在调用栈，避免放大历史存储。"""
    result = {"state": "unknown", "checked_at": time.time(), "repairable": False, "reason": ""}
    try:
        source_hash = str(item.get("source_hash") or "").lower()
        target_hash = str(item.get("hash") or item.get("to_download_id") or "").lower()
        if not source_hash or source_hash != target_hash:
            raise PathRepairBlocked("源/目标 infohash 不一致")
        source = plugin.service_info(item["source_downloader"])
        target = plugin.service_info(item.get("downloader") or item.get("to_download"))
        if not source or not target or target.type != "transmission":
            raise PathRepairBlocked("当前路径修复仅支持 Transmission 目标")
        st, tt = _one(plugin, source, source_hash), _one(plugin, target, target_hash)
        sf, tf = read_files(source, source_hash), read_files(target, target_hash)
        if [(i, s) for i, _, s in sf] != [(i, s) for i, _, s in tf]:
            raise PathRepairBlocked("源/目标文件索引、数量或大小不一致")
        differences = [{"index": a[0], "source": a[1], "target": b[1]} for a, b in zip(sf, tf) if a[1] != b[1]]
        result.update(state="mismatch" if differences else "matched", count=len(differences), differences=differences[:20])
        if not differences:
            result["reason"] = "源、目标内部路径一致"
            return result
        # 手工修复只接受统一根名称替换；多段/多文件改名中途失败难以原子恢复。
        sr = {n.split("/")[0] for _, n, _ in sf}
        tr = {n.split("/")[0] for _, n, _ in tf}
        if len(sr) != 1 or len(tr) != 1 or sr == tr:
            raise PathRepairBlocked("检测到路径差异；当前仅支持唯一根名称对齐")
        new, old = next(iter(sr)), next(iter(tr))
        if any(a[1] != new + b[1][len(old):] for a, b in zip(sf, tf)):
            raise PathRepairBlocked("内部相对路径不一致，不能仅修正根名称")
        source_complete = (field(st, "progress", default=0) == 1 if source.type == "qbittorrent"
                           else torrent_is_complete(st, source.type))
        if not source_complete:
            raise PathRepairBlocked("源任务尚未完整，保留现场")
        if str(get_torrent_state(tt, target.type)) != "stopped":
            raise PathRepairBlocked("目标必须已暂停；本功能不会自动暂停运行中的任务")
        if field(tt, "error", default=0):
            raise PathRepairBlocked("目标存在错误，需先处理后再修复路径")
        directory = get_save_path(tt, target.type)
        result.update(old_root=old, new_root=new, directory=directory)
        _disk_guard(target.instance.trc, directory, sf, old)
        fingerprint = [source_hash, item["source_downloader"], target.name, directory, sf, tf]
        result.update(repairable=True, token=hashlib.sha256(json.dumps(fingerprint, ensure_ascii=True).encode()).hexdigest(), reason="可仅对齐目标内部根名称；修复后必须校验，源任务保留")
    except PathRepairBlocked as exc:
        result["reason"] = str(exc)
    except Exception:
        # 底层异常可能携带 RPC 凭据或 tracker URL，不向历史和 UI 回传。
        result["reason"] = "路径查询或文件现场核验失败；未执行修复"
    return result


def repair(plugin, item, token):
    """调用者持有队列锁。执行时重读预检；不接收浏览器传入的路径。"""
    from .pipeline import save_transaction
    from .recheck import ensure_seed_recheck_worker
    from ...utils.config import observe_only

    if observe_only(plugin, "transfer") or plugin._event.is_set():
        raise PathRepairBlocked("转移处于观察模式或已停止，不允许修复")
    preview = diagnose(plugin, item)
    if not token or not preview.get("repairable") or preview.get("token") != token:
        raise PathRepairBlocked(preview["reason"] if not preview.get("repairable") else "文件现场已变化，请重新检测")
    service = plugin.service_info(item.get("downloader") or item.get("to_download"))
    # 在任何 RPC 写入前持久化专用隔离阶段，意外退出不会走原流程删目标/删源。
    item.update(downloader=service.name, hash=item.get("hash") or item["to_download_id"],
                phase="path_repair_verifying", path_repair_status="renaming", path_diagnostic=preview,
                path_repair_started_at=time.time(), target_verification_started=False, skipverify=False,
                source_deleted=False, target_confirmed=False)
    save_transaction(plugin, item)
    try:
        if plugin._event.is_set():
            raise PathRepairBlocked("插件已停止，取消路径修复")
        # 单次根改名：没有磁盘 rename/remove/move，也不执行下载任务删除。
        service.instance.trc.rename_torrent_path(item["hash"], preview["old_root"], preview["new_root"])
        after = diagnose(plugin, item)
        if after.get("state") != "matched":
            raise PathRepairBlocked("接口返回后路径仍未对齐，请重新检测；不自动回滚磁盘")
        if plugin._event.is_set():
            raise PathRepairBlocked("路径已对齐，但插件已停止；保留暂停任务待重新检测")
        if service.instance.recheck_torrents(ids=[item["hash"]]) is False:
            raise PathRepairBlocked("目标拒绝校验；保留暂停任务，未恢复或删源")
        item.update(path_repair_status="verifying", path_diagnostic=after, target_verification_started=True)
        save_transaction(plugin, item)
        ensure_seed_recheck_worker(plugin)
    except Exception:
        item.update(path_repair_status="blocked", error="路径修复或校验提交失败；保留源与目标，请重新检测")
        save_transaction(plugin, item)
        raise PathRepairBlocked(item["error"]) from None
    return {"code": 0, "msg": "目标内部路径已对齐，已提交真实校验；源任务保留", "diagnostic": after}


def detect_automatic(plugin, item):
    """限频只读检测；可选自动修复也必须经过与手动相同的安全门。"""
    if getattr(plugin, "_transfer_path_detect_enabled", False) is not True:
        return False
    if item.get("phase") == "path_repair_verifying":
        return True
    previous = item.get("path_diagnostic") or {}
    result = previous if time.time() - previous.get("checked_at", 0) < 60 else diagnose(plugin, item)
    item["path_diagnostic"] = result
    if result.get("state") != "mismatch":
        return False
    if getattr(plugin, "_transfer_path_auto_repair", False) and result.get("repairable") and not item.get("path_repair_status"):
        try:
            repair(plugin, item, result["token"])
        except PathRepairBlocked as exc:
            item["error"] = str(exc)
    return True


def advance_repair(plugin, item, service, task):
    """专用续办：绝不回滚删除目标、删源或启动未完成的目标。"""
    from .pipeline import save_source_record
    from .recheck import seed_is_checking, seed_is_ready

    if item.get("path_repair_status") != "verifying" or not item.get("target_verification_started"):
        return False
    state = get_torrent_state(task, service.type) if task is not None else None
    if seed_is_checking(state, service.type):
        return False
    if task is not None and not field(task, "error", default=0) and seed_is_ready(state, service.type, task):
        item.update(phase="completed", path_repair_status="verified", source_result="path_repaired_source_retained", error="")
        # 保留源，不在此处获取/借用任何 H&R 删除许可；是否启动交回正常转移轮次。
        save_source_record(plugin, item)
        return True
    if time.time() - item.get("path_repair_started_at", time.time()) > 120 * 60:
        item.update(path_repair_status="blocked", error="修复后的真实校验未通过或超时；保留源与目标")
        save_source_record(plugin, item)
    return False
