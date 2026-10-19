from contextlib import closing
import json,sqlite3,tempfile,unittest
from pathlib import Path
from store import Store,KINDS
from webapp import create_app

class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.origin='https://test.example'
        self.app=create_app(self.temp.name,self.origin,testing=True);self.auth=self.app.extensions['auth'];self.auth.set_password('synthetic-admin-password')
        self.auth.register('test_member','synthetic-member-password','synthetic-member-password')
        self.admin=self.signin('admin','synthetic-admin-password')
    def tearDown(self):self.temp.cleanup()
    def signin(self,name,password):
        c=self.app.test_client();r=c.post('/login',base_url=self.origin,headers={'Origin':self.origin},json={'username':name,'password':password});self.assertEqual(r.status_code,200)
        return c,c.get('/api/session',base_url=self.origin).json['data']['csrf']
    def api(self,pair,action,payload=None):
        c,csrf=pair
        return c.post('/api/'+action,base_url=self.origin,headers={'Origin':self.origin,'X-CSRF-Token':csrf},json=payload or {})
    def approve(self,tabs,approved=True):return self.api(self.admin,'member_access',{'userId':2,'approved':approved,'tabs':tabs})
    def test_pending_admin_only_and_immediate_permission_changes(self):
        c=self.app.test_client();r=c.post('/login',base_url=self.origin,headers={'Origin':self.origin},json={'username':'test_member','password':'synthetic-member-password'});self.assertEqual(r.status_code,403);self.assertNotIn('Set-Cookie',r.headers)
        members=self.api(self.admin,'members').json['data'];self.assertEqual(len(members),2);self.assertNotIn('password',members[0]);self.assertFalse(members[1]['approved']);self.assertEqual(members[1]['tabs'],[])
        self.assertEqual(self.approve(['memo']).status_code,200)
        member=self.signin('test_member','synthetic-member-password')
        self.assertEqual(self.api(member,'members').status_code,403)
        self.assertEqual(self.api(member,'member_access',{'userId':2,'approved':True,'tabs':list(KINDS)}).status_code,403)
        self.assertEqual(self.api(member,'save',{'kind':'job','title':'forbidden'}).status_code,403)
        self.assertEqual(self.api(member,'save',{'kind':'memo','title':'permitted'}).status_code,200)
        self.assertEqual(self.approve(['skill'],False).status_code,200)
        self.assertEqual(self.api(member,'list').status_code,403)
        self.assertEqual(self.approve(['skill']).status_code,200)
        self.assertEqual(self.api(member,'list').json['data']['records'],[])
        self.assertEqual(self.api(member,'save',{'kind':'skill','title':'new permission'}).status_code,200)
        self.assertEqual(self.api(self.admin,'member_access',{'userId':1,'approved':False,'tabs':[]}).status_code,400)
        self.assertEqual(self.approve(['unknown']).status_code,400)
        self.assertEqual(self.approve(['memo','memo']).status_code,400)
        self.assertEqual(self.approve([],True).status_code,200)
        self.assertEqual(self.api(member,'list').json['data']['records'],[])

    def test_every_data_path_filters_tabs_and_rejects_import_before_backup(self):
        self.approve(['skill']);member=self.signin('test_member','synthetic-member-password')
        store=Store(Path(self.temp.name)/'users'/'2')
        ids={kind:store.save({'kind':kind,'title':'synthetic '+kind}) for kind in KINDS}
        self.assertEqual([r['kind'] for r in self.api(member,'list').json['data']['records']],['skill'])
        exported=self.api(member,'export').json['data'];self.assertEqual([r['kind'] for r in exported['records']],['skill'])
        for kind in ['job','company','memo','contest']:
            for action in ['trash','restore']:
                self.assertEqual(self.api(member,action,{'id':ids[kind]}).status_code,403)
            self.assertEqual(self.api(member,'save',{'id':ids[kind],'kind':'skill','title':'kind swap attack'}).status_code,403)
        files=list((store.root/'backups').glob('*.json')) if (store.root/'backups').exists() else []
        self.assertEqual(self.api(member,'import',store.export()).status_code,403)
        self.assertEqual(len(list((store.root/'backups').glob('*.json'))) if (store.root/'backups').exists() else 0,len(files))
        response=self.api(member,'backup');self.assertEqual(response.status_code,200)
        backup=json.loads((store.root/'backups'/response.json['data']).read_text());self.assertEqual([r['kind'] for r in backup['records']],['skill'])
        self.assertEqual(len(store.list()),5)
        restarted=create_app(self.temp.name,self.origin,testing=True)
        self.assertEqual(restarted.extensions['auth'].access(2)['tabs'],['skill'])
        self.assertEqual(len(store.list()),5)

    def test_existing_members_migrate_pending_without_deleting_sessions_or_data(self):
        with tempfile.TemporaryDirectory() as root:
            store=Store(root);store.save({'kind':'memo','title':'legacy synthetic'})
            with closing(sqlite3.connect(Path(root)/'auth.sqlite3')) as db:
                db.executescript('CREATE TABLE users(id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT UNIQUE,password TEXT);CREATE TABLE sessions(token TEXT PRIMARY KEY,csrf TEXT,expires REAL);CREATE TABLE admin(id INTEGER PRIMARY KEY,password TEXT);')
                db.execute('INSERT INTO users VALUES(2,?,?)',('old_member','synthetic unused hash'))
                db.execute('INSERT INTO sessions VALUES(?,?,?)',('old-token-digest','old-csrf',9999999999));db.commit()
            app=create_app(root,self.origin,testing=True);auth=app.extensions['auth']
            self.assertFalse(auth.access(2)['approved'])
            with auth.connection() as db:self.assertEqual(db.execute('SELECT token,csrf,expires FROM sessions').fetchall(),[('old-token-digest','old-csrf',9999999999.0)])
            self.assertEqual(len(store.list()),1)

if __name__=='__main__':unittest.main()
