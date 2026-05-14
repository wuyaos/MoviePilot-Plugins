# input: none (pure functions, no external I/O)
# output: path utilities, FileItem conversion, gRPC error helpers
# pos: shared utilities for cd2_client / cd2_upload / cd2_api; no gRPC calls, no side effects
import re
from pathlib import PurePosixPath
from typing import Any, List, Optional

import grpc

from app.schemas import FileItem


def normalize_api_key(api_key: str) -> str:
    token = (api_key or "").strip().strip('"').strip("'")
    token = token.replace("\r", "").replace("\n", "").strip()
    token = re.sub(r"[\u200b-\u200f\u2060\ufeff]", "", token)
    if token.lower().startswith("authorization:"):
        token = token.split(":", 1)[1].strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return "".join(token.split())


def normalize_path(path: str) -> str:
    if not path:
        return "/"
    value = path.replace("\\", "/")
    if not value.startswith("/"):
        value = f"/{value}"
    value = str(PurePosixPath(value))
    if not value.startswith("/"):
        value = f"/{value}"
    return value


def join_path(parent_path: str, name: str) -> str:
    parent = str(PurePosixPath(parent_path))
    if parent in ("", "."):
        parent = "/"
    return f"/{name}" if parent == "/" else f"{parent}/{name}"


def to_cloud_path(path: str, token_root: str) -> str:
    normalized = normalize_path(path)
    if token_root == "/":
        return normalized
    if normalized == "/":
        return token_root
    if normalized == token_root or normalized.startswith(f"{token_root}/"):
        return normalized
    return join_path(token_root, normalized.lstrip("/"))


def strip_trailing_slash(path: str) -> str:
    """Normalize path and strip trailing slash (except root '/')."""
    value = to_cloud_path(path, "/")
    return value if value == "/" else value.rstrip("/")


def timestamp_to_int(timestamp: Any) -> Optional[int]:
    if not timestamp:
        return None
    seconds = getattr(timestamp, "seconds", None)
    if seconds is None:
        return None
    try:
        value = int(seconds)
        return value if value > 0 else None
    except Exception:
        return None


def rpc_error_text(error: grpc.RpcError) -> str:
    code = error.code()
    details = error.details() if hasattr(error, "details") else str(error)
    return f"{getattr(code, 'name', 'UNKNOWN')}: {details}"


def is_success(resp: Any) -> bool:
    if resp is None:
        return False
    if hasattr(resp, "success"):
        return bool(getattr(resp, "success"))
    if hasattr(resp, "result") and hasattr(resp.result, "success"):
        return bool(resp.result.success)
    return True


def result_paths(resp: Any) -> List[str]:
    paths = getattr(resp, "resultFilePaths", None)
    return list(paths) if paths else []


def human_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB", "PB", "EB"]
    i, value = 0, float(size_bytes)
    while value >= 1024 and i < len(units) - 1:
        value /= 1024
        i += 1
    return f"{value:.2f} {units[i]}"


def to_file_item(cloud_file: Any, disk_name: str) -> FileItem:
    is_dir = bool(getattr(cloud_file, "isDirectory", False))
    raw_path = getattr(cloud_file, "fullPathName", None) or "/"
    file_path = normalize_path(str(raw_path))
    if is_dir and file_path != "/":
        file_path = f"{file_path.rstrip('/')}/"

    name = getattr(cloud_file, "name", "")
    if not name:
        name = "/" if file_path == "/" else PurePosixPath(file_path.rstrip("/")).name

    pure_name = PurePosixPath(name)
    basename = name if is_dir else pure_name.stem
    extension = None if is_dir else (pure_name.suffix[1:] if pure_name.suffix else None)

    normalized_no_suffix = file_path if file_path == "/" else file_path.rstrip("/")
    fileid = getattr(cloud_file, "id", "") or normalized_no_suffix

    parent_fileid = None
    if normalized_no_suffix != "/":
        parent_path = str(PurePosixPath(normalized_no_suffix).parent)
        parent_fileid = "/" if parent_path in ("", ".") else parent_path

    size = None
    if not is_dir:
        try:
            size = int(getattr(cloud_file, "size", 0) or 0)
        except Exception:
            size = None

    modify_time = timestamp_to_int(getattr(cloud_file, "writeTime", None))
    if modify_time is None:
        modify_time = timestamp_to_int(getattr(cloud_file, "createTime", None))

    return FileItem(
        storage=disk_name,
        fileid=str(fileid),
        parent_fileid=parent_fileid,
        name=name,
        basename=basename,
        extension=extension,
        type="dir" if is_dir else "file",
        path=file_path,
        size=size,
        modify_time=modify_time,
    )


def root_item(disk_name: str) -> FileItem:
    return FileItem(
        storage=disk_name,
        fileid="/",
        parent_fileid=None,
        name="/",
        basename="/",
        extension=None,
        type="dir",
        path="/",
        size=None,
        modify_time=None,
    )
