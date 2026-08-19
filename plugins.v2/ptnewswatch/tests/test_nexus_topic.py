from core.models import SourceAuthMode, SourceKind, SourceSpec
from core.parsers.nexus_topic import extract_previous_page_url, parse_nexus_topic

SOURCE = SourceSpec(
    "pter_digest", "pterclub", "PTER", SourceKind.NEXUS_TOPIC,
    "https://pterclub.net/forums.php?action=viewtopic&topicid=2327&page=last#last",
    SourceAuthMode.MP_SITE_COOKIE,
)


def test_parse_pter_style_header_and_body():
    html = '''<html><body><a href="?action=viewtopic&topicid=2327&page=9"><b>&lt;&lt;上一页</b></a>
    <div><table id="pid192995"><tr><td><a href="?page=p192995#pid192995">#192995</a>
    <span class="nowrap"><a href="userdetails.php?id=1">CrazyL</a></span>
    <span title="2026-08-18 15:55:00">15时前</span></td></tr></table></div>
    <table class="main post"><tr><td class="rowfollow">profile</td><td>动态消息正文</td></tr></table>
    </body></html>'''
    entries = parse_nexus_topic(html, SOURCE)
    assert len(entries) == 1
    assert entries[0].entry_id == "pter_digest:192995"
    assert entries[0].author == "CrazyL"
    assert entries[0].content == "动态消息正文"
    assert entries[0].link.endswith("page=p192995#pid192995")
    assert extract_previous_page_url(html, SOURCE.url).endswith("page=9")


def test_parse_tjupt_text_timestamp():
    source = SourceSpec(
        "tjupt_digest", "tjupt", "TJU", SourceKind.NEXUS_TOPIC,
        "https://www.tjupt.org/forums.php?action=viewtopic&topicid=15461&page=last#last",
        SourceAuthMode.MP_SITE_COOKIE,
    )
    html = '''<div><table id="pid241231"><tr><td><a>#241231</a>
    <a href="userdetails.php?id=1">yang95</a> 2026-08-16 08:14:31</td></tr></table></div>
    <table class="main"><tr><td class="rowfollow">profile</td><td>NovaHD 开放注册</td></tr></table>'''
    entry = parse_nexus_topic(html, source)[0]
    assert entry.entry_id == "tjupt_digest:241231"
    assert entry.author == "yang95"
    assert entry.content == "NovaHD 开放注册"
