"""Exercise actual detached-HEAD pushes, branch races and failed validation on a local Git remote."""
import json,pathlib,subprocess,tempfile,unittest,os,contextlib,io
from publish_catalog import publish

def cmd(*args,cwd=None):return subprocess.run(list(map(str,args)),cwd=cwd,check=True,capture_output=True,text=True).stdout.strip()
class PublishTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.dir=pathlib.Path(self.temp.name);self.remote=self.dir/'remote.git';self.repo=self.dir/'runner'
  cmd('git','init','--bare',self.remote);cmd('git','clone',self.remote,self.repo)
  cmd('git','checkout','-b','main',cwd=self.repo);cmd('git','config','user.name','Test',cwd=self.repo);cmd('git','config','user.email','test@example.invalid',cwd=self.repo)
  (self.repo/'tools').mkdir();(self.repo/'checks').mkdir();(self.repo/'owner.txt').write_text('old')
  (self.repo/'catalog.json').write_text('{"voices":["last-good"]}')
  (self.repo/'tools/build_catalog.py').write_text('''import pathlib,json,os,subprocess
p=pathlib.Path('.')
if (p/'fail').exists():raise RuntimeError('validation failed')
(p/'catalog.json').write_text(json.dumps({'voices':[ (p/'owner.txt').read_text() ]}))
(p/'checks').mkdir(exist_ok=True)
for name in ['archive-inspection.json','needs-review.json']:(p/'checks'/name).write_text('{}')
race=os.environ.get('SV_TEST_RACE')
if race and not pathlib.Path(race).exists():
 pathlib.Path(race).touch()
 other=pathlib.Path(race).parent/'other'
 subprocess.run(['git','clone',os.environ['SV_TEST_REMOTE'],str(other)],check=True,capture_output=True)
 subprocess.run(['git','checkout','main'],cwd=other,check=True,capture_output=True)
 (other/'owner.txt').write_text('new-owner-value')
 for args in [['add','owner.txt'],['-c','user.name=Owner','-c','user.email=owner@example.invalid','commit','-m','Concurrent owner edit'],['push','origin','main']]:subprocess.run(['git',*args],cwd=other,check=True,capture_output=True)
''')
  cmd('git','add','.',cwd=self.repo);cmd('git','commit','-m','Initial',cwd=self.repo);cmd('git','push','origin','main',cwd=self.repo);cmd('git','checkout','--detach',cwd=self.repo)
 def tearDown(self):self.temp.cleanup()
 def remote_file(self,name):return cmd('git','--git-dir',self.remote,'show','main:'+name)
 def test_detached_push(self):
  publish(self.repo);self.assertEqual(['old'],json.loads(self.remote_file('catalog.json'))['voices']);self.assertEqual('HEAD',cmd('git','symbolic-ref','-q','--short','HEAD',cwd=self.repo) if False else cmd('git','rev-parse','--abbrev-ref','HEAD',cwd=self.repo))
 def test_race_regenerates_not_force_push(self):
  old=dict(os.environ);os.environ.update(SV_TEST_RACE=str(self.dir/'once'),SV_TEST_REMOTE=str(self.remote))
  try:publish(self.repo)
  finally:os.environ.clear();os.environ.update(old)
  self.assertEqual('new-owner-value',self.remote_file('owner.txt'));self.assertEqual(['new-owner-value'],json.loads(self.remote_file('catalog.json'))['voices'])
  self.assertIn('Concurrent owner edit',cmd('git','--git-dir',self.remote,'log','main','--format=%s'))
 def test_validation_failure_keeps_good_catalog(self):
  cmd('git','checkout','main',cwd=self.repo);(self.repo/'fail').touch();cmd('git','add','fail',cwd=self.repo);cmd('git','commit','-m','Bad input',cwd=self.repo);cmd('git','push','origin','main',cwd=self.repo)
  before=cmd('git','--git-dir',self.remote,'rev-parse','main')
  with self.assertRaises(subprocess.CalledProcessError):publish(self.repo)
  self.assertEqual(before,cmd('git','--git-dir',self.remote,'rev-parse','main'));self.assertEqual(['last-good'],json.loads(self.remote_file('catalog.json'))['voices'])
if __name__=='__main__':unittest.main()
