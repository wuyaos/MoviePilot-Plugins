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
