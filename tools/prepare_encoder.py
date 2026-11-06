"""Reuse a working MP3 encoder or unpack one pinned static binary. No apt graph."""
import pathlib,shutil,subprocess,urllib.request,hashlib,zipfile,os,tempfile
URL='https://files.pythonhosted.org/packages/a0/2d/43c8522a2038e9d0e7dbdf3a61195ecc31ca576fb1527a528c877e87d973/imageio_ffmpeg-0.6.0-py3-none-manylinux2014_x86_64.whl'
SHA='c7e46fcec401dd990405049d2e2f475e2b397779df2519b544b8aab515195282'
def usable(path):
 try:return subprocess.run([str(path),'-hide_banner','-encoders'],capture_output=True,timeout=10).stdout.find(b'libmp3lame')>=0
 except (OSError,subprocess.TimeoutExpired):return False
def main():
 cache=pathlib.Path.home()/'.cache/smartvoice/encoder-0.6.0';cache.mkdir(parents=True,exist_ok=True);target=cache/'ffmpeg'
 installed=shutil.which('ffmpeg')
 if installed and usable(installed):print('Using installed encoder');return
 if not target.exists() or not usable(target):
  with tempfile.TemporaryDirectory() as temp:
   p=pathlib.Path(temp)/'encoder.whl';h=hashlib.sha256();size=0
   with urllib.request.urlopen(URL,timeout=45) as source,p.open('wb') as out:
    for b in iter(lambda:source.read(1048576),b''):
     size+=len(b)
     if size>31000000:raise ValueError('Encoder download budget exceeded')
     h.update(b);out.write(b)
   if h.hexdigest()!=SHA:raise ValueError('Encoder checksum mismatch')
   with zipfile.ZipFile(p) as z:
    names=[n for n in z.namelist() if n.startswith('imageio_ffmpeg/binaries/ffmpeg-linux')]
    if len(names)!=1:raise ValueError('Unexpected encoder wheel')
    target.write_bytes(z.read(names[0]));target.chmod(0o755)
    for n in z.namelist():
     if 'LICENSE' in n:(cache/pathlib.PurePosixPath(n).name).write_bytes(z.read(n))
  if not usable(target):raise RuntimeError('Encoder cannot encode MP3')
 if os.environ.get('GITHUB_PATH'):
  with open(os.environ['GITHUB_PATH'],'a') as f:f.write(str(cache)+'\n')
 print('Using pinned cached standalone encoder')
if __name__=='__main__':main()
