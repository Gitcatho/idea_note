from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from werkzeug.security import generate_password_hash
from store import Store
from webapp import create_app, COOKIE

class MemberTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.origin = 'https://workspace.example:8443'
        self.app = create_app(self.temp.name, self.origin, testing=True)
        self.auth = self.app.extensions['auth']
        self.auth.set_password('synthetic-owner-password')

    def tearDown(self):
        self.temp.cleanup()

    def signup(self, name, password='synthetic-member-password', client=None):
        response=(client or self.app.test_client()).post('/signup', base_url=self.origin, headers={'Origin':self.origin}, json={'username':name,'password':password,'confirmation':password})
        if response.status_code==201:
            with self.auth.connection() as db:
                user_id=db.execute('SELECT id FROM users WHERE username=?',(name.lower(),)).fetchone()[0]
            self.auth.set_access(1,user_id,True,['job','company','memo','contest','skill'])
        return response

    def login(self, name, password='synthetic-member-password'):
        client = self.app.test_client()
        response = client.post('/login',base_url=self.origin,headers={'Origin':self.origin},json={'username':name,'password':password})
        self.assertEqual(response.status_code,200)
        csrf = client.get('/api/session',base_url=self.origin).json['data']['csrf']
        return client, csrf

    def api(self, pair, action, data=None):
        client, csrf = pair
        return client.post('/api/'+action,base_url=self.origin,headers={'Origin':self.origin,'X-CSRF-Token':csrf},json=data or {})

    def test_all_data_actions_are_isolated_and_backup_restart(self):
        self.assertEqual(self.signup('member_a').status_code,201)
        self.assertEqual(self.signup('member_b').status_code,201)
        a,b = self.login('member_a'),self.login('member_b')
        ids=[]
        for kind in ['job','company','memo','contest','skill']:
            record={'kind':kind,'title':'synthetic '+kind,'notes':'synthetic private text','owner_id':3,'user_id':3}
            if kind=='memo':
                record.update(memoType='resume',resumeData={'nameKo':'합성 테스트 이름','careers':[{'company':'합성 기업','start':'2023-01-01','end':'2024-01-01'}]})
            ids.append(self.api(a,'save',record).json['data'])
        self.assertEqual(self.api(b,'list').json['data']['records'],[])
        owner=self.login('admin','synthetic-owner-password')
        self.assertEqual(self.api(owner,'list').json['data']['records'],[])
        self.assertEqual(self.api(b,'export').json['data']['records'],[])
        for record_id in ids:
            self.assertEqual(self.api(b,'save',{'id':record_id,'kind':'memo','title':'foreign edit'}).status_code,400)
            for action in ['trash','restore']:
                self.assertEqual(self.api(b,action,{'id':record_id}).status_code,400)
        exported=self.api(a,'export').json['data']
        self.assertEqual(len(exported['records']),5)
        self.assertEqual(self.api(a,'trash',{'id':ids[0]}).status_code,200)
        self.assertEqual(self.api(a,'restore',{'id':ids[0]}).status_code,200)
        backup_name=self.api(b,'backup').json['data']
        with self.auth.connection() as db:
            user_id=db.execute('SELECT id FROM users WHERE username=?',('member_b',)).fetchone()[0]
        backup=Path(self.temp.name)/'users'/str(user_id)/'backups'/backup_name
        self.assertEqual(json.loads(backup.read_text())['records'],[])
        self.assertEqual(self.api(b,'import',exported).json['data'],5)
        self.assertEqual(self.api(b,'save',{'id':ids[0],'kind':'job','title':'own copied record'}).status_code,200)
        self.assertNotEqual(self.api(a,'list').json['data']['records'],self.api(b,'list').json['data']['records'])
        restarted=create_app(self.temp.name,self.origin,testing=True)
        token=a[0].get_cookie(COOKIE,domain='workspace.example').value
        client=restarted.test_client();client.set_cookie(COOKIE,token,domain='workspace.example')
        self.assertEqual(len(client.post('/api/list',base_url=self.origin,headers={'Origin':self.origin,'X-CSRF-Token':a[1]},json={}).json['data']['records']),5)
        restarted.extensions['backup_all']()
        for user_folder in (Path(self.temp.name)/'users').iterdir():
            latest=max((user_folder/'backups').glob('*.json'),key=lambda f:f.stat().st_mtime_ns)
            self.assertEqual(len(json.loads(latest.read_text())['records']),5)
        self.assertEqual(self.app.extensions['store'].list(),[])


    def test_signup_validation_limits_origin_and_reserved_owner(self):
        self.assertEqual(self.signup('ADMIN').status_code,409)
        self.assertEqual(self.signup('valid_user').status_code,201)
        self.assertEqual(self.signup('VALID_USER').status_code,409)
        for name in ['ab','../admin','a'*33,'아이디']:
            self.assertEqual(self.signup(name).status_code,400)
        self.assertEqual(self.signup('new_user','short').status_code,400)
        client=self.app.test_client()
        self.assertEqual(client.post('/signup',base_url=self.origin,json={}).status_code,403)
        self.assertEqual(client.post('/signup',base_url=self.origin,headers={'Origin':self.origin},json={'username':'another','password':'synthetic-member-password','confirmation':'different'}).status_code,400)
        self.signup('third_user')
        self.assertEqual(self.signup('fourth_user').status_code,429)
        restarted=create_app(self.temp.name,self.origin,testing=True)
        self.assertEqual(restarted.test_client().post('/signup',base_url=self.origin,headers={'Origin':self.origin},json={}).status_code,429)

    def test_legacy_migration_preserves_owner_records_and_cookie(self):
        with tempfile.TemporaryDirectory() as root:
            original=Store(root);record_id=original.save({'kind':'memo','title':'old synthetic note'})
            before=original.list()
            token='synthetic-legacy-token';csrf='synthetic-legacy-csrf';password='synthetic-legacy-password'
            with closing(sqlite3.connect(Path(root)/'auth.sqlite3')) as db:
                db.executescript('CREATE TABLE admin(id INTEGER PRIMARY KEY,password TEXT NOT NULL); CREATE TABLE sessions(token TEXT PRIMARY KEY,csrf TEXT NOT NULL,expires REAL NOT NULL); CREATE TABLE attempts(id INTEGER PRIMARY KEY,at REAL NOT NULL);')
                db.execute('INSERT INTO admin VALUES(1,?)',(generate_password_hash(password,method='scrypt'),))
                db.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),csrf,time.time()+3600))
                db.commit()
            app=create_app(root,self.origin,testing=True)
            client=app.test_client();client.set_cookie(COOKIE,token,domain='workspace.example')
            response=client.post('/api/list',base_url=self.origin,headers={'Origin':self.origin,'X-CSRF-Token':csrf},json={})
            self.assertEqual(response.json['data']['records'],before)
            self.assertEqual(app.extensions['auth'].session(token)[:2],(csrf,1))
            self.assertEqual(app.extensions['auth'].login(password,'admin')[1],200)
            self.assertEqual(app.extensions['auth'].register('new_member','synthetic-member-password','synthetic-member-password'),201)
            self.assertEqual(app.extensions['auth'].user_ids(),[1,2])
            self.assertEqual(original.list()[0]['id'],record_id)

    def test_owner_reserved_before_setup_and_logout_only_one_account(self):
        with tempfile.TemporaryDirectory() as root:
            app=create_app(root,self.origin,testing=True);auth=app.extensions['auth']
            self.assertEqual(auth.register('first_member','synthetic-member-password','synthetic-member-password'),201)
            auth.set_password('synthetic-owner-password')
            auth.set_access(1,2,True,['memo'])
            token,status=auth.login('synthetic-member-password','first_member')
            self.assertEqual(status,200)
            self.assertEqual(auth.session(token)[1],2)
            auth.set_password('synthetic-owner-password')
            self.assertIsNotNone(auth.session(token))
        self.signup('member_a');self.signup('member_b')
        a,b=self.login('member_a'),self.login('member_b')
        token=a[0].get_cookie(COOKIE,domain='workspace.example').value
        self.assertEqual(a[0].post('/logout',base_url=self.origin,headers={'Origin':self.origin,'X-CSRF-Token':a[1]}).status_code,200)
        a[0].set_cookie(COOKIE,token,domain='workspace.example')
        self.assertEqual(self.api(a,'list').status_code,401)
        self.assertEqual(self.api(b,'list').status_code,200)
        with self.auth.connection() as db:
            db.execute('INSERT INTO sessions(token,csrf,expires,user_id) VALUES(?,?,?,1)',('synthetic-expired-owner','synthetic-csrf',0))
        self.login('member_b')
        with self.auth.connection() as db:
            self.assertIsNotNone(db.execute('SELECT 1 FROM sessions WHERE token=?',('synthetic-expired-owner',)).fetchone())
        for _ in range(5):
            a[0].post('/login',base_url=self.origin,headers={'Origin':self.origin},json={'username':'member_a','password':'wrong'})
        self.assertEqual(a[0].post('/login',base_url=self.origin,headers={'Origin':self.origin},json={'username':'member_a','password':'synthetic-member-password'}).status_code,429)
        self.assertEqual(self.login('member_b')[0].get('/api/session',base_url=self.origin).status_code,200)

if __name__=='__main__':unittest.main()
