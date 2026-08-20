from core.auth.mp_site_cookie import SiteAuth
from core.fetchers.nexus_topic import NexusTopicFetcher
from core.models import SourceAuthMode, SourceKind, SourceSpec


class Response:
    status_code = 200
    headers = {}
    url = "https://pterclub.net/forums.php?action=viewtopic&topicid=1&page=last"
    text = '''<a href="https://evil.example/previous">上一页</a>
    <div><table id="pid1"><tr><td><a href="userdetails.php?id=1">U</a>
    <span title="2026-08-20 08:00:00">now</span></td></tr></table></div>
    <table class="main post"><tr><td>正文标题</td></tr></table>'''

    def raise_for_status(self):
        return None


def test_nexus_rejects_cross_origin_previous_page(monkeypatch):
    monkeypatch.setattr("core.fetchers.common.requests.get", lambda *args, **kwargs: Response())
    source = SourceSpec(
        "pter_digest", "pter", "PTer", SourceKind.NEXUS_TOPIC,
        "https://pterclub.net/forums.php?action=viewtopic&topicid=1&page=last",
        SourceAuthMode.MP_SITE_COOKIE, site_domain="pterclub.net",
    )
    result = NexusTopicFetcher().fetch(source, SiteAuth(cookie="secret", status="mp_site_cookie"))
    assert result.success is False
    assert "非同源" in result.error
