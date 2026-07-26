import time
from typing import Any, Dict, List, Optional

from .captcha import OcrRecognizer
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
        ocr_recognizer: Optional[OcrRecognizer] = None,
    ):
        self.http_client = http_client
        self.logger = logger
        self.trend_store = trend_store
        self.ocr_recognizer = ocr_recognizer or OcrRecognizer()

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
            batch_sell_indexes = [
                index for index, action in enumerate(plan)
                if action.get("op") == "sell" and action.get("source") == "warehouse"
            ] if site_config.supports_batch_sell() else []
            batch_sell_index_set = set(batch_sell_indexes)
            first_batch_sell_index = batch_sell_indexes[0] if batch_sell_indexes else None

            for index, action in enumerate(plan):
                if index in batch_sell_index_set:
                    if index != first_batch_sell_index:
                        continue
                    allowed = max(0, int(policy["max_sell_per_run"]) - sold_count)
                    batch_actions = [plan[action_index] for action_index in batch_sell_indexes]
                    results = self._execute_batch_sell(
                        batch_actions,
                        cookies,
                        site_config,
                        report.market_prices,
                        allowed,
                    )
                    report.actions.extend(results)
                    for result in results:
                        if result.success:
                            report.trades_count += 1
                            report.total_profit += result.profit
                            sold_count += 1
                    time.sleep(max(0.0, float(policy["request_interval"])))
                    continue

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

    def run_siqi_extras(
        self,
        cookie: str,
        site_config,
        options: Optional[Dict[str, bool]] = None,
        skip_daily: Optional[Dict[str, bool]] = None,
    ) -> List[ActionResult]:
        """执行思齐高风险动作；调用方负责每日状态的读取与保存。"""
        options = options or {}
        skip_daily = skip_daily or {}
        if site_config.site_id != "siqi" or not site_config.supports("captcha"):
            return []
        cookies = self._cookie_dict(cookie)
        if not cookies:
            return []

        results: List[ActionResult] = []
        actions = (
            ("auto_captcha_harvest", "harvest_captcha", lambda: self._do_siqi_captcha_harvest(
                cookies, site_config, bool(options.get("captcha_ocr", True))
            )),
            ("auto_steal", "steal", lambda: self._do_siqi_steal(cookies, site_config)),
            ("auto_like", "like", lambda: self._do_siqi_like(cookies, site_config)),
            ("auto_buy_slot", "buy_slot", lambda: self._do_siqi_buy_slot(cookies, site_config)),
        )
        for option, action, operation in actions:
            if not options.get(option, False) or skip_daily.get(action, False):
                continue
            try:
                results.append(operation())
            except Exception as error:
                results.append(ActionResult(action, site_config.site_name, False, message=str(error)))
        return results

    def _do_siqi_captcha_harvest(self, cookies, site_config, use_ocr=True) -> ActionResult:
        if use_ocr:
            try:
                response = self.http_client.get(site_config.get_harvest_captcha_url(), cookies)
                response.raise_for_status()
                captcha = site_config.parse_captcha_info(response.text)
                imagehash = captcha.get("imagehash")
                image_url = captcha.get("image_url") or (
                    site_config.get_captcha_image_url(imagehash) if imagehash else ""
                )
                if image_url and not str(image_url).startswith(("http://", "https://")):
                    image_url = f"{site_config.base_url.rstrip('/')}/{str(image_url).lstrip('/')}"
                recognized = self.ocr_recognizer.recognize(image_url, cookies, self.http_client) if image_url else None
                if imagehash and recognized:
                    submitted = self.http_client.post(
                        site_config.get_harvest_all_submit_url(),
                        cookies,
                        data={
                            "option": "harvest_all",
                            "imagehash": imagehash,
                            "imagestring": recognized,
                        },
                    )
                    submitted.raise_for_status()
                    parsed = site_config.parse_harvest_captcha_result(submitted.text)
                    if parsed.get("success"):
                        return ActionResult(
                            "harvest_captcha", "全部成熟作物", True,
                            message=parsed.get("message", "验证码收获成功"),
                        )
            except Exception:
                pass
        return self._do_siqi_plot_harvest(cookies, site_config)

    def _do_siqi_plot_harvest(self, cookies, site_config) -> ActionResult:
        response = self.http_client.get(site_config.get_warehouse_url(), cookies)
        response.raise_for_status()
        plots = site_config.parse_ready_plots(response.text)
        failures = 0
        for plot in plots:
            try:
                harvested = self.http_client.get(
                    site_config.get_harvest_plot_url(plot["land_id"], plot["plot_index"]),
                    cookies,
                )
                harvested.raise_for_status()
                if not site_config.parse_harvest_result(harvested.text).get("success"):
                    failures += 1
            except Exception:
                failures += 1
        success = bool(plots) and failures == 0
        message = (
            f"逐格收获已尝试 {len(plots)} 格" + (f"，失败 {failures} 格" if failures else "")
            if plots else "没有成熟作物可逐格收获"
        )
        return ActionResult("harvest_captcha", "成熟作物", success, message=message)

    @staticmethod
    def _siqi_target_fields(target: Any) -> Dict[str, Any]:
        if not isinstance(target, dict):
            return {"target_id": target}
        result = dict(target)
        result["target_id"] = (
            target.get("target_id") or target.get("victim_id") or target.get("farm_id")
            or target.get("id") or target.get("username")
        )
        return result

    def _do_siqi_steal(self, cookies, site_config) -> ActionResult:
        target_response = self.http_client.post(
            site_config.get_steal_target_url(), cookies, data={}
        )
        target_response.raise_for_status()
        targets = site_config.parse_steal_targets(target_response.text)
        if not targets:
            return ActionResult("steal", "随机农场", False, message="没有可偷菜目标")
        target = self._siqi_target_fields(targets[0])
        plots = target.get("plots") or target.get("victim_plots") or []
        plot = next(
            (
                item for item in plots
                if isinstance(item, dict) and str(item.get("is_ready", "1")) == "1"
            ),
            {},
        )
        data = {
            "victim_id": target.get("target_id"),
            "land_id": plot.get("land_id", target.get("land_id")),
            "plot_index": plot.get("plot_index", target.get("plot_index")),
        }
        if any(value is None for value in data.values()):
            return ActionResult("steal", str(data.get("victim_id") or "随机农场"), False, message="目标缺少可偷坑位")
        response = self.http_client.post(site_config.get_steal_plot_url(), cookies, data=data)
        response.raise_for_status()
        parsed = site_config.parse_steal_result(response.text)
        return ActionResult("steal", str(data["victim_id"]), bool(parsed.get("success")), message=parsed.get("message", ""))

    def _do_siqi_like(self, cookies, site_config) -> ActionResult:
        target_response = self.http_client.post(
            site_config.get_like_target_url(), cookies, data={}
        )
        target_response.raise_for_status()
        targets = site_config.parse_like_targets(target_response.text)
        if not targets:
            return ActionResult("like", "随机农场", False, message="没有可点赞目标")
        target = self._siqi_target_fields(targets[0])
        target_id = target.get("target_id")
        response = self.http_client.post(
            site_config.get_like_submit_url(), cookies,
            data={"target_id": target_id},
        )
        response.raise_for_status()
        parsed = site_config.parse_like_result(response.text)
        return ActionResult("like", str(target_id), bool(parsed.get("success")), message=parsed.get("message", ""))

    def _do_siqi_buy_slot(self, cookies, site_config) -> ActionResult:
        farm_response = self.http_client.get(site_config.get_warehouse_url(), cookies)
        farm_response.raise_for_status()
        targets = site_config.parse_buy_slot_targets(farm_response.text)
        if not targets:
            return ActionResult("buy_slot", "农场坑位", False, message="没有可购买坑位")
        land_id = targets[0]
        response = self.http_client.post(
            site_config.get_buy_plot_slot_url(), cookies,
            data={"land_id": land_id},
        )
        response.raise_for_status()
        parsed = site_config.parse_buy_slot_result(response.text)
        return ActionResult("buy_slot", str(land_id), bool(parsed.get("success")), message=parsed.get("message", ""))

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

    def _execute_batch_sell(
        self, action_group, cookies, site_config, market_prices, max_items
    ) -> List[ActionResult]:
        pending = action_group[:max_items]
        if not pending:
            return []

        sell_keys = [str(action.get("sell_key", "")) for action in pending]
        if not all(sell_keys):
            return [
                ActionResult(
                    "sell",
                    site_config.crops.get(action.get("crop_key", ""), {}).get(
                        "name", action.get("crop_key", "")
                    ),
                    False,
                    message="未找到出售标识",
                )
                for action in pending
            ]

        try:
            response = self.http_client.post(
                site_config.get_batch_sell_url(),
                cookies,
                data={"batch_keys[]": sell_keys},
            )
            response.raise_for_status()
            parsed = site_config.parse_batch_sell_result(response.text)
            sold_count = int(parsed.get("sold_count", -1))
            if sold_count < 0:
                sold_count = len(pending) if parsed.get("success") else 0
            sold_count = min(max(sold_count, 0), len(pending))
            message = parsed.get("message", "")
            results = []
            for index, action in enumerate(pending):
                crop_key = action.get("crop_key", "")
                crop = site_config.crops.get(crop_key, {})
                success = index < sold_count
                profit = 0
                if success:
                    price = int(market_prices.get(crop_key, 0))
                    cost = int(crop.get("cost", 0))
                    if price > 0 and cost > 0:
                        profit = price - cost
                results.append(ActionResult(
                    "sell",
                    crop.get("name", crop_key),
                    success,
                    profit=profit,
                    message=message,
                ))
            return results
        except Exception as error:
            return [
                ActionResult(
                    "sell",
                    site_config.crops.get(action.get("crop_key", ""), {}).get(
                        "name", action.get("crop_key", "")
                    ),
                    False,
                    message=str(error),
                )
                for action in pending
            ]

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
