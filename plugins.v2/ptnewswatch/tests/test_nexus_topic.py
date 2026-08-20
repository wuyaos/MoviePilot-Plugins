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
    assert entries[0].title == "动态消息正文"
    assert entries[0].content == ""
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
    assert entry.title == "NovaHD 开放注册"
    assert entry.content == ""


def test_parse_exact_post_body_excludes_profile_statistics_and_css():
    html = '''<html><body><div><table id="pid193040"><tr><td>
    <a href="userdetails.php?id=1">CrazyL</a>
    <span title="2026-08-20 08:06:00">刚刚</span></td></tr></table></div>
    <table class="main post"><tr>
      <td class="rowfollow">帖子：7129 上传：9.482 TB 下载：73.21 GB 分享率：132.615 做种积分: 847,609.7</td>
      <td class="rowfollow"><div id="pid193040body">
        <a href="https://www.tangpt.top/messages.php?id=1">https://www.tangpt.top/messages.php?id=1</a><br><br>
        1魔力起抽 仅限今明俩天<br>永V数量*77<br>永久彩虹*n<br>添加七夕勋章进奖池
      </div><style>ul.magic { display:none }</style><ul class="magic"><li>猫粮奖励</li></ul></td>
    </tr></table></body></html>'''
    entry = parse_nexus_topic(html, SOURCE)[0]
    assert entry.title == "1魔力起抽 仅限今明俩天"
    assert "https://www.tangpt.top/messages.php?id=1" in entry.content
    assert "永V数量*77" in entry.content
    assert "1魔力起抽" not in entry.content
    for unwanted in ("帖子：7129", "上传：", "分享率", "ul.magic", "猫粮奖励"):
        assert unwanted not in entry.content
