import subprocess,os,json,urllib.request,urllib.parse,tempfile,pathlib,zipfile,hashlib,stat,xml.etree.ElementTree as ET
REPO="UMEDJON12/smartvoice-voice-library"
TOKEN=os.environ["GH_TOKEN"]
class Redirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  u=urllib.parse.urlsplit(newurl)
  if u.scheme!="https" or u.hostname not in {"api.github.com","release-assets.githubusercontent.com","objects.githubusercontent.com","github.com","github-releases.githubusercontent.com"}:raise ValueError("Untrusted redirect")
  r=super().redirect_request(req,fp,code,msg,headers,newurl)
  if u.hostname!="api.github.com":r.remove_header("Authorization")
  return r
opener=urllib.request.build_opener(Redirect())
def get(path,binary=False):
 url=path if path.startswith("https://") else "https://api.github.com/repos/"+REPO+path
 assert urllib.parse.urlsplit(url).hostname=="api.github.com"
 return opener.open(urllib.request.Request(url,headers={"Authorization":"Bearer "+TOKEN,"Accept":"application/octet-stream" if binary else "application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"}),timeout=120)
def inspect(path):
 report={"files":[],"voices":[],"tokens":[],"headers":[]}
 with zipfile.ZipFile(path) as z:
  seen=set();total=0
  for i,e in enumerate(z.infolist()):
   p=e.filename.replace("\\","/")
   if i>=10000 or p.startswith("/") or ":" in p or any(x in ("..",".") for x in p.split("/")) or "\0" in p or p.casefold() in seen or e.flag_bits&1 or stat.S_ISLNK(e.external_attr>>16):raise ValueError("Unsafe ZIP")
   seen.add(p.casefold());total+=e.file_size
   if total>8*1024**3:raise ValueError("Expansion budget exceeded")
   if e.is_dir():continue
   sha=hashlib.sha256();small=bytearray();count=0
   with z.open(e) as stream:
    for b in iter(lambda:stream.read(65536),b""):
     count+=len(b);sha.update(b)
     if e.file_size<=1048576:small.extend(b)
   if count!=e.file_size:raise ValueError("ZIP size mismatch")
   report["files"].append({"path":p,"size":count,"sha256":sha.hexdigest()})
   leaf=pathlib.PurePosixPath(p).name
   if leaf in ("smartvoice-pack.json","multivoice.json"):
    j=json.loads(small.decode("utf-8-sig"))
    for v in j.get("voices",[]):
     safe={k:v[k] for k in ("engine","code","locale","name","folder","id","type","options") if k in v}
     safe["paramVoice"]=str(v.get("param","")).split("\n")[0][:160];report["voices"].append(safe)
   elif leaf=="config.yaml":
    # Only known public metadata keys; license param intentionally omitted.
    report["yaml"]=[line.strip() for line in small.decode("utf-8-sig").splitlines() if line.strip().split(":")[0].strip("- ") in {"code","locale","name","engine","folder","microsoft","google","type"}]
   elif leaf=="Tokens.xml":
    tree=ET.fromstring(small)
    strings=[{k:e.attrib.get(k,"") for k in ("name","value")} for e in tree.iter() if e.tag in ("String","string") and e.attrib.get("name") in {"VoiceName","Name","Locale","Language","Gender","VoicePath","LangDataPath"}]
    report["tokens"].append({"path":p,"attributes":strings})
   elif leaf.lower().endswith(".hdr") and small:
    try:
     tree=ET.fromstring(small);fields={}
     for e in tree.iter():
      if e.tag.lower() in {"voice","langcode","voiceoperatingpoint","language","name","datapackagename"}:fields[e.tag]=(e.text or "")[:240]
     report["headers"].append({"path":p,"metadata":fields})
    except ET.ParseError:report["headers"].append({"path":p,"xml":False})
 return report
def main():
 releases=json.load(get("/releases?per_page=100"));out=[]
 with tempfile.TemporaryDirectory() as temp:
  for r in releases:
   for a in r["assets"]:
    if not a["name"].lower().endswith((".zip",".zvoice")):continue
    row={"assetId":a["id"],"releaseId":r["id"],"tag":r["tag_name"],"draft":r["draft"],"name":a["name"],"size":a["size"]}
    try:
     p=pathlib.Path(temp)/str(a["id"]);h=hashlib.sha256();count=0
     with get(a["url"],True) as f,p.open("wb") as target:
      for b in iter(lambda:f.read(65536),b""):
       count+=len(b)
       if count>a["size"]:raise ValueError("Asset size changed")
       h.update(b);target.write(b)
     if count!=a["size"] or a.get("digest")!="sha256:"+h.hexdigest():raise ValueError("Asset digest mismatch")
     row["sha256"]=h.hexdigest();row.update(inspect(p));row["zipVerified"]=True
     try:
      done=subprocess.run(["java","-jar","tools/import-validator.jar",str(p),str(pathlib.Path(temp)/("import-"+str(a["id"])))],capture_output=True,text=True,timeout=180,check=True)
      row["importer"]=json.loads(done.stdout)
     except Exception as failure:row["importerError"]=str(failure)[:300]
    except Exception as e:row["error"]=str(e)[:300];row["errorType"]=type(e).__name__
    out.append(row);print("Inspected",a["id"],"ok" if row.get("zipVerified") else row.get("error"))
 pathlib.Path("checks").mkdir(exist_ok=True);pathlib.Path("checks/archive-inspection.json").write_text(json.dumps({"schemaVersion":1,"archives":out},ensure_ascii=False,indent=2)+"\n")
if __name__=="__main__":main()
