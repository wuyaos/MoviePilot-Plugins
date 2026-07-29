import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("shoutbox", ROOT / "base/shoutbox.py")
shoutbox = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shoutbox)


class ShoutboxObservationTests(unittest.TestCase):
    def test_all_browser_profile_evidence_is_valid_json(self):
        fixture = ROOT / "tests/fixtures/shoutbox_profiles.json"
        profiles = json.loads(fixture.read_text())
        self.assertEqual(len(profiles), 13)
        self.assertEqual(profiles["hxpt"]["url"], "/shoutbox.php?ajax_chat=1&type=")
        self.assertEqual(profiles["moment"]["direction"], "both")
    def test_invalid_snapshot_is_distinct_from_missing_message(self):
        profile = shoutbox.ShoutboxProfile(row_xpath="//td[@class='shoutrow']")
        snapshot = shoutbox.ShoutboxSnapshot.parse("<html><body>login</body></html>", profile)
        observed = shoutbox.observe(snapshot, profile, "wuyaos", "测试", ["测试"])
        self.assertFalse(observed.snapshot_valid)
        self.assertFalse(observed.sent)
        self.assertIn("未找到", observed.reason)

    def test_before_feedback_with_time_prefix(self):
        profile = shoutbox.ShoutboxProfile(
            row_xpath="//td[@class='shoutrow']",
            is_feedback=lambda row, username: "黑丝娘" in row.text and f"@{username}" in row.text,
        )
        html = """<table>
          <tr><td class='shoutrow'>[1分钟前] 黑丝娘 @wuyaos 黑丝娘很开心，奖励9GB上传</td></tr>
          <tr><td class='shoutrow'>[1分钟前] wuyaos 黑丝娘，求上传</td></tr>
        </table>"""
        observed = shoutbox.observe(shoutbox.ShoutboxSnapshot.parse(html, profile), profile,
                                    "wuyaos", "黑丝娘，求上传", ["黑丝娘，求上传", "黑丝娘，求工分"])
        self.assertTrue(observed.sent)
        self.assertIn("9GB", observed.feedback.text)

    def test_system_feedback_with_username_is_not_own_shout_boundary(self):
        profile = shoutbox.ShoutboxProfile(
            row_xpath="//td[@class='shoutrow']",
            direction=shoutbox.FeedbackDirection.BOTH,
            is_feedback=lambda row, username: f"【{username}的女友】" in row.text,
        )
        html = """<table>
          <tr><td class='shoutrow'>wuyaos 茄子</td></tr>
          <tr><td class='shoutrow'>【wuyaos的女友】她轻轻笑，奖励 +884 魔力。</td></tr>
        </table>"""
        observed = shoutbox.observe(shoutbox.ShoutboxSnapshot.parse(html, profile), profile,
                                    "wuyaos", "茄子", ["茄子", "保一条"])
        self.assertTrue(observed.sent)
        self.assertIn("+884", observed.feedback.text)

    def test_own_next_message_stops_feedback_window(self):
        profile = shoutbox.ShoutboxProfile(
            row_xpath="//td[@class='shoutrow']",
            direction=shoutbox.FeedbackDirection.BOTH,
            is_feedback=lambda row, username: "女友" in row.text,
        )
        html = """<table>
          <tr><td class='shoutrow'>wuyaos 茄子</td></tr>
          <tr><td class='shoutrow'>wuyaos 保一条</td></tr>
          <tr><td class='shoutrow'>【wuyaos的女友】奖励 +100 魔力。</td></tr>
        </table>"""
        observed = shoutbox.observe(shoutbox.ShoutboxSnapshot.parse(html, profile), profile,
                                    "wuyaos", "茄子", ["茄子", "保一条"])
        self.assertTrue(observed.sent)
        self.assertIsNone(observed.feedback)

    def test_external_pts_reward(self):
        profile = shoutbox.ShoutboxProfile(
            row_xpath="//td[@class='shoutrow']",
            direction=shoutbox.FeedbackDirection.EXTERNAL,
            external_feedback_xpath="//div[contains(@class, 'magic-reward-top')]",
            is_feedback=lambda row, username: f"用户「{username}」" in row.text,
        )
        html = """<div class='magic-reward-top system-msg'>恭喜用户「wuyaos」获得231点魔力值！</div>
        <table><tr><td class='shoutrow'>wuyaos 「短剧第一站」</td></tr></table>"""
        observed = shoutbox.observe(shoutbox.ShoutboxSnapshot.parse(html, profile), profile,
                                    "wuyaos", "「短剧第一站」", ["「短剧第一站」"])
        self.assertTrue(observed.sent)
        self.assertIn("231", observed.feedback.text)


if __name__ == "__main__":
    unittest.main()
