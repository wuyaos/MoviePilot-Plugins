import json
import re
import threading
from datetime import datetime, timedelta
from html import unescape
from typing import Any, Dict, List, Tuple, Optional
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


class MyPTMedalBuyer(_PluginBase):
    plugin_name = "myPT勋章续购"
    plugin_desc = "自动续购 myPT(cc.mypt.cc) 勋章，避免到期后忘记手动购买"
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/medal.png"
    plugin_version = "1.0.0"
    plugin_author = "wuyaos"
    author_url = "https://github.com/wuyaos"
    plugin_config_prefix = "myptmedalbuyer_"
    plugin_order = 36
    auth_level = 2

    SITE_DOMAIN = "mypt.cc"
    SITE_HOST = "cc.mypt.cc"
    SITE_NAME = "myPT"
    BASE_URL = "https://cc.mypt.cc"
    MEDAL_PATH = "/medal.php"
    AJAX_PATH = "/ajax.php"
    MAX_HISTORY = 50
    REQUEST_TIMEOUT = 30

    MEDALS = [
        {"id": "8", "name": "VIP", "valid": "30天", "bonus": "1000%", "price": "100,000"},
        {"id": "7", "name": "白金", "valid": "365天", "bonus": "100%", "price": "10,000"},
        {"id": "6", "name": "铂金", "valid": "365天", "bonus": "300%", "price": "50,000"},
        {"id": "5", "name": "黄金", "valid": "365天", "bonus": "500%", "price": "100,000"},
        {"id": "4", "name": "钻石", "valid": "365天", "bonus": "800%", "price": "500,000"},
        {"id": "3", "name": "至尊", "valid": "365天", "bonus": "1000%", "price": "1,000,000"},
        {"id": "2", "name": "功勋", "valid": "永久", "bonus": "0%", "price": "5,000,000（仅授予）"},
        {"id": "1", "name": "功臣", "valid": "永久", "bonus": "0%", "price": "10,000,000（仅授予）"},
    ]
    MEDAL_MAP = {item["id"]: item for item in MEDALS}

    _enabled = False
    _notify = True
    _cron = "0 9 * * *"
    _onlyonce = False
    _medal_ids: List[str] = []
    _site_id = ""
    _check_days = 3
    _use_proxy = False
    _lock = threading.Lock()

    def init_plugin(self, config: dict = None):
        config = config or {}
        self._enabled = bool(config.get("enabled", False))
        self._notify = bool(config.get("notify", True))
        self._cron = str(config.get("cron") or self._cron).strip()
        self._onlyonce = bool(config.get("onlyonce", False))
        self._medal_ids = [str(item) for item in (config.get("medal_ids") or [])]
        self._site_id = str(config.get("site_id") or "").strip()
        self._check_days = self._safe_int(config.get("check_days"), 3, min_value=0)
        self._use_proxy = bool(config.get("use_proxy", False))
        self._ensure_plugin_log_file()
        logger.info(
            f"myPT 勋章续购初始化完成：enabled={self._enabled}, cron={self._cron}, "
            f"site_id={self._site_id}, medal_ids={self._medal_ids}, check_days={self._check_days}"
        )
        if self._onlyonce:
            self._onlyonce = False
            self.update_config(self._config_snapshot(onlyonce=False))
            logger.info("收到立即运行请求，后台启动 myPT 勋章续购任务")
            threading.Thread(target=self.run_buy_task, kwargs={"force": True}, daemon=True).start()

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        return []

    def get_service(self) -> List[Dict[str, Any]]:
        if not self._enabled or not self._cron:
            return []
        try:
            trigger = CronTrigger.from_crontab(self._cron, timezone=pytz.timezone(settings.TZ))
        except Exception as err:
            logger.error(f"myPT 勋章续购 cron 表达式无效：{self._cron}，错误：{err}")
            return []
        return [{
            "id": "MyPTMedalBuyerCron",
            "name": "myPT勋章续购",
            "trigger": trigger,
            "func": self.run_buy_task,
            "kwargs": {"force": False}
        }]

    def stop_service(self):
        pass

    def run_buy_task(self, force: bool = False) -> Dict[str, Any]:
        if not self._lock.acquire(blocking=False):
            logger.warning("myPT 勋章续购任务启动失败：已有任务正在执行")
            return {"success": False, "message": "已有任务正在执行"}
        results: List[Dict[str, Any]] = []
        try:
            if not self._medal_ids:
                result = self._record_result("-", False, "请先选择要续购的勋章", status="config_error")
                return self._finish_results([result])

            site, cookie = self._get_site_cookie()
            if not site or not cookie:
                result = self._record_result("-", False, "未找到 myPT 站点或站点 Cookie 为空", status="auth_failed")
                return self._finish_results([result])

            html = self._fetch_medal_page(cookie, site)
            medals = self._parse_medals(html)
            self._save_overview(site, medals, html)

            for medal_id in self._medal_ids:
                medal_id = str(medal_id)
                medal_def = self.MEDAL_MAP.get(medal_id, {"name": f"勋章 {medal_id}", "valid": ""})
                medal = medals.get(medal_id, {})
                medal_name = medal.get("name") or medal_def.get("name") or f"勋章 {medal_id}"
                status = medal.get("status") or "unknown"
                button_text = medal.get("button_text") or "未识别"

                if status == "buy":
                    success, message = self._buy_medal(cookie, medal_id, site)
                    results.append(self._record_result(medal_name, success, message, status="success" if success else "failed"))
                elif status == "owned":
                    expire_at = medal.get("expire_at") or ""
                    msg = f"已拥有，跳过续购" + (f"，到期时间：{expire_at}" if expire_at else "")
                    results.append(self._record_result(medal_name, True, msg, status="skipped", save=False))
                elif status == "insufficient":
                    results.append(self._record_result(medal_name, False, "魔力不足，无法购买", status="failed"))
                elif status == "grant_only":
                    results.append(self._record_result(medal_name, True, "仅授予勋章，跳过", status="skipped", save=False))
                else:
                    results.append(self._record_result(medal_name, False, f"未识别按钮状态：{button_text}", status="failed"))

            return self._finish_results(results)
        except Exception as err:
            logger.error(f"myPT 勋章续购任务异常：{err}")
            result = self._record_result("-", False, f"任务异常：{err}", status="failed")
            return self._finish_results([result])
        finally:
            self._lock.release()

    def _get_site_cookie(self):
        try:
            if self._site_id:
                site = SiteOper().get(self._site_id)
                if site:
                    return site, (getattr(site, "cookie", "") or "").strip()
        except Exception as err:
            logger.warning(f"按配置站点 ID 读取 myPT 站点失败：{err}")
        try:
            site = SiteOper().get_by_domain(self.SITE_DOMAIN)
            if site:
                return site, (getattr(site, "cookie", "") or "").strip()
        except Exception as err:
            logger.debug(f"按域名读取 myPT 站点失败：{err}")
        try:
            for site in SiteOper().list_order_by_pri():
                domain = (getattr(site, "domain", "") or "").lower()
                url = (getattr(site, "url", "") or "").lower()
                name = (getattr(site, "name", "") or "").lower()
                if self.SITE_DOMAIN in domain or self.SITE_HOST in url or "mypt" in name:
                    return site, (getattr(site, "cookie", "") or "").strip()
        except Exception as err:
            logger.warning(f"遍历 MoviePilot 站点读取 myPT 失败：{err}")
        return None, ""

    def _fetch_medal_page(self, cookie: str, site=None) -> str:
        url = urljoin(self._base_url(site) + "/", self.MEDAL_PATH.lstrip("/"))
        res = RequestUtils(
            headers=self._page_headers(cookie, site),
            proxies=settings.PROXY if self._use_proxy else None,
            timeout=self.REQUEST_TIMEOUT
        ).get_res(url=url)
        if not res:
            raise RuntimeError("请求 medal.php 失败：无响应")
        if res.status_code in [401, 403]:
            raise RuntimeError(f"Cookie 失效或无权限：HTTP {res.status_code}")
        if res.status_code >= 500:
            raise RuntimeError(f"站点服务异常：HTTP {res.status_code}")
        return res.text or ""

    def _parse_medals(self, html: str) -> Dict[str, Dict[str, Any]]:
        medals: Dict[str, Dict[str, Any]] = {}
        if not html:
            return medals
        parser = etree.HTMLParser()
        tree = etree.HTML(html, parser=parser)
        if tree is None:
            return medals
        for row in tree.xpath("//tr[.//input[@data-id]]"):
            ids = row.xpath(".//input[@data-id]/@data-id")
            medal_id = str(ids[0]).strip() if ids else ""
            if not medal_id:
                continue
            cells_text = [self._clean_text(" ".join(td.xpath(".//text()"))) for td in row.xpath("./td")]
            buttons = row.xpath(".//input[@data-id=$mid]", mid=medal_id)
            buy_button = buttons[0] if buttons else None
            button_text = self._clean_text((buy_button.xpath("./@value") or [""])[0]) if buy_button is not None else ""
            disabled = bool(buy_button.xpath("./@disabled")) if buy_button is not None else False
            medal_name = self._extract_medal_name(row, medal_id)
            # medal.php 不显示到期日期，用 MEDAL_MAP 的 valid 字段作为有效期
            medal_def = self.MEDAL_MAP.get(medal_id, {})
            expire_at = medal_def.get("valid", "")
            status = self._button_status(button_text, disabled)
            medals[medal_id] = {
                "id": medal_id,
                "name": medal_name or self.MEDAL_MAP.get(medal_id, {}).get("name") or f"勋章 {medal_id}",
                "button_text": button_text,
                "disabled": disabled,
                "status": status,
                "expire_at": expire_at,
                "cells": cells_text,
            }
        logger.info(f"myPT 勋章页面解析完成：{len(medals)} 个勋章")
        return medals

    def _buy_medal(self, cookie: str, medal_id: str, site=None) -> Tuple[bool, str]:
        url = urljoin(self._base_url(site) + "/", self.AJAX_PATH.lstrip("/"))
        res = RequestUtils(
            headers=self._ajax_headers(cookie, site),
            proxies=settings.PROXY if self._use_proxy else None,
            timeout=self.REQUEST_TIMEOUT
        ).post_res(url=url, data={"action": "buyMedal", "id": medal_id})
        if not res:
            return False, "购买请求失败：无响应"
        return self._parse_buy_result(res)

    def _parse_buy_result(self, response) -> Tuple[bool, str]:
        if response.status_code >= 400:
            return False, f"购买请求失败：HTTP {response.status_code}"
        text = response.text or ""
        try:
            data = response.json()
        except Exception:
            try:
                data = json.loads(text or "{}")
            except Exception:
                return False, f"购买接口返回非 JSON：{self._to_log_text(text, 300)}"
        if not isinstance(data, dict):
            return False, "购买接口返回格式异常"
        msg = str(data.get("msg") or data.get("message") or data.get("info") or "接口未返回说明")
        ret = data.get("ret")
        if ret in [0, "0"]:
            return True, f"购买成功：{msg}"
        return False, f"购买失败：{msg}"

    def _record_result(self, medal_name: str, success: bool, message: str, status: str = "", save: bool = True) -> Dict[str, Any]:
        result = {
            "time": self._now_text(),
            "medal": medal_name,
            "success": bool(success),
            "status": status or ("success" if success else "failed"),
            "message": message,
        }
        if save:
            records = self._get_records()
            records.insert(0, result)
            self.save_data("history", records[:self.MAX_HISTORY])
        logger.info(f"myPT 勋章续购结果：medal={medal_name}, success={success}, message={message}")
        return result

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [{"component": "VForm", "content": [
            {"component": "VCard", "props": {"variant": "outlined", "class": "mt-3"}, "content": [
                {"component": "VCardTitle", "props": {"class": "d-flex align-center"}, "content": [
                    {"component": "VIcon", "props": {"color": "primary", "class": "mr-2"}, "text": "mdi-tune"},
                    {"component": "span", "text": "通用设置"}]},
                {"component": "VDivider"},
                {"component": "VCardText", "content": [
                    {"component": "VRow", "content": [
                        {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [
                            {"component": "VSwitch", "props": {"model": "enabled", "label": "启用插件", "color": "primary"}}]},
                        {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [
                            {"component": "VSwitch", "props": {"model": "notify", "label": "开启通知", "color": "info"}}]},
                        {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [
                            {"component": "VSwitch", "props": {"model": "onlyonce", "label": "立即运行一次", "color": "success"}}]},
                        {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [
                            {"component": "VSwitch", "props": {"model": "use_proxy", "label": "使用代理", "color": "warning"}}]}]},
                    {"component": "VRow", "content": [
                        {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [
                            {"component": "VTextField", "props": {"model": "cron", "label": "检查周期", "placeholder": "0 9 * * *", "hint": "5 位 cron 表达式，默认每天 09:00 检查"}}]},
                        {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [
                            {"component": "VTextField", "props": {"model": "check_days", "label": "到期提前天数", "type": "number", "min": 0, "hint": "仅对可解析到期时间的有限期勋章生效"}}]}]}]}]},
            {"component": "VCard", "props": {"variant": "outlined", "class": "mt-3"}, "content": [
                {"component": "VCardTitle", "props": {"class": "d-flex align-center"}, "content": [
                    {"component": "VIcon", "props": {"color": "warning", "class": "mr-2"}, "text": "mdi-medal"},
                    {"component": "span", "text": "勋章选择"}]},
                {"component": "VDivider"},
                {"component": "VCardText", "content": [
                    {"component": "VRow", "content": [
                        {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [
                            {"component": "VSelect", "props": {"model": "medal_ids", "label": "要续购的勋章", "items": self._medal_options(), "multiple": True, "chips": True, "clearable": True}}]},
                        {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [
                            {"component": "VSelect", "props": {"model": "site_id", "label": "myPT 站点", "items": self._site_options(), "clearable": True, "hint": "留空时自动匹配 domain=mypt.cc 或 URL=cc.mypt.cc"}}]}]}]}]},
            {"component": "VCard", "props": {"variant": "outlined", "class": "mt-3"}, "content": [
                {"component": "VCardTitle", "props": {"class": "d-flex align-center"}, "content": [
                    {"component": "VIcon", "props": {"color": "info", "class": "mr-2"}, "text": "mdi-information"},
                    {"component": "span", "text": "使用说明"}]},
                {"component": "VDivider"},
                {"component": "VCardText", "content": [
                    {"component": "VList", "props": {"density": "comfortable", "lines": "two"}, "content": [
                        {"component": "VListItem", "content": [{"component": "VListItemTitle", "text": "Cookie 来源"}, {"component": "VListItemSubtitle", "text": "插件从 MoviePilot 站点表读取 myPT(mypt.cc) Cookie，不使用浏览器。"}]},
                        {"component": "VListItem", "content": [{"component": "VListItemTitle", "text": "购买规则"}, {"component": "VListItemSubtitle", "text": "medal.php 按钮为“购买”时调用 ajax.php；已购买/仅授予跳过；魔力不足记录失败。"}]},
                        {"component": "VListItem", "content": [{"component": "VListItemTitle", "text": "接口参数"}, {"component": "VListItemSubtitle", "text": "POST /ajax.php action=buyMedal&id=<勋章ID>，ret=0 判定成功。"}]}]}]}]}
        ]}], self._config_snapshot(onlyonce=False)

    def get_page(self) -> List[dict]:
        try:
            return self._build_page()
        except Exception as err:
            logger.error(f"myPT 勋章续购详情页渲染失败：{err}")
            return [{"component": "VAlert", "props": {"type": "error", "variant": "tonal", "text": f"详情页渲染失败：{err}"}}]

    def _build_page(self) -> List[dict]:
        frost_style = 'background-color: rgba(var(--v-theme-surface), 0.75); backdrop-filter: blur(5px); -webkit-backdrop-filter: blur(5px); outline: 1px solid rgba(var(--v-theme-on-surface), 0.12); border-radius: 8px; box-sizing: border-box;'
        overview = self.get_data("overview") or {}
        medals = overview.get("medals") if isinstance(overview, dict) else []
        history = self._get_records()
        owned = [item for item in medals if isinstance(item, dict) and item.get("status") == "owned"] if isinstance(medals, list) else []
        magic = overview.get("magic") if isinstance(overview, dict) else ""

        def stat_block(icon: str, color: str, value: Any, label: str) -> dict:
            return {"component": "VCol", "props": {"cols": 12, "md": 4, "class": "pa-2"}, "content": [
                {"component": "div", "props": {"class": "text-center pa-3 d-flex flex-column justify-center", "style": frost_style}, "content": [
                    {"component": "div", "props": {"class": "d-flex justify-center align-center mb-1"}, "content": [
                        {"component": "VIcon", "props": {"style": f"color: {color};", "class": "mr-1"}, "text": icon},
                        {"component": "span", "props": {"class": "text-h6 font-weight-bold"}, "text": str(value) if value not in (None, "") else "—"}]},
                    {"component": "div", "props": {"class": "text-caption text-medium-emphasis"}, "text": label}]}
            ]}

        components = [{"component": "VCard", "props": {"variant": "outlined", "class": "mt-3 mb-4", "style": frost_style}, "content": [
            {"component": "VCardTitle", "props": {"class": "d-flex align-center"}, "content": [
                {"component": "VIcon", "props": {"color": "primary", "class": "mr-2"}, "text": "mdi-medal"},
                {"component": "span", "props": {"class": "text-h6 font-weight-bold"}, "text": "myPT 勋章概览"}]},
            {"component": "VDivider"},
            {"component": "VCardText", "props": {"class": "pa-2"}, "content": [
                {"component": "VRow", "props": {"no-gutters": True}, "content": [
                    stat_block("mdi-medal-outline", "#F9A825", len(owned), "当前拥有勋章"),
                    stat_block("mdi-star-four-points", "#7E57C2", magic or "未解析", "魔力余额"),
                    stat_block("mdi-clock-check", "#4CAF50", overview.get("updated_at") if isinstance(overview, dict) else "—", "最近检查")
                ]}
            ]}
        ]}]

        medal_rows = []
        for item in medals if isinstance(medals, list) else []:
            status = item.get("status") or "unknown"
            medal_rows.append({"component": "tr", "content": [
                {"component": "td", "text": item.get("id") or "—"},
                {"component": "td", "text": item.get("name") or "—"},
                {"component": "td", "text": item.get("expire_at") or "—"},
                {"component": "td", "content": [{"component": "VChip", "props": {"color": self._status_color(status), "size": "small", "variant": "tonal"}, "text": self._status_text(status)}]},
                {"component": "td", "text": item.get("button_text") or "—"}
            ]})
        components.append(self._table_card("当前勋章", ["ID", "名称", "到期时间", "状态", "按钮"], medal_rows, frost_style, "暂无勋章页面解析数据"))

        history_rows = []
        for item in history[:30]:
            history_rows.append({"component": "tr", "content": [
                {"component": "td", "props": {"class": "text-caption"}, "text": item.get("time") or "—"},
                {"component": "td", "text": item.get("medal") or "—"},
                {"component": "td", "content": [{"component": "VChip", "props": {"color": self._status_color(item.get("status")), "size": "small", "variant": "tonal"}, "text": self._status_text(item.get("status"))}]},
                {"component": "td", "props": {"class": "text-caption"}, "text": item.get("message") or "—"}
            ]})
        components.append(self._table_card("历史记录", ["时间", "勋章", "状态", "结果"], history_rows, frost_style, "暂无购买记录"))
        components.append({"component": "style", "text": ".v-table { border-radius: 8px; overflow: hidden; } .v-table th { background-color: rgba(var(--v-theme-primary), 0.05); color: rgb(var(--v-theme-primary)); font-weight: 600; }"})
        return components

    def _finish_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        should_notify = self._notify and any(item.get("status") != "skipped" for item in results)
        if should_notify:
            title = "【myPT勋章续购】"
            text = "\n".join([f"{item.get('medal')}: {self._status_text(item.get('status'))} - {item.get('message')}" for item in results])
            self.post_message(mtype=NotificationType.Plugin, title=title, text=text)
        success = all(item.get("success") for item in results if item.get("status") != "skipped") if results else False
        return {"success": success, "results": results, "message": f"处理 {len(results)} 个勋章"}

    def _save_overview(self, site, medals: Dict[str, Dict[str, Any]], html: str):
        self.save_data("overview", {
            "site": getattr(site, "name", None) or self.SITE_NAME,
            "site_id": getattr(site, "id", "") or "",
            "updated_at": self._now_text(),
            "magic": self._parse_magic(html),
            "medals": list(medals.values())
        })

    def _should_try_by_expire(self, medal: Dict[str, Any]) -> bool:
        expire_at = self._parse_time_text(medal.get("expire_at"))
        if not expire_at:
            return False
        return datetime.now() >= expire_at - timedelta(days=self._check_days)

    def _button_status(self, button_text: str, disabled: bool) -> str:
        if button_text == "购买" and not disabled:
            return "buy"
        if button_text == "已经购买":
            return "owned"
        if button_text == "需要更多魔力值":
            return "insufficient"
        if button_text == "仅授予":
            return "grant_only"
        return "unknown"

    def _extract_medal_name(self, row, medal_id: str) -> str:
        names = row.xpath(".//h1/text()")
        if names:
            return self._clean_text(names[0])
        cells = [self._clean_text(" ".join(td.xpath(".//text()"))) for td in row.xpath("./td")]
        return cells[2].split(" ")[0] if len(cells) > 2 and cells[2] else self.MEDAL_MAP.get(medal_id, {}).get("name", "")

    def _extract_expire_time(self, row) -> str:
        text = self._clean_text(" ".join(row.xpath(".//text()")))
        matches = re.findall(r"\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?", text)
        if not matches:
            return ""
        return matches[-1]

    def _parse_magic(self, html: str) -> str:
        text = self._html_to_text(html)
        # myPT 格式：魔力值 [使用]: 14,229.6
        patterns = [
            r"魔力值.*?([\d,]+(?:\.\d+)?)",
            r"Bonus\s*[:：]?\s*([\d,]+(?:\.\d+)?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return match.group(1)
        return ""

    def _page_headers(self, cookie: str, site=None) -> Dict[str, str]:
        return {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "accept-language": "zh-CN,zh;q=0.9",
            "cookie": cookie,
            "referer": self._base_url(site),
            "user-agent": self._user_agent(site),
        }

    def _ajax_headers(self, cookie: str, site=None) -> Dict[str, str]:
        return {
            "accept": "application/json, text/javascript, */*; q=0.01",
            "accept-language": "zh-CN,zh;q=0.9",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "cookie": cookie,
            "origin": self._base_url(site),
            "referer": urljoin(self._base_url(site) + "/", self.MEDAL_PATH.lstrip("/")),
            "user-agent": self._user_agent(site),
            "x-requested-with": "XMLHttpRequest",
        }

    def _base_url(self, site=None) -> str:
        return str(getattr(site, "url", "") or self.BASE_URL).strip().rstrip("/")

    @staticmethod
    def _user_agent(site=None) -> str:
        return (getattr(site, "ua", "") or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36").strip()

    def _config_snapshot(self, onlyonce: bool = False) -> Dict[str, Any]:
        return {
            "enabled": self._enabled,
            "notify": self._notify,
            "cron": self._cron,
            "onlyonce": onlyonce,
            "medal_ids": self._medal_ids,
            "site_id": self._site_id,
            "check_days": self._check_days,
            "use_proxy": self._use_proxy,
        }

    def _medal_options(self) -> List[Dict[str, Any]]:
        return [{"title": f"{item['id']} - {item['name']}（{item['valid']} / {item['bonus']} / {item['price']}）", "value": item["id"]} for item in self.MEDALS]

    def _site_options(self) -> List[Dict[str, Any]]:
        options = []
        try:
            for site in SiteOper().list_order_by_pri():
                domain = (getattr(site, "domain", "") or "").lower()
                url = (getattr(site, "url", "") or "").lower()
                name = getattr(site, "name", "") or ""
                if self.SITE_DOMAIN in domain or self.SITE_HOST in url or "mypt" in name.lower():
                    options.append({"title": f"{name}（{domain or url}）", "value": str(getattr(site, "id", ""))})
        except Exception as err:
            logger.warning(f"获取 myPT 站点列表失败：{err}")
        return options

    def _table_card(self, title: str, headers: List[str], rows: List[dict], frost_style: str, empty_text: str) -> dict:
        if not rows:
            return {"component": "VAlert", "props": {"type": "info", "variant": "tonal", "text": empty_text, "class": "mb-4"}}
        return {"component": "VCard", "props": {"variant": "outlined", "class": "mb-4", "style": frost_style}, "content": [
            {"component": "VCardTitle", "props": {"class": "d-flex align-center"}, "content": [
                {"component": "VIcon", "props": {"color": "primary", "class": "mr-2"}, "text": "mdi-table"},
                {"component": "span", "props": {"class": "text-h6 font-weight-bold"}, "text": title}]},
            {"component": "VDivider"},
            {"component": "VCardText", "props": {"class": "pa-0 pa-md-2"}, "content": [
                {"component": "VResponsive", "content": [
                    {"component": "VTable", "props": {"hover": True, "density": "comfortable"}, "content": [
                        {"component": "thead", "content": [{"component": "tr", "content": [{"component": "th", "text": header} for header in headers]}]},
                        {"component": "tbody", "content": rows}
                    ]}
                ]}
            ]}
        ]}

    def _get_records(self) -> List[Dict[str, Any]]:
        records = self.get_data("history") or []
        return records if isinstance(records, list) else []

    @staticmethod
    def _status_text(status: str) -> str:
        return {
            "success": "购买成功",
            "failed": "失败",
            "skipped": "跳过",
            "owned": "已拥有",
            "buy": "可购买",
            "insufficient": "魔力不足",
            "grant_only": "仅授予",
            "config_error": "配置错误",
            "auth_failed": "Cookie 失效",
            "unknown": "未知",
        }.get(status or "", status or "未知")

    @staticmethod
    def _status_color(status: str) -> str:
        return {
            "success": "success",
            "failed": "error",
            "skipped": "info",
            "owned": "success",
            "buy": "primary",
            "insufficient": "warning",
            "grant_only": "grey",
            "config_error": "warning",
            "auth_failed": "warning",
        }.get(status or "", "default")

    @staticmethod
    def _parse_time_text(value: Any) -> Optional[datetime]:
        if not value:
            return None
        text = str(value).strip()
        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"]:
            try:
                parsed = datetime.strptime(text, fmt)
                if fmt == "%Y-%m-%d":
                    return parsed.replace(hour=23, minute=59, second=59)
                return parsed
            except ValueError:
                continue
        return None

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
    def _ensure_plugin_log_file():
        try:
            path = settings.LOG_PATH / "plugins" / "myptmedalbuyer.log"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)
        except Exception as err:
            logger.debug(f"确保 myPT 勋章续购日志文件存在失败：{err}")
