import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from ..core.models import CropDef, parse_expire_minutes
except ImportError:  # 支持按插件根目录加入 sys.path 的离线测试方式
    from core.models import CropDef, parse_expire_minutes


CAPABILITY_BATCH_SELL = "batch_sell"


class FarmSiteConfig(ABC):
    site_id: str = ""
    site_name: str = ""
    domains: List[str] = []
    base_url: str = ""
    currency: str = "魔力"
    farm_path: str = "/magic_fram.php"
    warehouse_path: str = "/magic_fram.php"
    has_double_harvest: bool = False
    capabilities: Set[str] = set()

    crops: Dict[str, Dict[str, Any]] = {
        "crop_1": {"name": "小麦", "cost": 500, "type": "crop", "id": 1, "action": "plant"},
        "crop_2": {"name": "玉米", "cost": 1000, "type": "crop", "id": 2, "action": "plant"},
        "crop_3": {"name": "花生", "cost": 1500, "type": "crop", "id": 3, "action": "plant"},
        "crop_4": {"name": "土豆", "cost": 2000, "type": "crop", "id": 4, "action": "plant"},
        "animal_1": {"name": "鸡", "cost": 1000, "type": "animal", "id": 1, "action": "breed"},
        "animal_2": {"name": "猪", "cost": 2000, "type": "animal", "id": 2, "action": "breed"},
        "animal_3": {"name": "羊", "cost": 5000, "type": "animal", "id": 3, "action": "breed"},
        "animal_4": {"name": "牛", "cost": 10000, "type": "animal", "id": 4, "action": "breed"},
    }

    @abstractmethod
    def parse_market_prices(self, html: str) -> Dict[str, int]:
        raise NotImplementedError

    @abstractmethod
    def parse_crop_status(self, html: str) -> Dict[str, Dict]:
        raise NotImplementedError

    @abstractmethod
    def get_sell_key(self, html: str, item_type: str, item_id: int) -> Optional[str]:
        raise NotImplementedError

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    def supports_batch_sell(self) -> bool:
        return CAPABILITY_BATCH_SELL in self.capabilities

    def crops_as_models(self) -> List[CropDef]:
        return [CropDef(key=key, **crop) for key, crop in self.crops.items()]

    def get_farm_url(self) -> str:
        return f"{self.base_url}{self.farm_path}"

    def get_harvest_url(self, item_type: str, item_id: int) -> str:
        return f"{self.get_farm_url()}?action=harvest&type={item_type}&id={item_id}"

    def get_plant_url(self, item_type: str, item_id: int) -> str:
        return f"{self.get_farm_url()}?action=plant&type={item_type}&id={item_id}"

    def get_breed_url(self, item_type: str, item_id: int) -> str:
        return f"{self.get_farm_url()}?action=breed&type={item_type}&id={item_id}"

    def get_sell_url(self, sell_key: str) -> str:
        return f"{self.get_farm_url()}?action=sell&key={sell_key}"

    def get_batch_sell_url(self) -> str:
        return f"{self.get_farm_url()}?action=batch_sell&page=1&sort=expire_asc"

    def get_harvest_all_url(self) -> str:
        return f"{self.get_farm_url()}?action=harvest_all"

    def get_warehouse_url(self) -> str:
        return f"{self.base_url}{self.warehouse_path}?sort=expire_asc"

    def get_warehouse_page_url(self, page: int) -> str:
        return f"{self.get_warehouse_url()}&page={page}"

    def check_auth(self, html: str) -> bool:
        return not ("请登录" in html or ("登录" in html and "签到" not in html))

    def get_name_to_key_map(self) -> Dict[str, str]:
        return {crop["name"]: key for key, crop in self.crops.items()}

    def get_crop_by_name(self, name: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        for key, crop in self.crops.items():
            if crop["name"] == name:
                return key, crop
        return None

    def parse_harvest_result(self, html: str) -> Dict[str, Any]:
        double = self.has_double_harvest and any(token in html for token in ("双倍", "2倍", "双倍收获"))
        if "已收获" in html or "已经收获" in html:
            return {"success": True, "double": False, "message": "已收获"}
        if "成功" in html or "收获" in html:
            return {"success": True, "double": double, "message": "收获成功"}
        return {"success": False, "double": False, "message": "收获失败"}

    def parse_plant_result(self, html: str, action: str) -> Dict[str, Any]:
        action_name = "种植" if action == "plant" else "养殖"
        success = "成功" in html or action_name in html or "完成" in html
        return {"success": success, "message": f"{action_name}{'成功' if success else '失败'}"}

    def parse_sell_result(self, html: str) -> Dict[str, Any]:
        success = any(token in html for token in ("成功", "出售", "获得", "已出售", "已经出售"))
        return {"success": success, "message": "出售成功" if success else "出售失败"}

    def parse_batch_sell_result(self, html: str) -> Dict[str, Any]:
        text = " ".join(re.sub(r"<[^>]+>", " ", html or "").split())
        success_match = re.search(r"成功(?:出售)?\s*[：:]?\s*(\d+)\s*个", text)
        failed_match = re.search(r"失败(?:出售)?\s*[：:]?\s*(\d+)\s*个", text)
        if success_match:
            sold_count = int(success_match.group(1))
            failed_count = int(failed_match.group(1)) if failed_match else 0
            return {
                "success": failed_count == 0,
                "sold_count": sold_count,
                "message": f"批量出售成功 {sold_count} 个，失败 {failed_count} 个",
            }
        if failed_match or "失败" in text:
            failed_count = int(failed_match.group(1)) if failed_match else 0
            message = f"批量出售失败 {failed_count} 个" if failed_count else "批量出售失败"
            return {"success": False, "sold_count": 0, "message": message}
        return {"success": True, "sold_count": -1, "message": "批量出售请求已发出"}

    def parse_warehouse_items(self, html: str) -> List[Dict[str, Any]]:
        warehouse_start = html.find("<h2>仓库</h2>")
        if warehouse_start == -1:
            return []
        warehouse_html = html[warehouse_start:warehouse_start + 8000]
        rows = re.findall(
            r'<tr>\s*<td>.*?</td>\s*<td>([^<]+)</td>\s*<td>(\d+)</td>\s*<td>([^<]+)</td>\s*<td>.*?action=sell&key=([^"\']+).*?</td>\s*</tr>',
            warehouse_html,
            re.DOTALL,
        )
        return [self._warehouse_item(name, quantity, expire, sell_key) for name, quantity, expire, sell_key in rows]

    def parse_warehouse_page(self, html: str) -> Tuple[List[Dict], Optional[int]]:
        return self.parse_warehouse_items(html), None

    def parse_bonus(self, html: str) -> Optional[str]:
        return None

    def parse_market_trend(self, html: str) -> Dict[str, List[int]]:
        return {}

    def _warehouse_item(self, name: str, quantity: str, expire: str, sell_key: str) -> Dict[str, Any]:
        crop = self.get_crop_by_name(name.strip())
        expire_raw = expire.strip()
        return {
            "name": name.strip(),
            "quantity": int(quantity) if quantity.isdigit() else 1,
            "expire": expire_raw,
            "expire_raw": expire_raw,
            "expire_minutes": parse_expire_minutes(expire_raw),
            "sell_key": sell_key.strip().split("&")[0],
            "crop_key": crop[0] if crop else None,
        }
