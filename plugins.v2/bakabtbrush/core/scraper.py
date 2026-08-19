"""BakaBT 只读抓取与 HTML 解析。"""

from __future__ import annotations

import html as html_lib
import re
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

from .models import AccountSnapshot, BakaBTTorrent, BrowsePage, DetailPage


BASE_URL = "https://bakabt.me"
BROWSE_URL = f"{BASE_URL}/browse.php"
_ALLOWED_HOSTS = {"bakabt.me", "www.bakabt.me"}
_USER_AGENT = "Mozilla/5.0 (MoviePilot BakaBTBrush)"


class BakaBTError(RuntimeError):
    """不含 Cookie、请求头或私密下载 URL 的安全错误信息。"""


class BakaBTAuthError(BakaBTError):
    """站点返回登录页或认证失败。"""


def parse_size_mb(value: str) -> float | None:
    """把 BakaBT 显示的体积统一换算为 MB；GB 按 1024 MB 计算。"""
    match = re.search(r"([\d,.]+)\s*([kmgt]?i?b|[kmgt])?\b", value or "", re.IGNORECASE)
    if not match:
        return None
    try:
        number = float(match.group(1).replace(",", ""))
    except ValueError:
        return None

    unit = (match.group(2) or "b").lower()
    multipliers = {
        "b": 1 / (1024 * 1024),
        "k": 1 / 1024,
        "kb": 1 / 1024,
        "kib": 1 / 1024,
        "m": 1,
        "mb": 1,
        "mib": 1,
        "g": 1024,
        "gb": 1024,
        "gib": 1024,
        "t": 1024 * 1024,
        "tb": 1024 * 1024,
        "tib": 1024 * 1024,
    }
    return round(number * multipliers.get(unit, 1), 2)


def parse_browse_html(source: str, base_url: str = BASE_URL) -> BrowsePage:
    parser = _BrowseParser()
    parser.feed(source)
    parser.close()
    parser.finish()

    torrents = []
    for row in parser.rows:
        if not row["title"] or not row["detail_path"] or row["size_mb"] is None:
            continue
        torrents.append(BakaBTTorrent(
            torrent_id=row["torrent_id"],
            title=row["title"],
            detail_url=_to_bakabt_url(base_url, row["detail_path"]),
            size_mb=row["size_mb"],
            added_text=row["added_text"],
            published_at=row["published_at"],
            is_freeleech=row["is_freeleech"],
        ))

    account_url = (
        _to_bakabt_url(base_url, parser.account_path)
        if parser.account_path else None
    )
    return BrowsePage(torrents=torrents, account_url=account_url)


def parse_detail_html(source: str, base_url: str = BASE_URL) -> DetailPage:
    parser = _DetailParser()
    parser.feed(source)
    parser.close()
    return DetailPage(
        is_freeleech=parser.is_freeleech,
        published_at=_timestamp_to_datetime(parser.timestamp),
        download_url=(
            _to_bakabt_url(base_url, parser.download_path)
            if parser.download_path else None
        ),
        infohash=_extract_infohash(" ".join(parser.download_text_parts)),
    )


def parse_account_html(source: str) -> AccountSnapshot:
    text = _html_to_text(source)
    uploaded = _extract_labeled_size_mb(text, "Uploaded")
    downloaded = _extract_labeled_size_mb(text, "Downloaded")
    ratio_match = re.search(r"Share\s+ratio\s+([^\s]+)", text, re.IGNORECASE)
    ratio = ratio_match.group(1) if ratio_match else ""
    return AccountSnapshot(uploaded_mb=uploaded, downloaded_mb=downloaded, ratio=ratio)


def _extract_labeled_size_mb(text: str, label: str) -> float | None:
    match = re.search(
        rf"\b{re.escape(label)}\s+([\d,.]+\s*(?:[KMGT]?i?B|[KMGT]))\b",
        text,
        re.IGNORECASE,
    )
    return parse_size_mb(match.group(1)) if match else None


def _html_to_text(source: str) -> str:
    source = re.sub(r"<(script|style)\b[^>]*>[\s\S]*?</\1>", " ", source, flags=re.IGNORECASE)
    source = re.sub(r"<[^>]+>", " ", source)
    return re.sub(r"\s+", " ", html_lib.unescape(source)).strip()


def _timestamp_to_datetime(value: int | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(value, timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _extract_infohash(value: str) -> str | None:
    match = re.search(r"\binfo\s*hash\s*:\s*([a-f0-9]{40})\b", value or "", re.IGNORECASE)
    return match.group(1).lower() if match else None


def _classes(attrs: dict[str, str]) -> set[str]:
    return set((attrs.get("class") or "").split())


def _clean(value: str) -> str:
    return " ".join((value or "").split())


def _to_bakabt_url(base_url: str, path: str) -> str:
    result = urljoin(base_url.rstrip("/") + "/", path)
    _validate_bakabt_url(result)
    return result


def _validate_bakabt_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_HOSTS:
        raise BakaBTError("BakaBT 请求地址无效")


def _is_login_page(source: str) -> bool:
    text = source.lower()
    has_password = "type=\"password\"" in text or "type='password'" in text or "name=\"password\"" in text
    has_login = "login.php" in text or "sign in" in text
    return has_password and has_login


class _BrowseParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict[str, Any]] = []
        self.account_path: str | None = None
        self._row: dict[str, Any] | None = None
        self._cell_classes: set[str] = set()
        self._in_title_link = False

    def handle_starttag(self, tag: str, raw_attrs: list[tuple[str, str | None]]) -> None:
        attrs = {key.lower(): value or "" for key, value in raw_attrs}
        classes = _classes(attrs)

        if tag == "a" and "username" in classes and attrs.get("href", "").startswith("/user/"):
            self.account_path = attrs["href"]

        if tag == "tr" and "torrent" in classes:
            self._finish_row()
            self._row = {
                "title_parts": [], "detail_path": "", "added_parts": [], "size_parts": [],
                "timestamp": None, "is_freeleech": False,
            }
            self._cell_classes = set()
            self._in_title_link = False
            return

        if self._row is None:
            return
        if tag == "td":
            self._cell_classes = classes
        elif "freeleech" in classes:
            self._row["is_freeleech"] = True
        elif tag == "span" and "datetime" in classes and "added" in self._cell_classes:
            timestamp = attrs.get("data-timestamp", "")
            if timestamp.isdigit():
                self._row["timestamp"] = int(timestamp)
        elif tag == "a" and "name" in self._cell_classes and "title" in classes:
            self._row["detail_path"] = attrs.get("href", "")
            self._in_title_link = True

    def handle_endtag(self, tag: str) -> None:
        if self._row is None:
            return
        if tag == "a":
            self._in_title_link = False
        elif tag == "td":
            self._cell_classes = set()
        elif tag == "tr":
            self._finish_row()

    def handle_data(self, data: str) -> None:
        if self._row is None:
            return
        if self._in_title_link:
            self._row["title_parts"].append(data)
        if "added" in self._cell_classes:
            self._row["added_parts"].append(data)
        if "size" in self._cell_classes:
            self._row["size_parts"].append(data)

    def finish(self) -> None:
        self._finish_row()

    def _finish_row(self) -> None:
        if self._row is None:
            return
        detail_path = self._row["detail_path"]
        torrent_match = re.search(r"/torrent/(\d+)(?:/|$)", detail_path)
        title = _clean(" ".join(self._row["title_parts"]))
        added_text = _clean(" ".join(self._row["added_parts"]))
        size_text = _clean(" ".join(self._row["size_parts"]))
        self.rows.append({
            "torrent_id": torrent_match.group(1) if torrent_match else "",
            "title": title,
            "detail_path": detail_path,
            "size_mb": parse_size_mb(size_text),
            "added_text": added_text,
            "published_at": _timestamp_to_datetime(self._row["timestamp"]),
            "is_freeleech": self._row["is_freeleech"],
        })
        self._row = None
        self._cell_classes = set()
        self._in_title_link = False


class _DetailParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.is_freeleech = False
        self.timestamp: int | None = None
        self.download_path: str | None = None
        self.download_text_parts: list[str] = []
        self._in_download_link = False

    def handle_starttag(self, tag: str, raw_attrs: list[tuple[str, str | None]]) -> None:
        attrs = {key.lower(): value or "" for key, value in raw_attrs}
        classes = _classes(attrs)
        if "freeleech" in classes:
            self.is_freeleech = True
        if tag == "span" and "datetime" in classes:
            timestamp = attrs.get("data-timestamp", "")
            if timestamp.isdigit():
                self.timestamp = int(timestamp)
        if tag == "a":
            href = attrs.get("href", "")
            title = attrs.get("title", "").lower()
            is_torrent_link = href.lower().endswith(".torrent") and (
                "download_link" in classes or "download .torrent" in title
            )
            if is_torrent_link:
                self.download_path = href
                self._in_download_link = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self._in_download_link = False

    def handle_data(self, data: str) -> None:
        if self._in_download_link:
            self.download_text_parts.append(data)


class BakaBTClient:
    """复用一个 Cookie 的 BakaBT 只读客户端；所有地址限制在 bakabt.me。"""

    def __init__(self, cookie: str, timeout: int = 20, detail_retries: int = 3) -> None:
        self._cookie = (cookie or "").strip()
        self._timeout = max(1, int(timeout))
        self._detail_retries = max(0, int(detail_retries))

    def fetch_browse(self) -> BrowsePage:
        source = self._get_text(BROWSE_URL, retries=0)
        if _is_login_page(source):
            raise BakaBTAuthError("BakaBT 返回登录页，Cookie 可能已失效")
        page = parse_browse_html(source)
        if not page.torrents:
            raise BakaBTError("未识别到 BakaBT 种子列表，页面结构可能已变化")
        return page

    def fetch_detail(self, detail_url: str) -> DetailPage:
        source = self._get_text(detail_url, retries=self._detail_retries)
        if _is_login_page(source):
            raise BakaBTAuthError("BakaBT 返回登录页，Cookie 可能已失效")
        return parse_detail_html(source)

    def fetch_account(self, account_url: str) -> AccountSnapshot:
        source = self._get_text(account_url, retries=0)
        if _is_login_page(source):
            raise BakaBTAuthError("BakaBT 返回登录页，Cookie 可能已失效")
        return parse_account_html(source)

    def fetch_torrent(self, download_url: str) -> bytes:
        content = self._get_bytes(download_url, retries=self._detail_retries)
        if not content.startswith(b"d"):
            raise BakaBTError("BakaBT 种子文件响应无效")
        return content

    def _get_text(self, url: str, retries: int) -> str:
        response = self._request(url, retries)
        return response.text

    def _get_bytes(self, url: str, retries: int) -> bytes:
        response = self._request(url, retries)
        return bytes(response.content)

    def _request(self, url: str, retries: int):
        _validate_bakabt_url(url)
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                from app.utils.http import RequestUtils

                response = RequestUtils(
                    headers={
                        "User-Agent": _USER_AGENT,
                        "Accept": "text/html,application/xhtml+xml,application/x-bittorrent,*/*;q=0.8",
                        "Cookie": self._cookie,
                    },
                    timeout=self._timeout,
                ).get_res(url=url)
                if not response:
                    raise BakaBTError("BakaBT 无响应")
                status_code = getattr(response, "status_code", 0)
                if status_code in {401, 403}:
                    raise BakaBTAuthError("BakaBT 认证失败，Cookie 可能已失效")
                if status_code != 200:
                    raise BakaBTError(f"BakaBT 请求失败：HTTP {status_code}")
                final_url = getattr(response, "url", url)
                _validate_bakabt_url(final_url)
                return response
            except BakaBTAuthError:
                raise
            except Exception as err:
                last_error = err if isinstance(err, BakaBTError) else BakaBTError("BakaBT 请求失败")
                if attempt >= retries:
                    break
                time.sleep(0.3 * (attempt + 1))
        raise last_error or BakaBTError("BakaBT 请求失败")
