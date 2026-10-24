"""Discover forum adapters from integration modules; each declares its own UI and protocol metadata."""
from dataclasses import asdict
from importlib import import_module
from pkgutil import iter_modules


def _hostname(value):
    from .credentials import hostname
    return hostname(value)


def _discover():
    package = import_module("..integrations", __package__)
    adapters = {}
    for entry in iter_modules(package.__path__):
        if entry.name.startswith("_"):
            continue
        module = import_module(f"{package.__name__}.{entry.name}")
        declaration, adapter = getattr(module, "SITE", None), getattr(module, "ADAPTER", None)
        if not isinstance(declaration, dict) or adapter is None:
            continue
        site_id = declaration.get("id")
        if not site_id or site_id in adapters:
            raise ValueError(f"invalid_or_duplicate_forum_site:{site_id}")
        adapters[site_id] = (declaration, adapter)
    return adapters


_REGISTERED = _discover()
ADAPTERS = {key: value[1] for key, value in _REGISTERED.items()}


def site_names() -> dict:
    """站点 id → 中文名（通知文案用）。"""
    return {site_id: (declaration.get("name") or site_id)
            for site_id, (declaration, _) in _REGISTERED.items()}


def get_site(value):
    for site_id, (declaration, adapter) in _REGISTERED.items():
        if value == site_id or _hostname(value) == _hostname(declaration["domain"]):
            return {**declaration, "id": site_id, "adapter": adapter,
                    "credential": adapter.credential_spec}
    return None


def get_registry():
    return [{**declaration, "credential": {**asdict(adapter.credential_spec),
                                             "fields": declaration.get("fields", [])}}
            for declaration, adapter in _REGISTERED.values()]
