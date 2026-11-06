import unittest,copy,json,pathlib,os,tempfile,subprocess
os.environ.setdefault('GH_TOKEN','test-not-network')
from build_catalog import make,load
class Catalog56Tests(unittest.TestCase):
 def setUp(self):self.report=load('tools/tests/initial-inspection.json',{});self.overrides=load('metadata-overrides.json',{})
 def vocalizers(self):
  r=copy.deepcopy(self.report);r['archives']=r['archives'][:1]
  for name in ['Milena','Yuri']:
   for quality,variant in [('full-vssq5f22','VocalizerEx1'),('premium-high','VocalizerEx2')]:
    a=copy.deepcopy(self.report['archives'][0]);a.update(assetId=100+len(r['archives']),name=name+'-'+quality+'.zip',sha256=('%064x'%len(r['archives'])),draft=False);m=a['importer']['models'][0];m.update(engine='vocalizer-folder',code='rur/'+name.lower()+'/'+quality.replace('full-','full/'),name=name,locale='ru-RU',quality=quality,variant=variant,contentId=('%064x'%len(r['archives'])));r['archives'].append(a)
  return r
 def test_four_distinct_vocalizer_variants(self):
  c,p=make(self.vocalizers(),{}, {'voices':[]});v=[e for e in c['voices'] if e['provider']=='vocalizer-folder'];self.assertEqual(4,len(v));self.assertEqual(4,len({e['id'] for e in v}));self.assertEqual(4,len({e['modelId'] for e in v}));self.assertEqual({'VocalizerEx1','VocalizerEx2'},{e['variant'] for e in v});self.assertFalse(p)
 def test_optional_encoder_failure_keeps_compatible_model(self):
  r=copy.deepcopy(self.report);r['archives'][0]['sampleGeneration']=[{'status':'unavailable','stage':'sample-encoding','nativeAudioProduced':True}];c,p=make(r,self.overrides,{'voices':[]});self.assertEqual(6,len(c['voices']));self.assertFalse(p)
 def test_distinct_zip_equal_model_provenance(self):
  r=copy.deepcopy(self.report);a=copy.deepcopy(r['archives'][0]);a['assetId']=999;a['sha256']='f'*64;a['name']='repacked.zip';r['archives'].append(a);c,p=make(r,self.overrides,{'voices':[]});v=next(v for v in c['voices'] if v.get('alternateArchives'));self.assertFalse(v['alternateArchives'][0]['byteIdentical']);self.assertTrue(v['alternateArchives'][0]['modelContentIdentical']);self.assertEqual(1,v['packageVersion'])
 def test_verification_scope_not_android(self):
  c,p=make(self.report,self.overrides,{'voices':[]});self.assertTrue(all(v['verification']['import'] for v in c['voices']));self.assertFalse(any(v['verification']['androidPlayback'] or v['verification']['screenReader'] for v in c['voices']))
 def test_deleted_models_not_resurrected_from_history(self):
  old,_=make(self.report,self.overrides,{'voices':[]});r=copy.deepcopy(self.report);r['archives']=[];c,_=make(r,self.overrides,old);self.assertEqual([],c['voices'])
 def test_timestamp_stable_for_equal_catalog(self):
  c,_=make(self.report,self.overrides,{'voices':[]});again,_=make(self.report,self.overrides,c);self.assertEqual(c['generatedAt'],again['generatedAt'])
 def test_legacy_bridge_uses_requested_and_never_moves_tag(self):
  s=pathlib.Path('.github/workflows/catalog-release.yml').read_text();self.assertIn('types: [requested, completed]',s);self.assertIn('ref: main',s);self.assertIn('actions: write',s);self.assertNotIn('force',s)
if __name__=='__main__':unittest.main()
