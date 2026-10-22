"""V2 配置迁移；只访问本机宿主 API，不读取站点或旧插件数据文件。"""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from threading import RLock
from urllib.parse import urlsplit

SOURCES = ("AutoPtCheckin", "RousiCheckin", "SunnyPTSignin")
CONFIG_KEYS = ("enabled", "cron", "cron_mode", "interval_hours", "begin_hour", "end_hour",
               "notify", "queue_cnt")
DATA_UNAVAILABLE = {"RousiCheckin": ["history"], "SunnyPTSignin": ["records", "token_cache"]}


class MigrationError(ValueError):
    """可安全返回调用方的固定错误码。"""


def host_get(path):
    """固定 loopback、有限超时、不跟随重定向；宿主端点使用 API key。"""
    import requests
    from app.sdk.config import settings
    with requests.Session() as session:
        session.trust_env = False
        response = session.get(f"http://127.0.0.1:{settings.PORT}/api/v1/plugin{path}",
                               headers={"X-API-KEY": settings.API_TOKEN},
                               timeout=(3, 10), allow_redirects=False)
        response.raise_for_status()
        if response.status_code != 200:
            raise MigrationError("source_read_error")
        payload = response.json()
        if isinstance(payload, dict) and "success" in payload:
            if payload["success"] is not True:
                raise MigrationError("source_read_error")
            return payload.get("data")
        return payload


def read_sources(get=host_get):
    """先查已安装清单与本地版本，不能把同 ID 的 V3 配置作为旧来源。"""
    try:
        installed = get("/installed")
        catalog = get("/?state=installed") if "AutoPtCheckin" in installed else []
        if not isinstance(installed, list) or not isinstance(catalog, list):
            raise ValueError()
    except Exception:
        return {name: {"status": "source_error", "reason": "catalog_unavailable"} for name in SOURCES}
    result = {}
    for name in SOURCES:
        if name not in installed:
            result[name] = {"status": "source_missing", "reason": "not_installed"}
            continue
        if name == "AutoPtCheckin":
            meta = next((item for item in catalog if item.get("id") == name), {})
            version = str(meta.get("plugin_version") or "")
            try:
                major = int(version.split(".")[0])
            except ValueError:
                result[name] = {"status": "source_error", "reason": "version_unavailable"}
                continue
            if major >= 3:
                result[name] = {"status": "source_missing", "reason": "self_v3"}
                continue
        try:
            config = get("/" + name)
            if not isinstance(config, dict):
                raise ValueError()
            result[name] = {"status": "ready", "config": deepcopy(config)}
        except Exception:
            result[name] = {"status": "source_error", "reason": "config_unavailable"}
    return result


def domain(value):
    parsed = urlsplit(value if "://" in value else "https://" + value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("invalid domain")
    return parsed.hostname.lower()


def registry_mapping(value, registry):
    from .registry import _MATCHERS
    if value in {site["id"] for site in registry["sites"]}:
        return value
    host = domain(value)
    for site in registry["sites"]:
        match = _MATCHERS.get(site["id"])
        if match and match("https://" + host + "/"):
            return site["id"]
    return None


def build_preview(sources, target, registry, resolve=registry_mapping):
    """构造内部计划；API 仅返回键、来源及冲突，不回显旧凭据。"""
    changes, unmapped, unavailable = {}, [], []
    source_states = {name: {k: v for k, v in item.items() if k != "config"}
                     for name, item in sources.items()}
    for source, item in sources.items():
        if item["status"] != "ready":
            continue
        config = item["config"]
        unavailable.extend({"source": source, "key": key, "status": "data_unavailable"}
                           for key in DATA_UNAVAILABLE.get(source, []))
        if source != "AutoPtCheckin":
            prefix = "rousi" if source == "RousiCheckin" else "sunnypt"
            for key in (("username", "password", "token") if prefix == "sunnypt" else ("username", "password")):
                value = config.get(prefix + "_" + key, config.get(key))
                if value not in (None, ""):
                    changes[prefix + "_" + key] = {"source": source, "value": deepcopy(value)}
            continue
        values = {key: deepcopy(config[key]) for key in CONFIG_KEYS if key in config}
        customs, aliases = [], {}
        raw_customs = list(config.get("custom_sites_data") or [])
        for index, line in enumerate((config.get("custom_site_urls") or "").splitlines()):
            if not line.strip():
                continue
            parts = [part.strip() for part in line.split("|")]
            if len(parts) != 3:
                unmapped.append({"source": source, "key": "custom_site_urls", "index": index})
                continue
            if not any(item.get("url") == parts[1] for item in raw_customs):
                raw_customs.append({"name": parts[0], "url": parts[1], "render": parts[2].upper() == "Y"})
        for index, custom in enumerate(raw_customs):
            try:
                url = custom["url"]
                host = domain(url)
                if not url.startswith(("http://", "https://")) or not custom.get("name"):
                    raise ValueError()
                sid = "custom-" + sha256(url.encode()).hexdigest()[:16]
                aliases[str(custom.get("id", sid))] = sid
                aliases[host] = sid
                if not any(item["id"] == sid for item in customs):
                    customs.append({"id": sid, "name": custom["name"], "url": url,
                                    "emulate": bool(custom.get("emulate", custom.get("render", False))),
                                    "source": "自定义站点", "login_capable": True,
                                    "credential": "cookie", "fields": []})
            except (KeyError, ValueError, TypeError):
                unmapped.append({"source": source, "key": "custom_sites_data", "index": index})
        if "custom_sites_data" in config or "custom_site_urls" in config:
            values["custom_sites_data"] = customs
        for key in ("sign_sites", "login_sites"):
            if key not in config:
                continue
            mapped = []
            for index, value in enumerate(config[key] or []):
                try:
                    sid = aliases.get(str(value)) or aliases.get(domain(str(value))) or resolve(str(value), registry)
                except (ValueError, TypeError):
                    sid = None
                if sid:
                    if sid not in mapped:
                        mapped.append(sid)
                else:
                    unmapped.append({"source": source, "key": key, "index": index, "value": value})
            values[key] = mapped
        if "sign_sites" in values or "login_sites" in values:
            values["enabled_sites"] = list(dict.fromkeys(values.get("sign_sites", []) + values.get("login_sites", [])))
        changes.update({key: {"source": source, "value": value} for key, value in values.items()})
    for key, item in changes.items():
        item["conflict"] = key in target and target[key] not in (None, "", [], {}) and target[key] != item["value"]
    return {"sources": source_states, "changes": changes, "unmapped": unmapped, "data_unavailable": unavailable}


def public_preview(plan):
    result = deepcopy(plan)
    result["changes"] = [{"key": key, "source": item["source"], "conflict": item["conflict"]}
                         for key, item in plan["changes"].items()]
    for item in result["changes"]:
        key = item["key"]
        if not key.startswith(("rousi_", "sunnypt_")):
            item["value"] = deepcopy(plan["changes"][key]["value"])
    result["conflicts"] = [item for item in result["changes"] if item["conflict"]]
    return result


class Migration:
    BACKUP_KEY = "migration.v2.backup"
    STATE_KEY = "migration.v2.state"

    def __init__(self, plugin, sources=read_sources, registry=None):
        self.plugin, self.sources, self.registry = plugin, sources, registry
        self.lock = RLock()
        self._preview = None

    def _plan(self):
        from .registry import get_registry
        return build_preview(self.sources(), self.plugin._config, self.registry or get_registry())

    def preview(self):
        with self.lock:
            plan = self._plan()
            self._preview = (deepcopy(plan), deepcopy(self.plugin._config))
            return public_preview(plan)

    def execute(self, confirm=False, overwrite_conflicts=False):
        with self.lock:
            if confirm is not True or not isinstance(overwrite_conflicts, bool):
                raise MigrationError("confirmation_required")
            state = self.plugin.get_data(self.STATE_KEY)
            if state:
                if state.get("status") == "completed":
                    return {"status": "already_executed"}
                raise MigrationError("rollback_required")
            plan = self._plan()
            if self._preview != (plan, self.plugin._config):
                raise MigrationError("preview_required_or_stale")
            if any(item["status"] == "source_error" for item in plan["sources"].values()):
                raise MigrationError("source_read_error")
            applied = {key: deepcopy(item["value"]) for key, item in plan["changes"].items()
                       if overwrite_conflicts or not item["conflict"]}
            skipped_dependencies = []
            custom_change = plan["changes"].get("custom_sites_data")
            if custom_change and custom_change["conflict"] and not overwrite_conflicts:
                available = {item["id"] for item in self.plugin._config.get("custom_sites_data", [])}
                for key in ("enabled_sites", "sign_sites", "login_sites"):
                    if key in applied and any(str(sid).startswith("custom-") and sid not in available for sid in applied[key]):
                        skipped_dependencies.append(key)
                        del applied[key]
            if not applied:
                return {"status": "no_changes", "applied": []}
            backup = {"config": deepcopy(self.plugin._config),
                      "site_config": deepcopy(self.plugin.get_data("site_config")),
                      "time": datetime.now().astimezone().isoformat()}
            self.plugin.save_data(self.BACKUP_KEY, backup)
            self.plugin.save_data(self.STATE_KEY, {"status": "applying"})
            config = {**self.plugin._config, **applied}
            self.plugin.update_config(config)
            self.plugin.init_plugin(config)
            self.plugin.save_data(self.STATE_KEY, {"status": "completed", "applied": list(applied)})
            self._preview = None
            return {"status": "completed", "applied": list(applied), "backup_key": self.BACKUP_KEY, "skipped_dependencies": skipped_dependencies,
                    "skipped_conflicts": [key for key, item in plan["changes"].items() if item["conflict"] and not overwrite_conflicts]}
