"""Discuz dynamic sign link; receipt never replaces the fresh button/own row."""
import re
from dataclasses import replace
from datetime import date
from urllib.parse import parse_qs, urljoin, urlsplit

from lxml import html

from ...core.nexus import NexusSignin, SigninForm
from ...core.sitemodel import RecordSpec, page_available


class Yzyy(NexusSignin):
    id = 'yzyy'
    name = 'yzyy'
    url = 'https://yzyy.org/'
    attendance_path = '/plugin.php?id=zqlj_sign'
    hook_implemented = True
    record_spec = RecordSpec('//div[contains(concat(" ", normalize-space(@class), " "), " signbtn ")]', {'今日已打卡': 'signed', '点击打卡': 'unsigned'})

    def discover_form(self, ctx, page):
        before = self.read_before(ctx, page)
        if (ctx.credential.uid and before.evidence and before.evidence.uid
                and str(ctx.credential.uid) != before.evidence.uid):
            return None
        tree = html.fromstring(page.text)
        buttons = tree.xpath(self.record_spec.message)
        if len(buttons) != 1:
            return None
        links = buttons[0].xpath('.//a/@href')
        if len(links) != 1:
            return None
        action = urljoin(self.url, links[0])
        parsed = urlsplit(action)
        query = parse_qs(parsed.query)
        tokens = query.get('sign', [])
        if (parsed[:2] != urlsplit(self.url)[:2] or parsed.path != '/plugin.php'
                or query.get('id') != ['zqlj_sign'] or len(tokens) != 1
                or not re.fullmatch(r'[a-fA-F0-9]{8}', tokens[0])):
            return None
        return SigninForm(action, [], urljoin(self.url, self.attendance_path))

    def submit(self, ctx, form):
        ctx.http.get(form.action, referer=form.referer)

    def read_after(self, ctx, page):
        result = super().read_after(ctx, page)
        evidence = result.evidence
        if not evidence or not page_available(page) or self.parse_login(page).status == 'auth_failed':
            return result
        tree = html.fromstring(page.text)
        # Login identity must come from navigation, never the first leaderboard link.
        links = tree.xpath('//*[@id="um"]//a/@href')
        uids = {match.group(1) for link in links
                if (match := re.search(r'space-uid-(\d+)\.html', link))}
        uid = next(iter(uids)) if len(uids) == 1 else None
        record_date, row_status = '', ''
        if uid:
            rows = tree.xpath('//*[@id="tb_my"]//tr[.//a[@href="space-uid-' + uid + '.html"]]')
            if len(rows) == 1:
                text = rows[0].text_content()
                match = re.search(r'\d{4}-\d{2}-\d{2}', text)
                record_date = match.group(0) if match else ''
                if record_date == date.today().isoformat():
                    row_status = 'signed' if '今日已打卡' in text else ('unsigned' if '未打卡' in text else '')
        status = evidence.status
        if row_status:
            status = row_status if status in ('unconfirmed', row_status) else 'unconfirmed'
        if ctx.credential.uid and uid and str(ctx.credential.uid) != uid:
            status = 'unconfirmed'
        result.evidence = replace(evidence, button_text=evidence.raw_summary,
                                  uid=uid, date=record_date, status=status)
        result.status = type(result.status)({'signed': 'success', 'unsigned': 'failed'}.get(status, 'unconfirmed'))
        return result

    def read_before(self, ctx, page):
        result = self.read_after(ctx, page)
        if result.status == 'success':
            result.status = type(result.status)('already')
        return result
