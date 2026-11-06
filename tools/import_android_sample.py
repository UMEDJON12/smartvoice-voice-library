"""Verify a sample captured by the supplied exact-model Android test runner.
The repository owner explicitly submits its WAV+metadata; never infer a voice
from an arbitrary recording. No device is required for ordinary catalog refresh.
"""
import pathlib,json,hashlib,wave,array,subprocess,re,shutil,argparse
def accept(metadata,wav,root=pathlib.Path('.')):
 m=json.loads(pathlib.Path(metadata).read_text());wav=pathlib.Path(wav)
 catalog=json.loads((root/'catalog.json').read_text())
 voice=next((v for v in catalog['voices'] if (v['provider'],v['code'],v['contentId'],v['sha256'],v['quality'])==(m.get('provider'),m.get('code'),m.get('contentId'),m.get('archiveSha256'),m.get('quality'))),None)
 if voice is None or m.get('platform')!='android-arm' or m.get('nativeSynthesisVerified') is not True or m.get('androidTested') is not True:raise ValueError('Exact Android model evidence does not match the catalog')
 if wav.stat().st_size>10485760 or hashlib.sha256(wav.read_bytes()).hexdigest()!=m.get('sha256'):raise ValueError('Capture checksum mismatch')
 with wave.open(str(wav)) as w:
  if w.getnchannels()!=1 or w.getsampwidth()!=2 or not 8000<=w.getframerate()<=48000:raise ValueError('Unsupported PCM')
  duration=w.getnframes()/w.getframerate();pcm=array.array('h',w.readframes(w.getnframes()))
  if not .2<=duration<=20 or not any(abs(x)>10 for x in pcm):raise ValueError('Empty or invalid captured audio')
 name='android-'+hashlib.sha256((voice['provider']+'/'+voice['code']+'/'+voice['quality']+'/'+voice['sha256']).encode()).hexdigest()[:24]+'.mp3';target=root/'samples'/name;target.parent.mkdir(exist_ok=True);part=target.with_suffix('.part.mp3')
 try:
  subprocess.run(['ffmpeg','-v','error','-y','-i',str(wav),'-map_metadata','-1','-codec:a','libmp3lame','-q:a','3',str(part)],check=True,capture_output=True,timeout=30)
  if part.stat().st_size>2097152:raise ValueError('Encoded sample too large')
  part.replace(target)
 finally:part.unlink(missing_ok=True)
 index=root/'samples/index.json';data=json.loads(index.read_text()) if index.exists() else {'schemaVersion':1,'samples':[]}
 record={k:m[k] for k in ['provider','code','quality','archiveSha256','platform','nativeSynthesisVerified','androidTested']};record.update(file=name,format='mp3',sha256=hashlib.sha256(target.read_bytes()).hexdigest(),locale=voice.get('synthesisLocale',voice['locale']),audioVerified=True,durationSeconds=duration)
 data['samples']=[r for r in data['samples'] if (r['provider'],r['code'],r['quality'],r['archiveSha256'])!=(record['provider'],record['code'],record['quality'],record['archiveSha256'])]+[record];index.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');return target
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('metadata');p.add_argument('wave');a=p.parse_args();print(accept(a.metadata,a.wave))
