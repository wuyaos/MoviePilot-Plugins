"""TJUPT image quiz: exact cached text or Douban aHash match; never guess."""
import json
import re
from dataclasses import replace
from io import BytesIO
from urllib.parse import quote, urljoin, urlsplit

from lxml import html
from PIL import Image

from ...core.models import RewardSummary
from ...core.nexus import NexusSignin
from ...core.sitemodel import RecordSpec, page_available


class Tjupt(NexusSignin):
    id = 'tjupt'
    name = 'TJUPT'
    url = 'https://www.tjupt.org/'
    attendance_path = '/attendance.php'
    hook_implemented = True
    record_spec = RecordSpec('//a[@href="attendance.php"]', {'今日已签到': 'signed'})
    answer_key = 'tjupt.answer'
    reward_pattern = re.compile(
        r'(?:这是您的首次签到，本次签到获得|'
        r'签到成功，这是您的第\d+次签到，已连续签到\d+天，本次签到获得|'
        r'重新签到成功，本次签到获得)(\d+)个魔力值')

    @staticmethod
    def image_hash(content):
        with Image.open(BytesIO(content)) as image:
            gray = image.resize((10, 10)).convert('L')
            pixels = [gray.getpixel((x, y)) for y in range(10) for x in range(10)]
        average = sum(pixels) / 100
        return ''.join('1' if pixel > average else '0' for pixel in pixels)

    def read_after(self, ctx, page):
        result = super().read_after(ctx, page)
        if result.evidence:
            result.evidence = replace(result.evidence, button_text=result.evidence.raw_summary)
        return result

    def choose_answer(self, ctx, page):
        tree = html.fromstring(page.text)
        images = tree.xpath('//table[@class="captcha"]//img/@src')
        options = [(node.get('value'), node.tail or '') for node in tree.xpath('//input[@name="answer"]')]
        if len(images) != 1 or not options or any(not value or not text.strip() for value, text in options):
            return None
        image_url = urljoin(self.url, images[0])
        if urlsplit(image_url)[:2] != urlsplit(self.url)[:2]:
            return None
        digest = self.image_hash(ctx.http.get_bytes(image_url))
        cache = ctx.get_data(self.answer_key) if ctx.get_data else {}
        cache = cache if isinstance(cache, dict) else {}
        matches = [(value, text) for value, text in options if text == cache.get(digest)]
        if len(matches) == 1:
            return digest, *matches[0], cache
        if not ctx.public_get:
            return None
        for index, (value, text) in enumerate(options):
            if ctx.cancel.is_set() or (index and ctx.cancel.wait(5)):
                return None
            response = ctx.public_get('https://movie.douban.com/j/subject_suggest?q=' + quote(text))
            if response is None or response.status_code != 200:
                continue
            candidates = json.loads(response.text)
            if isinstance(candidates, dict):
                candidates = [candidates]
            if not isinstance(candidates, list):
                continue
            for candidate in candidates:
                image_url = candidate.get('img') if isinstance(candidate, dict) else None
                # Only Douban's HTTPS image CDN; no station cookies cross this boundary.
                host = urlsplit(image_url or '').hostname or ''
                if urlsplit(image_url or '').scheme != 'https' or not host.endswith('.doubanio.com'):
                    continue
                response = ctx.public_get(image_url, referer='https://movie.douban.com')
                if response is None or response.status_code != 200:
                    continue
                other = self.image_hash(response.content)
                if sum(a == b for a, b in zip(digest, other)) / 100 > 0.9:
                    return digest, value, text, cache
        return None

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
            answer = self.choose_answer(ctx, page)
        except Exception:
            return ctx.result(status='unconfirmed', message='图片或答案未确认，未提交')
        if ctx.cancel.is_set():
            return ctx.result(status='cancelled')
        if answer is None:
            return ctx.result(status='unconfirmed', message='无匹配答案，未提交')
        digest, value, text, cache = answer
        reward = None
        try:
            response = ctx.http.post(url, data=[('answer', value), ('submit', '提交')])
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
            # A numeric reward confirms the selected answer, not the fresh page status.
            if ctx.save_data:
                try:
                    ctx.save_data(self.answer_key, {**cache, digest: text})
                except Exception:
                    result.metadata['answer_cache'] = 'save_failed'
        return result
