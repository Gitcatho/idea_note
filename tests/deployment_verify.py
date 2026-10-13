"""Read-only post-deploy verification on Pi; never read password hashes or records."""
import json
from pathlib import Path
import subprocess

def output(*command):
    return subprocess.check_output(command,text=True)

root=Path('/home/jinho/News_idea-web')
before=json.loads((root/'tailscale-before.json').read_text())
after=json.loads(output('tailscale','serve','status','--json'))
assert after['TCP']['443']==before['TCP']['443']
host='pi-home.tail5eceb8.ts.net'
assert after['Web'][host+':443']==before['Web'][host+':443']
assert after['AllowFunnel'][host+':443']==before['AllowFunnel'][host+':443']
assert after['Web'][host+':8443']['Handlers']['/']['Proxy']=='http://127.0.0.1:4310'
assert after['AllowFunnel'][host+':8443'] is True
previous=(root/'services-before.txt').read_text().splitlines()
running=output('docker','ps','--format','{{.Names}} {{.ID}} {{.Image}}').splitlines()
assert all(row in running for row in previous), 'A previous service changed'
assert not any(row.startswith('news-idea-qa ') for row in running)
assert 'news-idea-qa-data' not in output('docker','volume','ls','--format','{{.Name}}').splitlines()
container=json.loads(output('docker','inspect','news-idea-web-1'))[0]
assert container['State']['Health']['Status']=='healthy'
assert container['HostConfig']['RestartPolicy']['Name']=='unless-stopped'
assert container['HostConfig']['ReadonlyRootfs'] is True
sql='''import sqlite3,json,pathlib
counts={}
for file,table in [('news-idea.sqlite3','records'),('auth.sqlite3','admin'),('auth.sqlite3','sessions')]:
 with sqlite3.connect('file:/data/'+file+'?mode=ro',uri=True) as db:
  counts[table]=db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]
counts['backups']=len(list(pathlib.Path('/data/backups').glob('backup-*.json')))
print(json.dumps(counts))'''
counts=json.loads(output('docker','exec','news-idea-web-1','python','-c',sql))
assert counts['records']==counts['admin']==counts['sessions']==0
assert counts['backups']>=1
image=json.loads(output('docker','image','inspect',container['Image']))[0]
assert image['Architecture']=='arm64'
result={'url':'https://'+host+':8443','container':'news-idea-web-1','image':container['Image'],'architecture':image['Architecture'],'health':'healthy','previous_services_unchanged':True,'funnel_443_unchanged':True,'funnel_8443_target':'127.0.0.1:4310','qa_removed':True,'production_counts':counts,'password_configured':False}
(root/'deployment-status.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
