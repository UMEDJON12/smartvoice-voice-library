"""Render actual Microsoft packages with the SAME 1.45 SDK family as SmartVoice.
No model parameters/keys are sent to a service or written to public diagnostics.
"""
import pathlib,hashlib,json,urllib.request,tempfile,subprocess,os,wave,array,re,shutil
SDK_VERSION='1.45.0'
SDK_SHA='a0f3d262b3be897a5c597732c44e8e3b9e74f5bd47683f1e58d013a98397eefa'
SDK_URL='https://repo.maven.apache.org/maven2/com/microsoft/cognitiveservices/speech/client-sdk-embedded/1.45.0/client-sdk-embedded-1.45.0.jar'
def ensure_sdk():
 cache=pathlib.Path(tempfile.gettempdir())/'smartvoice-host-speech-1.45';cache.mkdir(exist_ok=True);sdk=cache/'sdk.jar'
 if not sdk.exists() or hashlib.sha256(sdk.read_bytes()).hexdigest()!=SDK_SHA:
  part=cache/'sdk.part';h=hashlib.sha256();total=0
  with urllib.request.urlopen(SDK_URL,timeout=120) as source,part.open('wb') as target:
   for chunk in iter(lambda:source.read(1048576),b''):
    total+=len(chunk)
    if total>100*1024*1024:raise ValueError('SDK download budget exceeded')
    target.write(chunk);h.update(chunk)
  if h.hexdigest()!=SDK_SHA:part.unlink();raise ValueError('SDK checksum mismatch')
  part.replace(sdk)
 source=pathlib.Path('tools/NativeMicrosoftSample.java');validator=pathlib.Path('tools/import-validator.jar')
 fingerprint=hashlib.sha256(source.read_bytes()+validator.read_bytes()).hexdigest()[:16];classes=cache/fingerprint
 if not (classes/'NativeMicrosoftSample.class').exists():
  classes.mkdir(exist_ok=True);result=subprocess.run(['java','com.sun.tools.javac.Main','-source','8','-target','8','-encoding','UTF-8','-cp',str(sdk)+os.pathsep+str(validator.resolve()),'-d',str(classes),str(source)],capture_output=True,timeout=120)
  if result.returncode:raise RuntimeError('Sample renderer compilation failed')
 return sdk,classes

def existing(rows,archive,model):
 for sample in rows:
  if (sample.get('provider'),sample.get('code'),sample.get('quality'),sample.get('archiveSha256'))!=(model['engine'],model['code'],model.get('quality','unspecified'),archive['sha256']):continue
  name=sample.get('file','')
  if not re.fullmatch(r'[a-z0-9_.-]+\.mp3',name):continue
  p=pathlib.Path('samples')/name
  if p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==sample.get('sha256'):return sample
 return None

def create(archive,stage):
 samples=pathlib.Path('samples');samples.mkdir(exist_ok=True);index=samples/'index.json'
 rows=json.loads(index.read_text()).get('samples',[]) if index.exists() else []
 statuses=[];sdk=None
 for original in archive['importer']['models']:
  model=dict(original)
  overrides=json.loads(pathlib.Path('metadata-overrides.json').read_text()) if pathlib.Path('metadata-overrides.json').exists() else {}
  hint=dict(overrides.get(archive['sha256'],{}));hint.update(hint.get('models',{}).get(model['code'],{}))
  if model.get('quality','unspecified')=='unspecified' and hint.get('quality'):model['quality']=hint['quality']
  saved=existing(rows,archive,model)
  if saved:statuses.append({'code':model['code'],'status':'available','file':saved['file']});continue
  if model['engine']!='microsoft':
   statuses.append({'code':model['code'],'status':'unavailable','stage':'renderer-availability','errorCode':'AndroidNativeRuntimeRequired','reason':'This exact local model requires the bundled Android ARM native runtime; no compatible host renderer is available. Capture through SmartVoice on Android; never substitute a cloud or different voice.'});continue
  try:
   if sdk is None:sdk,classes=ensure_sdk()
  except Exception:
   statuses.append({'code':model['code'],'status':'unavailable','reason':'Host sample renderer unavailable'});continue
  identity=hashlib.sha256(('microsoft/'+model['code']+'/'+model.get('quality','unspecified')+'/'+archive['sha256']).encode()).hexdigest()[:24];target=samples/('microsoft-'+identity+'.mp3')
  with tempfile.TemporaryDirectory(prefix='sv-sample-') as tmp:
   wav=pathlib.Path(tmp)/'sample.wav'
   phase='renderer-execution'
   native_audio=False
   try:
    clean_env={k:v for k,v in os.environ.items() if not re.search(r'(?i)token|secret|password|credential',k)}
    done=subprocess.run(['java','-Xmx512m','-cp',os.pathsep.join(map(str,[classes,pathlib.Path('tools/import-validator.jar').resolve(),sdk])),'NativeMicrosoftSample',str(stage),model['code'],str(wav)],capture_output=True,text=True,timeout=90,env=clean_env)
    phase='renderer-output'
    result=json.loads(done.stdout.strip().splitlines()[-1]) if done.returncode==0 else {'success':False,'errorCode':'RendererProcessError'}
    if not result.get('success'):
     statuses.append({'code':model['code'],'status':'unavailable' if result.get('unavailable') else 'failed','errorCode':result.get('errorCode','No reviewed sample text')});continue
    native_audio=True;phase='wave-validation'
    with wave.open(str(wav)) as stream:
     assert stream.getnchannels()==1 and stream.getsampwidth()==2 and stream.getframerate()==24000
     duration=stream.getnframes()/24000;pcm=array.array('h',stream.readframes(stream.getnframes()))
     if not .2<=duration<=20 or not any(abs(x)>10 for x in pcm):raise ValueError('Empty or invalid sample')
    encoded=pathlib.Path(tmp)/'sample.mp3'
    phase='sample-encoding'
    ff=subprocess.run(['ffmpeg','-v','error','-y','-i',str(wav),'-map_metadata','-1','-codec:a','libmp3lame','-q:a','3',str(encoded)],capture_output=True,timeout=30)
    if ff.returncode or not encoded.exists() or encoded.stat().st_size>2097152:raise ValueError('Sample encoding failed')
    phase='sample-saving'
    pending=target.with_suffix('.part')
    try:shutil.copyfile(encoded,pending);pending.replace(target)
    finally:pending.unlink(missing_ok=True)
    record={'provider':'microsoft','code':model['code'],'locale':result['locale'],'quality':model.get('quality','unspecified'),'archiveSha256':archive['sha256'],'file':target.name,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'platform':'linux-x64','sdkVersion':SDK_VERSION,'sampleText':result['sampleText'],'durationSeconds':duration,'androidTested':False,'format':'mp3','nativeSynthesisVerified':True,'audioVerified':True}
    rows=[r for r in rows if not (r.get('code')==record['code'] and r.get('archiveSha256')==record['archiveSha256'] and r.get('quality')==record['quality'])];rows.append(record)
    statuses.append({'code':model['code'],'status':'available','file':target.name})
   except subprocess.TimeoutExpired:statuses.append({'code':model['code'],'status':'unavailable' if native_audio else 'failed','stage':phase,'nativeAudioProduced':native_audio,'errorCode':'EncodingTimeout' if native_audio else 'SynthesisTimeout'})
   except Exception as error:statuses.append({'code':model['code'],'status':'unavailable','reason':'Sample could not be saved','stage':phase,'errorClass':type(error).__name__,'nativeAudioProduced':native_audio})
 index.write_text(json.dumps({'schemaVersion':1,'samples':sorted(rows,key=lambda r:(r['code'],r['archiveSha256'],r['quality']))},ensure_ascii=False,indent=2)+'\n')
 return statuses
