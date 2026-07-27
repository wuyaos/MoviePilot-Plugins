import base64
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from ..core.models import CropDef, parse_expire_minutes
except ImportError:  # 支持按插件根目录加入 sys.path 的离线测试方式
    from core.models import CropDef, parse_expire_minutes


CAPABILITY_BATCH_SELL = "batch_sell"
CAPABILITY_SELL_INVENTORY = "sell_inventory"
CAPABILITY_PLANT_ALL = "plant_all"

IMAGE_FILES = {
    "小麦": "crop_wheat.png",
    "玉米": "crop_corn.png",
    "土豆": "crop_potato.png",
    "花生": "crop_peanut.png",
    "鸡": "animal_chicken1.png",
    "猪": "animal_pig2.png",
    "牛": "animal_cow1.png",
    "羊": "animal_sheep.png",
}

# 统一作物 emoji 回退表（通用农场与思齐共用，避免 mdi 矢单色图标与 emoji 混杂）
CROP_EMOJI = {
    "小麦": "🌾", "玉米": "🌽", "土豆": "🥔", "花生": "🥜",
    "鸡": "🐔", "猪": "🐷", "牛": "🐂", "羊": "🐑",
    "萝卜": "🥕", "西红柿": "🍅", "茄子": "🍆",
    "蘑菇": "🍄", "樱桃": "🍒", "水稻": "🍚", "稻": "🍚",
}


class FarmSiteConfig(ABC):
    _image_cache: Dict[str, str] = {}
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

    def resolve_crops(self, farm_html: str) -> Optional[Dict[str, Dict]]:
        """返回本次运行的有效作物字典；None 表示使用静态 crops。"""
        return None

    def parse_crop_status(self, html: str) -> Dict[str, Dict]:
        source = html or ""
        result: Dict[str, Dict] = {}
        for crop_key, crop in self.crops.items():
            harvest_pattern = (
                rf"action=harvest(?:&amp;|&)type={re.escape(crop['type'])}"
                rf"(?:&amp;|&)id={crop['id']}"
            )
            item_html = ""
            name_match = re.search(
                rf"<h3\b[^>]*>\s*{re.escape(crop['name'])}\s*</h3>",
                source,
                re.IGNORECASE,
            )
            if name_match:
                next_item = re.search(
                    r'<div\b[^>]*class=["\'][^"\']*farm-item',
                    source[name_match.end():],
                    re.IGNORECASE,
                )
                end = (
                    name_match.end() + next_item.start()
                    if next_item
                    else min(len(source), name_match.end() + 2000)
                )
                item_html = source[name_match.end():end]
            result[crop_key] = self._crop_status(
                can_harvest=bool(re.search(harvest_pattern, item_html or source)),
                item_html=item_html,
            )
        return result

    @abstractmethod
    def get_sell_key(self, html: str, item_type: str, item_id: int) -> Optional[str]:
        raise NotImplementedError

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    def supports_batch_sell(self) -> bool:
        return CAPABILITY_BATCH_SELL in self.capabilities

    def supports_sell_inventory(self) -> bool:
        return CAPABILITY_SELL_INVENTORY in self.capabilities

    def supports_plant_all(self) -> bool:
        return CAPABILITY_PLANT_ALL in self.capabilities

    def to_land_states(self, farm_html: str) -> List["LandState"]:
        """把站点农场页解析为统一 LandState 列表。

        通用实现基于 parse_crop_status（按 crop_key 索引，无地块概念），
        合成 land_id = f"{site_id}:{crop_key}"；思齐覆写为从 user_lands 解析真实地块。
        """
        from ..core.models import LandState  # 局部导入避免循环依赖
        crop_status = self.parse_crop_status(farm_html)
        land_states: List[LandState] = []
        now = time.time()
        for crop_key, status in crop_status.items():
            if not isinstance(status, dict):
                continue
            crop = self.crops.get(crop_key, {})
            remaining = status.get("remaining_minutes")
            can_harvest = bool(status.get("can_harvest"))
            state = status.get("state") or self._state_from_status(can_harvest, remaining)
            land_states.append(LandState(
                land_id=f"{self.site_id}:{crop_key}",
                site_id=self.site_id,
                crop_key=crop_key,
                plot_index=None,
                state=state,
                can_harvest=can_harvest,
                seed_id=crop.get("id"),
                seed_name=crop.get("name"),
                harvest_time=(now + remaining * 60) if remaining and remaining > 0 else None,
                remaining_minutes=remaining,
                grow_time=None,
                cost=crop.get("cost"),
                sellable=False,
            ))
        return land_states

    def crop_emoji(self, name: str) -> str:
        """返回作物/动物的统一 emoji 回退图标。"""
        return CROP_EMOJI.get(str(name or ""), "🌱")

    def crop_icon(self, name: str) -> Dict[str, str]:
        """返回统一图标结构：站点 PNG/URL 优先，缺失时回退 emoji。"""
        image = self.crop_image(name)
        emoji = self.crop_emoji(name)
        return {"image": image, "emoji": emoji}

    def crop_image(self, name: str) -> str:
        if name in FarmSiteConfig._image_cache:
            return FarmSiteConfig._image_cache[name]
        filename = IMAGE_FILES.get(name)
        if not filename:
            return ""
        try:
            image_bytes = (Path(__file__).parents[1] / "public" / filename).read_bytes()
            image = f"data:image/png;base64,{base64.b64encode(image_bytes).decode('ascii')}"
            FarmSiteConfig._image_cache[name] = image
        except Exception:
            # 图片缺失时不缓存空值，便于文件就绪后重试
            image = ""
        return image

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

    @staticmethod
    def _action_result_text(html: str) -> str:
        return " ".join(re.sub(r"<[^>]+>", " ", html or "").split())

    @staticmethod
    def _has_action_failure(text: str) -> bool:
        return any(
            token in text
            for token in ("失败", "错误", "异常", "无法", "不能", "未成功", "操作失败")
        )

    def parse_harvest_result(self, html: str) -> Dict[str, Any]:
        text = self._action_result_text(html)
        if self._has_action_failure(text):
            return {"success": False, "double": False, "message": "收获失败"}
        double = self.has_double_harvest and any(
            token in text for token in ("双倍", "2倍", "双倍收获")
        )
        if "已收获" in text or "已经收获" in text:
            return {"success": True, "double": False, "message": "已收获"}
        if "成功" in text or "收获" in text:
            return {"success": True, "double": double, "message": "收获成功"}
        return {"success": False, "double": False, "message": "收获失败"}

    def parse_plant_result(self, html: str, action: str) -> Dict[str, Any]:
        action_name = "种植" if action == "plant" else "养殖"
        text = self._action_result_text(html)
        if self._has_action_failure(text):
            return {"success": False, "message": f"{action_name}失败"}
        # 没有空地/已满属于正常跳过，不算失败也不计入成功
        skip_tokens = ("没有空地", "已满", "已种植", "未解锁")
        if any(token in text for token in skip_tokens):
            return {"success": True, "skipped": True, "message": f"无空地，跳过{action_name}"}
        # 真正的失败关键词
        failure_tokens = ("不足", "失败", "无法", "不能")
        if any(token in text for token in failure_tokens):
            return {"success": False, "message": f"{action_name}失败"}
        success = "成功" in text or action_name in text or "完成" in text
        return {"success": success, "message": f"{action_name}{'成功' if success else '失败'}"}

    def parse_sell_result(self, html: str) -> Dict[str, Any]:
        text = self._action_result_text(html)
        if self._has_action_failure(text):
            return {"success": False, "message": "出售失败"}
        success = any(token in text for token in ("成功", "出售", "获得", "已出售", "已经出售"))
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

    @staticmethod
    def _state_from_status(can_harvest: bool, remaining_minutes: Optional[int]) -> str:
        if can_harvest:
            return "ripe"
        if remaining_minutes is not None and remaining_minutes > 0:
            return "growing"
        return "empty"

    @staticmethod
    def _status_text(fragment: str) -> str:
        return " ".join(re.sub(r"<[^>]+>", " ", fragment or "").split())

    def _crop_status(self, can_harvest: bool, item_html: str = "") -> Dict[str, Any]:
        status_text = self._status_text(item_html)
        remaining_match = re.search(
            r"剩余时间\s*[:：]?\s*((?:\d+\s*(?:天|小时|分钟)\s*)+)",
            status_text,
        )
        remaining_minutes = (
            parse_expire_minutes(remaining_match.group(1)) if remaining_match else None
        )
        status: Dict[str, Any] = {
            "can_harvest": can_harvest,
            "remaining_minutes": remaining_minutes,
            "state": self._state_from_status(can_harvest, remaining_minutes),
        }
        grow_time_match = re.search(
            r"成长时间\s*[:：]?\s*((?:\d+\s*(?:天|小时|分钟)\s*)+)",
            status_text,
        )
        if grow_time_match:
            status["grow_time"] = "".join(grow_time_match.group(1).split())
        return status

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
