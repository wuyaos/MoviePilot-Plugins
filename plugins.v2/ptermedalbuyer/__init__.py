import re
import threading
from datetime import date, datetime
from html import unescape
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import pytz
from apscheduler.triggers.cron import CronTrigger
from lxml import etree

from app.core.config import settings
from app.db.site_oper import SiteOper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import NotificationType
from app.utils.http import RequestUtils


class PterMedalBuyer(_PluginBase):
    plugin_name = "pter勋章自动领取"
    plugin_desc = "定时检测 pterclub 当前页可领取勋章，按配置自动领取并记录历史"
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/medal.png"
    plugin_version = "1.0.4"
    plugin_author = "wuyaos"
    author_url = "https://github.com/wuyaos"
    plugin_config_prefix = "ptermedalbuyer_"
    plugin_order = 37
    auth_level = 2

    DEFAULT_SITE_DOMAIN = "pterclub.net"
    DEFAULT_PAGE = "page010"
    BASE_URL = "https://pterclub.net"
    MAX_EVENTS = 500
    REQUEST_TIMEOUT = 30

    _enabled = False
    _notify = True
    _cron = "0 9 * * *"
    _onlyonce = False
    _site_domain = DEFAULT_SITE_DOMAIN
    _page = DEFAULT_PAGE
    _max_price = 0
    _dry_run = False
    _lock = threading.Lock()

    def init_plugin(self, config: Optional[dict] = None):
        config = config or {}
        self._enabled = bool(config.get("enabled", False))
        self._notify = bool(config.get("notify", True))
        self._cron = str(config.get("cron") or "0 9 * * *").strip()
        self._onlyonce = bool(config.get("onlyonce", False))
        self._site_domain = self.DEFAULT_SITE_DOMAIN
        self._page = self.DEFAULT_PAGE
        self._max_price = self._safe_int(config.get("max_price"), 0, min_value=0)
        self._dry_run = bool(config.get("dry_run", False))
        self._ensure_plugin_log_file()
        logger.info(
            f"pter 勋章自动领取初始化完成：enabled={self._enabled}, cron={self._cron}, "
            f"site_domain={self._site_domain}, page={self._page}, "
            f"max_price={self._max_price}, dry_run={self._dry_run}"
        )
        if self._onlyonce:
            self._onlyonce = False
            self.update_config(self._config_snapshot(onlyonce=False))
            logger.info("收到立即运行请求，后台启动 pter 勋章自动领取任务")
            threading.Thread(target=self.run_buy_task, kwargs={"force": True, "trigger": "onlyonce"}, daemon=True).start()

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        return [{
            "path": "/PterMedalBuyer/run",
            "endpoint": self.run_once_api,
            "methods": ["POST"],
            "auth": "bear",
            "summary": "立即执行 pter 勋章自动领取",
            "description": "按当前插件配置立即执行一次 pter 勋章检测与领取任务。"
        }]

    def get_service(self) -> List[Dict[str, Any]]:
        if not self._enabled or not self._cron:
            return []
        try:
            trigger = CronTrigger.from_crontab(self._cron, timezone=pytz.timezone(settings.TZ))
        except Exception as err:
            logger.warning(f"pter 勋章自动领取 cron 表达式无效：{self._cron}，错误：{err}")
            return []
        return [{
            "id": "PterMedalBuyerCron",
            "name": "pter勋章自动领取",
            "trigger": trigger,
            "func": self.scheduled_run
        }]

    def stop_service(self):
        pass

    def scheduled_run(self):
        return self.run_buy_task(force=False, trigger="cron")

    def run_once_api(self) -> Dict[str, Any]:
        return self.run_buy_task(force=True, trigger="api")

    def run_buy_task(self, force: bool = False, trigger: str = "cron") -> Dict[str, Any]:
        if not self._lock.acquire(blocking=False):
            logger.warning("pter 勋章自动领取任务启动失败：已有任务正在执行")
            return {"success": False, "message": "已有任务正在执行"}
        started_at = self._now_text()
        events: List[Dict[str, Any]] = []
        medals: List[Dict[str, Any]] = []
        candidates: List[Dict[str, Any]] = []
        last_error = ""
        site = None
        cat_food = ""
        uid = ""
        username = ""
        try:
            logger.info(f"pter 勋章自动领取任务开始：trigger={trigger}, site={self._site_domain}")
            site, cookie = self._get_site_cookie()
            if not site or not cookie:
                event = self._event("auth_failed", trigger, "-", "", None, "未找到 pterclub 站点或站点 Cookie 为空")
                self._append_events([event])
                self._save_round(started_at, trigger, site, [], [], [event], "", "auth_failed", uid=uid, username=username)
                logger.info("pter 勋章自动领取任务结束：status=auth_failed, success=0, failed=0, cat_food=未知")
                return {"success": False, "message": event["reason"], "events": [event]}

            html = self._fetch_medal_page(cookie, site)
            if self._looks_login_page(html):
                event = self._event("auth_failed", trigger, "-", "", None, "Cookie 失效或页面需要登录/验证码")
                self._append_events([event])
                self._save_round(started_at, trigger, site, [], [], [event], "", "auth_failed", uid=uid, username=username)
                logger.info("pter 勋章自动领取任务结束：status=auth_failed, success=0, failed=0, cat_food=未知")
                return {"success": False, "message": event["reason"], "events": [event]}

            medals, cat_food = self._parse_medal_page(html, site)
            uid = self._parse_uid_from_html(html)
            if uid:
                try:
                    userdetails_html = self._fetch_userdetails(cookie, uid, site)
                    username = self._parse_username_from_userdetails(userdetails_html)
                    owned_medals = self._parse_owned_medals(userdetails_html, cookie, site)
                    legacy_owned = self.get_data("owned_medals") or {}
                    if isinstance(legacy_owned, dict) and legacy_owned and not self.get_data("owned_medals_purchased"):
                        self.save_data("owned_medals_purchased", legacy_owned)
                    self.save_data("owned_medals_userdetails", owned_medals)
                    self.save_data("owned_medals", owned_medals)
                    logger.info(f"pter 已拥有勋章解析完成：uid={uid}, count={len(owned_medals)}")
                except Exception as err:
                    logger.warning(f"pter 已拥有勋章解析失败：uid={uid}, error={err}")
            else:
                logger.warning("pter medal.php 未解析到当前用户 uid，跳过 userdetails 已拥有勋章解析")
            if not medals:
                event = self._event("buy_fail", trigger, "-", "", None, "未解析到 buymedal 表单或 medalchosen 输入框", status="parse_failed")
                events.append(event)
                self._append_events(events)
                self._save_round(started_at, trigger, site, medals, candidates, events, cat_food, "parse_failed", uid=uid, username=username)
                logger.info(f"pter 勋章自动领取任务结束：status=parse_failed, success=0, failed=1, cat_food={cat_food or '未知'}")
                return {"success": False, "message": event["reason"], "events": events}

            candidates = self._filter_candidates(medals, trigger, cat_food)
            logger.info(f"pter 勋章解析完成：cat_food={cat_food or '未知'}, medal_count={len(medals)}, available_count={len(candidates)}")
            skip_events = [item["event"] for item in medals if item.get("event")]
            events.extend(skip_events)

            for medal in candidates:
                if self._dry_run:
                    events.append(self._event(
                        "buy_skip", trigger, medal.get("id"), medal.get("value"), medal.get("price"),
                        "dry_run 开启，仅检测不购买", cat_food, status="dry_run"
                    ))
                    logger.info(f"pter 勋章购买：id={medal.get('id')}, price={medal.get('price') if medal.get('price') is not None else '未知'}, result=dry_run")
                    continue
                success, reason, verify_status, verify_html = self._buy_and_verify(cookie, site, medal)
                if verify_html:
                    verified_medals, cat_food_after = self._parse_medal_page(verify_html, site)
                    if cat_food_after:
                        cat_food = cat_food_after
                event_name = "buy_ok" if success else "buy_fail"
                event = self._event(
                    event_name, trigger, medal.get("id"), medal.get("value"), medal.get("price"),
                    reason, cat_food, status="success" if success else "failed", verify_status=verify_status
                )
                events.append(event)
                logger.info(f"pter 勋章购买：id={medal.get('id')}, price={medal.get('price') if medal.get('price') is not None else '未知'}, result={event.get('status')}")
                if success:
                    self._mark_owned(medal, event["time"])

            self._append_events(events)
            if self._dry_run and candidates:
                status = "dry_run"
            else:
                status = "success" if any(item.get("event") == "buy_ok" for item in events) else "no_available"
            self._save_round(started_at, trigger, site, medals, candidates, events, cat_food, status, uid=uid, username=username)
            self._send_notify(events, cat_food, candidates)
            success_count = len([item for item in events if item.get("event") == "buy_ok"])
            failed_count = len([item for item in events if item.get("event") == "buy_fail"])
            logger.info(f"pter 勋章自动领取任务结束：status={status}, success={success_count}, failed={failed_count}, cat_food={cat_food or '未知'}")
            return {"success": True, "message": f"处理 {len(candidates)} 个可领取勋章", "events": events}
        except Exception as err:
            last_error = self._to_log_text(err, 500)
            logger.error(f"pter 勋章自动领取任务异常：{err}")
            event = self._event("buy_fail", trigger, "-", "", None, f"任务异常：{err}", cat_food, status="failed")
            self._append_events([event])
            self._save_round(started_at, trigger, site, medals, candidates, [event], cat_food, "failed", last_error, uid=uid, username=username)
            logger.info(f"pter 勋章自动领取任务结束：status=failed, success=0, failed=1, cat_food={cat_food or '未知'}")
            return {"success": False, "message": str(err), "events": [event]}
        finally:
            self._lock.release()

    def _get_site_cookie(self):
        try:
            site = SiteOper().get_by_domain(self._site_domain)
            if site:
                return site, (getattr(site, "cookie", "") or "").strip()
        except Exception as err:
            logger.debug(f"按域名读取 pterclub 站点失败：{err}")
        try:
            domain_key = self._site_domain.lower()
            for site in SiteOper().list_order_by_pri():
                domain = (getattr(site, "domain", "") or "").lower()
                url = (getattr(site, "url", "") or "").lower()
                name = (getattr(site, "name", "") or "").lower()
                if domain_key in domain or domain_key in url or "pter" in name:
                    return site, (getattr(site, "cookie", "") or "").strip()
        except Exception as err:
            logger.warning(f"遍历 MoviePilot 站点读取 pterclub 失败：{err}")
        return None, ""

    def _fetch_medal_page(self, cookie: str, site=None) -> str:
        url = self._medal_url(site)
        res = RequestUtils(headers=self._page_headers(cookie, site), timeout=self.REQUEST_TIMEOUT).get_res(url=url)
        if not res:
            raise RuntimeError("请求 pter medal.php 失败：无响应")
        if res.status_code in [401, 403]:
            raise RuntimeError(f"Cookie 失效或无权限：HTTP {res.status_code}")
        if res.status_code >= 500:
            raise RuntimeError(f"站点服务异常：HTTP {res.status_code}")
        return res.text or ""

    def _fetch_userdetails(self, cookie: str, uid: str, site=None) -> str:
        url = urljoin(self._base_url(site) + "/", f"userdetails.php?id={uid}")
        res = RequestUtils(headers=self._page_headers(cookie, site), timeout=self.REQUEST_TIMEOUT).get_res(url=url)
        if not res:
            raise RuntimeError("请求 pter userdetails.php 失败：无响应")
        if res.status_code in [401, 403]:
            raise RuntimeError(f"Cookie 失效或无权限：HTTP {res.status_code}")
        if res.status_code >= 500:
            raise RuntimeError(f"站点服务异常：HTTP {res.status_code}")
        return res.text or ""

    def _parse_owned_medals(self, userdetails_html: str, cookie: str = "", site=None) -> List[Dict[str, Any]]:
        if not userdetails_html:
            return []
        tree = etree.HTML(userdetails_html, parser=etree.HTMLParser())
        if tree is None:
            return []
        owned: List[Dict[str, Any]] = []
        for img in tree.xpath("//td[contains(concat(' ', normalize-space(@class), ' '), ' rowfollow ')]//img[contains(@src, 'storage/uploadpicz/hz/')]"):
            title = self._clean_text((img.xpath("./@title") or [""])[0])
            src = self._clean_text((img.xpath("./@src") or [""])[0])
            if not src:
                continue
            img_src = urljoin(self.BASE_URL + "/", src)
            owned.append({
                "name": title or img_src.rsplit("/", 1)[-1],
                "img_src": img_src,
            })
        return owned

    def _parse_medal_page(self, html: str, site=None) -> Tuple[List[Dict[str, Any]], str]:
        if not html:
            return [], ""
        tree = etree.HTML(html, parser=etree.HTMLParser())
        if tree is None:
            return [], ""
        page_url = self._medal_url(site)
        cat_food = self._parse_cat_food(html)
        medals: List[Dict[str, Any]] = []
        forms = tree.xpath("//form[contains(@action, 'buymedal')]")
        for form in forms:
            action_raw = (form.xpath("./@action") or [""])[0]
            if self._page and self._page not in action_raw and self._page not in page_url:
                continue
            form_action = urljoin(page_url, action_raw or f"?page={self._page}&action=buymedal")
            hidden_fields = self._form_fields(form)
            form_text = self._clean_text(" ".join(form.xpath(".//text()")))
            term_text = self._extract_term_text(form_text)
            in_term = self._is_in_term(term_text)
            for input_node in form.xpath(".//input[@name='medalchosen']"):
                value = self._clean_text((input_node.xpath("./@value") or [""])[0])
                if not value:
                    continue
                medal_id = self._parse_medal_id(value)
                price = self._parse_price(value)
                disabled = bool(input_node.xpath("./@disabled"))
                status = "unavailable" if disabled else "available"
                if not in_term and not disabled:
                    status = "expired"
                medals.append({
                    "id": medal_id,
                    "value": value,
                    "price": price,
                    "price_text": self._parse_price_text(value),
                    "disabled": disabled,
                    "status": status,
                    "term_text": term_text,
                    "in_term": in_term,
                    "form_action": form_action,
                    "form_fields": hidden_fields,
                    "updated_at": self._now_text(),
                    "target_hit": True,
                    "skip_reason": "",
                })
        logger.info(f"pter 勋章页面解析完成：{len(medals)} 个勋章")
        return medals, cat_food

    @staticmethod
    def _form_fields(form) -> Dict[str, str]:
        fields: Dict[str, str] = {}
        for node in form.xpath(".//input[@name] | .//select[@name] | .//textarea[@name]"):
            name = (node.xpath("./@name") or [""])[0]
            if not name or name == "medalchosen":
                continue
            value = (node.xpath("./@value") or [""])[0]
            fields[str(name)] = str(value)
        return fields

    def _filter_candidates(self, medals: List[Dict[str, Any]], trigger: str, cat_food: str = "") -> List[Dict[str, Any]]:
        candidates = []
        for medal in medals:
            reason = ""
            status = "skipped"
            if medal.get("disabled"):
                status = "unavailable"
                reason = "页面按钮 disabled，已换领/过期/猫粮不足无法区分，按不可领取处理"
            elif not medal.get("in_term", True):
                reason = "不在勋章领取期限内"
                status = "expired"
            elif self._max_price and medal.get("price") is None:
                reason = "价格解析失败且设置了 max_price，跳过"
                status = "price_unknown"
            elif self._max_price and self._safe_int(medal.get("price"), 0) > self._max_price:
                reason = f"价格 {medal.get('price')} 超过上限 {self._max_price}"
                status = "price_exceeded"
            else:
                candidates.append(medal)

            if reason:
                medal["skip_reason"] = reason
                medal["event"] = self._event(
                    "buy_skip", trigger, medal.get("id"), medal.get("value"), medal.get("price"), reason, cat_food, status=status
                )
        return candidates

    def _buy_and_verify(self, cookie: str, site, medal: Dict[str, Any]) -> Tuple[bool, str, str, str]:
        data = dict(medal.get("form_fields") or {})
        data["medalchosen"] = medal.get("value") or ""
        post_text = ""
        try:
            res = RequestUtils(headers=self._post_headers(cookie, site), timeout=self.REQUEST_TIMEOUT).post_res(
                url=medal.get("form_action") or self._buy_url(site), data=data
            )
            if res:
                post_text = res.text or ""
                if res.status_code >= 400:
                    return False, f"购买请求失败：HTTP {res.status_code}", "post_failed", ""
        except Exception as err:
            logger.warning(f"pter 勋章 {medal.get('id')} POST 异常，尝试二次 GET 验证：{err}")
            post_text = f"POST 异常：{err}"

        verify_html = ""
        try:
            verify_html = self._fetch_medal_page(cookie, site)
            verified_medals, _ = self._parse_medal_page(verify_html, site)
            verified = self._find_medal(verified_medals, str(medal.get("id") or ""), str(medal.get("value") or ""))
            if verified and verified.get("disabled"):
                return True, "购买成功，二次 GET 验证勋章已变为 disabled", "disabled_after_post", verify_html
            success_hint = any(word in post_text for word in ["成功", "已换领", "已领取", "购买成功", "换领成功", "领取成功"])
            if success_hint and verified and verified.get("status") == "unavailable":
                return True, "购买响应提示成功，且二次 GET 已不可再次提交", "success_text_verified", verify_html
            return False, "POST 后二次 GET 未确认勋章变为已领取/disabled", "verify_not_changed", verify_html
        except Exception as err:
            if any(word in post_text for word in ["成功", "已换领", "已领取", "购买成功", "换领成功", "领取成功"]):
                return False, f"响应疑似成功但二次验证失败：{err}", "unknown", verify_html
            return False, f"购买后验证失败：{err}", "verify_failed", verify_html

    @staticmethod
    def _find_medal(medals: List[Dict[str, Any]], medal_id: str, value: str) -> Optional[Dict[str, Any]]:
        for medal in medals:
            if medal_id and medal.get("id") == medal_id:
                return medal
            if value and medal.get("value") == value:
                return medal
        return None

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [{"component": "VForm", "content": [
            {"component": "VCard", "props": {"variant": "outlined", "class": "mt-3"}, "content": [
                {"component": "VCardTitle", "text": "基础设置"},
                {"component": "VDivider"},
                {"component": "VCardText", "content": [
                    {"component": "VRow", "content": [
                        {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [{"component": "VSwitch", "props": {"model": "enabled", "label": "启用", "color": "primary"}}]},
                        {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [{"component": "VSwitch", "props": {"model": "notify", "label": "通知", "color": "info"}}]},
                        {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [{"component": "VSwitch", "props": {"model": "dry_run", "label": "仅检测不购买", "color": "warning", "hint": "只检测并通知，不实际购买"}}]},
                        {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [{"component": "VSwitch", "props": {"model": "onlyonce", "label": "立即运行", "color": "success", "hint": "保存后执行一次"}}]}
                    ]},
                    {"component": "VRow", "content": [
                        {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [{"component": "VCronField", "props": {"model": "cron", "label": "执行周期", "placeholder": "0 9 * * *", "hint": "Cron 表达式，默认每天 09:00"}}]},
                        {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [{"component": "VTextField", "props": {"model": "max_price", "label": "单枚猫粮上限", "type": "number", "min": 0, "hint": "0 表示无上限"}}]}
                    ]}
                ]}
            ]},
            {"component": "VAlert", "props": {"type": "info", "variant": "tonal", "class": "mt-3", "text": "定时检测 pterclub 当前页可领取勋章，自动领取并通知；已拥有勋章从用户详情页解析。"}}
        ]}], self._config_snapshot(onlyonce=False)

    def get_page(self) -> List[dict]:
        try:
            return self._build_page()
        except Exception as err:
            logger.error(f"pter 勋章自动领取详情页渲染失败：{err}")
            return [{"component": "VAlert", "props": {"type": "error", "variant": "tonal", "text": f"详情页渲染失败：{err}"}}]

    def _build_page(self) -> List[dict]:
        summary = self.get_data("summary") or {}
        summary = summary if isinstance(summary, dict) else {}
        last_round = self.get_data("last_round") or {}
        last_round = last_round if isinstance(last_round, dict) else {}
        medals_data = last_round.get("medals")
        medals: List[Dict[str, Any]] = []
        if isinstance(medals_data, list):
            for item in medals_data:
                if isinstance(item, dict):
                    medals.append(item)
        events = self._get_events()
        owned_data = self.get_data("owned_medals_userdetails") or self.get_data("owned_medals") or []
        owned: List[Dict[str, Any]] = []
        if isinstance(owned_data, list):
            for item in owned_data:
                if isinstance(item, dict):
                    owned.append(item)
        elif isinstance(owned_data, dict):
            for item in owned_data.values():
                if isinstance(item, dict):
                    owned.append(item)
        purchased_map = self.get_data("owned_medals_purchased") or {}
        purchased: List[Dict[str, Any]] = []
        if isinstance(purchased_map, dict):
            for item in purchased_map.values():
                if isinstance(item, dict):
                    purchased.append(item)
        purchased.sort(key=lambda item: str(item.get("purchased_at") or ""), reverse=True)
        username = last_round.get("username")
        uid = last_round.get("uid")
        cat_food = last_round.get("cat_food")
        status_text = self._status_text(str(last_round.get("status") or "")) if last_round.get("status") else "-"
        recent_at = last_round.get("started_at") or last_round.get("updated_at")

        overview_body = [{"component": "VRow", "props": {"class": "align-stretch ga-2 flex-md-nowrap"}, "content": [
            self._info_col("用户名", username),
            self._info_col("UID", uid),
            self._info_col("猫粮", cat_food),
            self._info_col("状态", status_text),
            self._info_col("最近", recent_at),
        ]}]
        overview_content: List[dict] = []
        overview_content.append({"component": "VCardTitle", "text": "基本信息"})
        overview_content.append({"component": "VDivider"})
        overview_content.append({"component": "VCardText", "content": overview_body})
        overview_card: dict = {"component": "VCard", "props": {"variant": "outlined", "class": "mb-4 mt-3"}, "content": overview_content}
        components: List[dict] = [overview_card]

        components.append(self._owned_card(owned))
        components.append(self._recent_purchased_card([item for item in purchased if item.get("purchased_at")][:5]))
        components.append(self._data_table("运行历史", [
            {"title": "时间", "key": "started_at"}, {"title": "触发方式", "key": "trigger"},
            {"title": "状态", "key": "status_text"}, {"title": "检测勋章数", "key": "medal_count"},
            {"title": "可领取数", "key": "candidate_count"}, {"title": "购买成功", "key": "buy_ok"},
            {"title": "购买失败", "key": "buy_fail"}, {"title": "猫粮余额", "key": "cat_food"},
            {"title": "说明", "key": "note"}
        ], self._round_history_items(last_round, events)))
        return components

    def _owned_card(self, owned: List[Dict[str, Any]]) -> dict:
        content = []
        if owned:
            first_line = 12
            content.append(self._owned_medal_grid(owned[:first_line]))
            remaining = owned[first_line:]
            if remaining:
                content.append({"component": "VExpansionPanels", "props": {"variant": "accordion", "class": "mt-2"}, "content": [{
                    "component": "VExpansionPanel", "content": [
                        {"component": "VExpansionPanelTitle", "text": f"展开剩余（{len(remaining)}个）"},
                        {"component": "VExpansionPanelText", "content": [self._owned_medal_grid(remaining)]}
                    ]
                }]})
        return {"component": "VCard", "props": {"variant": "outlined", "class": "mb-4"}, "content": [
            {"component": "VCardTitle", "text": f"已拥有勋章（{len(owned)}个）"},
            {"component": "VCardText", "content": content or [{"component": "VAlert", "props": {"type": "info", "variant": "tonal", "text": "暂无已拥有勋章数据"}}]}
        ]}

    @staticmethod
    def _owned_medal_grid(items: List[Dict[str, Any]]) -> dict:
        return {"component": "div", "props": {"style": "display:flex;flex-wrap:wrap;gap:8px"}, "content": [{
            "component": "VCol", "props": {"cols": "auto", "style": "width:64px;flex:0 0 64px"}, "content": [{
                "component": "VCard", "props": {"variant": "tonal", "class": "h-100 rounded-lg border", "width": 64}, "content": [{
                    "component": "VCardText", "props": {"class": "text-center pa-2"}, "content": [
                        {"component": "VImg", "props": {"src": item.get("img_src") or "", "max-width": 48, "height": 48, "contain": True, "class": "mx-auto flex-grow-0"}},
                        {"component": "div", "props": {"style": "max-width:48px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:10px", "class": "mx-auto mt-1"}, "text": item.get("name") or "—"}
                    ]
                }]
            }]
        } for item in items if isinstance(item, dict)]}

    @staticmethod
    def _recent_purchased_card(items: List[Dict[str, Any]]) -> dict:
        content = [{"component": "VRow", "content": [{
            "component": "VCol", "props": {"cols": 12, "sm": 6, "md": 4, "lg": 2}, "content": [{
                "component": "VCard", "props": {"variant": "tonal", "class": "h-100 text-center"}, "content": [
                    {"component": "VImg", "props": {"src": item.get("img_src") or "", "max-width": 48, "height": 48, "contain": True, "class": "mt-3 mx-auto"}},
                    {"component": "VCardText", "props": {"class": "py-2"}, "content": [
                        {"component": "div", "props": {"style": "max-width:48px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:10px", "class": "mx-auto"}, "text": item.get("name") or item.get("id") or "—"},
                        {"component": "div", "props": {"class": "text-caption text-medium-emphasis mt-1"}, "text": item.get("purchased_at") or "—"}
                    ]}
                ]
            }]
        } for item in items if isinstance(item, dict)]}] if items else [{"component": "VAlert", "props": {"type": "info", "variant": "tonal", "text": "暂无近期领取勋章数据"}}]
        return {"component": "VCard", "props": {"variant": "outlined", "class": "mb-4"}, "content": [
            {"component": "VCardTitle", "text": "近期领取勋章"},
            {"component": "VCardText", "content": content}
        ]}

    @staticmethod
    def _data_table(title: str, headers: List[dict], items: List[dict], embedded: bool = False) -> dict:
        table = {"component": "VDataTable", "props": {"headers": headers, "items": items, "items-per-page": 10, "density": "compact"}}
        if embedded:
            return table
        return {"component": "VCard", "props": {"variant": "outlined", "class": "mb-4"}, "content": [
            {"component": "VCardTitle", "text": title},
            {"component": "VCardText", "content": [table]}
        ]}

    @staticmethod
    def _info_col(label: str, value: Any) -> dict:
        return {"component": "VCol", "props": {"cols": 12, "md": "auto", "class": "d-flex", "style": "flex:1 1 0;min-width:0"}, "content": [
            {"component": "VCard", "props": {"variant": "tonal", "class": "h-100 w-100 rounded-lg border"}, "content": [
                {"component": "VCardText", "props": {"class": "h-100 d-flex flex-column justify-center py-4"}, "content": [
                    {"component": "div", "props": {"class": "text-caption text-medium-emphasis"}, "text": label},
                    {"component": "div", "props": {"class": "text-h6 font-weight-bold mt-1 text-truncate"}, "text": str(value if value not in [None, ""] else "-")}
                ]}
            ]}
        ]}

    def _save_round(self, started_at: str, trigger: str, site, medals: List[Dict[str, Any]], candidates: List[Dict[str, Any]],
                    events: List[Dict[str, Any]], cat_food: str, status: str, last_error: str = "",
                    uid: str = "", username: str = ""):
        ended_at = self._now_text()
        site_name = getattr(site, "name", None) or self._site_domain
        safe_medals = [{k: v for k, v in item.items() if k not in ["form_fields"]} for item in medals]
        safe_candidates = [{k: v for k, v in item.items() if k not in ["form_fields"]} for item in candidates]
        buy_ok = len([item for item in events if item.get("event") == "buy_ok"])
        buy_fail = len([item for item in events if item.get("event") == "buy_fail"])
        buy_skip = len([item for item in events if item.get("event") == "buy_skip"])
        last_round = {
            "started_at": started_at,
            "ended_at": ended_at,
            "trigger": trigger,
            "site": site_name,
            "site_name": site_name,
            "site_id": getattr(site, "id", "") if site else "",
            "page": self._page,
            "uid": uid,
            "username": username,
            "cat_food": cat_food,
            "medals": safe_medals,
            "buy_candidates": safe_candidates,
            "events": events,
            "status": status,
            "last_error": last_error,
            "medal_count": len(safe_medals),
            "candidate_count": len(safe_candidates),
            "buy_ok": buy_ok,
            "buy_fail": buy_fail,
            "buy_skip": buy_skip,
        }
        self.save_data("last_round", last_round)
        last_rounds = self.get_data("last_rounds") or []
        if not isinstance(last_rounds, list):
            last_rounds = []
        last_rounds.append({k: v for k, v in last_round.items() if k not in ["medals", "buy_candidates", "events"]})
        self.save_data("last_rounds", last_rounds[-20:])
        self.save_data("summary", {
            "updated_at": ended_at,
            "site": site_name,
            "site_name": site_name,
            "page": self._page,
            "uid": uid,
            "username": username,
            "cat_food": cat_food,
            "status": status,
            "last_error": last_error,
            "buy_ok": buy_ok,
            "buy_fail": buy_fail,
            "buy_skip": buy_skip,
        })

    def _append_events(self, events: List[Dict[str, Any]]):
        if not events:
            return
        old_events = self._get_events()
        old_events.extend(events)
        self.save_data("events", old_events[-self.MAX_EVENTS:])

    def _get_events(self) -> List[Dict[str, Any]]:
        events = self.get_data("events") or []
        if isinstance(events, list) and events:
            return events
        last_round = self.get_data("last_round") or {}
        round_events = last_round.get("events") if isinstance(last_round, dict) else []
        return round_events if isinstance(round_events, list) else []

    def _mark_owned(self, medal: Dict[str, Any], purchased_at: str = "", source: str = "history"):
        medal_id = medal.get("id") or medal.get("value")
        if not medal_id:
            return
        owned = self.get_data("owned_medals_purchased") or {}
        if not isinstance(owned, dict):
            owned = {}
        current = owned.get(medal_id) or {}
        owned[medal_id] = {
            "id": medal_id,
            "value": medal.get("value") or current.get("value") or "",
            "name": medal.get("name") or current.get("name") or medal_id,
            "img_src": medal.get("img_src") or current.get("img_src") or "",
            "price": medal.get("price") if medal.get("price") is not None else current.get("price"),
            "first_seen_at": current.get("first_seen_at") or self._now_text(),
            "purchased_at": purchased_at or current.get("purchased_at") or "",
            "source": source or current.get("source") or "page",
            "term_text": medal.get("term_text") or current.get("term_text") or "",
            "last_seen_status": medal.get("status") or current.get("last_seen_status") or "",
        }
        self.save_data("owned_medals_purchased", owned)

    def _send_notify(self, events: List[Dict[str, Any]], cat_food: str, candidates: Optional[List[Dict[str, Any]]] = None):
        if not self._notify:
            return
        if self._dry_run:
            candidates = candidates or []
            if not candidates:
                return
            lines = [f"有 {len(candidates)} 枚勋章可领取："]
            for item in candidates:
                lines.append(f"- {item.get('id')}: {item.get('price') if item.get('price') is not None else '未知'} 猫粮")
            lines.append(f"当前猫粮：{cat_food or '未知'}")
            self.post_message(mtype=NotificationType.Plugin, title="【pter勋章自动领取】", text="\n".join(lines))
            return
        buy_events = [item for item in events if item.get("event") in ["buy_ok", "buy_fail"]]
        if not buy_events:
            return
        lines = ["本次领取结果："]
        for item in buy_events:
            result = "成功" if item.get("event") == "buy_ok" else "失败"
            lines.append(f"- {item.get('medal_id')}: {item.get('price') if item.get('price') is not None else '未知'} 猫粮，{result}（{item.get('reason') or '—'}）")
        lines.append(f"剩余猫粮：{cat_food or '未知'}")
        self.post_message(mtype=NotificationType.Plugin, title="【pter勋章自动领取】", text="\n".join(lines))

    def _event(self, event: str, trigger: str, medal_id: Any, medal_value: Any, price: Any, reason: str,
               cat_food_after: str = "", status: str = "", verify_status: str = "") -> Dict[str, Any]:
        return {
            "time": self._now_text(),
            "event": event,
            "trigger": trigger,
            "medal_id": str(medal_id or ""),
            "medal_value": str(medal_value or ""),
            "price": price,
            "result": status or event,
            "reason": self._to_log_text(reason, 500),
            "cat_food_after": cat_food_after,
            "verify_status": verify_status,
        }

    def _page_headers(self, cookie: str, site=None) -> Dict[str, str]:
        return {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "accept-language": "zh-CN,zh;q=0.9",
            "cookie": cookie,
            "referer": self._base_url(site),
            "user-agent": self._user_agent(site),
        }

    def _post_headers(self, cookie: str, site=None) -> Dict[str, str]:
        return {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "accept-language": "zh-CN,zh;q=0.9",
            "content-type": "application/x-www-form-urlencoded",
            "cookie": cookie,
            "origin": self._base_url(site),
            "referer": self._medal_url(site),
            "user-agent": self._user_agent(site),
        }

    def _base_url(self, site=None) -> str:
        url = str(getattr(site, "url", "") or self.BASE_URL).strip().rstrip("/")
        if not url.startswith("http"):
            url = f"https://{self._site_domain}"
        return url

    def _medal_url(self, site=None) -> str:
        return urljoin(self._base_url(site) + "/", f"medal.php?page={self._page}")

    def _buy_url(self, site=None) -> str:
        return urljoin(self._base_url(site) + "/", f"medal.php?page={self._page}&action=buymedal")

    @staticmethod
    def _user_agent(site=None) -> str:
        return (getattr(site, "ua", "") or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36").strip()

    def _config_snapshot(self, onlyonce: bool = False) -> Dict[str, Any]:
        return {
            "enabled": self._enabled,
            "cron": self._cron,
            "notify": self._notify,
            "onlyonce": onlyonce,
            "max_price": self._max_price,
            "dry_run": self._dry_run,
        }

    @staticmethod
    def _parse_medal_id(value: str) -> str:
        match = re.search(r"(\d{3}-\d{3})", value or "")
        return match.group(1) if match else ""

    @staticmethod
    def _parse_price(value: str) -> Optional[int]:
        match = re.search(r"(\d[\d,]*)\s*猫粮", value or "")
        if not match:
            return None
        try:
            return int(match.group(1).replace(",", ""))
        except ValueError:
            return None

    @staticmethod
    def _parse_price_text(value: str) -> str:
        match = re.search(r"(\d[\d,]*\s*猫粮)", value or "")
        return match.group(1) if match else ""

    @staticmethod
    def _extract_term_text(text: str) -> str:
        match = re.search(r"此徽章仅于[^。；;\n]*?(?:换领|领取)", text or "")
        return match.group(0) if match else ""

    def _is_in_term(self, term_text: str) -> bool:
        if not term_text:
            return True
        match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日至(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日", term_text)
        if not match:
            return True
        start_year, start_month, start_day, end_year, end_month, end_day = match.groups()
        try:
            start = date(int(start_year), int(start_month), int(start_day))
            end = date(int(end_year or start_year), int(end_month), int(end_day))
            today = datetime.now().date()
            return start <= today <= end
        except ValueError:
            return True

    @staticmethod
    def _parse_uid_from_html(html: str) -> str:
        matches = re.findall(r"userdetails\.php\?id=(\d+)", html or "")
        return matches[0] if matches else ""

    @staticmethod
    def _parse_username_from_userdetails(html: str) -> str:
        if not html:
            return ""
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
        if title_match:
            title = PterMedalBuyer._clean_text(title_match.group(1))
            match = re.search(r"::\s*(?:用户详情\s*[-–—]\s*)?(\S+)", title)
            if match:
                return PterMedalBuyer._clean_text(match.group(1))
        text = PterMedalBuyer._html_to_text(html)
        match = re.search(r"用户名\s*[:：]?\s*([^\s]+)", text)
        return PterMedalBuyer._clean_text(match.group(1)) if match else ""

    @staticmethod
    def _parse_cat_food(html: str) -> str:
        text = PterMedalBuyer._html_to_text(html)
        patterns = [
            r"(?:猫粮|Karma)\s*(?:\[[^\]]*\]\s*)?[:：]?\s*([\d,]+(?:\.\d+)?)",
            r"([\d,]+(?:\.\d+)?)\s*猫粮",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return match.group(1)
        return ""

    @staticmethod
    def _looks_login_page(html: str) -> bool:
        text = PterMedalBuyer._html_to_text(html).lower()
        return any(word in text for word in ["login.php", "登录", "验证码", "captcha"]) and "medalchosen" not in (html or "")

    @staticmethod
    def _html_to_text(content: str) -> str:
        text = re.sub(r"<(script|style).*?</\1>", " ", content or "", flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = unescape(text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _clean_text(value: Any) -> str:
        return re.sub(r"\s+", " ", unescape(str(value or ""))).strip()

    @staticmethod
    def _to_log_text(value: Any, max_length: int = 1000) -> str:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        return f"{text[:max_length]}..." if len(text) > max_length else text

    @staticmethod
    def _now_text() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _safe_int(value: Any, default: int, min_value: Optional[int] = None) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = default
        if min_value is not None:
            number = max(number, min_value)
        return number

    @staticmethod
    def _status_text(status: str) -> str:
        return {
            "success": "成功",
            "failed": "失败",
            "skipped": "跳过",
            "no_available": "无可领取",
            "parse_failed": "解析失败",
            "auth_failed": "Cookie 失效",
            "dry_run": "仅检测",
            "owned": "已拥有",
            "available": "可领取",
            "unavailable": "不可领取",
            "expired": "过期/未到期",
            "price_exceeded": "超价",
        }.get(status or "", status or "未知")

    def _round_history_items(self, last_round: Dict[str, Any], events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        rounds = self.get_data("last_rounds") or []
        if isinstance(rounds, list) and rounds:
            items = [self._round_history_item(item) for item in reversed(rounds[-20:]) if isinstance(item, dict)]
            if items:
                return items
        if events:
            return self._event_round_history_items(events)
        if isinstance(last_round, dict) and last_round:
            return [self._round_history_item(last_round)]
        return []

    def _round_history_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        raw_events = item.get("events")
        events: List[Dict[str, Any]] = []
        if isinstance(raw_events, list):
            events = [event for event in raw_events if isinstance(event, dict)]
        buy_ok = item.get("buy_ok")
        buy_fail = item.get("buy_fail")
        if buy_ok is None:
            buy_ok = len([event for event in events if event.get("event") == "buy_ok"])
        if buy_fail is None:
            buy_fail = len([event for event in events if event.get("event") == "buy_fail"])
        note = item.get("last_error") or ""
        if not note and events:
            note = "；".join([str(event.get("reason") or "") for event in events if event.get("event") in ["buy_ok", "buy_fail", "auth_failed"] and event.get("reason")][:3])
        return {
            "started_at": item.get("started_at") or item.get("time") or item.get("ended_at") or "—",
            "trigger": item.get("trigger") or "—",
            "status_text": self._status_text(str(item.get("status") or "")),
            "medal_count": item.get("medal_count") if item.get("medal_count") is not None else len(item.get("medals") or []),
            "candidate_count": item.get("candidate_count") if item.get("candidate_count") is not None else len(item.get("buy_candidates") or []),
            "buy_ok": buy_ok,
            "buy_fail": buy_fail,
            "cat_food": item.get("cat_food") or "—",
            "note": self._to_log_text(note or "—", 120),
        }

    def _event_round_history_items(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        for event in events:
            if not isinstance(event, dict):
                continue
            key = (str(event.get("trigger") or "—"), str(event.get("time") or "—")[:16])
            grouped.setdefault(key, []).append(event)
        items = [self._event_round_history_item(group) for group in grouped.values() if group]
        return list(reversed(items[-20:]))

    def _event_round_history_item(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        last_event = events[-1]
        event_names = [str(event.get("event") or "") for event in events]
        status = "success" if "buy_ok" in event_names else "failed" if "buy_fail" in event_names else str(last_event.get("result") or last_event.get("event") or "")
        notes = [str(event.get("reason") or "") for event in events if event.get("reason")]
        return {
            "started_at": last_event.get("time") or "—",
            "trigger": last_event.get("trigger") or "—",
            "status_text": self._status_text(status),
            "medal_count": "—",
            "candidate_count": len([event for event in events if event.get("event") in ["buy_ok", "buy_fail", "buy_skip"]]),
            "buy_ok": len([event for event in events if event.get("event") == "buy_ok"]),
            "buy_fail": len([event for event in events if event.get("event") == "buy_fail"]),
            "cat_food": last_event.get("cat_food_after") or "—",
            "note": self._to_log_text("；".join(notes[:3]) or "—", 120),
        }

    @staticmethod
    def _ensure_plugin_log_file():
        try:
            path = settings.LOG_PATH / "plugins" / "ptermedalbuyer.log"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)
        except Exception as err:
            logger.debug(f"确保 pter 勋章自动领取日志文件存在失败：{err}")
