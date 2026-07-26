import time
from typing import Any, Dict, List, Optional

from .captcha import OcrRecognizer
from .http_client import AuthError, FarmHttpClient
from .models import ActionResult, SiteRunReport
from .strategy import DEFAULT_POLICY, plan_harvest, plan_smart
from .trend import PriceTrendStore


class FarmExecutor:
    ACTION_NAMES = {
        "harvest_all": "一键收获",
        "harvest": "收获",
        "plant": "种植",
        "sell": "出售",
        "harvest_captcha": "验证码收获",
        "steal": "偷菜",
        "like": "点赞",
        "buy_slot": "扩地",
    }

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

    def _log(self, level: str, message: str) -> None:
        try:
            getattr(self.logger, level)(f"[FarmAuto] {message}")
        except (AttributeError, TypeError):
            pass

    def _log_action(self, site_name: str, result: ActionResult) -> None:
        action = self.ACTION_NAMES.get(result.action, result.action)
        outcome = "成功" if result.success else "失败"
        self._log(
            "info",
            f"{site_name} {action} {result.target} {outcome}: {result.message}",
        )

    @staticmethod
    def _error_context(error: BaseException, url: str = "") -> str:
        response = getattr(error, "response", None)
        error_url = url or getattr(response, "url", "")
        status = getattr(response, "status_code", None)
        context = []
        if error_url:
            context.append(f"url={error_url}")
        if status is not None:
            context.append(f"status={status}")
        return f"{error} ({', '.join(context)})" if context else str(error)

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
        site_name = site_config.site_name
        dry_run = bool(policy.get("dry_run", False))
        self._log("info", f"{site_name} 开始执行（mode={mode}, dry_run={dry_run}）")
        cookies = self._cookie_dict(cookie)
        if not cookies:
            report.status = "failed"
            report.message = "未提供有效 Cookie"
            self._log("error", f"{site_name} 认证 异常：{report.message}")
            return report

        current_action = "拉取农场页"
        current_url = site_config.get_farm_url()
        try:
            self._log("debug", f"{site_name} 拉取农场页 {current_url}")
            farm_response = self.http_client.get(current_url, cookies)
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
            current_action = "拉取仓库"
            current_url = site_config.get_warehouse_url()
            warehouse = self._fetch_warehouse(cookies, site_config)
            report.warehouse = warehouse
            harvestable = sum(
                bool(status.get("can_harvest"))
                for status in report.crop_status.values()
                if isinstance(status, dict)
            )
            self._log(
                "info",
                f"{site_name} 解析到 {len(report.market_prices)} 种价格、"
                f"{harvestable} 可收获、{len(warehouse)} 仓库项",
            )

            current_action = "生成计划"
            current_url = ""
            if mode == "smart":
                plan = plan_smart(snapshot, warehouse, site_config, policy)
            elif mode == "harvest":
                plan = plan_harvest(snapshot, warehouse, site_config, policy)
            else:
                report.status = "skipped"
                report.message = f"不支持的运行模式：{mode}"
                self._log("error", f"{site_name} 生成计划 异常：{report.message}")
                return report

            self._log("debug", f"{site_name} 执行计划 {len(plan)} 步")
            if policy["dry_run"]:
                for action in plan:
                    crop = site_config.crops.get(action["crop_key"], {})
                    target = crop.get("name", action["crop_key"])
                    for _ in range(int(action.get("quantity", 1))):
                        result = ActionResult(
                            action["op"], target, True, message="dry-run：仅记录计划"
                        )
                        report.actions.append(result)
                        self._log_action(site_name, result)
                report.status = "skipped"
                report.message = f"dry-run：记录 {len(report.actions)} 个计划操作"
                self._log(
                    "info",
                    f"{site_name} 完成：{report.trades_count} 笔交易，利润 "
                    f"{report.total_profit} {site_config.currency}",
                )
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
                        self._log_action(site_name, result)
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
                    self._log_action(site_name, result)
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
            self._log(
                "info",
                f"{site_name} 完成：{report.trades_count} 笔交易，利润 "
                f"{report.total_profit} {site_config.currency}",
            )
        except AuthError as error:
            report.status = "failed"
            report.message = f"认证失败：{error}"
            failed_action = getattr(error, "farm_action", current_action)
            failed_url = getattr(error, "farm_url", current_url)
            self._log(
                "error",
                f"{site_name} {failed_action} 异常："
                f"{self._error_context(error, failed_url)}",
            )
        except Exception as error:
            report.status = "failed"
            report.message = str(error)
            self._log(
                "error",
                f"{site_name} {current_action} 异常："
                f"{self._error_context(error, current_url)}",
            )
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
                result = operation()
            except Exception as error:
                self._log(
                    "error",
                    f"{site_config.site_name} {self.ACTION_NAMES.get(action, action)} "
                    f"异常：{self._error_context(error)}",
                )
                result = ActionResult(
                    action, site_config.site_name, False, message=str(error)
                )
            results.append(result)
            self._log_action(site_config.site_name, result)
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
            self._log(
                "error",
                f"{site_config.site_name} 出售 异常："
                f"{self._error_context(error, site_config.get_batch_sell_url())}",
            )
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
        action_url = ""

        try:
            if operation == "harvest_all":
                action_url = site_config.get_harvest_all_url()
                response = self.http_client.get(action_url, cookies)
                response.raise_for_status()
                parsed = site_config.parse_harvest_result(response.text)
            elif operation == "harvest":
                action_url = site_config.get_harvest_url(crop["type"], crop["id"])
                response = self.http_client.get(action_url, cookies)
                response.raise_for_status()
                parsed = site_config.parse_harvest_result(response.text)
            elif operation == "plant":
                crop_action = crop.get("action", "plant")
                url = (
                    site_config.get_breed_url(crop["type"], crop["id"])
                    if crop_action == "breed"
                    else site_config.get_plant_url(crop["type"], crop["id"])
                )
                action_url = url
                response = self.http_client.get(action_url, cookies)
                response.raise_for_status()
                parsed = site_config.parse_plant_result(response.text, crop_action)
            elif operation == "sell":
                sell_key = action.get("sell_key")
                if action.get("source") == "field":
                    action_url = site_config.get_farm_url()
                    latest = self.http_client.get(action_url, cookies)
                    latest.raise_for_status()
                    farm_html = latest.text
                    sell_key = site_config.get_sell_key(farm_html, crop["type"], crop["id"])
                    sell_key = sell_key or f"{crop['type']}_{crop['id']}"
                if not sell_key:
                    return ActionResult("sell", target, False, message="未找到出售标识"), farm_html
                action_url = site_config.get_sell_url(sell_key)
                response = self.http_client.get(action_url, cookies)
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
        except AuthError as error:
            error.farm_action = self.ACTION_NAMES.get(operation, operation)
            error.farm_url = action_url
            raise
        except Exception as error:
            self._log(
                "error",
                f"{site_config.site_name} {self.ACTION_NAMES.get(operation, operation)} "
                f"异常：{self._error_context(error, action_url)}",
            )
            return ActionResult(operation, target, False, message=str(error)), farm_html
