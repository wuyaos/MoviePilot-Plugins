import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


class SiteModuleTests(unittest.TestCase):
    def test_expected_site_modules_exist(self):
        self.assertTrue((ROOT / "sites/qingwa.py").exists())
        self.assertTrue((ROOT / "sites/zm.py").exists())
        self.assertTrue((ROOT / "sites/nexusphp.py").exists())

    def test_each_site_module_is_syntax_valid(self):
        for path in (ROOT / "sites").glob("*.py"):
            ast.parse(path.read_text(encoding="utf-8"))

    def test_task_type_is_explicit(self):
        for name in ("qingwa.py", "zm.py", "nexusphp.py"):
            text = (ROOT / "sites" / name).read_text(encoding="utf-8")
            self.assertIn("TaskType.", text)

    def test_nexusphp_is_capability_only(self):
        loader = (ROOT / "sites/__init__.py").read_text(encoding="utf-8")
        plugin = (ROOT / "__init__.py").read_text(encoding="utf-8")
        self.assertIn('if module_info.name == "nexusphp":', loader)
        self.assertIn("NexusPHP 仅作为能力组合，不提供通用任务", plugin)

    def test_nexusphp_handler_is_not_registered_as_site(self):
        text = (ROOT / "sites/__init__.py").read_text(encoding="utf-8")
        self.assertNotIn("通用 NexusPHP 必须最后加载", text)
        self.assertIn("continue", text[text.index('if module_info.name == "nexusphp":'):])


if __name__ == "__main__":
    unittest.main()
