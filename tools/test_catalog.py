import os,copy,unittest
os.environ.setdefault("GH_TOKEN","test-not-used-for-network")
from build_catalog import make,load
class CatalogTests(unittest.TestCase):
 def setUp(self):
  self.report=load("tools/tests/initial-inspection.json",{});self.overrides=load("metadata-overrides.json",{})
 def test_six(self):
  c,p=make(self.report,self.overrides,{"voices":[]});self.assertFalse(p);self.assertEqual(6,len(c["voices"]));self.assertEqual(4,sum(v["provider"]=="microsoft" for v in c["voices"]));self.assertEqual(2,sum(v["provider"]=="vocalizer-folder" for v in c["voices"]));self.assertTrue(all(not v["published"] for v in c["voices"]));self.assertTrue(all("/untagged-" not in v["downloadUrl"] for v in c["voices"]));self.assertEqual({"ar-SA","fa-IR","uz-UZ","tr-TR","zh-CN"},{v["locale"] for v in c["voices"]})
 def test_publication_and_rename(self):
  c,_=make(self.report,self.overrides,{"voices":[]});r=copy.deepcopy(self.report)
  for a in r["archives"]:a["draft"]=False
  p,_=make(r,self.overrides,c);self.assertTrue(all(v["published"] for v in p["voices"]));self.assertEqual([v["id"] for v in c["voices"]],[v["id"] for v in p["voices"]])
  a=copy.deepcopy(r["archives"][0]);a["name"]="renamed.zip";r["archives"].insert(0,a);d,_=make(r,self.overrides,p);self.assertEqual(6,len(d["voices"]))
 def test_new_language_provider_and_quality(self):
  r=copy.deepcopy(self.report);a=copy.deepcopy(r["archives"][0]);a["name"]="new.zip";a["sha256"]="a"*64;m=a["importer"]["models"][0];m.update(engine="google",code="new-model",name="New Voice",locale="de-DE",contentId="a"*16,quality="high");r["archives"].insert(0,a)
  c,_=make(r,{},{"voices":[]});self.assertTrue(any(v["provider"]=="google" and v["locale"]=="de-DE" for v in c["voices"]));m["engine"]="unknown";c,p=make(r,{},{"voices":[]});self.assertEqual(6,len(c["voices"]));self.assertTrue(p)
 def test_version_and_override(self):
  c,_=make(self.report,self.overrides,{"voices":[]});r=copy.deepcopy(self.report);r["archives"][0]["importer"]["models"][0]["contentId"]="e"*16
  newer,_=make(r,self.overrides,c);changed=[v for v in newer["voices"] if v["contentId"]=="e"*16][0];self.assertEqual(2,changed["packageVersion"]);self.assertEqual(1,len(changed["previousContents"]));again,_=make(r,self.overrides,newer);self.assertEqual(2,next(v for v in again["voices"] if v["id"]==changed["id"])["packageVersion"])
  bad=copy.deepcopy(self.overrides);bad[r["archives"][0]["sha256"]]={"provider":"google"};_,p=make(r,bad,c);self.assertTrue(p)
 def test_deleted_asset_disappears(self):
  before,_=make(self.report,self.overrides,{"voices":[]});r=copy.deepcopy(self.report);removed=r['archives'].pop();c,_=make(r,self.overrides,before)
  self.assertEqual(5,len(c['voices']));self.assertFalse(any(v['sha256']==removed['sha256'] for v in c['voices']))
 def test_bad_new_archive_and_failed_existing(self):
  before,_=make(self.report,self.overrides,{"voices":[]});r=copy.deepcopy(self.report)
  bad={'assetId':999,'name':'bad.zip','tag':'voices-test','error':'Invalid ZIP'};r['archives'].append(bad)
  c,p=make(r,self.overrides,before);self.assertEqual(6,len(c['voices']));self.assertEqual(1,len(p))
  old=r['archives'][0];old.pop('importer');old['importerError']='failed validation'
  with self.assertRaises(RuntimeError):make(r,self.overrides,before)
 def test_transient_failure_keeps_catalog(self):
  r=copy.deepcopy(self.report);r['archives'][0]['errorType']='URLError'
  with self.assertRaises(RuntimeError):make(r,self.overrides,{"voices":[]})
if __name__=="__main__":unittest.main()
