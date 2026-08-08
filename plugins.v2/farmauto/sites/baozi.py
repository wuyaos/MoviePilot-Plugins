import re
from typing import Any, Dict, List, Optional

from .base import FarmSiteConfig


class BaoziConfig(FarmSiteConfig):
    site_id = "baozi"
    site_name = "包子"
    domains = ["p.t-baozi.cc", "t-baozi.cc", "baozi.cc"]
    base_url = "https://p.t-baozi.cc"
    currency = "魔力"
    capabilities = {"harvest_all"}

    def parse_bonus(self, html: str) -> Optional[str]:
        """解析包子农场页顶部的魔力值。"""
        text = re.sub(r"<[^>]+>", " ", html or "")
        match = re.search(r"魔力值\s*[:：]?\s*([\d,]+(?:\.\d+)?)", text)
        return match.group(1).replace(",", "") if match else None

    def parse_market_prices(self, html: str) -> Dict[str, int]:
        result: Dict[str, int] = {}
        name_to_key = self.get_name_to_key_map()
        patterns = (
            r"<tr>\s*<td>([^<]+)</td>\s*<td>(\d+)</td>\s*</tr>",
            r"<td><img[^>]+></td>\s*<td>([^<]+)</td>\s*<td>(\d+)</td>",
        )
        for pattern in patterns:
            for name, price in re.findall(pattern, html, re.DOTALL):
                key = name_to_key.get(name.strip())
                if key:
                    result[key] = int(price)
            if result:
                break
        return result

    def parse_warehouse_items(self, html: str) -> List[Dict[str, Any]]:
        warehouse_start = html.find("<!-- 仓库 -->")
        if warehouse_start == -1:
            warehouse_start = html.find("<h2>仓库</h2>")
        if warehouse_start != -1:
            warehouse_html = html[warehouse_start:warehouse_start + 5000]
        else:
            warehouse_html = ""
            for section in re.findall(r'<div class="farm-section">(.*?)</div>', html, re.DOTALL):
                if "仓库" in section:
                    warehouse_html = section
                    break
            if not warehouse_html:
                return []
        pattern = r'<tr>\s*<td>([^<]+)</td>\s*<td>(\d+)</td>\s*<td>([^<]+)</td>\s*<td>.*?action=sell&key=([^"\']+).*?</td>\s*</tr>'
        return [
            self._warehouse_item(name, quantity, expire, sell_key)
            for name, quantity, expire, sell_key in re.findall(pattern, warehouse_html, re.DOTALL)
        ]

    def get_sell_key(self, html: str, item_type: str, item_id: int) -> Optional[str]:
        return f"{item_type}_{item_id}"
