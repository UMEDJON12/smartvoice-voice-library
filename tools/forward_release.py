"""Route an immutable legacy release workflow to current main before heavy work.
Only same-repository release runs qualify. No tag is moved or rewritten.
"""
import os,json,urllib.request,urllib.error,pathlib
def main():
 event=json.loads(pathlib.Path(os.environ['GITHUB_EVENT_PATH']).read_text());run=event['workflow_run'];repo=os.environ['GITHUB_REPOSITORY']
 forward=run['event']=='release' and run['head_repository']['full_name']==repo
 if event['action']=='completed' and run['conclusion']!='failure':forward=False
 if event['action']=='requested' and forward:
  # The frozen voices-001 revision is the confirmed historical dispatcher.
  forward=run['head_sha']=='fe31fe01e40a82ae27d0bc4b60081d691b39bb7e'
  if forward:
   request=urllib.request.Request('https://api.github.com/repos/'+repo+'/actions/runs/'+str(int(run['id']))+'/cancel',method='POST',headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
   try:
    with urllib.request.urlopen(request,timeout=20) as response:print('Stopped legacy execution; current main owns the catalog update')
   except urllib.error.HTTPError as error:
    if error.code!=409:raise # already finished: a normal race, not a failed handoff
 with open(os.environ['GITHUB_OUTPUT'],'a') as out:out.write('forward='+str(forward).lower()+'\n')
if __name__=='__main__':main()
