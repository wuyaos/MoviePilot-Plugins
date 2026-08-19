from __future__ import annotations

from datetime import datetime, timezone
from types import ModuleType, SimpleNamespace
import sys

import pytest

from core.scraper import (
    BakaBTClient,
    BakaBTError,
    parse_account_html,
    parse_browse_html,
    parse_detail_html,
    parse_size_mb,
)


BROWSE_HTML = """
<a class="username" href="/user/2081582/example">example</a>
<table class="torrents"><tbody>
<tr class="torrent alt0 new">
  <td class="category"></td>
  <td class="name"><a class="title" href="/torrent/360859/example">Example <em>Anime</em></a><span class="icon freeleech" title="Freeleech"></span></td>
  <td class="added">today</td><td class="size">1.5 GB</td><td class="peers">1 / 1 / 1</td>
</tr>
<tr class="torrent alt1">
  <td class="category"></td>
  <td class="name"><a class="title" href="/torrent/360858/normal">Normal</a></td>
  <td class="added"><span class="datetime" data-timestamp="1787088936">18 Aug '26</span></td>
  <td class="size">148 MB</td><td class="peers">1 / 1 / 1</td>
</tr>
</tbody></table>
"""

DETAIL_HTML = """
<span class="icon freeleech" title="Freeleech"></span>
<span class="datetime" data-timestamp="1787088936">date</span>
<a class="download_link" href="/download/360859/token/example.torrent" title="Download .torrent">
Download torrent: example.torrent 148 MB info hash: bcd1548f0436b22517c8bce05ff96c896878fce8
</a>
"""

ACCOUNT_HTML = """
<div>Uploaded 1.50 GB - (0.00 KB/s)</div>
<div>Downloaded 512 MB - (0.00 KB/s)</div>
<div>Share ratio 3.00</div>
"""


def test_size_is_normalized_to_mb():
    assert parse_size_mb("1.5 GB") == 1536
    assert parse_size_mb("148 MB") == 148
    assert parse_size_mb("1024 KB") == 1
    assert parse_size_mb("") is None


def test_browse_parser_extracts_freeleech_title_size_time_and_account_url():
    page = parse_browse_html(BROWSE_HTML)

    assert page.account_url == "https://bakabt.me/user/2081582/example"
    assert len(page.torrents) == 2
    free = page.torrents[0]
    assert free.torrent_id == "360859"
    assert free.title == "Example Anime"
    assert free.is_freeleech is True
    assert free.size_mb == 1536
    assert free.published_at is None
    assert free.added_text == "today"

    dated = page.torrents[1]
    assert dated.published_at == datetime(2026, 8, 18, 21, 35, 36, tzinfo=timezone.utc)


def test_detail_parser_rechecks_freeleech_and_extracts_private_download_path():
    detail = parse_detail_html(DETAIL_HTML)

    assert detail.is_freeleech is True
    assert detail.download_url == "https://bakabt.me/download/360859/token/example.torrent"
    assert detail.infohash == "bcd1548f0436b22517c8bce05ff96c896878fce8"
    assert detail.published_at == datetime(2026, 8, 18, 21, 35, 36, tzinfo=timezone.utc)


def test_account_parser_extracts_total_transfer_and_ratio():
    account = parse_account_html(ACCOUNT_HTML)

    assert account.uploaded_mb == 1536
    assert account.downloaded_mb == 512
    assert account.ratio == "3.00"


def test_client_constructs_moviepilot_requestutils_path(monkeypatch):
    captured = {}

    class FakeRequestUtils:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def get_res(self, *, url):
            captured["url"] = url
            return SimpleNamespace(status_code=200, text=BROWSE_HTML, content=BROWSE_HTML.encode(), url=url)

    app = ModuleType("app")
    utils = ModuleType("app.utils")
    http = ModuleType("app.utils.http")
    http.RequestUtils = FakeRequestUtils
    monkeypatch.setitem(sys.modules, "app", app)
    monkeypatch.setitem(sys.modules, "app.utils", utils)
    monkeypatch.setitem(sys.modules, "app.utils.http", http)

    page = BakaBTClient("bbtid=test", timeout=12).fetch_browse()

    assert len(page.torrents) == 2
    assert captured["url"] == "https://bakabt.me/browse.php"
    assert captured["timeout"] == 12
    assert captured["headers"]["Cookie"] == "bbtid=test"


def test_external_detail_url_is_rejected():
    with pytest.raises(BakaBTError):
        parse_detail_html('<a class="download_link" href="https://evil.example/a.torrent" title="Download .torrent">x</a>')
