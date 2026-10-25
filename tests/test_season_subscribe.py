"""离线运行：python -m unittest discover -s tests -p test_season_subscribe.py。"""
import importlib.util
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from rich.console import Console

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("season_subscribe", ROOT / "scripts/season_subscribe.py")
cli = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = cli
spec.loader.exec_module(cli)


class SeasonSubscribeTests(unittest.TestCase):
    def test_parse_yuc_fixture(self):
        html = (ROOT / "tests/fixtures/season_subscribe/yuc.html").read_text(encoding="utf-8")
        entries, declared, warnings = cli.parse_yuc(html)
        self.assertEqual(declared, 5)
        self.assertEqual(len(entries), 4)
        self.assertIn("重复", " ".join(warnings))
        self.assertEqual(entries[0].title, "长篇 第2期")
        self.assertEqual(entries[0].weekday, "周三 (水)")
        self.assertEqual(entries[0].air_date, "9/30")
        self.assertEqual(entries[0].air_time, "25:30")
        self.assertEqual(entries[0].region, "港澳台")
        self.assertTrue(entries[1].network_release)
        self.assertEqual(entries[1].air_date, "9/25")
        self.assertEqual(entries[2].title, "Original Only")
        self.assertIn("缺失标题", entries[3].title)

    def test_yuc_declared_boundary_and_missing_intro(self):
        html = (ROOT / "tests/fixtures/season_subscribe/yuc.html").read_text(encoding="utf-8")
        entries, declared, warnings = cli.parse_yuc(html.replace("<b>5</b>", "<b>2</b>"))
        self.assertEqual((len(entries), declared), (2, 2))
        self.assertTrue(warnings)
        with self.assertRaises(ValueError):
            cli.parse_yuc("<meta name='description' content='共收录 100 部'>")

    def test_selection_and_scores(self):
        self.assertEqual(cli.select_seasons("2,3,2", [2, 3]), [2, 3])
        self.assertEqual(cli.select_seasons("all", [2, 3]), [2, 3])
        self.assertEqual(cli.select_seasons("0", [2, 3]), [])
        for invalid in ("1", "2,x", "-1"):
            with self.assertRaises(ValueError):
                cli.select_seasons(invalid, [2, 3])
        self.assertEqual(cli.score(8.6, 10), "8.6 / 10")
        self.assertEqual(cli.score(87, 100), "87 / 100")
        self.assertEqual(cli.score(0, 100), "暂无")
        self.assertEqual(cli.score(None, 10), "暂无")
        self.assertNotEqual(cli.normalized("作品2"), cli.normalized("作品"))

    def test_auto_match_by_name_year_type(self):
        anime = cli.Anime("顶点武装", "VERTEX FORCE", kind="TV", year=2026)
        good = {"name_cn": "至高之力", "name": "バーテックスフォース", "date": "2026-10-03",
                "format": "TV", "id": 1, "aliases": ["VERTEX FORCE"]}
        bad = {"name_cn": "绿色星球", "name": "La Planète Verte", "date": None, "format": "", "id": 2}
        self.assertGreaterEqual(cli.name_score(good, anime), 4)
        self.assertEqual(cli.name_score(bad, anime), 0)
        self.assertGreaterEqual(cli.match_score(good, anime), 7)
        with patch.object(cli, "console", Console(file=io.StringIO(), markup=False)):
            self.assertEqual(cli.auto_match([good, bad], anime, "Bangumi"), good)
        # 同名不同年份：分差不足以自动选，必须人工核对
        sequel = dict(good, id=3, date="2024-07-05")
        with patch.object(cli, "console", Console(file=io.StringIO(), markup=False)):
            self.assertIsNone(cli.auto_match([sequel, good], anime, "Bangumi"))

    def test_recognize_fallback(self):
        media = {"title": "Test", "type": "电视剧", "media_source": "tmdb", "media_id": "12"}
        calls = []

        def handler(request):
            calls.append(request.url.params.get("title"))
            info = media if request.url.params.get("title") == "原名X" else {}
            return httpx.Response(200, json={"success": True, "data": {"media_info": info}})

        with httpx.Client(base_url="https://mp.invalid/api/v1/", transport=httpx.MockTransport(handler)) as client:
            found, used = cli.recognize_any(cli.MoviePilot(client), ["中文名", "原名X", "原名X"])
        self.assertEqual(used, "原名X")
        self.assertEqual(found, media)
        self.assertEqual(calls, ["中文名", "原名X"])

    def test_dry_run_and_confirmation_gate(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(200, json={"success": True, "data": {"id": 7}})
        with httpx.Client(base_url="https://mp.invalid/api/v1/", transport=httpx.MockTransport(handler)) as client:
            mp = cli.MoviePilot(client)
            mp.create({"season": 2}, confirmed=True)
            self.assertEqual(calls, [])
            mp.apply = True
            mp.create({"season": 2})
            self.assertEqual(calls, [])
            self.assertEqual(mp.create({"season": 2}, confirmed=True), {"id": 7})
            self.assertEqual(str(calls[0].url), "https://mp.invalid/api/v1/subscribe/")
            self.assertEqual(calls[0].method, "POST")

    def test_interactive_dry_run_skips_existing_and_never_posts(self):
        calls = []
        media = {"title": "测试番", "type": "电视剧", "year": "2026",
                 "media_source": "tmdb", "media_id": "12"}
        def handler(request):
            calls.append(request.method)
            if request.url.path.endswith("recognize"):
                data = {"media_info": media}
            elif request.url.path.endswith("seasons"):
                data = [{"season_number": i, "air_date": "2026-10-01"} for i in (1, 2, 3)]
            else:
                data = [{**media, "id": 5, "season": 1, "state": "N"}]
            return httpx.Response(200, json={"success": True, "data": data})
        output = io.StringIO()
        with httpx.Client(base_url="https://mp.invalid/api/v1/", transport=httpx.MockTransport(handler)) as client, \
             patch.object(cli, "console", Console(file=output, markup=False)), \
             patch.object(cli, "ask", side_effect=["y", "all", "y"]):
            cli.subscribe_anime(cli.MoviePilot(client), cli.Anime("测试番"), {}, {})
        self.assertNotIn("POST", calls)
        self.assertIn("S01", output.getvalue())
        self.assertIn("已订阅", output.getvalue())
        self.assertEqual(output.getvalue().count("未发送 POST"), 2)

    def test_mp_failure_and_identity_safety(self):
        with httpx.Client(base_url="https://mp.invalid/api/v1/", transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json={"success": False, "message": "secret"}))) as client:
            with self.assertRaisesRegex(ValueError, "MP 返回失败"):
                cli.MoviePilot(client).subscriptions()
        with self.assertRaises(ValueError):
            cli.identity({"tmdb_id": 12})
        self.assertFalse(cli.existing([{"media_source": "douban", "media_id": "12", "season": 2}],
                                     {"media_source": "tmdb", "media_id": "12"}, 2))

    def test_q_and_default_mode(self):
        with patch.object(cli.console, "input", return_value="q"):
            with self.assertRaises(SystemExit):
                cli.ask("test")
        args = cli.arguments(["--year", "2026", "--month", "10", "--mp-url", "http://localhost"])
        self.assertFalse(args.apply)


if __name__ == "__main__":
    unittest.main()
