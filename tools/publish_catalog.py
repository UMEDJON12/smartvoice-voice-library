"""Commit generated files to latest main, retrying races without force-push or JSON merges."""
import pathlib,subprocess,tempfile,sys,json,urllib.parse
FILES=['catalog.json','checks/archive-inspection.json','checks/needs-review.json','samples']
def git(root,*args,check=True):
 return subprocess.run(['git','-C',str(root),*args],check=check,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
def publish(root,attempts=3):
 root=pathlib.Path(root).resolve()
 for attempt in range(attempts):
  git(root,'fetch','origin','main')
  base=git(root,'rev-parse','origin/main').stdout.strip()
  with tempfile.TemporaryDirectory(prefix='smartvoice-catalog-') as temp:
   work=pathlib.Path(temp)/'main'
   git(root,'worktree','add','--detach',str(work),base)
   try:
    subprocess.run([sys.executable,'tools/build_catalog.py'],cwd=work,check=True)
    git(work,'add','--',*FILES)
    catalog=json.loads((work/'catalog.json').read_text())
    for voice in catalog.get('voices',[]):
     url=voice.get('sampleUrlV2')
     if url:
      filename=pathlib.PurePosixPath(urllib.parse.urlsplit(url).path).name
      git(work,'ls-files','--error-unmatch','--','samples/'+filename)

    if git(work,'diff','--cached','--quiet',check=False).returncode==0:
     print('Catalog already current on main');return
    git(work,'-c','user.name=github-actions[bot]','-c','user.email=41898282+github-actions[bot]@users.noreply.github.com','commit','-m','Update verified SmartVoice voice catalog')
    pushed=git(work,'push','origin','HEAD:refs/heads/main',check=False)
    if pushed.returncode==0:
     print('Verified catalog saved to main:',git(work,'rev-parse','HEAD').stdout.strip());return
    # A concurrent main update requires regeneration using its new tools,
    # overrides and catalog history. Never force-push generated JSON.
    git(root,'fetch','origin','main')
    latest=git(root,'rev-parse','origin/main').stdout.strip()
    if latest==base:raise RuntimeError('Could not push main; history left unchanged: '+pushed.stderr)
    print('Main changed concurrently; regenerating from its latest commit')
   finally:git(root,'worktree','remove','--force',str(work))
 raise RuntimeError('Main kept changing; no history overwritten. Retry the workflow.')
if __name__=='__main__':publish(pathlib.Path(__file__).resolve().parent.parent)
