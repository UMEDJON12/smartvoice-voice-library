from validator_diagnostics import diagnostic
import subprocess,os,json,urllib.request,urllib.error,urllib.parse,tempfile,pathlib,zipfile,hashlib,stat,xml.etree.ElementTree as ET
REPO="UMEDJON12/smartvoice-voice-library"
TOKEN=os.environ.get("GH_TOKEN","")
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
     safe={k:v[k] for k in ("engine","code","locale","name","folder","id","type") if k in v}
     report["voices"].append(safe)
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
      if e.tag.lower() in {"voice","langcode","voiceoperatingpoint","voicemodel","BROKERSTRING","language","name","datapackagename"}:fields[e.tag]=(e.text or "")[:240]
     report["headers"].append({"path":p,"metadata":fields})
    except ET.ParseError:report["headers"].append({"path":p,"xml":False})
 return report
def main():
 import copy
 releases=[];out=[];cached={}
 previous=pathlib.Path('checks/archive-inspection.json')
 if previous.exists():cached={r['assetId']:r for r in json.loads(previous.read_text()).get('archives',[])}
 fingerprint=hashlib.sha256(pathlib.Path(__file__).read_bytes()+pathlib.Path('tools/import-validator.jar').read_bytes()).hexdigest()
 renderer=hashlib.sha256(pathlib.Path('tools/generate_samples.py').read_bytes()+pathlib.Path('tools/NativeMicrosoftSample.java').read_bytes()).hexdigest()
 if os.environ.get('SMARTVOICE_RELEASES_FILE'):releases=json.loads(pathlib.Path(os.environ['SMARTVOICE_RELEASES_FILE']).read_text())
 else:
  for page in range(1,101):
   batch=json.load(get('/releases?per_page=100&page='+str(page)));releases.extend(batch)
   if len(batch)<100:break
  else:raise ValueError('Release pagination budget exceeded')
 force=os.environ.get('SMARTVOICE_FULL_RECHECK')=='1'
 with tempfile.TemporaryDirectory() as temp:
  for r in releases:
   # Public catalogs process only published archives, never resurrect a draft.
   if r['draft']:continue
   for a in sorted(r['assets'],key=lambda a:(a['updated_at'],a['id']),reverse=True):
    if not a['name'].lower().endswith(('.zip','.zvoice')):continue
    row={'assetId':a['id'],'releaseId':r['id'],'tag':r['tag_name'],'draft':False,'name':a['name'],'size':a['size'],'assetUpdatedAt':a['updated_at']}
    digest=a.get('digest','');prior=cached.get(a['id']) or next((x for x in cached.values() if digest=='sha256:'+x.get('sha256','')), {})
    reusable=not force and digest=='sha256:'+prior.get('sha256','') and prior.get('size')==a['size'] and prior.get('validationFingerprint')==fingerprint and prior.get('zipVerified') and 'importer' in prior
    if reusable:
     row=copy.deepcopy(prior);row.update(assetId=a['id'],name=a['name'],tag=r['tag_name'],releaseId=r['id'],draft=False,assetUpdatedAt=a['updated_at']);row['inspectionCacheHit']=True
     # Cached samples and recorded unsupported renderers need no ZIP download.
     ready=True
     if pathlib.Path('samples/index.json').exists():
      sample_rows=json.loads(pathlib.Path('samples/index.json').read_text()).get('samples',[])
      for status in row.get('sampleGeneration',[]):
       if status.get('status')=='available':
        record=next((s for s in sample_rows if s.get('file')==status.get('file')),None)
        f=pathlib.Path('samples')/str(status.get('file','invalid'))
        if not record or not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest()!=record.get('sha256'):ready=False
     if row.get('sampleGeneratorFingerprint')==renderer and ready and os.environ.get('SMARTVOICE_SAMPLES')=='1':
      out.append(row);print('Reused verified archive',a['id'],flush=True);continue
     if os.environ.get('SMARTVOICE_SAMPLES')!='1':out.append(row);continue
    try:
     p=pathlib.Path(temp)/str(a['id']);local=pathlib.Path(os.environ.get('SMARTVOICE_ARCHIVE_DIR','/nonexistent'))/str(a['id'])
     h=hashlib.sha256();count=0
     source=local.open('rb') if local.is_file() else get(a['url'],True)
     with source as f,p.open('wb') as target:
      for b in iter(lambda:f.read(1048576),b''):
       count+=len(b)
       if count>a['size']:raise ValueError('Asset size changed')
       h.update(b);target.write(b)
     if count!=a['size'] or digest!='sha256:'+h.hexdigest():raise ValueError('Asset digest mismatch')
     row['sha256']=h.hexdigest()
     if not reusable:row.update(inspect(p));row['zipVerified']=True
     stage=pathlib.Path(temp)/('import-'+str(a['id']))
     try:
      done=subprocess.run(['java','-jar','tools/import-validator.jar',str(p),str(stage)]+(['--keep-stage'] if os.environ.get('SMARTVOICE_SAMPLES')=='1' else []),capture_output=True,text=True,timeout=300)
      if done.returncode==0:
       row['importer']=json.loads(done.stdout);row['detectedFormat']=row['importer'].get('format','Unknown ZIP');row['validationFingerprint']=fingerprint
       row['validation']={'zip':True,'resources':True,'import':True,'androidPlayback':False,'screenReader':False}
       if os.environ.get('SMARTVOICE_SAMPLES')=='1':
        from generate_samples import create
        row['sampleGeneration']=create(row,stage);row['sampleGeneratorFingerprint']=renderer
      else:
       row['importerDiagnostic']=diagnostic(done.stderr,done.returncode);row['importerError']=row['importerDiagnostic']['reason']
     except subprocess.TimeoutExpired:
      row['importerDiagnostic']=diagnostic('{"code":"validator-timeout","stage":"validator-execution"}',-1);row['importerError']=row['importerDiagnostic']['reason']
     except Exception as e:
      # Preview infrastructure is optional, never relabel a validated import.
      if 'importer' in row:row['sampleGeneration']=[{'status':'unavailable','stage':'sample-infrastructure','errorClass':type(e).__name__}]
      else:row['importerDiagnostic']=diagnostic('',-1);row['importerError']=row['importerDiagnostic']['reason']
     finally:
      import shutil
      shutil.rmtree(stage,ignore_errors=True);p.unlink(missing_ok=True)
    except Exception as e:
     row['errorType']=type(e).__name__;row['error']='Ошибка сети GitHub' if isinstance(e,(urllib.error.URLError,TimeoutError,ConnectionError)) else 'Архив повреждён или не прошёл проверку безопасности'
     row['importerDiagnostic']={'format':'Invalid ZIP','stage':'archive-security','errorClass':type(e).__name__,'reason':row['error'],'missingResources':[]}
    cached[a['id']]=row
    out.append(row);print('Inspected',a['id'],'ok' if row.get('zipVerified') else row.get('error'),flush=True)
 pathlib.Path('checks').mkdir(exist_ok=True);pending=pathlib.Path('checks/archive-inspection.part');pending.write_text(json.dumps({'schemaVersion':1,'archives':out},ensure_ascii=False,indent=2)+'\n');pending.replace(previous)
if __name__=='__main__':main()
