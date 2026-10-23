"""Credential-free site declarations; execution stays in the shared native flows."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin

from ...core.api_signin import ApiSignin
from ...core.attendance_captcha import solve_attendance_captcha
from ...core.credentials import CredentialSpec
from ...core.get_signin import GetSignin
from ...core.nexus import NexusSignin, SigninForm
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
            "attendance_path": item.get("safe_read_path", item.get("attendance_path", "/attendance.php")),
            "credential": CredentialSpec(),
            "record_spec": RecordSpec(
                item.get("message", '//*[@id="batch2-message-pending-calibration"]'),
                item.get("status_map", {"未签到": "unsigned"}),
            ),
            "hook_implemented": True,
            "verified": False,
        }
        for key in ("signed_marker", "use_default_message", "signin_capable", "emulate", "protocol_pending", "login_notice"):
            if key in item:
                attrs[key] = item[key]
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
        if item.get("captcha", False):
            attrs["solve_captcha"] = _solve_captcha
        if item.get("signin_capable") is False:
            attrs["signin"] = _signin_not_applicable
        generated = type(class_name, (base,), attrs)
        globals()[class_name] = generated
        classes.append(generated)
    return classes


_GENERIC_SITES = build_generic_sites()
