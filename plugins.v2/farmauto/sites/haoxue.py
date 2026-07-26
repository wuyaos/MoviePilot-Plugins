import html as html_lib
import re
from typing import Any, Dict, List, Optional, Tuple

from .base import FarmSiteConfig, parse_expire_minutes


class HaoxueConfig(FarmSiteConfig):
    site_id = "haoxue"
    site_name = "好学"
    domains = ["www.hxpt.org", "hxpt.org"]
    base_url = "https://www.hxpt.org"
    currency = "火花"
    capabilities = {"harvest_all", "expiry_sale", "warehouse_pagination"}

    @staticmethod
    def _text(fragment: str) -> str:
        text = re.sub(r"<[^>]+>", "", fragment or "")
        return html_lib.unescape(text).replace("\xa0", " ").strip()

    @staticmethod
    def _section(html: str, title_pattern: str) -> str:
        heading = re.search(rf"<h2\b[^>]*>.*?(?:{title_pattern}).*?</h2>", html or "", re.DOTALL | re.IGNORECASE)
        if not heading:
            return html or ""
        following = html[heading.end():]
        next_heading = re.search(r"<h2\b", following, re.IGNORECASE)
        return following[:next_heading.start()] if next_heading else following

    def parse_market_prices(self, html: str) -> Dict[str, int]:
        result: Dict[str, int] = {}
        name_to_key = self.get_name_to_key_map()
        market_html = self._section(html or "", r"菜市场|市场")
        for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", market_html, re.DOTALL | re.IGNORECASE):
            cells = [self._text(cell) for cell in re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.DOTALL | re.IGNORECASE)]
            for index, name in enumerate(cells[:-1]):
                key = name_to_key.get(name)
                price_match = re.search(r"\d+", cells[index + 1])
                if not key or not price_match or key in result:
                    continue
                price = int(price_match.group())
                if 100 <= price <= 20000:
                    result[key] = price
        if len(result) < len(self.crops):
            for name, key in name_to_key.items():
                match = re.search(
                    rf"<td\b[^>]*>\s*{re.escape(name)}\s*</td>\s*(?:<!--.*?-->)?\s*"
                    r"<td\b[^>]*>\s*(\d+)\s*</td>",
                    market_html,
                    re.DOTALL | re.IGNORECASE,
                )
                if match and key not in result and 100 <= int(match.group(1)) <= 20000:
                    result[key] = int(match.group(1))
        return result

    def parse_crop_status(self, html: str) -> Dict[str, Dict]:
        return super().parse_crop_status(html)

    def parse_warehouse_items(self, html: str) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        source = self._section(html or "", r"仓库")
        crop_names = self.get_name_to_key_map()
        for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", source, re.DOTALL | re.IGNORECASE):
            sell_key = re.search(r"action=sell(?:&amp;|&)key=([^&\"']+)", row, re.IGNORECASE)
            if not sell_key:
                continue
            cells = [self._text(cell) for cell in re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.DOTALL | re.IGNORECASE)]
            name_index = next((index for index, value in enumerate(cells) if value in crop_names), None)
            if name_index is None or name_index + 1 >= len(cells):
                continue
            quantity = re.search(r"\d+", cells[name_index + 1])
            if not quantity:
                continue
            times = [value for value in cells[name_index + 2:] if re.search(r"已过期|\d+\s*(?:天|小时|分钟)", value)]
            expire = times[-1] if times else ""
            items.append(self._warehouse_item(cells[name_index], quantity.group(), expire, sell_key.group(1)))
        return items

    def parse_warehouse_page(self, html: str) -> Tuple[List[Dict], Optional[int]]:
        items = self.parse_warehouse_items(html)
        page = re.search(r"页\s*(\d+)\s*共\s*(\d+)", html or "") or re.search(r"第\s*(\d+)\s*/\s*(\d+)\s*页", html or "")
        if page:
            current, total = map(int, page.groups())
            return items, current + 1 if current < total else None
        total = re.search(r'class=["\'][^"\']*pagination-info[^"\']*["\'][^>]*>[^<]*共\s*(\d+)', html or "", re.IGNORECASE)
        return items, 2 if total and int(total.group(1)) > 1 else None

    def get_warehouse_page_url(self, page: int) -> str:
        return f"{self.get_warehouse_url()}&page={page}"

    def parse_bonus(self, html: str) -> Optional[str]:
        match = re.search(r"当前(?:火花|魔力值|魔力)\s*[:：]\s*([\d,.]+)", self._text(html or ""))
        return match.group(1).replace(",", "") if match else None

    def get_sell_key(self, html: str, item_type: str, item_id: int) -> Optional[str]:
        match = re.search(rf"action=sell(?:&amp;|&)key=({item_type}_{item_id}_\d+)", html or "")
        if match:
            return match.group(1)
        match = re.search(rf"{item_type}_{item_id}_\d+", html or "")
        return match.group(0) if match else None
