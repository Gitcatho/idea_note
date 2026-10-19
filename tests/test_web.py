import tempfile
import unittest
from webapp import create_app, COOKIE

class WebTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.origin = 'https://workspace.example:8443'
        self.app = create_app(self.temp.name, self.origin, testing=True)
        self.app.extensions['auth'].set_password('test-only-password-12345')
        self.client = self.app.test_client()
        self.csrf = ''

    def tearDown(self):
        self.temp.cleanup()

    def test_password_minimum(self):
        auth = self.app.extensions['auth']
        with self.assertRaises(ValueError):
            auth.set_password('x' * 9)
        auth.set_password('x' * 10)
        self.assertEqual(auth.login('x' * 10)[1], 200)

    def login(self):
        response = self.client.post('/login', base_url=self.origin, headers={'Origin':self.origin}, json={'username':'admin','password':'test-only-password-12345'})
        self.assertEqual(response.status_code, 200)
        self.csrf = self.client.get('/api/session', base_url=self.origin).json['data']['csrf']
        return response

    def post(self, action, data=None):
        return self.client.post('/api/'+action, base_url=self.origin, json=data or {}, headers={'Origin':self.origin, 'X-CSRF-Token':self.csrf})

    def test_every_private_route_requires_login(self):
        for action in ('list','save','trash','restore','export','import','backup','session'):
            self.assertEqual(self.post(action).status_code, 401, action)
        for path in ('/','/assets/app.js','/assets/app.css','/assets/web.js','/backups/test.json','/news-idea.sqlite3','/auth.sqlite3','/attachments/test','/static/index.html','/assets/../auth.sqlite3'):
            self.assertEqual(self.client.get(path, base_url=self.origin).status_code, 302, path)
        self.assertEqual(self.client.get('/api/session', base_url=self.origin).status_code, 401)

    def test_csrf_host_origin_and_secure_cookie(self):
        response = self.login()
        cookie = response.headers['Set-Cookie']
        for flag in ('Secure','HttpOnly','SameSite=Strict'):
            self.assertIn(flag, cookie)
        self.assertEqual(self.client.post('/api/backup', base_url=self.origin, headers={'Origin':self.origin}, json={}).status_code, 403)
        self.assertEqual(self.client.post('/api/backup', base_url=self.origin, headers={'Origin':'https://evil.example','X-CSRF-Token':self.csrf}, json={}).status_code, 403)
        self.assertEqual(self.client.get('/healthz', base_url='https://evil.example').status_code, 400)
        self.assertEqual(self.client.post('/login', base_url=self.origin, json={}).status_code, 403)
        for path in ('/backups/test.json','/news-idea.sqlite3','/auth.sqlite3','/attachments/test','/assets/../auth.sqlite3'):
            self.assertEqual(self.client.get(path, base_url=self.origin).status_code, 404)

    def test_logout_password_rotation_expiry(self):
        self.login()
        old = self.client.get_cookie(COOKIE, domain='workspace.example').value
        response = self.client.post('/logout', base_url=self.origin, headers={'Origin':self.origin,'X-CSRF-Token':self.csrf})
        self.assertEqual(response.status_code, 200)
        self.client.set_cookie(COOKIE, old, domain='workspace.example')
        self.assertEqual(self.post('list').status_code, 401)
        self.login()
        self.app.extensions['auth'].set_password('test-only-password-12345')
        self.assertEqual(self.post('list').status_code, 401)
        self.login()
        with self.app.extensions['auth'].connection() as db:
            db.execute('UPDATE sessions SET expires=0')
        self.assertEqual(self.post('list').status_code, 401)

    def test_persistent_rate_limit(self):
        for _ in range(5):
            self.assertEqual(self.client.post('/login', base_url=self.origin, headers={'Origin':self.origin}, json={'username':'admin','password':'wrong'}).status_code, 401)
        other = create_app(self.temp.name, self.origin, testing=True).test_client()
        response = other.post('/login', base_url=self.origin, headers={'Origin':self.origin,'X-Forwarded-For':'1.2.3.4'}, json={'username':'admin','password':'test-only-password-12345'})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers['Retry-After'], '900')

    def test_crud_backup_import_restart(self):
        self.login()
        ids=[]
        for kind in ('job','company','memo','contest','skill'):
            response = self.post('save', {'kind':kind,'title':kind,'notes':'private test memo','mode':'dated','deadline':'2026-10-14','deadlineTime':'17:00','schedules':'2026-10-15 10:00 | 제출'})
            self.assertEqual(response.status_code, 200)
            ids.append(response.json['data'])
        self.assertEqual(self.post('save', {'id':ids[0],'kind':'job','title':'edited','mode':'rolling'}).status_code, 200)
        self.post('trash', {'id':ids[0]})
        self.assertTrue(next(r for r in self.post('list').json['data']['records'] if r['id']==ids[0])['deleted'])
        self.post('restore', {'id':ids[0]})
        exported=self.post('export').json['data']
        self.assertEqual(self.post('import', exported).json['data'], 0)
        self.assertEqual(self.post('backup').status_code, 200)
        with tempfile.TemporaryDirectory() as restored:
            app=create_app(restored, self.origin, testing=True)
            self.assertEqual(app.extensions['store'].merge(exported), 5)
            self.assertEqual(len(app.extensions['store'].list()), 5)
        restarted=create_app(self.temp.name, self.origin, testing=True)
        self.assertEqual(len(restarted.extensions['store'].list()), 5)
        self.assertIsNotNone(restarted.extensions['auth'].session(self.client.get_cookie(COOKIE, domain='workspace.example').value))

    def test_invalid_import_and_size_limit(self):
        self.login()
        self.assertEqual(self.post('import', {'format':'bad'}).status_code, 400)
        response=self.client.post('/api/import', base_url=self.origin, headers={'Origin':self.origin,'X-CSRF-Token':self.csrf,'Content-Type':'application/json'}, data=b' ' * 20_000_001)
        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.post('list').json['data']['records'], [])
        response=self.client.get('/',base_url=self.origin)
        self.assertIn("script-src 'self'",response.headers['Content-Security-Policy'])
        self.assertEqual(response.headers['Cache-Control'],'no-store')

if __name__ == '__main__':
    unittest.main()
