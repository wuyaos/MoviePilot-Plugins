from core.models import SourceAuthMode, SourceKind, SourceSpec
from core.parsers.feed import parse_feed


def source(kind):
    return SourceSpec("s", "x", "Source", kind, "https://example.com/feed", SourceAuthMode.PUBLIC)


def test_rss_parse_guid_content_and_author():
    xml = '''<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
    <channel><item><guid>g1</guid><title>T</title><link>https://e/p/1</link>
    <pubDate>Wed, 19 Aug 2026 10:27:57 GMT</pubDate><dc:creator>A</dc:creator>
    <description><![CDATA[<b>Hello</b> world]]></description></item></channel></rss>'''
    entries = parse_feed(xml, source(SourceKind.RSS))
    assert len(entries) == 1
    assert entries[0].entry_id == "g1"
    assert entries[0].author == "A"
    assert entries[0].content == "Hello world"


def test_atom_empty_and_entry_parse():
    empty = '<feed xmlns="http://www.w3.org/2005/Atom"><title>empty</title></feed>'
    assert parse_feed(empty, source(SourceKind.ATOM)) == []
    xml = '''<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>a1</id><title>T</title>
    <updated>2026-08-19T13:33:11Z</updated><link href="https://e/p/1"/>
    <author><name>U</name></author><summary>Text</summary></entry></feed>'''
    entries = parse_feed(xml, source(SourceKind.ATOM))
    assert entries[0].entry_id == "a1"
    assert entries[0].author == "U"


def test_rss_preserves_paragraph_list_quote_and_rejects_javascript_link():
    xml = '''<rss version="2.0"><channel><item>
    <guid>rich-1</guid><title>结构化正文</title><link>javascript:alert(1)</link>
    <pubDate>Wed, 19 Aug 2026 10:27:57 GMT</pubDate>
    <description><![CDATA[
      <p>第一段</p><p>第二段</p><ul><li>条目一</li><li>条目二</li></ul>
      <blockquote><p>引用文字</p></blockquote>
    ]]></description></item></channel></rss>'''
    entry = parse_feed(xml, source(SourceKind.RSS))[0]
    assert "第一段\n\n第二段" in entry.content
    assert "- 条目一" in entry.content
    assert "- 条目二" in entry.content
    assert "> 引用文字" in entry.content
    assert entry.link == ""


def test_atom_rejects_javascript_alternate_link():
    xml = '''<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>a2</id><title>T</title>
    <updated>2026-08-19T13:33:11Z</updated><link href="javascript:alert(1)"/>
    <summary>Text</summary></entry></feed>'''
    assert parse_feed(xml, source(SourceKind.ATOM))[0].link == ""


def test_nested_feed_content_preserves_tail_text():
    xml = '''<rss version="2.0"><channel><item><guid>tail</guid><title>T</title>
    <pubDate>Wed, 19 Aug 2026 10:27:57 GMT</pubDate>
    <description><p>第一段</p>中间文字<p>第二段</p></description>
    </item></channel></rss>'''
    content = parse_feed(xml, source(SourceKind.RSS))[0].content
    assert "第一段" in content
    assert "中间文字" in content
    assert "第二段" in content
