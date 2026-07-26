import time
from typing import Any, Dict, List, Optional

from .http_client import AuthError, FarmHttpClient
from .models import ActionResult, SiteRunReport
from .strategy import DEFAULT_POLICY, plan_harvest, plan_smart
from .trend import PriceTrendStore


class FarmExecutor:
    def __init__(
        self,
        http_client: FarmHttpClient,
        logger,
        trend_store: Optional[PriceTrendStore] = None,
    ):
        self.http_client = http_client
        self.logger = logger
        self.trend_store = trend_store

    @staticmethod
    def _cookie_dict(cookie: str) -> Dict[str, str]:
        cookies: Dict[str, str] = {}
        for part in (cookie or "").split(";"):
            if "=" in part:
                key, value = part.strip().split("=", 1)
                cookies[key.strip()] = value.strip()
        return cookies

    def run_site(self, cookie: str, site_config, mode: str, policy: dict) -> SiteRunReport:
        policy = {**DEFAULT_POLICY, **(policy or {})}
        report = SiteRunReport(site_config.site_id, site_config.site_name, mode)
        cookies = self._cookie_dict(cookie)
        if not cookies:
            report.status = "failed"
            report.message = "未提供有效 Cookie"
            return report

        try:
            farm_response = self.http_client.get(site_config.get_farm_url(), cookies)
            farm_response.raise_for_status()
            farm_html = farm_response.text
            if not site_config.check_auth(farm_html):
                raise AuthError("Cookie 已失效")

            report.market_prices = site_config.parse_market_prices(farm_html)
            if self.trend_store is not None:
                self.trend_store.record(site_config.site_id, report.market_prices)
            report.crop_status = site_config.parse_crop_status(farm_html)
            snapshot = {
                "market_prices": report.market_prices,
                "crop_status": report.crop_status,
            }
            warehouse = self._fetch_warehouse(cookies, site_config)
            report.warehouse = warehouse

            if mode == "smart":
                plan = plan_smart(snapshot, warehouse, site_config, policy)
            elif mode == "harvest":
                plan = plan_harvest(snapshot, warehouse, site_config, policy)
            else:
                report.status = "skipped"
                report.message = f"不支持的运行模式：{mode}"
                return report

            if policy["dry_run"]:
                for action in plan:
                    crop = site_config.crops.get(action["crop_key"], {})
                    target = crop.get("name", action["crop_key"])
                    for _ in range(int(action.get("quantity", 1))):
                        report.actions.append(ActionResult(
                            action["op"], target, True, message="dry-run：仅记录计划"
                        ))
                report.status = "skipped"
                report.message = f"dry-run：记录 {len(report.actions)} 个计划操作"
                return report

            sold_count = 0
            field_html = farm_html
            blocked_crops = set()
            for action in plan:
                crop_key = action["crop_key"]
                if crop_key in blocked_crops and action["op"] in ("plant", "sell") and action.get("source") == "field":
                    continue
                quantity = int(action.get("quantity", 1))
                if action["op"] == "sell":
                    allowed = max(0, int(policy["max_sell_per_run"]) - sold_count)
                    quantity = min(quantity, allowed)
                for _ in range(quantity):
                    result, field_html = self._execute_action(
                        action,
                        cookies,
                        site_config,
                        policy,
                        field_html,
                        report.market_prices,
                    )
                    report.actions.append(result)
                    if result.success:
                        report.trades_count += 1
                        report.total_profit += result.profit
                        if action["op"] == "sell":
                            sold_count += 1
                    elif action["op"] == "harvest" and action.get("source") == "field":
                        blocked_crops.add(crop_key)
                        break
                    time.sleep(max(0.0, float(policy["request_interval"])))

            failures = sum(not action.success for action in report.actions)
            report.status = "partial" if failures else "completed"
            report.message = (
                f"完成 {report.trades_count} 个操作"
                if report.actions
                else "无可执行操作"
            )
        except AuthError as error:
            report.status = "failed"
            report.message = f"认证失败：{error}"
        except Exception as error:
            report.status = "failed"
            report.message = str(error)
            try:
                self.logger.error(f"{site_config.site_name} 农场任务失败：{error}")
            except Exception:
                pass
        return report

    def _fetch_warehouse(self, cookies: Dict[str, str], site_config) -> List[Dict[str, Any]]:
        response = self.http_client.get(site_config.get_warehouse_url(), cookies)
        response.raise_for_status()
        items, next_page = site_config.parse_warehouse_page(response.text)
        page_count = 1
        while site_config.supports("warehouse_pagination") and next_page is not None and page_count < 10:
            response = self.http_client.get(site_config.get_warehouse_page_url(next_page), cookies)
            response.raise_for_status()
            page_items, next_page = site_config.parse_warehouse_page(response.text)
            items.extend(page_items)
            page_count += 1
        return items

    def _execute_action(
        self, action, cookies, site_config, policy, farm_html, market_prices
    ):
        crop_key = action.get("crop_key", "")
        crop = site_config.crops.get(crop_key, {})
        target = crop.get("name", crop_key)
        operation = action.get("op", "unknown")

        try:
            if operation == "harvest_all":
                response = self.http_client.get(site_config.get_harvest_all_url(), cookies)
                response.raise_for_status()
                parsed = site_config.parse_harvest_result(response.text)
            elif operation == "harvest":
                response = self.http_client.get(
                    site_config.get_harvest_url(crop["type"], crop["id"]), cookies
                )
                response.raise_for_status()
                parsed = site_config.parse_harvest_result(response.text)
            elif operation == "plant":
                crop_action = crop.get("action", "plant")
                url = (
                    site_config.get_breed_url(crop["type"], crop["id"])
                    if crop_action == "breed"
                    else site_config.get_plant_url(crop["type"], crop["id"])
                )
                response = self.http_client.get(url, cookies)
                response.raise_for_status()
                parsed = site_config.parse_plant_result(response.text, crop_action)
            elif operation == "sell":
                sell_key = action.get("sell_key")
                if action.get("source") == "field":
                    latest = self.http_client.get(site_config.get_farm_url(), cookies)
                    latest.raise_for_status()
                    farm_html = latest.text
                    sell_key = site_config.get_sell_key(farm_html, crop["type"], crop["id"])
                    sell_key = sell_key or f"{crop['type']}_{crop['id']}"
                if not sell_key:
                    return ActionResult("sell", target, False, message="未找到出售标识"), farm_html
                response = self.http_client.get(site_config.get_sell_url(sell_key), cookies)
                response.raise_for_status()
                parsed = site_config.parse_sell_result(response.text)
            else:
                return ActionResult(operation, target, False, message="未知操作"), farm_html

            success = bool(parsed.get("success"))
            profit = 0
            if success and operation == "sell":
                price = int(market_prices.get(crop_key, 0))
                cost = int(crop.get("cost", 0))
                if price > 0 and cost > 0:
                    profit = price - cost
            result = ActionResult(
                operation,
                target,
                success,
                double=bool(parsed.get("double", False)),
                profit=profit,
                message=parsed.get("message", ""),
            )
            return result, farm_html
        except AuthError:
            raise
        except Exception as error:
            return ActionResult(operation, target, False, message=str(error)), farm_html
