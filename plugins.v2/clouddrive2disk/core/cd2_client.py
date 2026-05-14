# input: cd2_url (http(s)://host:port), api_key string
# output: Cd2Client — gRPC channel, auth metadata, helper RPC methods
# pos: low-level gRPC transport layer for CloudDrive2Disk; used by cd2_api.py and cd2_upload.py
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import grpc
from google.protobuf import empty_pb2

from app.core.config import settings
from app.log import logger

from ..proto import cd2_pb2 as pb2
from ..proto import cd2_pb2_grpc as pb2_grpc
from .cd2_helpers import (
    normalize_api_key,
    normalize_path,
    join_path,
    to_cloud_path,
    rpc_error_text,
    is_success,
)

_GRPC_OPTIONS = [
    ("grpc.max_send_message_length", 20 * 1024 * 1024),
    ("grpc.max_receive_message_length", 20 * 1024 * 1024),
    ("grpc.keepalive_time_ms", 30_000),
    ("grpc.keepalive_timeout_ms", 10_000),
    ("grpc.keepalive_permit_without_calls", 1),
    ("grpc.http2.max_pings_without_data", 0),
]


class Cd2Client:
    """Low-level gRPC client: channel, auth, basic RPC helpers."""

    def __init__(self, cd2_url: str, api_key: str):
        parsed = urlsplit(cd2_url)
        self.scheme = parsed.scheme or "http"
        self.host = parsed.netloc or parsed.path or "127.0.0.1:19798"

        token = normalize_api_key(api_key)
        if not token:
            raise RuntimeError("CloudDrive2 API key 不能为空")

        self._api_key = token
        self._metadata: List[Tuple[str, str]] = [("authorization", f"Bearer {token}")]
        self._token_fp = __import__("hashlib").sha256(token.encode()).hexdigest()[:10]
        self._token_len = len(token)
        self._auth_failed_logged = False

        self._channel = grpc.insecure_channel(self.host, options=_GRPC_OPTIONS)
        self.stub = pb2_grpc.CloudDriveFileSrvStub(self._channel)

        self._probe()
        self.token_root = self._init_token_root()
        self._preflight()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def close(self):
        try:
            if self._channel is not None:
                self._channel.close()
                self._channel = None
        except Exception:
            pass

    def __del__(self):
        self.close()

    # ------------------------------------------------------------------
    # Auth & init
    # ------------------------------------------------------------------
    def _probe(self):
        try:
            self.stub.GetSystemInfo(empty_pb2.Empty())
        except grpc.RpcError as e:
            raise RuntimeError(
                f"CloudDrive2 服务不可用或地址不正确: {self.host}, {rpc_error_text(e)}"
            ) from e

    def _init_token_root(self) -> str:
        try:
            info = self.stub.GetApiTokenInfo(pb2.StringValue(value=self._api_key))
            perms = getattr(info, "permissions", None)
            if perms and hasattr(perms, "allow_list") and not perms.allow_list:
                logger.warning(
                    "【CloudDrive2Disk】当前 API key 未授予目录读取权限 allow_list，插件将无法浏览文件"
                )
            root = normalize_path(getattr(info, "rootDir", "") or "/")
            return root.rstrip("/") or "/"
        except grpc.RpcError as e:
            if e.code() not in (grpc.StatusCode.UNAUTHENTICATED, grpc.StatusCode.UNIMPLEMENTED):
                logger.debug(f"【CloudDrive2Disk】读取 token rootDir 失败: {rpc_error_text(e)}")
            return "/"
        except Exception as e:
            logger.debug(f"【CloudDrive2Disk】读取 token rootDir 失败: {e}")
            return "/"

    def _preflight(self):
        try:
            self.call("GetAccountStatus", empty_pb2.Empty())
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.UNAUTHENTICATED:
                raise RuntimeError(
                    f"CloudDrive2 鉴权失败: endpoint={self.host}, token_fp={self._token_fp}, "
                    "请确认 token 来自当前实例且未过期未删除"
                ) from e

        target = self.token_root or "/"
        try:
            self.list_files(target)
        except grpc.RpcError as e:
            code = e.code()
            if code == grpc.StatusCode.UNAUTHENTICATED:
                raise RuntimeError(
                    f"CloudDrive2 鉴权失败: endpoint={self.host}, token_fp={self._token_fp}"
                ) from e
            if code == grpc.StatusCode.PERMISSION_DENIED:
                raise RuntimeError(
                    f"CloudDrive2 API key 缺少目录读取权限 allow_list: root={target}"
                ) from e

    # ------------------------------------------------------------------
    # Core RPC helpers
    # ------------------------------------------------------------------
    def call(self, method_name: str, request: Any) -> Any:
        rpc = getattr(self.stub, method_name)
        try:
            return rpc(request, metadata=self._metadata)
        except grpc.RpcError:
            raise

    def list_files(self, path: str, force_refresh: bool = False) -> List[Any]:
        req = pb2.ListSubFileRequest(path=path, forceRefresh=force_refresh)
        result: List[Any] = []
        for reply in self.stub.GetSubFiles(req, metadata=self._metadata):
            result.extend(reply.subFiles)
        return result

    def log_auth_error_once(self, action: str, target: str, error: grpc.RpcError):
        if not self._auth_failed_logged:
            logger.error(
                f"【CloudDrive2Disk】CloudDrive2 鉴权失败，请检查 API key 或权限设置 "
                f"(endpoint={self.host}, token_fp={self._token_fp}, token_len={self._token_len})"
            )
            logger.error("【CloudDrive2Disk】请确认 token 来自当前 CloudDrive2 实例，且未过期、未删除")
            self._auth_failed_logged = True
        logger.debug(f"【CloudDrive2Disk】{action}失败: {target}, {rpc_error_text(error)}")

    # ------------------------------------------------------------------
    # Download URL resolution
    # ------------------------------------------------------------------
    def resolve_download_url(self, path: str) -> Tuple[str, Dict[str, str]]:
        req = pb2.GetDownloadUrlPathRequest(
            path=path, preview=False, lazy_read=False, get_direct_url=True
        )
        info = self.call("GetDownloadUrlPath", req)

        headers: Dict[str, str] = {}
        ua = getattr(info, "userAgent", "")
        if ua:
            headers["User-Agent"] = ua
        elif getattr(settings, "USER_AGENT", None):
            headers["User-Agent"] = settings.USER_AGENT

        for k, v in (getattr(info, "additionalHeaders", None) or {}).items():
            headers[str(k)] = str(v)

        direct = getattr(info, "directUrl", "")
        if direct:
            return direct, headers

        dl_path = getattr(info, "downloadUrlPath", "")
        if not dl_path:
            raise RuntimeError("CloudDrive2 未返回下载地址")

        filled = (
            str(dl_path)
            .replace("{SCHEME}", self.scheme)
            .replace("{HOST}", self.host)
            .replace("{PREVIEW}", "false")
        )
        if not filled.startswith("/"):
            filled = f"/{filled}"
        return f"{self.scheme}://{self.host}{filled}", headers

    # ------------------------------------------------------------------
    # Path helpers (relative to token_root)
    # ------------------------------------------------------------------
    def cloud_path(self, path: str) -> str:
        return to_cloud_path(path, self.token_root)

    def norm_dir(self, path: str) -> str:
        v = self.cloud_path(path)
        return v if v == "/" else v.rstrip("/")

    def norm_file(self, path: str) -> str:
        return self.norm_dir(path)
