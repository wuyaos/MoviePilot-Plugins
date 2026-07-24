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

    def test_fallback_module_is_separate(self):
        text = (ROOT / "sites/nexusphp.py").read_text(encoding="utf-8")
        self.assertIn("class NexusPHPHandler", text)
        self.assertIn("class Tasks", text)


if __name__ == "__main__":
    unittest.main()
