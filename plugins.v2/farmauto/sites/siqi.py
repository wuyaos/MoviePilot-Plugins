import html as html_lib
import json
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

from .base import FarmSiteConfig


class SiqiConfig(FarmSiteConfig):
    site_id = "siqi"
    site_name = "思齐"
    domains = ["si-qi.xyz", "siqi.xyz"]
    base_url = "https://si-qi.xyz"
    currency = "魔力"
    farm_path = "/plant_game.php"
    warehouse_path = "/plant_game.php"
    capabilities = {"captcha", "social"}

    # 思齐通过 fetch 动态下发种子商店；源码中唯一固定的默认种子是 ID 1 萝卜。
    crops = {
        "crop_1": {"name": "萝卜", "cost": 0, "type": "crop", "id": 1, "action": "plant"},
    }

    @staticmethod
    def _json_dict(source: str) -> Dict[str, Any]:
        try:
            value = json.loads(source or "")
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _text(fragment: str) -> str:
        text = re.sub(r"<[^>]+>", " ", fragment or "")
        return " ".join(html_lib.unescape(text).split())

    @staticmethod
    def _number(value: Any) -> Optional[int]:
        match = re.search(r"-?\d[\d,]*(?:\.\d+)?", str(value or ""))
        if not match:
            return None
        try:
            return int(float(match.group(0).replace(",", "")))
        except (TypeError, ValueError):
            return None

    def _action_url(self, action: str, **params: Any) -> str:
        query = {"action": action}
        query.update({key: value for key, value in params.items() if value is not None and value != ""})
        return f"{self.get_farm_url()}?{urlencode(query)}"

    def get_warehouse_url(self) -> str:
        return self._action_url("fetch")

    def parse_market_prices(self, html: str) -> Dict[str, int]:
        data = self._json_dict(html)
        result: Dict[str, int] = {}
        for seed in data.get("seeds") or []:
            if not isinstance(seed, dict):
                continue
            seed_id = self._number(seed.get("id"))
            price = self._number(seed.get("base_reward") or seed.get("unit_reward") or seed.get("price"))
            if seed_id is not None and price is not None:
                result[f"crop_{seed_id}"] = price
        if result:
            return result

        name_to_key = self.get_name_to_key_map()
        for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", html or "", re.DOTALL | re.IGNORECASE):
            cells = [self._text(cell) for cell in re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.DOTALL | re.IGNORECASE)]
            for index, name in enumerate(cells[:-1]):
                key = name_to_key.get(name)
                price = self._number(cells[index + 1]) if key else None
                if key and price is not None and key not in result:
                    result[key] = price
                    break
        return result

    def parse_crop_status(self, html: str) -> Dict[str, Dict]:
        data = self._json_dict(html)
        statuses: Dict[str, Dict] = {}
        for plot in data.get("user_lands") or []:
            if not isinstance(plot, dict) or not plot.get("seed_id"):
                continue
            seed_id = self._number(plot.get("seed_id"))
            if seed_id is None:
                continue
            ready = str(plot.get("is_ready", "0")) == "1"
            statuses[f"crop_{seed_id}"] = {
                "can_harvest": ready,
                "land_id": plot.get("land_id"),
                "plot_index": plot.get("plot_index"),
                "harvest_time": plot.get("harvest_time"),
            }
        if statuses:
            return statuses

        source = html or ""
        for key, crop in self.crops.items():
            pattern = rf"action=harvest(?:&amp;|&)[^\"']*seed_id={crop['id']}"
            statuses[key] = {"can_harvest": bool(re.search(pattern, source, re.IGNORECASE))}
        return statuses

    def parse_warehouse_items(self, html: str) -> List[Dict[str, Any]]:
        data = self._json_dict(html)
        items: List[Dict[str, Any]] = []
        for item in data.get("inventory") or []:
            if not isinstance(item, dict):
                continue
            seed_id = self._number(item.get("seed_id") or item.get("id"))
            quantity = self._number(item.get("quantity"))
            if seed_id is None or quantity is None:
                continue
            crop = self.crops.get(f"crop_{seed_id}")
            name = str(item.get("name") or (crop or {}).get("name") or f"作物 {seed_id}")
            items.append(self._warehouse_item(name, str(quantity), "", str(seed_id)))
        if data:
            return items

        for row in re.findall(r"(<tr\b[^>]*>.*?</tr>)", html or "", re.DOTALL | re.IGNORECASE):
            seed_match = re.search(r"(?:data-seed-id|seed_id)[=\"':\s]+(\d+)", row, re.IGNORECASE)
            cells = [self._text(cell) for cell in re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.DOTALL | re.IGNORECASE)]
            if not seed_match or len(cells) < 2:
                continue
            quantity = next((self._number(cell) for cell in cells[1:] if self._number(cell) is not None), None)
            if quantity is not None:
                items.append(self._warehouse_item(cells[0], str(quantity), "", seed_match.group(1)))
        return items

    def parse_warehouse_page(self, html: str) -> Tuple[List[Dict], Optional[int]]:
        return self.parse_warehouse_items(html), None

    def get_sell_key(self, html: str, item_type: str, item_id: int) -> Optional[str]:
        expected = f"{item_type}_{item_id}"
        for item in self.parse_warehouse_items(html):
            if item.get("crop_key") == expected or item.get("sell_key") == str(item_id):
                return str(item_id)
        return None

    def parse_bonus(self, html: str) -> Optional[str]:
        data = self._json_dict(html)
        value = data.get("user_bonus") if data else None
        if value is not None:
            return str(value)
        match = re.search(r"(?:当前)?魔力(?:值)?\s*[:：]?\s*([\d,.]+)", self._text(html or ""))
        return match.group(1).replace(",", "") if match else None

    def get_harvest_captcha_url(self) -> str:
        return self._action_url("get_harvest_all_captcha")

    def get_captcha_image_url(self, imagehash: str) -> str:
        return f"{self.base_url}/captcha.php?{urlencode({'imagehash': imagehash})}"

    def parse_captcha_info(self, html: str) -> Dict[str, Any]:
        data = self._json_dict(html)
        captcha = data.get("captcha") if isinstance(data.get("captcha"), dict) else data
        imagehash = captcha.get("imagehash") or captcha.get("token") if isinstance(captcha, dict) else None
        image_url = captcha.get("image_url") or captcha.get("url") if isinstance(captcha, dict) else None
        if imagehash or image_url:
            result = dict(captcha)
            result.update({"token": str(imagehash or ""), "imagehash": str(imagehash or ""), "image_url": str(image_url or "")})
            return result

        token_match = re.search(r'(?:imagehash|token)["\']?\s*(?:=|:)\s*["\']([^"\']+)', html or "", re.IGNORECASE)
        image_match = re.search(r'<img[^>]+(?:id=["\'][^"\']*captcha[^"\']*["\'][^>]+)?src=["\']([^"\']+)', html or "", re.IGNORECASE)
        if not token_match and not image_match:
            return {}
        token = html_lib.unescape(token_match.group(1)) if token_match else ""
        return {"token": token, "imagehash": token, "image_url": html_lib.unescape(image_match.group(1)) if image_match else ""}

    def get_harvest_all_submit_url(self, token: str = "") -> str:
        return f"{self.get_farm_url()}?{urlencode({'option': 'harvest_all'})}"

    def get_harvest_plot_url(self, land_id: Any, plot_index: Any) -> str:
        return self._action_url("harvest", land_id=land_id, plot_index=plot_index)

    def parse_ready_plots(self, html: str) -> List[Dict[str, Any]]:
        data = self._json_dict(html)
        ready_plots: List[Dict[str, Any]] = []
        for plot in data.get("user_lands") or []:
            if not isinstance(plot, dict) or not plot.get("seed_id"):
                continue
            is_ready = str(plot.get("is_ready", "0")) == "1"
            if not is_ready:
                continue
            land_id = plot.get("land_id")
            plot_index = plot.get("plot_index")
            if land_id is not None and plot_index is not None:
                ready_plots.append({"land_id": land_id, "plot_index": plot_index})
        return ready_plots

    def get_steal_target_url(self) -> str:
        return self._action_url("get_victim_farm")

    def parse_steal_targets(self, html: str) -> List[Dict[str, Any]]:
        data = self._json_dict(html)
        if data:
            targets = data.get("targets") or data.get("victims")
            if isinstance(targets, list):
                return [target for target in targets if isinstance(target, dict)]
            victim_id = data.get("victim_id")
            if victim_id is not None:
                return [{
                    "target_id": victim_id,
                    "name": data.get("victim_name") or data.get("username") or "",
                    "plots": data.get("victim_plots") or data.get("user_lands") or [],
                }]
            return []

        targets: List[Dict[str, Any]] = []
        for tag in re.findall(r"<[^>]+data-(?:victim|target)-id=[^>]+>", html or "", re.IGNORECASE):
            target_id = re.search(r'data-(?:victim|target)-id=["\']?([^\s"\'>]+)', tag, re.IGNORECASE)
            name = re.search(r'data-(?:username|name)=["\']([^"\']*)', tag, re.IGNORECASE)
            if target_id:
                targets.append({"target_id": target_id.group(1), "name": html_lib.unescape(name.group(1)) if name else ""})
        return targets

    def get_steal_plot_url(self, target_id: Any = None, plot_id: Any = None) -> str:
        return f"{self.get_farm_url()}?{urlencode({'option': 'steal'})}"

    def get_like_target_url(self) -> str:
        return self._action_url("random_like_targets")

    def parse_like_targets(self, html: str) -> List[Any]:
        data = self._json_dict(html)
        if data:
            targets = data.get("targets") or data.get("farms") or data.get("usernames") or []
            return list(targets) if isinstance(targets, list) else []
        return [
            html_lib.unescape(value).strip()
            for value in re.findall(r'data-(?:target-id|farm-id|username|like-target)=["\']([^"\']+)', html or "", re.IGNORECASE)
        ]

    def get_like_submit_url(self) -> str:
        return f"{self.get_farm_url()}?{urlencode({'option': 'like'})}"

    def get_buy_plot_slot_url(self) -> str:
        return f"{self.get_farm_url()}?{urlencode({'option': 'buy_plot_slot'})}"

    def parse_buy_slot_targets(self, html: str) -> List[Any]:
        data = self._json_dict(html)
        plot_slot = data.get("plot_slot") if isinstance(data.get("plot_slot"), dict) else {}
        next_costs = plot_slot.get("next_slot_cost_by_land") or {}
        if plot_slot.get("enabled") and isinstance(next_costs, dict):
            return [land_id for land_id, cost in next_costs.items() if self._number(cost)]
        candidates = (
            data.get("buyable_lands")
            or data.get("available_lands")
            or data.get("purchasable_lands")
            or []
        )
        result: List[Any] = []
        for land in candidates if isinstance(candidates, list) else []:
            if isinstance(land, dict):
                land_id = land.get("land_id", land.get("id"))
            else:
                land_id = land
            if land_id is not None and land_id != "":
                result.append(land_id)
        if result:
            return result
        for land in data.get("lands") or []:
            if not isinstance(land, dict):
                continue
            if land.get("can_buy_slot") or land.get("buyable") or land.get("can_expand"):
                land_id = land.get("land_id", land.get("id"))
                if land_id is not None and land_id != "":
                    result.append(land_id)
        return result

    def _parse_action_result(self, html: str, success_tokens: Tuple[str, ...], success_message: str, failure_message: str) -> Dict[str, Any]:
        data = self._json_dict(html)
        if data:
            result = dict(data)
            success = bool(data.get("success"))
            message = data.get("msg") or data.get("message") or (success_message if success else failure_message)
            result.update({"success": success, "message": str(message)})
            return result
        text = self._text(html or "")
        success = any(token in text for token in success_tokens)
        return {"success": success, "message": text or (success_message if success else failure_message)}

    def parse_steal_result(self, html: str) -> Dict[str, Any]:
        return self._parse_action_result(html, ("偷菜成功", "偷取成功", "获得"), "偷菜成功", "偷菜失败")

    def parse_harvest_captcha_result(self, html: str) -> Dict[str, Any]:
        return self._parse_action_result(html, ("收获成功", "一键收获", "已收获"), "验证码收获成功", "验证码收获失败")

    def parse_like_result(self, html: str) -> Dict[str, Any]:
        return self._parse_action_result(html, ("点赞成功", "已点赞", "点赞完成"), "点赞成功", "点赞失败")

    def parse_buy_slot_result(self, html: str) -> Dict[str, Any]:
        return self._parse_action_result(html, ("购买成功", "扩地成功", "坑位"), "扩地成功", "扩地失败")
