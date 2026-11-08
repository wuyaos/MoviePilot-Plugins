"""声明式 UI（get_form / get_page）结构断言。"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

# parents[3] = tests/v3/jyingcheckin/test_ui.py → 仓库根
PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "jyingcheckin"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def config_form():
    return _load_module("jying_config_form", PLUGIN_DIR / "config_form.py")


def test_build_form_shape(config_form):
    form, model = config_form.build_form()
    assert isinstance(form, list) and form
    vform = form[0]
    assert vform["component"] == "VForm"
    text = json.dumps(vform, ensure_ascii=False)
    # 所有配置键都出现在表单里
    for key in ("enabled", "notify", "lucky_mode", "onlyonce", "username",
                "password", "cron", "retry_count", "retry_interval"):
        assert f'"model": "{key}"' in text, key
    # model 与 config_defaults.json 一致
    defaults = json.loads((PLUGIN_DIR / "config_defaults.json").read_text(encoding="utf-8"))
    assert model == defaults


def test_build_form_no_custom_components(config_form):
    """只允许宿主已知的 Vuetify 组件。"""
    form, _ = config_form.build_form()
    allowed = {"VForm", "VCard", "VCardTitle", "VCardText", "VDivider", "VRow",
               "VCol", "VTextField", "VSwitch", "VAlert", "VIcon", "span"}
    seen = set()

    def walk(node):
        if isinstance(node, dict):
            comp = node.get("component")
            if comp:
                seen.add(comp)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(form)
    assert seen <= allowed, seen - allowed
