"""Single-admin workspace. No signup, filesystem serving, or desktop DB discovery."""
import argparse
from contextlib import contextmanager
import getpass
import hashlib
import hmac
import logging
import os
from pathlib import Path
import secrets
import signal
import sqlite3
import sys
import time
import threading
from urllib.parse import urlsplit

from flask import Flask, Response, g, jsonify, redirect, request
from werkzeug.security import generate_password_hash, check_password_hash
from desktop import SOURCES
from store import Store

ROOT = Path(__file__).resolve().parent
COOKIE = 'news_session'

class Auth:
    def __init__(self, root):
        self.path = Path(root) / 'auth.sqlite3'
        with self.connection() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS admin (id INTEGER PRIMARY KEY CHECK(id=1), password TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, csrf TEXT NOT NULL, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS attempts (id INTEGER PRIMARY KEY, at REAL NOT NULL);''')
        os.chmod(self.path, 0o600)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            with db:
                yield db
        finally:
            db.close()

    def set_password(self, password):
        if len(password) < 10 or len(password) > 1024:
            raise ValueError('비밀번호는 10~1024자로 설정하세요.')
        hashed = generate_password_hash(password, method='scrypt')
        with self.connection() as db:
            db.execute('INSERT OR REPLACE INTO admin VALUES (1,?)', (hashed,))
            db.execute('DELETE FROM sessions')
            db.execute('DELETE FROM attempts')

    def login(self, password):
        # Single admin: global persistent limit cannot be bypassed with proxy headers.
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM attempts WHERE at<?', (time.time()-900,))
            if db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0] >= 5:
                return None, 429
            db.execute('INSERT INTO attempts(at) VALUES (?)', (time.time(),))
            row = db.execute('SELECT password FROM admin WHERE id=1').fetchone()
            valid = row and isinstance(password, str) and len(password) <= 1024 and check_password_hash(row[0], password)
            if not valid:
                return None, 401
            token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            db.execute('DELETE FROM sessions WHERE expires<?', (time.time(),))
            db.execute('INSERT INTO sessions VALUES (?,?,?)', (self.digest(token), csrf, time.time()+43200))
            db.execute('DELETE FROM attempts')
            return token, 200

    @staticmethod
    def digest(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def session(self, token):
        with self.connection() as db:
            return db.execute('SELECT csrf FROM sessions WHERE token=? AND expires>?', (self.digest(token), time.time())).fetchone()

LOGIN = '''<!doctype html><html lang="ko"><meta name="viewport" content="width=device-width,initial-scale=1"><title>News_idea 로그인</title>
<link rel="stylesheet" href="/login.css"><main><h1>News_idea</h1><p>개인 관리자 로그인</p><form id="login"><label>관리자 비밀번호<input id="password" type="password" autocomplete="current-password" required maxlength="1024"></label><button>로그인</button><p id="error" role="alert"></p></form></main><script src="/login.js"></script></html>'''
LOGIN_JS = '''document.getElementById('login').onsubmit=async e=>{e.preventDefault();const b=e.target.querySelector('button');b.disabled=true;try{const r=await fetch('/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:document.getElementById('password').value})});if(r.ok)location.replace('/');else document.getElementById('error').textContent=r.status===429?'시도가 너무 많습니다. 15분 후 다시 시도하세요.':'로그인하지 못했습니다.';}catch(e){document.getElementById('error').textContent='연결을 확인하세요.';}finally{b.disabled=false;}};'''

def create_app(data_root, origin='http://127.0.0.1:4310', testing=False):
    parsed = urlsplit(origin)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.path or parsed.query or parsed.fragment or parsed.username:
        raise ValueError('NEWS_ORIGIN은 경로 없는 http/https origin이어야 합니다.')
    if parsed.scheme == 'http' and parsed.hostname not in ('127.0.0.1', 'localhost'):
        raise ValueError('HTTP는 로컬 개발에서만 허용됩니다.')
    app = Flask(__name__, static_folder=None)
    app.config.update(TESTING=testing, MAX_CONTENT_LENGTH=20_000_000)
    store = Store(data_root)
    auth = Auth(data_root)
    app.extensions.update(store=store, auth=auth)
    secure = parsed.scheme == 'https'
    store.backup()

    @app.before_request
    def guard():
        if request.host != parsed.netloc:
            return jsonify(error='잘못된 호스트입니다.'), 400
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and request.headers.get('Origin') != origin:
            return jsonify(error='요청 출처가 올바르지 않습니다.'), 403
        if request.path in ('/login', '/login.js', '/login.css', '/healthz'):
            return None
        token = request.cookies.get(COOKIE, '')
        session = auth.session(token)
        if not session:
            return (jsonify(error='로그인이 필요합니다.'), 401) if request.path.startswith('/api/') or request.path == '/logout' else redirect('/login')
        g.csrf = session[0]
        if request.method not in ('GET', 'HEAD') and not hmac.compare_digest(request.headers.get('X-CSRF-Token', '').encode(), g.csrf.encode()):
            return jsonify(error='보안 토큰이 올바르지 않습니다.'), 403

    @app.after_request
    def headers(response):
        response.headers.update({'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff', 'Referrer-Policy':'no-referrer', 'X-Frame-Options':'DENY', 'Content-Security-Policy':"default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})
        if secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    @app.get('/healthz')
    def health():
        with store.connection() as db:
            db.execute('SELECT 1 FROM records LIMIT 1').fetchone()
        return jsonify(status='ok')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'GET':
            return Response(LOGIN, mimetype='text/html')
        body = request.get_json(silent=True)
        token, status = auth.login(body.get('password') if isinstance(body, dict) else None)
        response = jsonify(ok=status == 200)
        response.status_code = status
        if token:
            response.set_cookie(COOKIE, token, max_age=43200, secure=secure, httponly=True, samesite='Strict', path='/')
        if status == 429:
            response.headers['Retry-After'] = '900'
        return response

    @app.get('/login.js')
    def login_js():
        return Response(LOGIN_JS, mimetype='text/javascript')

    @app.get('/login.css')
    def login_css():
        return Response('body{font:16px system-ui;background:#f5f7fb;margin:0}main{max-width:360px;margin:12vh auto;padding:24px}input,button{box-sizing:border-box;width:100%;padding:14px;margin:14px 0}#error{color:#a22}', mimetype='text/css')

    @app.post('/logout')
    def logout():
        with auth.connection() as db:
            db.execute('DELETE FROM sessions WHERE token=?', (auth.digest(request.cookies.get(COOKIE, '')),))
        response = jsonify(ok=True)
        response.delete_cookie(COOKIE, path='/', secure=secure, httponly=True, samesite='Strict')
        response.headers['Clear-Site-Data'] = '"cache", "cookies", "storage"'
        return response

    @app.get('/')
    def index():
        html = (ROOT/'static/index.html').read_text()
        html = html.replace(html[html.index('<meta http-equiv='):html.index('<title>')], '')
        html = html.replace('<style>/*APP_CSS*/</style>', '<link rel="stylesheet" href="/assets/app.css">')
        html = html.replace('<script>/*APP_JS*/</script>', '<script src="/assets/web.js"></script><script src="/assets/app.js"></script>')
        html = html.replace('로컬 전용 워크스페이스', '개인 웹 워크스페이스').replace('개인 메모는 이 Mac에 저장됩니다.', '로그인한 관리자만 접근합니다.')
        html = html.replace('<button id="trashTab">', '<button id="logout">로그아웃</button><button id="trashTab">')
        html = html.replace('하나의 로컬 공간', '개인 서버').replace('앱 시작 시', '서버 시작 시')
        return Response(html, mimetype='text/html')

    @app.get('/assets/<name>')
    def asset(name):
        if name not in ('app.js', 'app.css', 'web.js'):
            return '', 404
        return Response((ROOT/'static'/name).read_text(), mimetype='text/css' if name.endswith('.css') else 'text/javascript')

    @app.post('/api/<action>')
    def api(action):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(ok=False, error='JSON 객체가 필요합니다.'), 400
        try:
            if action == 'session':
                data = {'csrf':g.csrf}
            elif action == 'list':
                data = {'records':store.list(), 'sources':SOURCES, 'root':'개인 서버 저장소'}
            elif action == 'save':
                data = store.save(payload)
            elif action in ('trash', 'restore'):
                if not isinstance(payload.get('id'), str):
                    raise ValueError('ID를 확인하세요.')
                store.trash(payload['id'], action == 'trash')
                data = True
            elif action == 'export':
                data = store.export()
            elif action == 'import':
                store.backup()
                data = store.merge(payload)
            elif action == 'backup':
                data = Path(store.backup()).name
            else:
                return jsonify(ok=False, error='지원하지 않는 동작입니다.'), 404
            return jsonify(ok=True, data=data)
        except ValueError as e:
            return jsonify(ok=False, error=str(e)), 400
        except Exception:
            return jsonify(ok=False, error='저장소 작업에 실패했습니다. 권한과 저장 공간을 확인하세요.'), 500

    @app.get('/api/session')
    def session_info():
        return jsonify(ok=True, data={'csrf':g.csrf})

    @app.errorhandler(413)
    def too_large(error):
        return jsonify(ok=False, error='20MB 이하 파일만 지원합니다.'), 413

    return app

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-root', type=Path, default=Path(os.environ.get('NEWS_DATA_ROOT', 'var/web')))
    parser.add_argument('--set-password', action='store_true')
    parser.add_argument('--port', type=int, default=4310)
    args = parser.parse_args()
    os.umask(0o077)
    if sys.platform == 'linux':
        import resource
        # Pi kernel has no memory cgroup controller; bound this process instead.
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
    if args.set_password:
        Store(args.data_root)
        password = getpass.getpass('새 관리자 비밀번호 (10자 이상): ')
        if password != getpass.getpass('다시 입력: '):
            raise SystemExit('비밀번호가 일치하지 않습니다.')
        Auth(args.data_root).set_password(password)
        print('관리자 비밀번호 설정 완료. 기존 세션은 무효화했습니다.')
        return
    origin = os.environ.get('NEWS_ORIGIN', f'http://127.0.0.1:{args.port}')
    app = create_app(args.data_root, origin)
    with app.extensions['auth'].connection() as db:
        if not db.execute('SELECT 1 FROM admin').fetchone():
            logging.warning('Administrator password is not configured; all logins remain disabled. Use --set-password locally.')
    from waitress import serve
    # Python as container PID 1 must explicitly handle Docker's SIGTERM.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    def daily_backup():
        while True:
            time.sleep(86400)
            try:
                app.extensions['store'].backup()
            except Exception:
                logging.error('Scheduled backup failed; check disk space and permissions.')
    threading.Thread(target=daily_backup, daemon=True).start()
    serve(app, host='127.0.0.1', port=args.port, threads=4, max_request_body_size=20_000_000)

if __name__ == '__main__':
    main()
