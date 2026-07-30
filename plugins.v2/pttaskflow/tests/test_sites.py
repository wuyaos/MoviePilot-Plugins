"""全站声明契约测试：不发网络请求，只验证注册和 Task/Control 展开。"""
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).parents[1]
PACKAGE = "pttaskflow_site_test"


def package(name, path):
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules[name] = module


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# 只加载领域依赖，绕开插件入口的 MoviePilot app 依赖。
package(PACKAGE, ROOT)
package(f"{PACKAGE}.core", ROOT / "core")
package(f"{PACKAGE}.actions", ROOT / "actions")
package(f"{PACKAGE}.sites", ROOT / "sites")
models = load(f"{PACKAGE}.core.models", ROOT / "core/models.py")
load(f"{PACKAGE}.core.task_keys", ROOT / "core/task_keys.py")
load(f"{PACKAGE}.actions.checkin", ROOT / "actions/checkin.py")
load(f"{PACKAGE}.core.task", ROOT / "core/task.py")
load(f"{PACKAGE}.core.shoutbox", ROOT / "core/shoutbox.py")

# Site 基类导入 app 依赖，替换为最小 stub 只用于导入注册表。
app = types.ModuleType("app")
app.__path__ = []
sys.modules["app"] = app
db = types.ModuleType("app.db")
db.__path__ = []
sys.modules["app.db"] = db
site_oper = types.ModuleType("app.db.site_oper")
site_oper.SiteOper = type("SiteOper", (), {})
sys.modules["app.db.site_oper"] = site_oper
log = types.ModuleType("app.log")
log.logger = types.SimpleNamespace(error=lambda *a, **k: None, warning=lambda *a, **k: None)
sys.modules["app.log"] = log
site = load(f"{PACKAGE}.core.site", ROOT / "core/site.py")

# 已加载 Site 依赖后逐个加载站点文件并检查类。
SITE_FILES = [
    "azusa", "cangbao", "car", "city13", "crabpt", "cspt", "cyanbug", "dubhe",
    "freefarm", "ggpt", "hxpt", "lajidui", "longpt", "luckpt", "moment", "mypt",
    "novahd", "ptlgs", "ptskit", "qingwa", "railgunpt", "tangpt", "vclib", "zm",
]


class SiteContractTests(unittest.TestCase):
    def test_all_site_modules_define_composable_tasks(self):
        for filename in SITE_FILES:
            module = load(f"{PACKAGE}.sites.{filename}", ROOT / "sites" / f"{filename}.py")
            site_class = next(value for value in module.__dict__.values()
                              if isinstance(value, type) and hasattr(value, "site_name")
                              and value.__module__ == module.__name__)
            self.assertTrue(site_class.site_name, filename)
            self.assertTrue(site_class.domain, filename)
            self.assertTrue(site_class.tasks, filename)
            for task in site_class.tasks:
                self.assertTrue(task.name, f"{filename} task name")
                self.assertTrue(task.task_type, f"{filename} task type")

    def test_task_keys_do_not_include_site_name(self):
        for index, filename in enumerate(SITE_FILES, start=1):
            module = load(f"{PACKAGE}.sites.key_{filename}", ROOT / "sites" / f"{filename}.py")
            site_class = next(value for value in module.__dict__.values()
                              if isinstance(value, type) and hasattr(value, "site_name")
                              and value.__module__ == module.__name__)
            instance = site_class({"id": str(index), "name": site_class.site_name,
                                   "domain": site_class.domain, "url": "https://example.org"})
            for task in instance.tasks:
                self.assertNotIn(site_class.site_name.lower(), task.key(instance).lower())


if __name__ == "__main__":
    unittest.main()
