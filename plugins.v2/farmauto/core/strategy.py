from typing import Any, Dict, List, Optional

from .models import WarehouseItem

DEFAULT_POLICY: Dict[str, Any] = {
    "min_profit_rate": 0.0,
    "max_profit_rate": 0.0,
    "max_sell_per_run": 50,
    "expire_threshold_minutes": 120,
    "request_interval": 1.0,
    "dry_run": False,
    "auto_harvest": True,
    "auto_plant": True,
    "auto_sell": True,
    "expiry_sale": True,
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
    max_profit_rate = float(policy["max_profit_rate"])
    profit = market_price - cost
    if market_price <= cost:
        return False
    if min_profit_rate > 0 and cost > 0 and profit < cost * min_profit_rate:
        return False
    # cost=0 时跳过 max_profit_rate 限制(纯利润作物)
    if cost == 0:
        return True
    return max_profit_rate <= 0 or profit <= cost * max_profit_rate


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


def plan_smart(
    snapshot, warehouse, site_config, policy, crops_override: Optional[Dict] = None
) -> List[dict]:
    policy = _policy(policy)
    plan: List[dict] = []
    remaining_sales = int(policy["max_sell_per_run"])
    market_prices = snapshot.get("market_prices", {})
    crop_status = snapshot.get("crop_status", {})
    warehouse_items = [_warehouse_model(item) for item in warehouse]
    crops = crops_override if crops_override is not None else site_config.crops

    for crop_key, crop in crops.items():
        price = int(market_prices.get(crop_key, 0))
        # 收获不受 should_sell 限制（收获免费，即使亏损也该收获成熟作物）
        can_harvest = crop_status.get(crop_key, {}).get("can_harvest") and policy["auto_harvest"]
        should_sell_flag = should_sell(crop, price, policy)
        if not should_sell_flag and not can_harvest:
            continue
        if should_sell_flag and policy["auto_sell"]:
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
        if can_harvest:
            plan.append({"op": "harvest", "crop_key": crop_key, "source": "field", "quantity": 1})
            if policy["auto_plant"]:
                plan.append({"op": "plant", "crop_key": crop_key, "source": "field", "quantity": 1})
            # sell_inventory 类站点(如思齐)收获后作物进背包, field sell 时背包还没货, 跳过
            if should_sell_flag and policy["auto_sell"] and remaining_sales > 0 and not site_config.supports_sell_inventory():
                plan.append({"op": "sell", "crop_key": crop_key, "source": "field", "quantity": 1})
                remaining_sales -= 1
    return plan


def plan_harvest(
    snapshot, warehouse, site_config, policy, crops_override: Optional[Dict] = None
) -> List[dict]:
    policy = _policy(policy)
    plan: List[dict] = []
    crop_status = snapshot.get("crop_status", {})
    market_prices = snapshot.get("market_prices", {})
    crops = crops_override if crops_override is not None else site_config.crops

    if policy["auto_harvest"]:
        if site_config.supports("harvest_all"):
            plan.append({"op": "harvest_all", "crop_key": "all", "source": "field", "quantity": 1})
        else:
            for crop_key, status in crop_status.items():
                if status.get("can_harvest") and crop_key in crops:
                    plan.append({"op": "harvest", "crop_key": crop_key, "source": "field", "quantity": 1})

    if policy["auto_plant"]:
        for crop_key in crops:
            plan.append({"op": "plant", "crop_key": crop_key, "source": "field", "quantity": 1})

    threshold = int(policy["expire_threshold_minutes"])
    remaining_sales = int(policy["max_sell_per_run"])
    warehouse_items = [_warehouse_model(item) for item in warehouse]
    warehouse_items.sort(key=lambda item: item.expire_minutes if item.expire_minutes is not None else 10**12)
    for item in warehouse_items:
        crop = crops.get(item.crop_key or "")
        if not crop or not item.sell_key or remaining_sales <= 0:
            continue
        price = int(market_prices.get(item.crop_key, 0))
        profit_sale = policy["auto_sell"] and should_sell(crop, price, policy)
        expiry_sale = (
            policy["expiry_sale"]
            and site_config.supports("expiry_sale")
            and is_expiry(item, threshold)
        )
        if not (profit_sale or expiry_sale):
            continue
        quantity = min(item.quantity, remaining_sales)
        plan.append({
            "op": "sell", "crop_key": item.crop_key, "source": "warehouse",
            "quantity": quantity, "sell_key": item.sell_key,
        })
        remaining_sales -= quantity
    return plan


def plan_warehouse_sales(
    warehouse, market_prices: dict, crops: dict, site_config, policy: dict
) -> List[dict]:
    """按临期优先、盈利其次生成仓库出售计划。"""
    remaining_sales = int(policy["max_sell_per_run"])
    threshold = int(policy["expire_threshold_minutes"])
    items = [_warehouse_model(item) for item in warehouse]
    items.sort(key=lambda item: item.expire_minutes if item.expire_minutes is not None else 10**12)
    plan: List[dict] = []
    for item in items:
        if remaining_sales <= 0:
            break
        crop = crops.get(item.crop_key or "")
        if not crop or not item.sell_key:
            continue
        price = int(market_prices.get(item.crop_key, 0))
        expiry_sale = (
            policy["expiry_sale"]
            and site_config.supports("expiry_sale")
            and is_expiry(item, threshold)
        )
        profit_sale = policy["auto_sell"] and should_sell(crop, price, policy)
        if not (expiry_sale or profit_sale):
            continue
        quantity = min(item.quantity, remaining_sales)
        plan.append({
            "op": "sell", "crop_key": item.crop_key, "source": "warehouse",
            "quantity": quantity, "sell_key": item.sell_key,
        })
        remaining_sales -= quantity
    return plan


def plan_generic_run(
    snapshot, warehouse, site_config, policy, crops_override: Optional[Dict] = None
) -> List[dict]:
    """普通农场：收获 → 种植/养殖 → 仓库临期或盈利出售。"""
    policy = _policy(policy)
    plan: List[dict] = []
    market_prices = snapshot.get("market_prices", {})
    crop_status = snapshot.get("crop_status", {})
    crops = crops_override if crops_override is not None else site_config.crops
    harvestable = [
        crop_key for crop_key, status in crop_status.items()
        if crop_key in crops and isinstance(status, dict) and status.get("can_harvest")
    ]

    if policy["auto_harvest"] and harvestable:
        if site_config.supports("harvest_all"):
            plan.append({"op": "harvest_all", "crop_key": "all", "source": "field", "quantity": 1})
        else:
            plan.extend(
                {"op": "harvest", "crop_key": crop_key, "source": "field", "quantity": 1}
                for crop_key in harvestable
            )

    if policy["auto_plant"]:
        for crop_key in crops:
            status = crop_status.get(crop_key, {})
            if not isinstance(status, dict):
                continue
            # 本轮收获后对应位置会变为空；初始明确 empty 的位置也可种植。
            if crop_key in harvestable or status.get("state") == "empty":
                plan.append({"op": "plant", "crop_key": crop_key, "source": "field", "quantity": 1})

    plan.extend(plan_warehouse_sales(warehouse, market_prices, crops, site_config, policy))
    return plan


def plan_siqi_run(
    snapshot, warehouse, site_config, policy, crops_override: Optional[Dict] = None
) -> List[dict]:
    """思齐静态计划骨架；执行器后续按阶段刷新状态。

    当前计划只生成逐地块收获、一次批量种植和真实背包出售，避免每收获一格就重复
    plant_fill_empty。批量种植仅在初始存在已解锁空地或本轮存在成熟地块时生成。
    """
    policy = _policy(policy)
    plan: List[dict] = []
    market_prices = snapshot.get("market_prices", {})
    crop_status = snapshot.get("crop_status", {})
    crops = crops_override if crops_override is not None else site_config.crops
    ready_plots = [
        (plot_key, status) for plot_key, status in crop_status.items()
        if isinstance(status, dict)
        and status.get("state") == "ripe"
        and status.get("can_harvest")
        and status.get("crop_key") in crops
    ]
    empty_plots = [
        status for status in crop_status.values()
        if isinstance(status, dict)
        and status.get("state") == "empty"
        and status.get("plot_index") is not None
    ]

    if policy["auto_harvest"]:
        plan.extend(
            {"op": "harvest", "crop_key": plot_key, "source": "field", "quantity": 1}
            for plot_key, _ in ready_plots
        )
    if policy["auto_plant"] and (empty_plots or (policy["auto_harvest"] and ready_plots)):
        plan.append({"op": "plant", "crop_key": "all", "source": "field", "quantity": 1})
    plan.extend(plan_warehouse_sales(warehouse, market_prices, crops, site_config, policy))
    return plan


def plan_run(
    snapshot, warehouse, site_config, policy, crops_override: Optional[Dict] = None
) -> List[dict]:
    """兼容入口：按站点类型分发到互不交叉的计划流程。"""
    planner = plan_siqi_run if site_config.site_id == "siqi" else plan_generic_run
    return planner(snapshot, warehouse, site_config, policy, crops_override)
