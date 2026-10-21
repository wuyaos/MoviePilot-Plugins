"""Conservative DOM evidence; synthetic selectors are not production certification."""
import re
from lxml import html
from ..core.models import Evidence, RewardSummary


def document(page):
    return html.fromstring(page or "<html></html>")


def text(node):
    return " ".join(node.itertext()).strip()


def parse_record(page, uid, business_date):
    root = document(page)
    buttons = root.xpath('//button | //input[@type="submit"]')
    button = next((text(node) or node.get("value", "") for node in buttons
                   if "签" in (text(node) or node.get("value", ""))), "")
    # Require the UID link inside the actual record row, never a page-wide success word.
    for row in root.xpath('//tr'):
        links = row.xpath('.//a[@href]')
        ids = [re.search(r'(?:uid=|space-uid-)(\d+)', link.get('href', '')) for link in links]
        ids += [re.search(r'/u/(\d+)(?:/|$)', link.get('href', '')) for link in links]
        if not any(match and match.group(1) == uid for match in ids):
            continue
        row_text = text(row)
        dates = re.findall(r'\d{4}-\d{2}-\d{2}', row_text)
        if business_date not in dates:
            continue
        states = [text(cell) for cell in row.xpath('./td')]
        status = next((value for value in states if value in ("已签到", "签到成功", "未签到")), "")
        return Evidence(button, uid, business_date, status), row
    return Evidence(button_text=button), None


def reward_from_row(row):
    if row is None:
        return None
    value = text(row)
    money = re.search(r'大洋[：:\s]*(\d+(?:\.\d+)?)', value)
    days = re.search(r'累计签到[：:\s]*(\d+)\s*天', value)
    return RewardSummary(current_balance=money.group(1) if money else None,
                         recent_activity=days.group(0) if days else None, unit="大洋")
