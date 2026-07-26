from typing import Any, Dict, List

from .models import WarehouseItem

DEFAULT_POLICY: Dict[str, Any] = {
    "min_profit_rate": 0.0,
    "max_sell_per_run": 50,
    "expire_threshold_minutes": 120,
    "request_interval": 1.0,
    "dry_run": False,
}


def effective_site_policy(global_policy: dict, site_overrides: dict, site_id: str) -> dict:
    override = site_overrides.get(site_id, {}) if isinstance(site_overrides, dict) else {}
    policy = {**(global_policy or {}), **(override if isinstance(override, dict) else {})}
    return {key: value for key, value in policy.items() if key not in ("enabled", "mode")}


def effective_site_mode(default_mode: str, site_overrides: dict, site_id: str) -> str:
    override = site_overrides.get(site_id, {}) if isinstance(site_overrides, dict) else {}
    return override.get("mode", default_mode) if isinstance(override, dict) else default_mode


def site_is_enabled(site_overrides: dict, site_id: str) -> bool:
    override = site_overrides.get(site_id, {}) if isinstance(site_overrides, dict) else {}
    return not (isinstance(override, dict) and override.get("enabled") is False)


def _policy(policy: dict) -> dict:
    return {**DEFAULT_POLICY, **(policy or {})}


def should_sell(crop: dict, market_price: int, policy: dict) -> bool:
    policy = _policy(policy)
    cost = int(crop.get("cost", 0))
    min_profit_rate = float(policy["min_profit_rate"])
    if min_profit_rate == 0:
        return market_price > cost
    return market_price > 0 and market_price - cost >= cost * min_profit_rate


def is_expiry(item: WarehouseItem, threshold_minutes: int) -> bool:
    return item.expire_minutes is not None and item.expire_minutes <= threshold_minutes


def _warehouse_model(item: Any) -> WarehouseItem:
    if isinstance(item, WarehouseItem):
        return item
    return WarehouseItem(
        name=item.get("name", ""),
        quantity=int(item.get("quantity", 1)),
        expire_raw=item.get("expire_raw", item.get("expire", "")),
        expire_minutes=item.get("expire_minutes"),
        sell_key=item.get("sell_key", ""),
        crop_key=item.get("crop_key"),
    )


def plan_smart(snapshot, warehouse, site_config, policy) -> List[dict]:
    policy = _policy(policy)
    plan: List[dict] = []
    remaining_sales = int(policy["max_sell_per_run"])
    market_prices = snapshot.get("market_prices", {})
    crop_status = snapshot.get("crop_status", {})
    warehouse_items = [_warehouse_model(item) for item in warehouse]

    for crop_key, crop in site_config.crops.items():
        price = int(market_prices.get(crop_key, 0))
        if not should_sell(crop, price, policy):
            continue
        for item in warehouse_items:
            if remaining_sales <= 0 or item.crop_key != crop_key or not item.sell_key:
                continue
            quantity = min(item.quantity, remaining_sales)
            if quantity > 0:
                plan.append({
                    "op": "sell", "crop_key": crop_key, "source": "warehouse",
                    "quantity": quantity, "sell_key": item.sell_key,
                })
                remaining_sales -= quantity
        if crop_status.get(crop_key, {}).get("can_harvest"):
            plan.append({"op": "harvest", "crop_key": crop_key, "source": "field", "quantity": 1})
            plan.append({"op": "plant", "crop_key": crop_key, "source": "field", "quantity": 1})
            if remaining_sales > 0:
                plan.append({"op": "sell", "crop_key": crop_key, "source": "field", "quantity": 1})
                remaining_sales -= 1
    return plan


def plan_harvest(snapshot, warehouse, site_config, policy) -> List[dict]:
    policy = _policy(policy)
    plan: List[dict] = []
    crop_status = snapshot.get("crop_status", {})
    market_prices = snapshot.get("market_prices", {})

    if site_config.supports("harvest_all"):
        plan.append({"op": "harvest_all", "crop_key": "all", "source": "field", "quantity": 1})
    else:
        for crop_key, status in crop_status.items():
            if status.get("can_harvest") and crop_key in site_config.crops:
                plan.append({"op": "harvest", "crop_key": crop_key, "source": "field", "quantity": 1})

    for crop_key in site_config.crops:
        plan.append({"op": "plant", "crop_key": crop_key, "source": "field", "quantity": 1})

    threshold = int(policy["expire_threshold_minutes"])
    remaining_sales = int(policy["max_sell_per_run"])
    warehouse_items = [_warehouse_model(item) for item in warehouse]
    warehouse_items.sort(key=lambda item: item.expire_minutes if item.expire_minutes is not None else 10**12)
    for item in warehouse_items:
        crop = site_config.crops.get(item.crop_key or "")
        if not crop or not item.sell_key or remaining_sales <= 0:
            continue
        price = int(market_prices.get(item.crop_key, 0))
        expiry_sale = site_config.supports("expiry_sale") and is_expiry(item, threshold)
        if not (expiry_sale or should_sell(crop, price, policy)):
            continue
        quantity = min(item.quantity, remaining_sales)
        plan.append({
            "op": "sell", "crop_key": item.crop_key, "source": "warehouse",
            "quantity": quantity, "sell_key": item.sell_key,
        })
        remaining_sales -= quantity
    return plan
