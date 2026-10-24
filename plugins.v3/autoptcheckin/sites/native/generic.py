"""Credential-free site declarations; execution stays in the shared native flows."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin

from lxml import html

from ...core.api_signin import ApiSignin
from ...core.attendance_captcha import solve_attendance_captcha
from ...core.credentials import CredentialSpec
from ...core.get_signin import GetSignin
from ...core.nexus import NexusSignin, SigninForm
from ...core.sitemodel import RecordSpec, page_available

NATIVE_ALIASES = {"pterclub.net": "pterclub", "kp.m-team.cc": "mteam"}
_DECLARATIONS = Path(__file__).with_name("generic_sites.json")


def _solve_captcha(self, ctx, page, form):
    return solve_attendance_captcha(ctx, page, form)


def _discover_static_form(self, ctx, page):
    return SigninForm(urljoin(self.url, self.form_path), list(self.form_data.items()))


def _signin_not_applicable(self, ctx):
    result = ctx.result(status="skipped", message="signin_not_applicable")
    result.metadata["reason"] = "signin_not_applicable"
    return result


def _shaobaoyuan_read_before(self, ctx, page):
    # This site's nginx denial is served with HTTP 200, even with its stored Cookie.
    text = page.text if page is not None else ""
    if text and len(text.encode("utf-8")) <= 2048:
        doc = html.fromstring(text)
        if (doc.xpath('//title[normalize-space(.)="403 Forbidden"]')
                and doc.xpath('//h1[normalize-space(.)="403 Forbidden"]')
                and doc.xpath('//center[normalize-space(.)="nginx"]')
                and not doc.xpath('//form')):
            result = ctx.result(status="network_error", message="站点防护页拦截：nginx 403 Forbidden（HTTP 200）")
            result.metadata["defer_submission"] = True
            return result
    return NexusSignin.read_before(self, ctx, page)


def build_generic_sites() -> list[type[NexusSignin]]:
    declarations = json.loads(_DECLARATIONS.read_text(encoding="utf-8"))
    classes = []
    for item in declarations:
        class_name = "Generic" + re.sub(r"[^A-Za-z0-9]", "_", item["id"]).title()
        base = NexusSignin
        attrs = {
            "__module__": __name__,
            "id": item["id"],
            "name": item["name"],
            "url": item["url"],
            "attendance_path": item.get("safe_read_path", item.get("attendance_path")),  # null=仅登录站
            "credential": CredentialSpec(),
            "record_spec": RecordSpec(
                item.get("message", '//*[@id="batch2-message-pending-calibration"]'),
                item.get("status_map", {"未签到": "unsigned"}),
            ),
            "hook_implemented": True,
            "verified": False,
        }
        for key in ("signed_marker", "use_default_message", "signin_capable", "emulate", "slow", "protocol_pending", "login_notice", "cloak_steps", "cloak_entry_path", "browser_login", "headful", "slow_timeout", "impersonate"):
            if key in item:
                attrs[key] = item[key]
        if item["id"] == "shaobaoyuan":
            attrs["read_before"] = _shaobaoyuan_read_before
        if "success_texts" in item:
            attrs["success_texts"] = tuple(item["success_texts"])
        if "action_get" in item:
            attrs["attendance_path"] = item["safe_read_path"]
            base = GetSignin
            attrs["action_path"] = item["action_get"]
            attrs["action_referer"] = item.get("referer", False)
        if "form_data" in item:
            attrs.update(form_data=item["form_data"], form_path=item["form_path"],
                         discover_form=_discover_static_form)
        if "response_json" in item:
            attrs["attendance_path"] = item["safe_read_path"]
            base = ApiSignin
            response = item["response_json"]
            # JSON object keys are strings; pairs preserve numeric/bool key types.
            states = dict(response["status_map"])
            if len(states) != len(response["status_map"]):
                raise ValueError("response_json status_map contains duplicate or bool/int-colliding keys")
            attrs["record_spec"] = RecordSpec(source="response_json",
                                               response_field=response["field"], status_map=states)
            attrs["action_path"] = item["action_path"]
        # cloak_steps 页面动作自含验证处理；OCR/滑块 solve 仅在非动作站挂载。
        if item.get("captcha", False) and not item.get("cloak_steps"):
            attrs["solve_captcha"] = _solve_captcha
        # attendance_path 显式为 null（键存在且值为 None）＝仅登录站，signin 一律不适用；
        # 键缺省（D1 下沉站用 safe_read_path/action_path）不在此列。
        login_only = item.get("signin_capable") is False or (
            "attendance_path" in item and item["attendance_path"] is None)
        if login_only:
            attrs["signin"] = _signin_not_applicable
        if item.get("cloak_steps"):
            steps = tuple(item["cloak_steps"])

            def discover_form(self, ctx, page):
                # 浏览器动作站无标准表单；合成提交占位让标准前读/回读流程承载动作。
                return SigninForm(urljoin(self.url, self.attendance_path), [])

            def submit(self, ctx, form, _steps=tuple(steps)):
                from ...core.cloak import run_page_action
                results = run_page_action(ctx.http.session, list(_steps)) or []
                # steps 明细暂存到 ctx，read_after 写进 result.metadata（MP 日志 INFO/WARNING 不落盘，
                # qnap 诊断唯一可靠通道是 history/响应里的 metadata）。
                ctx.cloak_steps_result = [list(r) for r in results]
                # 动作后落点页即回读证据：站点每次进入都可能发新滑块门页，
                # 二次 GET 会重新拿到门页导致证据丢失（自由农场实证）。
                from ...core.models import LoginPage
                page = ctx.http.session.page
                ctx.cloak_read = LoginPage(page.content(), page.url, 200)

            def read_after(self, ctx, page, _base=base):
                stashed = getattr(ctx, "cloak_read", None)
                if stashed is not None:
                    ctx.cloak_read = None
                    if page_available(stashed):
                        return _base.read_after(self, ctx, stashed)
                return _base.read_after(self, ctx, page)

            attrs["discover_form"] = discover_form
            attrs["submit"] = submit
            attrs["read_after"] = read_after
        generated = type(class_name, (base,), attrs)
        globals()[class_name] = generated
        classes.append(generated)
    return classes


_GENERIC_SITES = build_generic_sites()
