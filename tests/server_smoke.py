"""Run on Pi against ONLY the disposable news-idea-qa container/volume.

Passwords and cookies stay in process memory, never printed or written.
"""
import json
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request

CONTAINER = 'news-idea-qa'
ORIGIN = 'https://pi-home.tail5eceb8.ts.net:8443'
endpoint = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:4311'
cookie = csrf = ''
password = secrets.token_urlsafe(32)
seed = '''import sys
from webapp import Auth
from store import Store
s=Store('/data')
with s.connection() as db: db.execute('DELETE FROM records')
Auth('/data').set_password(sys.stdin.read())'''
subprocess.run(['docker','exec','-i',CONTAINER,'python','-c',seed], input=password, text=True, check=True, capture_output=True)
opener = urllib.request.build_opener(urllib.request.HTTPHandler, urllib.request.HTTPSHandler)

def call(path, data=None, authenticated=False, origin=ORIGIN, token=None):
    headers = {'Host':ORIGIN.split('//')[1], 'Origin':origin}
    if authenticated:
        headers.update({'Cookie':cookie,'X-CSRF-Token':csrf if token is None else token})
    body = None if data is None else json.dumps(data).encode()
    if body is not None:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(endpoint+path, data=body, headers=headers)
    try:
        response = opener.open(req, timeout=15)
    except urllib.error.HTTPError as error:
        response = error
    raw = response.read()
    return response.status, response.headers, json.loads(raw) if 'application/json' in response.headers.get('Content-Type','') else raw

def ready():
    for _ in range(100):
        try:
            if call('/healthz')[0] == 200:
                return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(.3)
    raise AssertionError('QA health did not recover')

ready()
checks=[]
for action in ('list','save','trash','restore','export','import','backup','session'):
    assert call('/api/'+action,{})[0] == 401, action
checks.append('all anonymous data APIs blocked')
assert call('/login',{'username':'admin','password':'incorrect'})[0] == 401
status,headers,body=call('/login',{'username':'admin','password':password})
assert status == 200
cookie=headers['Set-Cookie'].split(';',1)[0]
assert all(flag in headers['Set-Cookie'] for flag in ('Secure','HttpOnly','SameSite=Strict'))
csrf=call('/api/session',authenticated=True)[2]['data']['csrf']
checks.append('login and secure cookies')
assert call('/api/backup',{},True,origin='https://invalid.example')[0] == 403
assert call('/api/backup',{},True,token='invalid')[0] == 403
checks.append('origin and CSRF rejection')
for path in ('/auth.sqlite3','/news-idea.sqlite3','/backups/test.json','/attachments/test','/assets/../auth.sqlite3'):
    assert call(path,authenticated=True)[0] == 404, path
checks.append('DB backup and file paths not served')
ids=[]
for kind in ('job','company','memo','contest','skill'):
    status,_,body=call('/api/save',{'kind':kind,'title':'QA '+kind,'notes':'Synthetic data only','mode':'dated','deadline':'2026-10-14','deadlineTime':'17:00','schedules':'2026-10-15 10:00 | QA'},True)
    assert status == 200
    ids.append(body['data'])
assert call('/api/save',{'id':ids[0],'kind':'job','title':'QA edited','mode':'rolling'},True)[0] == 200
assert call('/api/trash',{'id':ids[0]},True)[0] == 200
rows=call('/api/list',{},True)[2]['data']['records']
assert next(r for r in rows if r['id']==ids[0])['deleted']
assert call('/api/restore',{'id':ids[0]},True)[0] == 200
checks.append('five kinds CRUD and trash restore')
exported=call('/api/export',{},True)[2]['data']
assert len(exported['records']) == 5
assert call('/api/import',exported,True)[2]['data'] == 0
assert call('/api/backup',{},True)[0] == 200
assert call('/api/import',{'format':'invalid'},True)[0] == 400
checks.append('export import dedup backup and invalid import')
if endpoint.startswith('http:'):
    count=int(subprocess.check_output(['docker','inspect','--format','{{.RestartCount}}',CONTAINER],text=True).strip())
    subprocess.run(['docker','exec',CONTAINER,'python','-c','import os,signal; os.kill(1, signal.SIGTERM)'],check=True,capture_output=True)
    time.sleep(1)
    ready()
    after=int(subprocess.check_output(['docker','inspect','--format','{{.RestartCount}}',CONTAINER],text=True).strip())
    assert after > count, 'restart policy did not restart QA container'
    assert len(call('/api/list',{},True)[2]['data']['records']) == 5
    checks.append('process termination automatic restart and persistence')
assert call('/logout',{},True)[0] == 200
assert call('/api/list',{},True)[0] == 401
checks.append('logout replay rejected')
print(json.dumps({'endpoint':endpoint,'passed':len(checks),'checks':checks},ensure_ascii=False))
