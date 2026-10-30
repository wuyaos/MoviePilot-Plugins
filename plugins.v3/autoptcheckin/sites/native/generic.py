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
from ...core.nexus import NexusSignin, PageActionSignin, SigninForm
from ...core.sitemodel import RecordSpec

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


# 声明协议 → 执行基类。protocol 是显式必填键：不再靠 action_get/form_data/cloak_steps 这类
# 互斥键的存在性去推断流程（那正是“按键存在性判流程”的老毛病）。
_PROTOCOL_BASES = {
    "nexus": NexusSignin,
    "form": NexusSignin,
    "api": ApiSignin,
    "get": GetSignin,
    "page_action": PageActionSignin,
    "login_only": NexusSignin,
}
# 这些协议的回读页是 safe_read_path，与动作页不同址。
_SAFE_READ_PROTOCOLS = ("api", "get", "form")


def _require(item, key):
    if key not in item:
        raise ValueError(f"declaration {item.get('id')!r} missing required key {key!r}")
    return item[key]


def build_generic_sites() -> list[type[NexusSignin]]:
    declarations = json.loads(_DECLARATIONS.read_text(encoding="utf-8"))
    classes = []
    for item in declarations:
        class_name = "Generic" + re.sub(r"[^A-Za-z0-9]", "_", item["id"]).title()
        protocol = _require(item, "protocol")
        if protocol not in _PROTOCOL_BASES:
            raise ValueError(f"declaration {item['id']!r} has unknown protocol {protocol!r}")
        base = _PROTOCOL_BASES[protocol]
        if protocol in _SAFE_READ_PROTOCOLS:
            attendance_path = _require(item, "safe_read_path")
        else:
            # 键存在且为 null＝仅登录站（由 protocol=login_only 表达），不是遗漏。
            attendance_path = item.get("attendance_path")
        attrs = {
            "__module__": __name__,
            "id": item["id"],
            "name": item["name"],
            "url": item["url"],
            "attendance_path": attendance_path,
            "credential": CredentialSpec(),
            # message 留空＝未声明专用选择器，由 NexusSignin.message_spec 回退默认链。
            "record_spec": RecordSpec(
                item.get("message", ""),
                item.get("status_map", {"未签到": "unsigned"}),
            ),
        }
        for key in ("signed_marker", "use_default_message", "signin_capable", "emulate", "slow", "protocol_pending", "login_notice", "login_page_notice", "cloak_entry_path", "browser_login", "headful", "slow_timeout", "impersonate", "reset_hour"):
            if key in item:
                attrs[key] = item[key]
        if item["id"] == "shaobaoyuan":
            attrs["read_before"] = _shaobaoyuan_read_before
        if "success_texts" in item:
            attrs["success_texts"] = tuple(item["success_texts"])
        if protocol == "get":
            attrs["action_path"] = _require(item, "action_get")
            attrs["action_referer"] = item.get("referer", False)
        elif protocol == "api":
            response = _require(item, "response_json")
            # JSON object keys are strings; pairs preserve numeric/bool key types.
            states = dict(response["status_map"])
            if len(states) != len(response["status_map"]):
                raise ValueError("response_json status_map contains duplicate or bool/int-colliding keys")
            attrs["record_spec"] = RecordSpec(source="response_json",
                                              response_field=response["field"], status_map=states)
            attrs["action_path"] = _require(item, "action_path")
        elif protocol == "form":
            attrs.update(form_data=_require(item, "form_data"),
                         form_path=_require(item, "form_path"),
                         discover_form=_discover_static_form)
        elif protocol == "page_action":
            # 动作链与「落点页即证据」的回读语义都在 PageActionSignin，声明只给步骤序列。
            attrs["cloak_steps"] = tuple(_require(item, "cloak_steps"))
        # 页面动作站自含验证处理；OCR/滑块 solve 只在非动作站挂载。
        if item.get("captcha", False) and protocol != "page_action":
            attrs["solve_captcha"] = _solve_captcha
        if protocol == "login_only":
            attrs["signin"] = _signin_not_applicable
        generated = type(class_name, (base,), attrs)
        globals()[class_name] = generated
        classes.append(generated)
    return classes


_GENERIC_SITES = build_generic_sites()
