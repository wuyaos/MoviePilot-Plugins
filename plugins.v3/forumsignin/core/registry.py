from dataclasses import asdict
from .credentials import hostname
from ..integrations.fengchao import Fengchao
from ..integrations.yaowan import Yaowan
from ..integrations.ssdforum import SSDForum

ADAPTERS = {"fengchao": Fengchao, "yaowan": Yaowan, "ssdforum": SSDForum}
NAMES = {"fengchao": "蜂巢", "yaowan": "药丸", "ssdforum": "SSDForum"}


def get_site(value):
    for site_id, adapter in ADAPTERS.items():
        if value == site_id or hostname(value) == hostname(adapter.base):
            return {"id": site_id, "name": NAMES[site_id], "domain": hostname(adapter.base),
                    "credential": adapter.credential_spec, "adapter": adapter}
    return None


def get_registry():
    return [{"id": key, "name": NAMES[key], "domain": hostname(adapter.base),
             "source": "插件适配", "signin_capable": True, "login_capable": False,
             "credential": asdict(adapter.credential_spec)} for key, adapter in ADAPTERS.items()]
