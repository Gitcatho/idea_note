"""Account-isolated workspace; no filesystem serving or desktop DB discovery."""
import argparse
import getpass
import hmac
import logging
import os
from pathlib import Path
import signal
import sys
import time
import threading
from urllib.parse import urlsplit

from flask import Flask, Response, g, jsonify, redirect, request
from desktop import SOURCES
from store import Store, KINDS
from accounts import Auth
from skill_llm import SkillLLM, LLMError, configured

ROOT = Path(__file__).resolve().parent
COOKIE = 'news_session'

LOGIN = (ROOT/'static/login.html').read_text()
LOGIN_JS = (ROOT/'static/login.js').read_text()

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
    skill_llm=SkillLLM(auth)
    app.extensions['skill_llm']=skill_llm
    secure = parsed.scheme == 'https'
    def member_store(user_id):
        return store if user_id == 1 else Store(Path(data_root)/'users'/str(user_id))

    def backup_all():
        # A failed member backup must not stop attempts for other members.
        failed = False
        for user_id in sorted(set([1] + auth.user_ids())):
            try:
                member_store(user_id).backup()
            except Exception:
                failed = True
                logging.error('Scheduled backup failed; check disk space and permissions.')
        if failed:
            raise OSError('One or more member backups failed.')
    app.extensions['backup_all'] = backup_all
    backup_all()

    @app.before_request
    def guard():
        if request.host != parsed.netloc:
            return jsonify(error='잘못된 호스트입니다.'), 400
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and request.headers.get('Origin') != origin:
            return jsonify(error='요청 출처가 올바르지 않습니다.'), 403
        if request.path in ('/login', '/signup', '/login.js', '/login.css', '/healthz'):
            return None
        token = request.cookies.get(COOKIE, '')
        session = auth.session(token)
        if not session:
            return (jsonify(error='로그인이 필요합니다.'), 401) if request.path.startswith('/api/') or request.path == '/logout' else redirect('/login')
        g.csrf, g.user_id, g.username = session
        g.access = auth.access(g.user_id)
        if not g.access["approved"] and request.path != "/logout":
            if request.path.startswith("/api/"):
                return jsonify(ok=False,error="관리자 승인을 기다리거나 이용이 중지된 계정입니다."), 403
            return redirect("/login?pending=1")
        g.store = member_store(g.user_id)
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
        token, status = auth.login(body.get('password') if isinstance(body, dict) else None, body.get('username') if isinstance(body, dict) else None)
        response = jsonify(ok=status == 200, error="관리자 승인을 기다리거나 이용이 중지된 계정입니다." if status == 403 else "")
        response.status_code = status
        if token:
            response.set_cookie(COOKIE, token, max_age=43200, secure=secure, httponly=True, samesite='Strict', path='/')
        if status == 429:
            response.headers['Retry-After'] = '900'
        return response

    @app.route('/signup', methods=['GET', 'POST'])
    def signup():
        if request.method == 'GET':
            return Response(LOGIN.replace('data-mode="login"', 'data-mode="signup"'), mimetype='text/html')
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify(ok=False, error='입력을 확인하세요.'), 400
        try:
            status = auth.register(body.get('username'), body.get('password'), body.get('confirmation'))
        except ValueError as error:
            return jsonify(ok=False, error=str(error)), 400
        response = jsonify(ok=status == 201, error='가입할 수 없습니다. 다른 아이디를 사용하거나 운영자에게 문의하세요.' if status == 409 else '가입 시도가 많습니다. 한 시간 후 다시 시도하세요.' if status == 429 else '')
        response.status_code = status
        if status == 429:
            response.headers['Retry-After'] = '3600'
        return response

    @app.get('/login.js')
    def login_js():
        return Response(LOGIN_JS, mimetype='text/javascript')

    @app.get('/login.css')
    def login_css():
        return Response((ROOT/'static/login.css').read_text(), mimetype='text/css')

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
        html = html.replace('<script>/*RESUME_JS*/</script>', '<script src="/assets/resume.js"></script>')
        html = html.replace('<script>/*APP_JS*/</script>', '<script src="/assets/web.js"></script><script src="/assets/app.js"></script>')
        html = html.replace('로컬 전용 워크스페이스', '개인 웹 워크스페이스').replace('개인 메모는 이 Mac에 저장됩니다.', '<span id="memberIdentity">로그인한 회원의 개인 공간입니다.</span>')
        html = html.replace('<button id="trashTab">', '<button id="logout">로그아웃</button><button id="trashTab">')
        html = html.replace('<script src="/assets/app.js"></script>', '<script src="/assets/app.js"></script><script src="/assets/members.js"></script><script src="/assets/skill-llm.js"></script>')
        html = html.replace('하나의 로컬 공간', '개인 서버').replace('앱 시작 시', '서버 시작 시')
        return Response(html, mimetype='text/html')

    @app.get('/assets/<name>')
    def asset(name):
        if name not in ('app.js', 'app.css', 'web.js', 'resume.js', 'members.js', 'skill-llm.js'):
            return '', 404
        return Response((ROOT/'static'/name).read_text(), mimetype='text/css' if name.endswith('.css') else 'text/javascript')

    def visible_export():
        data=g.store.export()
        data['records']=[record for record in data['records'] if record['kind'] in g.access['tabs']]
        return data

    def check_kind(kind):
        if kind not in g.access['tabs']:
            raise PermissionError('이 탭을 이용할 권한이 없습니다.')

    def check_existing(id_):
        with g.store.connection() as db:
            row=db.execute('SELECT json_extract(payload,?) FROM records WHERE id=?',('$.kind',id_)).fetchone()
        if row:
            check_kind(row[0])

    @app.post('/api/<action>')
    def api(action):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(ok=False, error='JSON 객체가 필요합니다.'), 400
        try:
            if action in ('llm_status','llm_draft'):
                check_kind('skill')
                data={'configured':configured()} if action=='llm_status' else skill_llm.draft(g.user_id,payload)
            elif action in ('members','member_access'):
                if g.user_id != 1:
                    raise PermissionError('관리자만 회원 권한을 관리할 수 있습니다.')
                data=auth.members(g.user_id) if action=='members' else auth.set_access(g.user_id,payload.get('userId'),payload.get('approved'),payload.get('tabs'))
            elif action == 'session':
                data = {'csrf':g.csrf, 'username':g.username, **g.access}
            elif action == 'list':
                data = {'records':visible_export()['records'], 'sources':SOURCES, 'root':'개인 서버 저장소', 'permissions':g.access}
            elif action == 'save':
                check_kind(payload.get('kind'))
                if payload.get('id'):
                    check_existing(payload['id'])
                data = g.store.save(payload)
            elif action in ('trash', 'restore'):
                if not isinstance(payload.get('id'), str):
                    raise ValueError('ID를 확인하세요.')
                check_existing(payload['id'])
                g.store.trash(payload['id'], action == 'trash')
                data = True
            elif action == 'export':
                data = visible_export()
            elif action == 'import':
                if not isinstance(payload.get('records'),list):
                    raise ValueError('백업 형식을 확인하세요.')
                for record in payload['records']:
                    if not isinstance(record,dict):
                        raise ValueError('백업 형식을 확인하세요.')
                    check_kind(record.get('kind'))
                g.store.backup(visible_export())
                data = g.store.merge(payload)
            elif action == 'backup':
                data = Path(g.store.backup(visible_export())).name
            else:
                return jsonify(ok=False, error='지원하지 않는 동작입니다.'), 404
            return jsonify(ok=True, data=data)
        except LLMError as e:
            return jsonify(ok=False,error=str(e)), e.status
        except PermissionError as e:
            return jsonify(ok=False,error=str(e)), 403
        except ValueError as e:
            return jsonify(ok=False, error=str(e)), 400
        except Exception:
            return jsonify(ok=False, error='저장소 작업에 실패했습니다. 권한과 저장 공간을 확인하세요.'), 500

    @app.get('/api/session')
    def session_info():
        return jsonify(ok=True, data={'csrf':g.csrf, 'username':g.username, **g.access})

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
        password = getpass.getpass('admin 계정 비밀번호 (10자 이상): ')
        if password != getpass.getpass('다시 입력: '):
            raise SystemExit('비밀번호가 일치하지 않습니다.')
        Auth(args.data_root).set_password(password)
        print('admin 비밀번호 설정 완료. admin 세션만 무효화했습니다.')
        return
    origin = os.environ.get('NEWS_ORIGIN', f'http://127.0.0.1:{args.port}')
    app = create_app(args.data_root, origin)
    with app.extensions['auth'].connection() as db:
        if not db.execute('SELECT 1 FROM admin').fetchone():
            logging.warning('Legacy admin password is not configured. Use --set-password locally to access existing owner records.')
    from waitress import serve
    # Python as container PID 1 must explicitly handle Docker's SIGTERM.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    def daily_backup():
        while True:
            time.sleep(86400)
            try:
                app.extensions['backup_all']()
            except Exception:
                logging.error('Scheduled backup failed; check disk space and permissions.')
    threading.Thread(target=daily_backup, daemon=True).start()
    serve(app, host='127.0.0.1', port=args.port, threads=4, max_request_body_size=20_000_000)

if __name__ == '__main__':
    main()
