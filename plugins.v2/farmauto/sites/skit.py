import html as html_lib
import re
from typing import Any, Dict, List, Optional, Tuple

from .base import CAPABILITY_BATCH_SELL, FarmSiteConfig


class SkitConfig(FarmSiteConfig):
    site_id = "skit"
    site_name = "拾刻"
    domains = ["ptskit.org", "www.ptskit.org"]
    base_url = "https://www.ptskit.org"
    currency = "魔力"
    farm_path = "/magic_farm.php"
    warehouse_path = "/magic_farm.php"
    capabilities = {
        "harvest_all", "expiry_sale", "warehouse_pagination", CAPABILITY_BATCH_SELL
    }

    @staticmethod
    def _cell_text(fragment: str) -> str:
        text = re.sub(r"<[^>]+>", " ", fragment)
        return " ".join(html_lib.unescape(text).split())

    @staticmethod
    def _price(text: str) -> Optional[int]:
        match = re.search(r"\d[\d,]*(?:\.\d+)?", text)
        if not match:
            return None
        try:
            return int(float(match.group(0).replace(",", "")))
        except (TypeError, ValueError):
            return None

    def parse_market_prices(self, html: str) -> Dict[str, int]:
        result: Dict[str, int] = {}
        name_to_key = self.get_name_to_key_map()

        market_tables = re.findall(
            r'<table[^>]*class=["\'][^"\']*\bmarket-table\b[^"\']*["\'][^>]*>(.*?)</table>',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        for table in market_tables:
            for row in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.DOTALL | re.IGNORECASE):
                cells = [
                    self._cell_text(cell)
                    for cell in re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL | re.IGNORECASE)
                ]
                for index, name in enumerate(cells[:-1]):
                    crop_key = name_to_key.get(name)
                    price = self._price(cells[index + 1]) if crop_key else None
                    if crop_key and price is not None:
                        result[crop_key] = price
                        break

        if len(result) < len(self.crops):
            market_start = html.find("菜市场")
            if market_start == -1:
                market_start = html.find("市场")
            market_html = html[market_start:market_start + 12000] if market_start != -1 else ""
            for name, crop_key in name_to_key.items():
                if crop_key in result:
                    continue
                match = re.search(
                    rf"<td[^>]*>\s*{re.escape(name)}\s*</td>\s*<td[^>]*>(.*?)</td>",
                    market_html,
                    re.DOTALL | re.IGNORECASE,
                )
                price = self._price(self._cell_text(match.group(1))) if match else None
                if price is not None:
                    result[crop_key] = price
        return result

    def parse_warehouse_items(self, html: str) -> List[Dict[str, Any]]:
        tables = re.findall(
            r'<table[^>]*class=["\'][^"\']*\bwarehouse-table\b[^"\']*["\'][^>]*>(.*?)</table>',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        if not tables:
            return []

        items: List[Dict[str, Any]] = []
        for table in tables:
            for row in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.DOTALL | re.IGNORECASE):
                raw_cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL | re.IGNORECASE)
                cells = [self._cell_text(cell) for cell in raw_cells]
                if len(cells) >= 8:
                    name, quantity, expire = cells[1], cells[2], cells[4]
                elif len(cells) >= 4:
                    name, quantity, expire = cells[0], cells[1], cells[3]
                else:
                    continue
                if not self.get_crop_by_name(name):
                    continue

                checkbox = re.search(
                    r'<input[^>]*name=["\']batch_keys\[\]["\'][^>]*value=["\']([^"\']+)',
                    row,
                    re.IGNORECASE,
                ) or re.search(
                    r'<input[^>]*value=["\']([^"\']+)["\'][^>]*name=["\']batch_keys\[\]',
                    row,
                    re.IGNORECASE,
                )
                link = re.search(r"(?:\?|&amp;|&)key=([^&\"'<>]+)", row, re.IGNORECASE)
                sell_key = html_lib.unescape(checkbox.group(1) if checkbox else link.group(1) if link else "")
                if not sell_key:
                    continue
                quantity_match = re.search(r"\d+", quantity.replace(",", ""))
                clean_quantity = quantity_match.group(0) if quantity_match else "1"
                items.append(self._warehouse_item(name, clean_quantity, expire, sell_key))
        return items

    def parse_warehouse_page(self, html: str) -> Tuple[List[Dict], Optional[int]]:
        items = self.parse_warehouse_items(html)
        page_match = re.search(r"页\s*(\d+)\s*共\s*(\d+)", self._cell_text(html))
        if page_match:
            current_page, total_pages = map(int, page_match.groups())
            return items, current_page + 1 if current_page < total_pages else None

        next_link = re.search(
            r'<a[^>]*href=["\'][^"\']*[?&](?:amp;)?page=(\d+)[^"\']*["\'][^>]*>'
            r'\s*(?:下一页|下页|›|»)',
            html,
            re.IGNORECASE,
        )
        return items, int(next_link.group(1)) if next_link else None

    def parse_bonus(self, html: str) -> Optional[str]:
        match = re.search(
            r'<div[^>]*class=["\'][^"\']*\bpoints-display\b[^"\']*["\'][^>]*>(.*?)</div>',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        if not match:
            return None
        value = re.sub(r"^.*?当前魔力值\s*[：:]?\s*", "", self._cell_text(match.group(1)))
        return value or None

    def get_sell_key(self, html: str, item_type: str, item_id: int) -> Optional[str]:
        crop = self.crops.get(f"{item_type}_{item_id}")
        if crop:
            for item in self.parse_warehouse_items(html):
                if item.get("name") == crop["name"] and item.get("sell_key"):
                    return str(item["sell_key"])
        match = re.search(rf"(?:\?|&amp;|&)key=({re.escape(item_type)}_{item_id}[^&\"'<>]*)", html)
        return html_lib.unescape(match.group(1)) if match else None
