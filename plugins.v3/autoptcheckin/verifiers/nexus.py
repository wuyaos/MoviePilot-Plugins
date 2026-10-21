"""保守的 Nexus 页面定位；合成夹具不能证明生产页面兼容性。"""
import re
from lxml import html
from ..core.models import Evidence


class NexusVerifier:
    button_xpath = '//button[@id="sign_in"]'
    signed_texts = ()

    def identity(self, page):
        tree = html.fromstring(page)
        # 只认账号导航区，不拿排行榜里第一个用户冒充本人。
        links = tree.xpath('//*[@id="info_block" or @id="user-info"]//a[contains(@href,"userdetails.php?id=")]/@href')
        ids = {m.group(1) for link in links if (m := re.search(r'userdetails\.php\?id=(\d+)', link))}
        return next(iter(ids)) if len(ids) == 1 else ''

    def parse_login(self, page):
        return Evidence(uid=self.identity(page) or None)

    def preflight(self, page):
        tree = html.fromstring(page)
        buttons = tree.xpath(self.button_xpath)
        # 只认签到控件本身；全页匹配会被排行榜/说明文字中的“已签到”污染。
        button_text = ' '.join((node.get('value') or node.text_content()).strip()
                               for node in buttons)
        if any(text in button_text for text in self.signed_texts):
            return 'already'
        if len(buttons) == 1 and buttons[0].get('disabled') is None:
            return 'unsigned'
        return 'unknown'

    def parse(self, page, uid, business_date):
        tree = html.fromstring(page)
        buttons = tree.xpath(self.button_xpath)
        button = ''
        if len(buttons) == 1:
            button = (buttons[0].get('value') or buttons[0].text_content()).strip()
        identity = self.identity(page)
        if identity and uid and identity != uid:
            return Evidence(button_text=button, uid=identity)
        target = uid or identity
        matches = []
        for row in tree.xpath('//tr'):
            row_uid = row.get('data-uid', '')
            links = row.xpath('.//a[contains(@href,"userdetails.php?id=")]/@href')
            ids = {m.group(1) for link in links if (m := re.search(r'userdetails\.php\?id=(\d+)', link))}
            if not row_uid and len(ids) == 1:
                row_uid = next(iter(ids))
            if not target or row_uid != target:
                continue
            text = row.text_content()
            dates = re.findall(r'(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)', text)
            states = row.xpath('./td[@class="status"]/text()')
            state = states[0].strip() if len(states) == 1 else ''
            if not state:
                found = re.findall(r'未签到|已签到|签到成功|not_signed|success|already|failed', text)
                state = found[0] if len(found) == 1 else ''
            if dates == [business_date]:
                matches.append(Evidence(button_text=button, uid=row_uid, date=dates[0], status=state))
        if len(matches) == 1:
            return matches[0]
        return Evidence(button_text=button, uid=identity or None)
