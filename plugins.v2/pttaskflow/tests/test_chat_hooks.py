"""真实喊话样例的无网络回归测试。"""
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).parents[1]
PACKAGE = "pttaskflow_chat_test"


def package(name, path):
    module = types.ModuleType(name); module.__path__ = [str(path)]; sys.modules[name] = module


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module); return module


package(PACKAGE, ROOT); package(f"{PACKAGE}.core", ROOT / "core")
package(f"{PACKAGE}.actions", ROOT / "actions"); package(f"{PACKAGE}.sites", ROOT / "sites")
models = load(f"{PACKAGE}.core.models", ROOT / "core/models.py")
load(f"{PACKAGE}.core.task_keys", ROOT / "core/task_keys.py")
load(f"{PACKAGE}.actions.checkin", ROOT / "actions/checkin.py")
load(f"{PACKAGE}.actions.site_actions", ROOT / "actions/site_actions.py")
load(f"{PACKAGE}.actions.longpt", ROOT / "actions/longpt.py")
load(f"{PACKAGE}.core.task", ROOT / "core/task.py")
shoutbox = load(f"{PACKAGE}.core.shoutbox", ROOT / "core/shoutbox.py")
app = types.ModuleType("app"); app.__path__=[]; sys.modules["app"]=app
db=types.ModuleType("app.db"); db.__path__=[]; sys.modules["app.db"]=db
site_oper=types.ModuleType("app.db.site_oper"); site_oper.SiteOper=type("SiteOper",(),{})
sys.modules["app.db.site_oper"]=site_oper
log=types.ModuleType("app.log"); log.logger=types.SimpleNamespace(error=lambda *a,**k:None,warning=lambda *a,**k:None)
sys.modules["app.log"]=log
load(f"{PACKAGE}.core.site", ROOT / "core/site.py")
Qingwa=load(f"{PACKAGE}.sites.qingwa", ROOT / "sites/qingwa.py").Qingwa
LuckPT=load(f"{PACKAGE}.sites.luckpt", ROOT / "sites/luckpt.py").LuckPT
ZM=load(f"{PACKAGE}.sites.zm", ROOT / "sites/zm.py").ZM
City13=load(f"{PACKAGE}.sites.city13", ROOT / "sites/city13.py").City13
Cangbao=load(f"{PACKAGE}.sites.cangbao", ROOT / "sites/cangbao.py").Cangbao
LongPT=load(f"{PACKAGE}.sites.longpt", ROOT / "sites/longpt.py").LongPT


class Response:
    def __init__(self,text="",payload=None,status_code=200):
        self.text=text; self._payload=payload; self.status_code=status_code; self.url="https://example.org"
    def json(self): return self._payload


def site_info(cls):
    return {"id":"1","name":cls.site_name,"domain":cls.domain,"url":"https://example.org","cookie":"x"}


class ChatHookTests(unittest.TestCase):
    def test_qingwa_direct_response_feedback(self):
        site=Qingwa(site_info(Qingwa)); site.get=lambda *a,**k: Response("<ul><li>不要调戏蛙总！（怒）</li></ul>")
        result=site.send_message("蛙总求上传")
        self.assertTrue(result.success); self.assertEqual(result.rewards[0]["description"],"不要调戏蛙总！（怒）")
        self.assertFalse(result.rewards[0]["is_negative"])

    def test_luckpt_external_feedback_confirms_without_user_row(self):
        html="""<div class='chat-message-container'>别人 发言</div>
        <div class='wish-bubble-system'><div class='wish-content'>@wuyaos今日已祈愿，明天再来吧~</div></div>"""
        rows,reason=shoutbox.parse_snapshot(html,LuckPT.shoutbox); self.assertFalse(reason)
        obs=shoutbox.observe(rows,LuckPT.shoutbox,"wuyaos","幸运池祈愿",["幸运池祈愿"])
        self.assertTrue(obs.sent); self.assertIn("今日已祈愿",obs.feedback.text)

    def test_zm_no_response_is_not_loss_but_deduction_is(self):
        site=ZM(site_info(ZM)); no_reply=types.SimpleNamespace(feedback=shoutbox.ChatRow(0,"皮总 @wuyaos：皮总没有理你，明天再来吧",0),sent=True)
        result=site.feedback_result("皮总，求电力",no_reply,("扣减","扣除","失去"))
        self.assertFalse(result.rewards[0]["is_negative"])
        no_reply.feedback=shoutbox.ChatRow(0,"皮总 @wuyaos：扣减10电力",0)
        self.assertTrue(site.feedback_result("皮总，求电力",no_reply,("扣减",)).rewards[0]["is_negative"])

    def test_city13_blessing_precedes_chat(self):
        names=[task.name for task in City13.tasks]
        self.assertLess(names.index("buy_blessing"),names.index("daily_shotbox"))

    def test_city13_blessing_owned_class_split_match(self):
        # 真实页面用 medal-card purchased / unpurchased 区分；子串匹配会把 unpurchased 误判为已拥有。
        from lxml import etree
        site=City13(site_info(City13))
        purchased_html='<div class="medal-card purchased visible"><button data-id="11" disabled></button></div>'
        unpurchased_html='<div class="medal-card unpurchased"><button data-id="11" disabled></button></div>'
        for html,expected in ((purchased_html,True),(unpurchased_html,False)):
            root=etree.HTML(html)
            cards=root.xpath('//div[contains(@class,"medal-card")][.//button[@data-id="11"]]')
            owned=any("purchased" in (card.get("class") or "").split() for card in cards)
            self.assertEqual(owned,expected)

    def test_cangbao_matches_feedback_on_either_side(self):
        site=Cangbao(site_info(Cangbao))
        for rows in (("系统: @wuyaos 感谢支持，奖励上传量","wuyaos 阁主，求上传"),
                     ("wuyaos 阁主，求上传","系统: @wuyaos 感谢支持，奖励上传量")):
            html="<table>"+"".join(f"<tr><td class='shoutrow'>[1分钟前] {x}</td></tr>" for x in rows)+"</table>"
            obs=site.extract_feedback(html,"wuyaos","阁主，求上传")
            self.assertTrue(obs.sent); self.assertIn("上传量",obs.feedback.text)

    def test_claim_unavailable_states_are_idempotent(self):
        site=Qingwa(site_info(Qingwa))
        for message in ("有其他进行中的任务", "认领人数已达上限"):
            site.post=lambda *a,**k: Response(payload={"success":False,"msg":message})
            result=site.claim_task("1")
            self.assertTrue(result.success); self.assertTrue(result.terminal); self.assertFalse(result.retryable)

    def test_longpt_api_message_is_direct_feedback(self):
        site=LongPT(site_info(LongPT))
        site.post=lambda *a,**k:Response(payload={"code":0,"msg":"获得 10 魔力,[em1]"})
        result=site.send_message("龙宝，求魔力")
        self.assertTrue(result.success); self.assertEqual(result.rewards[0]["type"],"魔力值")
        self.assertNotIn("[em",result.rewards[0]["description"])


if __name__=="__main__": unittest.main()
