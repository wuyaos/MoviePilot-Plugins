# input: qBittorrent URL/credentials, torrent 文件
# output: qB 会话登录、hash 检查、种子提交
# pos: qBittorrent API 客户端层

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.log import logger
from app.utils.http import RequestUtils

from .models import QBSettings

USER_AGENT = "AZ_KeepAlive/1.0"


class QBClient:
    """qBittorrent Web API 客户端"""

    def __init__(self, qb: QBSettings, timeout: int = 30, proxies: dict | None = None):
        self._qb = qb
        self._timeout = timeout
        self._proxies = proxies
        self._session: Any = None

    def _ensure_session(self) -> Any:
        if self._session is not None:
            return self._session
        import requests as req
        self._session = req.Session()
        if self._qb.username or self._qb.password:
            logger.debug(f"登录 qBittorrent: {self._qb.url}")
            resp = self._session.post(
                f"{self._qb.url}/api/v2/auth/login",
                data={"username": self._qb.username, "password": self._qb.password},
                headers={"Referer": self._qb.url, "User-Agent": USER_AGENT},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            if resp.text.strip() not in {"Ok", "Ok."}:
                raise RuntimeError(f"qB 登录失败: {resp.text.strip()}")
        return self._session

    def has_hash(self, infohash: str) -> bool:
        """检查 qBittorrent 是否已有该 infohash"""
        session = self._ensure_session()
        resp = session.get(
            f"{self._qb.url}/api/v2/torrents/info",
            params={"hashes": infohash},
            headers={"Referer": self._qb.url, "User-Agent": USER_AGENT},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            raise RuntimeError("qB torrents/info 返回非列表")
        return any(str(it.get("hash", "")).lower() == infohash for it in data)

    def add_torrent(self, torrent_path: Path) -> None:
        """提交 .torrent 文件到 qBittorrent"""
        session = self._ensure_session()
        with torrent_path.open("rb") as f:
            resp = session.post(
                f"{self._qb.url}/api/v2/torrents/add",
                data={"category": self._qb.category, "tags": self._qb.tags},
                files={"torrents": (torrent_path.name, f, "application/x-bittorrent")},
                headers={"Referer": self._qb.url, "User-Agent": USER_AGENT},
                timeout=self._timeout,
            )
        resp.raise_for_status()
        body = resp.text.strip()
        if body and body != "Ok.":
            raise RuntimeError(f"qB 拒绝种子: {body}")
        logger.info(f"种子已提交 qBittorrent: {torrent_path.name}")


def torrent_infohash(torrent_path: Path) -> str:
    """从 .torrent 文件解析 infohash"""
    try:
        from torf import Torrent
    except ImportError:
        raise RuntimeError("缺少依赖: torf")
    t = Torrent.read(torrent_path)
    return str(t.infohash).lower()
