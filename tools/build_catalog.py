"""Build reviewed, structurally compatible catalog records; never publish releases."""
import re,hashlib,json,pathlib,urllib.parse,datetime
import inspect_archives
ROOT=pathlib.Path(".")
PROVIDERS={"microsoft","google","vocalizer-folder"}
def load(p,default):
 try:return json.loads(pathlib.Path(p).read_text())
 except FileNotFoundError:return default
def base_locale(locale):
 parts=locale.split('-');region=next((p for p in parts[1:] if len(p)==2 or len(p)==3 and p.isdigit()),'')
 return parts[0]+('-'+region if region else '')
def attach_sample(entry,locale):
 if entry.get('sampleUrl'):return # Keep an explicitly supplied, already working owner sample.
 index=load('samples/index.json',{'samples':[]})
 for sample in index.get('samples',[]):
  if (sample.get('provider'),sample.get('code'),sample.get('quality'),sample.get('archiveSha256'))!=(entry['provider'],entry['code'],entry['quality'],entry['sha256']):continue
  filename=sample.get('file','')
  if not re.fullmatch(r'[a-z0-9_.-]+\.(mp3|wav|ogg|m4a)',filename):continue
  p=pathlib.Path('samples')/filename
  if not p.is_file() or p.stat().st_size>2097152 or hashlib.sha256(p.read_bytes()).hexdigest()!=sample.get('sha256'):continue
  data=p.read_bytes()[:12]
  if not (data.startswith(b'ID3') or data[:2] in (b'\xff\xf3',b'\xff\xfb',b'\xff\xf2',b'\xff\xfa') or data.startswith(b'RIFF') and data[8:12]==b'WAVE'):continue
  # Old APKs ignore V2 and keep parsing this schema. Only 5.2.55 accepts repo-hosted samples.
  entry['sampleUrlV2']='https://raw.githubusercontent.com/'+inspect_archives.REPO+'/main/samples/'+filename
  entry['sampleSha256']=sample['sha256'];entry['sampleSource']={'platform':sample.get('platform',''),'sdkVersion':sample.get('sdkVersion',''),'androidTested':False}
  break

def make(report,overrides,previous):
 old={v["id"]:v for v in previous.get("voices",[])};selected={};problems=[]
 for archive in report["archives"]:
  if archive.get("errorType") in {"HTTPError","URLError","TimeoutError","ConnectionError"}:raise RuntimeError("Temporary GitHub failure; retaining previous catalog")
  if not archive.get("zipVerified") or "importer" not in archive:
   if any(v.get("filename")==archive["name"] and v.get("releaseTag")==archive["tag"] for v in previous.get("voices",[])):
    raise RuntimeError("Previously cataloged archive failed validation; retaining previous catalog")
   problem={"assetId":archive["assetId"],"name":archive["name"],"reason":archive.get("importerError",archive.get("error","not compatible"))};problem.update(archive.get("importerDiagnostic",{}));problems.append(problem);continue
  override=overrides.get(archive["sha256"],{})
  for m in archive["importer"]["models"]:
   hint=dict(override);hint.update(override.get("models",{}).get(m["code"],{}));provider=m["engine"]
   if provider not in PROVIDERS:problems.append({"assetId":archive["assetId"],"reason":"unknown provider"});continue
   if hint.get("provider",provider)!=provider:problems.append({"assetId":archive["assetId"],"reason":"provider contradicts validated package"});continue
   if m.get("quality") not in (None,"unspecified") and hint.get("quality",m["quality"])!=m["quality"]:problems.append({"assetId":archive["assetId"],"reason":"quality contradicts validated package"});continue
   if m.get("locale") and hint.get("locale",m["locale"])!=m["locale"]:problems.append({"assetId":archive["assetId"],"reason":"locale contradicts validated package"});continue
   locale=m.get("locale") or hint.get("locale");quality=hint.get("quality",m.get("quality","unspecified"))
   if not locale or not quality:problems.append({"assetId":archive["assetId"],"reason":"owner metadata required"});continue
   model=provider+":"+(m["code"].rsplit("/",1)[0] if provider=="vocalizer-folder" else m["code"])
   identity=provider+"-"+hashlib.sha256((model+"/"+quality).encode()).hexdigest()[:24]
   e={"id":identity,"modelId":model,"provider":provider,"code":m["code"],"contentId":m["contentId"],"name":hint.get("name",m["name"]),"locale":base_locale(locale),"synthesisLocale":locale,"gender":hint.get("gender",""),"quality":quality,"variant":quality,"sizeBytes":archive["size"],"unpackedBytes":max(archive["importer"]["unpackedBytes"],sum(f["size"] for f in archive["files"])),"filename":archive["name"],"sha256":archive["sha256"],"downloadUrl":"https://github.com/"+inspect_archives.REPO+"/releases/download/"+urllib.parse.quote(archive["tag"],safe="")+"/"+urllib.parse.quote(archive["name"],safe=""),"packageVersion":1,"minAppCode":m.get("minAppCode",4169),"minSdk":26 if provider in {"microsoft","google"} else 21,"verificationStatus":"verified","verificationScope":"SmartVoice ZIP import and resource structure; native synthesis not tested","published":not archive["draft"],"releaseTag":archive["tag"],"sampleUrl":hint.get("sampleUrl",""),"previousContents":[]}
   failed=next((x for x in archive.get('sampleGeneration',[]) if x.get('code')==m['code'] and x.get('status')=='failed'),None)
   if failed:
    if identity in old:raise RuntimeError('Previously cataloged model failed real synthesis; retaining previous catalog')
    problems.append({'assetId':archive['assetId'],'name':archive['name'],'format':archive['importer'].get('format','Unknown ZIP'),'stage':'native-synthesis','errorClass':'MicrosoftEmbeddedSpeechError','reason':'Microsoft Embedded Speech SDK 1.45 did not produce audio','missingResources':[]});continue
   attach_sample(e,locale)
   # A draft update must not hide an existing published model.
   before=selected.get(identity)
   if before and (before["published"] or not e["published"]):continue
   selected[identity]=e
 for identity,e in selected.items():
  before=old.get(identity)
  if before:
   e["packageVersion"]=before["packageVersion"]+(e["contentId"]!=before["contentId"])
   e["previousContents"]=before.get("previousContents",[])[-31:]
   if e["contentId"]!=before["contentId"]:e["previousContents"].append({"contentId":before["contentId"],"packageVersion":before["packageVersion"]})
 return {"schemaVersion":1,"generatedAt":datetime.datetime.now(datetime.timezone.utc).isoformat(),"voices":sorted(selected.values(),key=lambda v:(v["provider"],v["locale"],v["name"],v["quality"]))},problems
def main():
 inspect_archives.main()
 report=load("checks/archive-inspection.json",{})
 catalog,problems=make(report,load("metadata-overrides.json",{}),load("catalog.json",{"voices":[]}))
 pathlib.Path("catalog.json").write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+"\n")
 pathlib.Path("checks/needs-review.json").write_text(json.dumps({"items":problems},ensure_ascii=False,indent=2)+"\n")
 print("Compatible records:",len(catalog["voices"]),"Pending owner review:",len(problems))
if __name__=="__main__":main()
