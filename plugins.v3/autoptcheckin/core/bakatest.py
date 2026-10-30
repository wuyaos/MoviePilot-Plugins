"""V2 random-choice bakatest protocol; only fresh scoped evidence sets status."""
import random
import re
from urllib.parse import urljoin

from lxml import html

from .models import RewardSummary
from .nexus import NexusSignin, SigninForm
from .sitemodel import page_available


class BakatestSignin(NexusSignin):
    attendance_path = '/bakatest.php'
    reward_pattern = re.compile(r'(\d+)点魔力值')

    def discover_form(self, ctx, page):
        tree = html.fromstring(page.text)
        forms = tree.xpath('//form[.//input[@name="questionid"] and .//input[@name="choice[]"]]')
        if len(forms) != 1:
            return None
        form = forms[0]
        ids = form.xpath('.//input[@name="questionid"]/@value')
        options = form.xpath('.//input[@name="choice[]" and not(@disabled)]/@value')
        questions = form.xpath('.//td[@class="text" and contains(text(),"请问：")]')
        if len(ids) != 1 or not ids[0] or not options or not all(options) or len(questions) != 1:
            return None
        return SigninForm(urljoin(self.url, self.attendance_path), [
            ('questionid', ids[0]), ('choice[]', random.choice(options)),
            ('usercomment', '太难了！'), ('wantskip', '不会')])

    def signin(self, ctx):
        if ctx.cancel.is_set():
            return ctx.result(status='cancelled')
        url = urljoin(self.url, self.attendance_path)
        try:
            page = ctx.http.get(url)
            login = self.parse_login(page)
            if login.status == 'auth_failed':
                return ctx.result(status='auth_failed', message=login.message)
            if not page_available(page):
                return ctx.result(status='unconfirmed', message='签到页面不可达')
            before = self.read_before(ctx, page)
            if before.status == 'already':
                return before
            form = self.discover_form(ctx, page)
        except Exception:
            return ctx.result(status='unconfirmed', message='问答表单未确认')
        if ctx.cancel.is_set():
            return ctx.result(status='cancelled')
        if form is None:
            return ctx.result(status='unconfirmed', message='问答表单未确认，未提交')
        reward = None
        try:
            response = ctx.http.post(form.action, data=form.data)
            if page_available(response) and self.parse_login(response).status != 'auth_failed':
                match = self.reward_pattern.search(html.fromstring(response.text).text_content())
                reward = match.group(1) if match else None
        except Exception:
            pass
        finally:
            try:
                fresh = ctx.http.get(url)
            except Exception:
                fresh = None
        result = self.read_after(ctx, fresh)
        if reward is not None:
            result.reward = RewardSummary(reported=reward, unit='魔力值')
        return result
