"""Build reviewed, structurally compatible catalog records; never publish releases."""
import hashlib,json,pathlib,urllib.parse,datetime
import inspect_archives
ROOT=pathlib.Path(".")
PROVIDERS={"microsoft","google","vocalizer-folder"}
def load(p,default):
 try:return json.loads(pathlib.Path(p).read_text())
 except FileNotFoundError:return default
def make(report,overrides,previous):
 old={v["id"]:v for v in previous.get("voices",[])};selected={};problems=[]
 for archive in report["archives"]:
  if archive.get("errorType") in {"HTTPError","URLError","TimeoutError","ConnectionError"}:raise RuntimeError("Temporary GitHub failure; retaining previous catalog")
  if not archive.get("zipVerified") or "importer" not in archive:
   problems.append({"assetId":archive["assetId"],"reason":archive.get("importerError",archive.get("error","not compatible"))});continue
  override=overrides.get(archive["sha256"],{})
  for m in archive["importer"]["models"]:
   provider=m["engine"]
   if provider not in PROVIDERS:problems.append({"assetId":archive["assetId"],"reason":"unknown provider"});continue
   if override.get("provider",provider)!=provider:problems.append({"assetId":archive["assetId"],"reason":"provider contradicts validated package"});continue
   locale=m.get("locale",override.get("locale"));quality=override.get("quality",m.get("quality","unspecified"))
   if not locale or not quality:problems.append({"assetId":archive["assetId"],"reason":"owner metadata required"});continue
   model=provider+":"+(m["code"].rsplit("/",1)[0] if provider=="vocalizer-folder" else m["code"])
   identity=provider+"-"+hashlib.sha256((model+"/"+quality).encode()).hexdigest()[:24]
   e={"id":identity,"modelId":model,"provider":provider,"code":m["code"],"contentId":m["contentId"],"name":override.get("name",m["name"]),"locale":locale,"gender":override.get("gender",""),"quality":quality,"variant":quality,"sizeBytes":archive["size"],"unpackedBytes":archive["importer"]["unpackedBytes"],"filename":archive["name"],"sha256":archive["sha256"],"downloadUrl":"https://github.com/"+inspect_archives.REPO+"/releases/download/"+urllib.parse.quote(archive["tag"],safe="")+"/"+urllib.parse.quote(archive["name"],safe=""),"packageVersion":1,"minAppCode":4169,"minSdk":26 if provider in {"microsoft","google"} else 21,"verificationStatus":"verified","verificationScope":"SmartVoice ZIP import and resource structure; native synthesis not tested","published":not archive["draft"],"releaseTag":archive["tag"],"sampleUrl":override.get("sampleUrl",""),"previousContents":[]}
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
