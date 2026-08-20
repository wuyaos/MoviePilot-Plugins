"""将不可信论坛/Feed HTML 转换为保留基本结构的纯文本。"""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser

_BLOCK_START = {"p", "div", "section", "article", "header", "footer", "table", "tr"}
_IGNORED = {"script", "style", "noscript", "form", "button", "svg"}


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored_depth = 0
        self.quote_depth = 0

    def handle_starttag(self, tag: str, attrs):
        tag = _tag(tag)
        if tag in _IGNORED:
            self.ignored_depth += 1
            return
        if self.ignored_depth:
            return
        if tag in _BLOCK_START:
            self._break(2)
        elif tag == "br":
            self._break(1)
        elif tag == "li":
            self._break(1)
            self.parts.append("- ")
        elif tag == "blockquote":
            self._break(2)
            self.quote_depth += 1
            self.parts.append("> ")

    def handle_endtag(self, tag: str):
        tag = _tag(tag)
        if tag in _IGNORED:
            self.ignored_depth = max(0, self.ignored_depth - 1)
            return
        if self.ignored_depth:
            return
        if tag in _BLOCK_START:
            self._break(2)
        elif tag == "li":
            self._break(1)
        elif tag == "blockquote":
            self.quote_depth = max(0, self.quote_depth - 1)
            self._break(2)

    def handle_data(self, data: str):
        if self.ignored_depth or not data:
            return
        text = re.sub(r"[\t\r\f\v ]+", " ", data)
        if not text.strip():
            return
        if self.quote_depth and (not self.parts or self.parts[-1].endswith("\n")):
            self.parts.append("> ")
        self.parts.append(text)

    def _break(self, count: int):
        current = "".join(self.parts[-2:])
        trailing = len(current) - len(current.rstrip("\n"))
        if trailing < count:
            self.parts.append("\n" * (count - trailing))


def html_to_text(value: str) -> str:
    parser = _TextParser()
    parser.feed(str(value or ""))
    parser.close()
    return normalize_text("".join(parser.parts))


def normalize_text(value: str) -> str:
    value = _format_markdown_hints(html.unescape(str(value or "")))
    lines: list[str] = []
    for raw in value.splitlines():
        line = re.sub(r"[\t ]+", " ", raw).strip()
        if not line:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        lines.append(line)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _format_markdown_hints(value: str) -> str:
    value = re.sub(r"!\[[^\]]*\]\(https?://[^)]+\)", "[图片]", value)
    value = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1：\2", value)
    value = re.sub(r"\s+>\s+", "\n> ", value)
    value = re.sub(r"(?<=\S)\s+-\s+(?=\S)", "\n- ", value)
    return value


def _tag(tag: str) -> str:
    return tag.rsplit(":", 1)[-1].lower()
