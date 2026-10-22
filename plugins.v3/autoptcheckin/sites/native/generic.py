"""Generated NexusPHP declarations for QNAP sites without a dedicated adapter.

The source table is deliberately credential-free. Runtime cookie lookup remains in
managed site data; these declarations only provide the shared attendance contract.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ...core.credentials import CredentialSpec
from ...core.nexus import NexusSignin
from ...core.sitemodel import RecordSpec

# QNAP aliases differ from native adapter URLs; keep them out of the generic table.
NATIVE_ALIASES = {"pterclub.net": "pterclub", "kp.m-team.cc": "mteam"}
_DECLARATIONS = Path(__file__).with_name("generic_sites.json")


def build_generic_sites() -> list[type[NexusSignin]]:
    declarations = json.loads(_DECLARATIONS.read_text(encoding="utf-8"))
    classes = []
    for item in declarations:
        class_name = "Generic" + re.sub(r"[^A-Za-z0-9]", "_", item["id"]).title()
        attrs = {
            "__module__": __name__,
            "id": item["id"],
            "name": item["name"],
            "url": item["url"],
            "attendance_path": item.get("attendance_path", "/attendance.php"),
            "credential": CredentialSpec(),
            "record_spec": RecordSpec(
                '//*[@id="batch2-message-pending-calibration"]',
                {"未签到": "unsigned"},
            ),
            "hook_implemented": True,
            "verified": False,
        }
        generated = type(class_name, (NexusSignin,), attrs)
        globals()[class_name] = generated
        classes.append(generated)
    return classes


_GENERIC_SITES = build_generic_sites()
