import html as html_lib
import re
from typing import Any, Dict, List, Optional, Tuple

from .base import FarmSiteConfig


class PlayLetConfig(FarmSiteConfig):
    site_id = "playlet"
    site_name = "PlayLet"
    domains = ["playlet.cc", "www.playlet.cc"]
    base_url = "https://playlet.cc"
    currency = "魔力"
    capabilities = {"harvest_all", "expiry_sale", "warehouse_pagination"}

    @staticmethod
    def _text(fragment: str) -> str:
        text = re.sub(r"<[^>]+>", "", fragment or "")
        return html_lib.unescape(text).replace("\xa0", " ").strip()

    def parse_market_prices(self, html: str) -> Dict[str, int]:
        result: Dict[str, int] = {}
        name_to_key = self.get_name_to_key_map()
        market_start = re.search(r"菜市场|市场行情", html or "")
        market_html = html[market_start.start():] if market_start else (html or "")

        for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", market_html, re.DOTALL | re.IGNORECASE):
            cells = [self._text(cell) for cell in re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.DOTALL | re.IGNORECASE)]
            for index, name in enumerate(cells[:-1]):
                key = name_to_key.get(name)
                price_match = re.search(r"\d+", cells[index + 1])
                if key and price_match and key not in result:
                    result[key] = int(price_match.group())

        # 兼容没有标准 tr 的旧页面片段。
        if len(result) < len(self.crops):
            for name, key in name_to_key.items():
                match = re.search(
                    rf"<td\b[^>]*>\s*(?:<[^>]+>\s*)*{re.escape(name)}\s*(?:</[^>]+>\s*)*</td>\s*"
                    r"<td\b[^>]*>\s*(\d+)\s*</td>",
                    market_html,
                    re.DOTALL | re.IGNORECASE,
                )
                if match and key not in result:
                    result[key] = int(match.group(1))
        return result

    def parse_crop_status(self, html: str) -> Dict[str, Dict]:
        source = html or ""
        result: Dict[str, Dict] = {}
        for key, crop in self.crops.items():
            harvest_pattern = rf"action=harvest(?:&amp;|&)type={crop['type']}(?:&amp;|&)id={crop['id']}"
            status: Dict[str, Any] = {"can_harvest": bool(re.search(harvest_pattern, source))}
            name_match = re.search(rf"<h3\b[^>]*>\s*{re.escape(crop['name'])}\s*</h3>", source, re.IGNORECASE)
            if name_match:
                next_item = re.search(r'<div\b[^>]*class=["\'][^"\']*farm-item', source[name_match.end():], re.IGNORECASE)
                end = name_match.end() + next_item.start() if next_item else min(len(source), name_match.end() + 2000)
                item_html = source[name_match.end():end]
                remaining = re.search(r"剩余时间\s*[:：]?\s*([^<]+)", item_html)
                if remaining:
                    from .base import parse_expire_minutes
                    status["remaining_minutes"] = parse_expire_minutes(self._text(remaining.group(1)))
            result[key] = status
        return result

    def parse_warehouse_items(self, html: str) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        warehouse_start = re.search(r"仓库", html or "")
        source = html[warehouse_start.start():] if warehouse_start else (html or "")
        crop_names = self.get_name_to_key_map()
        for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", source, re.DOTALL | re.IGNORECASE):
            sell_key = re.search(r"action=sell(?:&amp;|&)key=([^&\"']+)", row, re.IGNORECASE)
            if not sell_key:
                continue
            cells = [self._text(cell) for cell in re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.DOTALL | re.IGNORECASE)]
            name_index = next((i for i, value in enumerate(cells) if value in crop_names), None)
            if name_index is None or name_index + 1 >= len(cells):
                continue
            quantity_match = re.search(r"\d+", cells[name_index + 1])
            if not quantity_match:
                continue
            time_values = [value for value in cells[name_index + 2:] if re.search(r"已过期|\d+\s*(?:天|小时|分钟)", value)]
            expire = time_values[-1] if time_values else ""
            items.append(self._warehouse_item(cells[name_index], quantity_match.group(), expire, sell_key.group(1)))
        return items

    def parse_warehouse_page(self, html: str) -> Tuple[List[Dict], Optional[int]]:
        items = self.parse_warehouse_items(html)
        page = re.search(r"页\s*(\d+)\s*共\s*(\d+)", html or "")
        if not page:
            page = re.search(r"第\s*(\d+)\s*/\s*(\d+)\s*页", html or "")
        if page:
            current, total = map(int, page.groups())
            return items, current + 1 if current < total else None
        total = re.search(r'class=["\'][^"\']*pagination-info[^"\']*["\'][^>]*>[^<]*共\s*(\d+)', html or "", re.IGNORECASE)
        return items, 2 if total and int(total.group(1)) > 1 else None

    def get_warehouse_page_url(self, page: int) -> str:
        return f"{self.get_warehouse_url()}&page={page}"

    def parse_bonus(self, html: str) -> Optional[str]:
        match = re.search(r"当前(?:魔力值|魔力|火花)\s*[:：]\s*([\d,.]+)", self._text(html or ""))
        return match.group(1).replace(",", "") if match else None

    def get_sell_key(self, html: str, item_type: str, item_id: int) -> Optional[str]:
        match = re.search(rf"action=sell(?:&amp;|&)key=({item_type}_{item_id}(?:_\d+)?)", html or "")
        return match.group(1) if match else f"{item_type}_{item_id}"
