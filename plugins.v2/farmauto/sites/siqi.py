import html as html_lib
import json
import re
import time
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
    capabilities = {"captcha", "social", "sell_inventory"}

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

    @classmethod
    def _without_sensitive_fields(cls, value: Any) -> Any:
        sensitive = {"cookie", "cookies", "set-cookie", "authorization"}
        if isinstance(value, dict):
            return {
                key: cls._without_sensitive_fields(item)
                for key, item in value.items()
                if str(key).lower() not in sensitive
            }
        if isinstance(value, list):
            return [cls._without_sensitive_fields(item) for item in value]
        return value

    @staticmethod
    def _text(fragment: str) -> str:
        text = re.sub(r"<[^>]+>", " ", fragment or "")
        return " ".join(html_lib.unescape(text).split())

    @staticmethod
    def _number(value: Any) -> Optional[int]:
        match = re.search(r"-?\d[\d,]*(?:\.\d+)?", str("" if value is None else value))
        if not match:
            return None
        try:
            return int(float(match.group(0).replace(",", "")))
        except (TypeError, ValueError):
            return None

    def _action_url(self, action: str, **params: Any) -> str:
        query = {"action": action}
        query.update({key: value for key, value in params.items() if value is not None and value != ""})
        return f"{self.base_url}{self.farm_path}?{urlencode(query)}"

    def get_farm_url(self) -> str:
        # 思齐 GET ?action=fetch 返回 JSON 农场数据，而非 HTML 页面
        return self._action_url("fetch")

    def get_warehouse_url(self) -> str:
        return self._action_url("fetch")

    def resolve_crops(self, farm_html: str) -> Optional[Dict[str, Dict]]:
        data = self._json_dict(farm_html)
        seeds = data.get("seeds") or []
        if not seeds:
            return None
        crops: Dict[str, Dict] = {}
        for seed in seeds:
            if not isinstance(seed, dict):
                continue
            seed_id = self._number(seed.get("id") or seed.get("seed_id"))
            if seed_id is None:
                continue
            crops[f"crop_{seed_id}"] = {
                "name": str(seed.get("name") or f"作物{seed_id}"),
                "cost": self._number(seed.get("cost")) or 0,
                "type": "crop",
                "id": seed_id,
                "action": "plant",
                "grow_time": seed.get("grow_time"),
                "unlock_harvest": self._number(seed.get("unlock_harvest")) or 0,
            }
        return crops or None

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
            if not isinstance(plot, dict):
                continue
            seed_id = self._number(plot.get("seed_id"))
            land_id = plot.get("land_id")
            plot_index = plot.get("plot_index")
            if seed_id is not None and seed_id != 0:
                # 已种植的 plot
                ready = str(plot.get("is_ready", "0")) == "1"
                harvest_time = self._number(plot.get("harvest_time"))
                if not ready and harvest_time and harvest_time <= time.time():
                    ready = True
                key = f"crop_{seed_id}"
                if key not in statuses or (ready and not statuses[key].get("can_harvest")):
                    statuses[key] = {
                        "can_harvest": ready,
                        "land_id": land_id,
                        "plot_index": plot_index,
                        "harvest_time": plot.get("harvest_time"),
                    }
            else:
                # 空地也记录(供 plant 使用)
                statuses[f"empty_{land_id}_{plot_index}"] = {
                    "can_harvest": False,
                    "land_id": land_id,
                    "plot_index": plot_index,
                    "harvest_time": None,
                    "is_empty": True,
                }
        if statuses:
            return statuses

        source = html or ""
        for key, crop in self.crops.items():
            pattern = rf"action=harvest(?:&amp;|&)[^\"']*seed_id={crop['id']}"
            statuses[key] = {"can_harvest": bool(re.search(pattern, source, re.IGNORECASE))}
        return statuses

    def to_land_states(self, farm_html: str) -> List["LandState"]:
        """思齐覆写：从 fetch JSON 的 user_lands 解析真实地块。"""
        from ..core.models import LandState
        data = self._json_dict(farm_html)
        lands: List[LandState] = []
        now = time.time()
        # seeds 用于反查 name/cost/grow_time
        seed_map: Dict[int, Dict[str, Any]] = {}
        for seed in data.get("seeds") or []:
            sid = self._number(seed.get("id"))
            if sid is not None:
                seed_map[sid] = seed
        for plot in data.get("user_lands") or []:
            if not isinstance(plot, dict):
                continue
            land_id = plot.get("land_id")
            plot_index = plot.get("plot_index")
            seed_id = self._number(plot.get("seed_id"))
            ready = str(plot.get("is_ready", "0")) == "1"
            harvest_time = self._number(plot.get("harvest_time"))
            if not ready and harvest_time and harvest_time <= now:
                ready = True
            seed = seed_map.get(seed_id) if seed_id else None
            crop_key = f"crop_{seed_id}" if seed_id else None
            if seed_id and not ready:
                remaining = max(0, int((harvest_time - now) / 60)) if harvest_time else None
                state = "growing"
            elif seed_id and ready:
                remaining = 0
                state = "ripe"
            else:
                remaining = None
                state = "empty"
            grow_time_raw = (seed or {}).get("grow_time")
            grow_time = self._number(grow_time_raw) if isinstance(grow_time_raw, (int, float, str)) else None
            lands.append(LandState(
                land_id=str(land_id),
                site_id=self.site_id,
                crop_key=crop_key,
                plot_index=self._number(plot_index),
                state=state,
                can_harvest=ready,
                seed_id=seed_id,
                seed_name=str((seed or {}).get("name") or ""),
                harvest_time=harvest_time,
                remaining_minutes=remaining,
                grow_time=grow_time,
                cost=self._number((seed or {}).get("cost")),
                sellable=False,
            ))
        return lands

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
            crop_key = f"crop_{seed_id}"
            crop = self.crops.get(crop_key)
            name = str(item.get("name") or (crop or {}).get("name") or f"作物 {seed_id}")
            warehouse_item = self._warehouse_item(name, str(quantity), "", str(seed_id))
            warehouse_item["crop_key"] = crop_key
            items.append(warehouse_item)
        if data:
            return items

        for row in re.findall(r"(<tr\b[^>]*>.*?</tr>)", html or "", re.DOTALL | re.IGNORECASE):
            seed_match = re.search(r"(?:data-seed-id|seed_id)[=\"':\s]+(\d+)", row, re.IGNORECASE)
            cells = [self._text(cell) for cell in re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.DOTALL | re.IGNORECASE)]
            if not seed_match or len(cells) < 2:
                continue
            quantity = next((self._number(cell) for cell in cells[1:] if self._number(cell) is not None), None)
            if quantity is not None:
                warehouse_item = self._warehouse_item(
                    cells[0], str(quantity), "", seed_match.group(1)
                )
                warehouse_item["crop_key"] = f"crop_{seed_match.group(1)}"
                items.append(warehouse_item)
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

    def parse_farm_info(self, html: str) -> Dict[str, Any]:
        """解析 fetch 接口的完整农场数据，缺失字段使用前端可安全消费的默认值。"""
        result: Dict[str, Any] = {
            "user_bonus": 0,
            "user_stats": {"total_harvest": 0, "total_steal_gain": 0},
            "user_steal_gain": 0,
            "farm_like_total": 0,
            "user_farm_like_total": 0,
            "seeds": [],
            "user_lands": [],
            "inventory": [],
            "like_max": 0,
            "like_remaining": 0,
            "like_next_in": None,
            "plot_slot": {
                "enabled": False,
                "available": False,
                "max_per_land": 0,
                "effective_plot_counts": {},
                "next_slot_cost_by_land": {},
            },
            "user_logs": [],
        }
        try:
            data = self._json_dict(html)
            bonus = self._number(data.get("user_bonus")) if data else self._number(self.parse_bonus(html))
            if bonus is not None:
                result["user_bonus"] = bonus

            raw_stats = data.get("user_stats") if isinstance(data.get("user_stats"), dict) else {}
            total_harvest = self._number(raw_stats.get("total_harvest"))
            total_steal_gain = self._number(raw_stats.get("total_steal_gain"))
            result["user_stats"] = {
                "total_harvest": total_harvest or 0,
                "total_steal_gain": total_steal_gain or 0,
            }

            steal_gain = self._number(data.get("user_steal_gain"))
            if steal_gain is None:
                steal_gain = total_steal_gain
            result["user_steal_gain"] = steal_gain or 0

            like_total = self._number(data.get("farm_like_total"))
            user_like_total = self._number(data.get("user_farm_like_total"))
            if like_total is None:
                like_total = user_like_total
            if user_like_total is None:
                user_like_total = like_total
            result["farm_like_total"] = like_total or 0
            result["user_farm_like_total"] = user_like_total or 0

            seeds: List[Dict[str, Any]] = []
            seed_by_id: Dict[int, Dict[str, Any]] = {}
            for raw_seed in data.get("seeds") or []:
                if not isinstance(raw_seed, dict):
                    continue
                seed_id = self._number(raw_seed.get("seed_id") or raw_seed.get("id"))
                if seed_id is None:
                    continue
                raw_stage_icons = raw_seed.get("stage_icons")
                stage_icons = {
                    phase: str(raw_stage_icons.get(phase) or "")
                    for phase in ("seedling", "growth", "mature")
                    if isinstance(raw_stage_icons, dict) and raw_stage_icons.get(phase)
                }
                grow_time = raw_seed.get("grow_time")
                seed = {
                    "seed_id": seed_id,
                    "name": str(raw_seed.get("name") or f"作物 {seed_id}"),
                    "base_reward": self._number(raw_seed.get("base_reward")) or 0,
                    "cost": self._number(raw_seed.get("cost")) or 0,
                    "icon": str(raw_seed.get("icon") or ""),
                    "emoji": self.crop_emoji(str(raw_seed.get("name") or "")),
                    "grow_time": str(grow_time) if grow_time is not None else "",
                    "unlock_harvest": self._number(
                        raw_seed.get("unlock_harvest")
                        or raw_seed.get("required_harvest")
                        or raw_seed.get("harvest_required")
                    ) or 0,
                    "stage_icons": stage_icons,
                }
                seeds.append(seed)
                seed_by_id[seed_id] = seed
            result["seeds"] = seeds

            raw_plot_slot = data.get("plot_slot") if isinstance(data.get("plot_slot"), dict) else {}
            raw_costs = raw_plot_slot.get("next_slot_cost_by_land")
            next_costs = dict(raw_costs) if isinstance(raw_costs, dict) else {}
            raw_effective_counts = raw_plot_slot.get("effective_plot_counts")
            if not isinstance(raw_effective_counts, dict):
                raw_effective_counts = {}
            effective_counts = {
                str(land_id): self._number(count) or 0
                for land_id, count in raw_effective_counts.items()
            }

            lands_by_id: Dict[str, Dict[str, Any]] = {}
            for raw_land in data.get("lands") or []:
                if not isinstance(raw_land, dict):
                    continue
                land_id = raw_land.get("land_id", raw_land.get("id"))
                if land_id is not None:
                    lands_by_id[str(land_id)] = raw_land

            user_lands: List[Dict[str, Any]] = []
            for raw_plot in data.get("user_lands") or []:
                if not isinstance(raw_plot, dict):
                    continue
                land_id = raw_plot.get("land_id", raw_plot.get("id"))
                land = lands_by_id.get(str(land_id), {})
                seed_id = self._number(raw_plot.get("seed_id"))
                raw_effective_count = raw_plot.get("effective_plot_count")
                if raw_effective_count is None:
                    raw_effective_count = effective_counts.get(
                        str(land_id), effective_counts.get(land_id)
                    )
                effective_count = self._number(raw_effective_count)
                plot_count = self._number(raw_plot.get("plot_count", land.get("plot_count")))
                seed = seed_by_id.get(seed_id) if seed_id is not None else None
                unlock_harvest = self._number(
                    raw_plot.get("unlock_harvest")
                    or land.get("unlock_harvest")
                    or land.get("required_harvest")
                    or land.get("harvest_required")
                )
                user_lands.append({
                    "land_id": land_id,
                    "name": str(raw_plot.get("name") or land.get("name") or ""),
                    "seed_id": seed_id,
                    "seed_name": str((seed or {}).get("name") or ""),
                    "seed": dict(seed) if seed else None,
                    "unlock_harvest": unlock_harvest or 0,
                    "plot_index": self._number(raw_plot.get("plot_index")),
                    "is_ready": str(raw_plot.get("is_ready", "0")) == "1",
                    "plant_time": self._number(raw_plot.get("plant_time")),
                    "harvest_time": self._number(raw_plot.get("harvest_time")),
                    "effective_plot_count": effective_count or plot_count or 0,
                    "plot_count": plot_count or effective_count or 0,
                })

            # 补全未解锁的 land（无实际 plot 但有地块元数据）
            represented_land_ids = {str(plot.get("land_id")) for plot in user_lands}
            for land_id, land in lands_by_id.items():
                if land_id in represented_land_ids:
                    continue
                unlock_harvest = self._number(
                    land.get("unlock_harvest")
                    or land.get("required_harvest")
                    or land.get("harvest_required")
                )
                user_lands.append({
                    "land_id": land_id,
                    "name": str(land.get("name") or ""),
                    "seed_id": None,
                    "seed_name": "",
                    "seed": None,
                    "unlock_harvest": unlock_harvest or 0,
                    "plot_index": None,
                    "is_ready": False,
                    "plant_time": None,
                    "harvest_time": None,
                    "effective_plot_count": effective_counts.get(str(land_id), 0) or 0,
                    "plot_count": self._number(land.get("plot_count")) or 0,
                })
            result["user_lands"] = user_lands

            inventory: List[Dict[str, Any]] = []
            for raw_item in data.get("inventory") or []:
                if not isinstance(raw_item, dict):
                    continue
                seed_id = self._number(raw_item.get("seed_id") or raw_item.get("id"))
                if seed_id is None:
                    continue
                seed = seed_by_id.get(seed_id, {})
                inventory.append({
                    "seed_id": seed_id,
                    "name": str(raw_item.get("name") or seed.get("name") or f"作物 {seed_id}"),
                    "quantity": self._number(raw_item.get("quantity")) or 0,
                    "unit_reward": self._number(
                        raw_item.get("unit_reward") or raw_item.get("base_unit_reward")
                    ) or self._number(seed.get("base_reward")) or 0,
                })
            result["inventory"] = inventory

            for field in ("like_max", "like_remaining"):
                value = self._number(data.get(field))
                result[field] = value or 0
            result["like_next_in"] = data.get("like_next_in")
            enabled = raw_plot_slot.get("enabled")
            available = raw_plot_slot.get("available")
            if enabled is None:
                enabled = available
            if enabled is None:
                enabled = any(self._number(cost) for cost in next_costs.values())
            if available is None:
                available = enabled
            result["plot_slot"] = {
                "enabled": bool(enabled),
                "available": bool(available),
                "max_per_land": self._number(raw_plot_slot.get("max_per_land")) or 0,
                "effective_plot_counts": effective_counts,
                "next_slot_cost_by_land": next_costs,
            }

            # 操作记录(对齐 KoWming p-history-list, 来自 fetch JSON user_logs)
            raw_logs = data.get("user_logs") if isinstance(data.get("user_logs"), list) else []
            logs: List[Dict[str, Any]] = []
            for raw_log in raw_logs:
                if not isinstance(raw_log, dict):
                    continue
                action = str(raw_log.get("action") or "").strip()
                value = self._number(raw_log.get("value")) or 0
                logs.append({
                    "action": action,
                    "seed_name": str(raw_log.get("seed_name") or ""),
                    "seed_icon": str(raw_log.get("seed_icon") or ""),
                    "land_name": str(raw_log.get("land_name") or ""),
                    "plot_index": self._number(raw_log.get("plot_index")),
                    "quantity": self._number(raw_log.get("quantity")) or 0,
                    "value": value,
                    "value_unit": "收获值" if action == "harvest" else "魔力值",
                    "created_at": str(raw_log.get("created_at") or ""),
                })
            result["user_logs"] = logs

            if not data:
                text = html or ""
                steal_match = re.search(r'id=["\']user-steal-gain["\'][^>]*>\s*([^<]+)', text)
                like_match = re.search(r'id=["\']user-farm-like-total["\'][^>]*>\s*([^<]+)', text)
                if steal_match:
                    result["user_steal_gain"] = self._number(steal_match.group(1)) or 0
                    result["user_stats"]["total_steal_gain"] = result["user_steal_gain"]
                if like_match:
                    result["farm_like_total"] = self._number(like_match.group(1)) or 0
                    result["user_farm_like_total"] = result["farm_like_total"]
        except Exception:
            # 站点字段可能随版本变化；详情接口应始终返回稳定结构。
            return result
        return result

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

    def get_harvest_all_submit_url(self) -> str:
        return f"{self.base_url}{self.farm_path}"

    def get_harvest_plot_url(self, land_id: Any, plot_index: Any) -> str:
        return self._action_url("harvest", land_id=land_id, plot_index=plot_index)

    def get_plant_plot_url(self) -> str:
        return self._action_url("plant")

    def parse_harvest_result(self, html: str) -> Dict[str, Any]:
        return self._parse_action_result(html, ("收获成功", "已收获"), "收获成功", "收获失败")

    def parse_plant_result(self, html: str, action: str = "plant") -> Dict[str, Any]:
        return self._parse_action_result(html, ("种植成功", "已种植"), "种植成功", "种植失败")

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
                return [
                    self._without_sensitive_fields(target)
                    for target in targets
                    if isinstance(target, dict)
                ]
            victim_id = data.get("victim_id")
            if victim_id is not None:
                return [{
                    "target_id": victim_id,
                    "name": data.get("victim_name") or data.get("username") or "",
                    "plots": self._without_sensitive_fields(
                        data.get("victim_plots") or data.get("user_lands") or []
                    ),
                }]
            return []

        targets: List[Dict[str, Any]] = []
        for tag in re.findall(r"<[^>]+data-(?:victim|target)-id=[^>]+>", html or "", re.IGNORECASE):
            target_id = re.search(r'data-(?:victim|target)-id=["\']?([^\s"\'>]+)', tag, re.IGNORECASE)
            name = re.search(r'data-(?:username|name)=["\']([^"\']*)', tag, re.IGNORECASE)
            if target_id:
                targets.append({"target_id": target_id.group(1), "name": html_lib.unescape(name.group(1)) if name else ""})
        return targets

    def get_steal_plot_url(self) -> str:
        return f"{self.base_url}{self.farm_path}"

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
        return f"{self.base_url}{self.farm_path}"

    def get_visit_submit_url(self) -> str:
        return self._action_url("view_farm_by_username")

    def get_sell_inventory_url(self) -> str:
        return self._action_url("sell_inventory")

    def get_buy_plot_slot_url(self) -> str:
        return f"{self.base_url}{self.farm_path}"

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

    def parse_visit_result(self, html: str) -> Dict[str, Any]:
        return self._parse_action_result(html, ("访问成功", "参观成功", "的农场"), "访问成功", "访问失败")

    def parse_sell_result(self, html: str) -> Dict[str, Any]:
        return self._parse_action_result(html, ("出售成功", "已出售", "获得"), "出售成功", "出售失败")

    def parse_buy_slot_result(self, html: str) -> Dict[str, Any]:
        return self._parse_action_result(html, ("购买成功", "扩地成功", "坑位"), "扩地成功", "扩地失败")
