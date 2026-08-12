"""织梦独立 date 调度契约测试。"""
import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
import sys, types, unittest
ROOT=Path(__file__).parents[1]; P='pttaskflow_scheduler_test'
def pkg(n,p):m=types.ModuleType(n);m.__path__=[str(p)];sys.modules[n]=m
def load(n,p):s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
pkg(P,ROOT);pkg(P+'.core',ROOT/'core')
app=types.ModuleType('app');app.__path__=[];sys.modules['app']=app
core=types.ModuleType('app.core');core.__path__=[];sys.modules['app.core']=core
cfg=types.ModuleType('app.core.config');cfg.settings=types.SimpleNamespace(TZ='Asia/Shanghai');sys.modules['app.core.config']=cfg
log=types.ModuleType('app.log');log.logger=types.SimpleNamespace(error=lambda*a,**k:None,warning=lambda*a,**k:None);sys.modules['app.log']=log
aps=types.ModuleType('apscheduler');aps.__path__=[];sys.modules['apscheduler']=aps
triggers=types.ModuleType('apscheduler.triggers');triggers.__path__=[];sys.modules['apscheduler.triggers']=triggers
cron=types.ModuleType('apscheduler.triggers.cron')
cron.CronTrigger=type('CronTrigger',(),{'from_crontab':classmethod(lambda cls,*a,**k:('cron',a,k))})
sys.modules['apscheduler.triggers.cron']=cron
date=types.ModuleType('apscheduler.triggers.date')
date.DateTrigger=type('DateTrigger',(),{'__init__':lambda self,run_date:setattr(self,'run_date',run_date)})
sys.modules['apscheduler.triggers.date']=date
scheduler=load(P+'.core.scheduler',ROOT/'core/scheduler.py')

class Plugin:
 def __init__(self,mail='',last=''):
  self.config=types.SimpleNamespace(
   enabled=True,cron='4 0 * * *',zm_mail_time=mail,last_zm_execution_time=last)
 def runtime_sites(self): return [types.SimpleNamespace(domain='zmpt.cc')]
 def run_scheduled(self): pass
 def run_zm(self): pass

class SchedulerTests(unittest.TestCase):
 def test_zm_service_registered_separately(self):
  services=scheduler.TaskScheduler(Plugin()).services()
  self.assertEqual([x['id'] for x in services],['pttaskflow_main','pttaskflow_zm'])
 def test_missing_mail_time_runs_soon(self):
  before=datetime.now(); run=scheduler.TaskScheduler(Plugin())._next_zm_time()
  self.assertLessEqual((run-before).total_seconds(),5)
 def test_expired_mail_time_runs_soon(self):
  old=(datetime.now()-timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')
  run=scheduler.TaskScheduler(Plugin(old))._next_zm_time()
  self.assertLessEqual((run-datetime.now()).total_seconds(),5)
 def test_expired_mail_time_uses_recent_execution_fallback(self):
  old=(datetime.now()-timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')
  last=datetime.now().replace(microsecond=0)-timedelta(minutes=5)
  run=scheduler.TaskScheduler(Plugin(old,last.isoformat()))._next_zm_time()
  self.assertAlmostEqual((run-last).total_seconds(),24*3600,delta=1)
 def test_future_mail_time_uses_24_hours(self):
  value=datetime.now().replace(microsecond=0)-timedelta(hours=23)
  run=scheduler.TaskScheduler(Plugin(value.strftime('%Y-%m-%d %H:%M:%S')))._next_zm_time()
  self.assertAlmostEqual((run-value).total_seconds(),24*3600,delta=1)

if __name__=='__main__':unittest.main()
