"""按域名与 ControlKind 迁移配置的测试。"""
import importlib.util
from pathlib import Path
import sys, types, unittest
ROOT=Path(__file__).parents[1]; PACKAGE="pttaskflow_migration_test"
def package(n,p): m=types.ModuleType(n); m.__path__=[str(p)]; sys.modules[n]=m
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p); m=importlib.util.module_from_spec(s); sys.modules[n]=m; s.loader.exec_module(m); return m
package(PACKAGE,ROOT); package(f"{PACKAGE}.core",ROOT/"core"); package(f"{PACKAGE}.actions",ROOT/"actions"); package(f"{PACKAGE}.sites",ROOT/"sites")
load(f"{PACKAGE}.core.models",ROOT/"core/models.py"); load(f"{PACKAGE}.core.task_keys",ROOT/"core/task_keys.py")
filter_stale_site_ids=load(f"{PACKAGE}.core.config",ROOT/"core/config.py").filter_stale_site_ids
load(f"{PACKAGE}.actions.checkin",ROOT/"actions/checkin.py"); load(f"{PACKAGE}.actions.longpt",ROOT/"actions/longpt.py"); load(f"{PACKAGE}.actions.medal_site",ROOT/"actions/medal_site.py"); load(f"{PACKAGE}.actions.site_actions",ROOT/"actions/site_actions.py")
load(f"{PACKAGE}.core.task",ROOT/"core/task.py"); load(f"{PACKAGE}.core.shoutbox",ROOT/"core/shoutbox.py")
app=types.ModuleType('app');app.__path__=[];sys.modules['app']=app;db=types.ModuleType('app.db');db.__path__=[];sys.modules['app.db']=db
op=types.ModuleType('app.db.site_oper');op.SiteOper=type('SiteOper',(),{});sys.modules['app.db.site_oper']=op
log=types.ModuleType('app.log');log.logger=types.SimpleNamespace(error=lambda*a,**k:None,warning=lambda*a,**k:None);sys.modules['app.log']=log
load(f"{PACKAGE}.core.site",ROOT/"core/site.py")
LongPT=load(f"{PACKAGE}.sites.longpt",ROOT/"sites/longpt.py").LongPT
MyPT=load(f"{PACKAGE}.sites.mypt",ROOT/"sites/mypt.py").MyPT
Qingwa=load(f"{PACKAGE}.sites.qingwa",ROOT/"sites/qingwa.py").Qingwa
City13=load(f"{PACKAGE}.sites.city13",ROOT/"sites/city13.py").City13
migrate=load(f"{PACKAGE}.core.config_migration",ROOT/"core/config_migration.py").migrate_siteautotask_config

class MigrationTests(unittest.TestCase):
 def setUp(self):
  self.remote=[{'id':'10','domain':'longpt.org'},{'id':'11','domain':'mypt.cc'},{'id':'12','domain':'qingwapt.com'},{'id':'13','domain':'13city.org'}]
  self.local=[{'id':'65','domain':'longpt.org','name':'LongPT','url':'https://longpt.org'},{'id':'91','domain':'mypt.cc','name':'myPT','url':'https://mypt.cc'},{'id':'7','domain':'qingwapt.com','name':'青蛙','url':'https://qingwapt.com'},{'id':'75','domain':'13city.org','name':'13City','url':'https://13city.org'}]
 def test_domain_and_control_kind_migration(self):
  legacy={'enabled':True,'chat_sites':['10','11','12','13'],'claim_10_claim':'8','task_10_claim':True,
          'task_10_daily_lottery':True,'claim_10_daily_shotbox':'龙宝，求上传',
          'claim_11_buy_medal':['8','999'],'qingwa_daily_bonus':True,
          'thirteencity_auto_buy_blessing':True}
  out,summary=migrate(legacy,self.remote,self.local,[LongPT,MyPT,Qingwa,City13])
  self.assertEqual(out['site_ids'],['65','91','7','75'])
  self.assertEqual(out['task_65_claim'],'8'); self.assertEqual(out['task_65_daily_shotbox'],'upload')
  self.assertTrue(out['task_65_daily_lottery']); self.assertEqual(out['task_91_buy_medal'],['8'])
  self.assertTrue(out['task_7_daily_exchange']); self.assertTrue(out['task_75_buy_blessing'])
  self.assertEqual(len(summary['mapped_sites']),4)
 def test_uncertain_select_remains_disabled(self):
  out,summary=migrate({'chat_sites':['10'],'task_10_daily_shotbox':True},self.remote,self.local,[LongPT])
  self.assertNotIn('task_65_daily_shotbox',out); self.assertIn('task_10_daily_shotbox',summary['skipped_controls'])

 def test_filter_stale_site_ids_preserves_valid_and_drops_stale(self):
  self.assertEqual(filter_stale_site_ids([104,109,'157'],{'104','157'}),[104,'157'])
  self.assertEqual(filter_stale_site_ids([],{'104'}),[])

if __name__=='__main__':unittest.main()
