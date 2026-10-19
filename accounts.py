"""Local account authentication; credentials never leave the server."""
from contextlib import contextmanager
import hashlib
import json
from store import KINDS
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from werkzeug.security import generate_password_hash, check_password_hash

class Auth:
    def __init__(self, root):
        self.path = Path(root) / 'auth.sqlite3'
        with self.connection() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS admin (id INTEGER PRIMARY KEY CHECK(id=1), password TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, csrf TEXT NOT NULL, expires REAL NOT NULL, user_id INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE IF NOT EXISTS attempts (id INTEGER PRIMARY KEY, at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS account_attempts (id INTEGER PRIMARY KEY, username TEXT NOT NULL, at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS signup_attempts (id INTEGER PRIMARY KEY, at REAL NOT NULL);''')
            columns = {r[1] for r in db.execute('PRAGMA table_info(sessions)')}
            if 'user_id' not in columns:
                db.execute('ALTER TABLE sessions ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1')
            legacy = db.execute('SELECT password FROM admin WHERE id=1').fetchone()
            if legacy:
                db.execute('INSERT OR IGNORE INTO users(id,username,password) VALUES(1,?,?)', ('admin', legacy[0]))
            user_columns={r[1] for r in db.execute('PRAGMA table_info(users)')}
            if 'approved' not in user_columns:
                db.execute('ALTER TABLE users ADD COLUMN approved INTEGER NOT NULL DEFAULT 0')
            if 'tabs' not in user_columns:
                db.execute("ALTER TABLE users ADD COLUMN tabs TEXT NOT NULL DEFAULT '[]'")
            db.execute('UPDATE users SET approved=1,tabs=? WHERE id=1',(json.dumps(list(KINDS)),))
        os.chmod(self.path, 0o600)
        self.dummy_hash = generate_password_hash(secrets.token_urlsafe(32), method='scrypt')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def username(value):
        if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_]{3,32}', value):
            raise ValueError('아이디는 영문·숫자·밑줄 3~32자로 입력하세요.')
        return value.lower()

    @staticmethod
    def password(value):
        if not isinstance(value, str) or not 10 <= len(value) <= 1024:
            raise ValueError('비밀번호는 10~1024자로 설정하세요.')
        return value

    def set_password(self, password):
        hashed = generate_password_hash(self.password(password), method='scrypt')
        with self.connection() as db:
            db.execute('INSERT OR REPLACE INTO admin VALUES (1,?)', (hashed,))
            db.execute('INSERT INTO users(id,username,password) VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET password=excluded.password', ('admin', hashed))
            db.execute('UPDATE users SET approved=1,tabs=? WHERE id=1',(json.dumps(list(KINDS)),))
            db.execute('DELETE FROM sessions WHERE user_id=1')
            db.execute('DELETE FROM attempts')
            db.execute('DELETE FROM account_attempts WHERE username=?', ('admin',))

    def register(self, username, password, confirmation):
        # Global persistent ceiling bounds public signup abuse on a personal Pi.
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM signup_attempts WHERE at<?', (time.time()-3600,))
            if db.execute('SELECT COUNT(*) FROM signup_attempts').fetchone()[0] >= 10:
                return 429
            db.execute('INSERT INTO signup_attempts(at) VALUES(?)', (time.time(),))
        username = self.username(username)
        password = self.password(password)
        if password != confirmation:
            raise ValueError('비밀번호 확인이 일치하지 않습니다.')
        hashed = generate_password_hash(password, method='scrypt')
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            # Reserve legacy owner ID even before its password is configured.
            if username == 'admin' or db.execute('SELECT COUNT(*) FROM users').fetchone()[0] >= 100:
                return 409
            if db.execute('SELECT 1 FROM users WHERE username=?', (username,)).fetchone():
                return 409
            next_id = max(2, db.execute('SELECT COALESCE(MAX(id),1)+1 FROM users').fetchone()[0])
            db.execute('INSERT INTO users(id,username,password) VALUES(?,?,?)', (next_id, username, hashed))
        return 201

    def login(self, password, username='admin'):
        try:
            username = self.username(username)
        except ValueError:
            username = ''
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            cutoff = time.time()-900
            db.execute('DELETE FROM attempts WHERE at<?', (cutoff,))
            db.execute('DELETE FROM account_attempts WHERE at<?', (cutoff,))
            limited = db.execute('SELECT COUNT(*) FROM account_attempts WHERE username=?', (username,)).fetchone()[0] >= 5
            if limited or db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0] >= 30:
                return None, 429
            db.execute('INSERT INTO attempts(at) VALUES (?)', (time.time(),))
            db.execute('INSERT INTO account_attempts(username,at) VALUES(?,?)', (username,time.time()))
            row = db.execute('SELECT id,password FROM users WHERE username=?', (username,)).fetchone()
            valid = isinstance(password, str) and len(password) <= 1024 and check_password_hash(row[1] if row else self.dummy_hash, password)
            if not row or not valid:
                return None, 401
            db.execute('DELETE FROM account_attempts WHERE username=?', (username,))
            if row[0] != 1 and not db.execute('SELECT approved FROM users WHERE id=?',(row[0],)).fetchone()[0]:
                return None, 403
            token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            db.execute('DELETE FROM sessions WHERE user_id=? AND expires<?', (row[0],time.time()))
            db.execute('INSERT INTO sessions(token,csrf,expires,user_id) VALUES (?,?,?,?)', (self.digest(token), csrf, time.time()+43200,row[0]))
            db.execute('DELETE FROM account_attempts WHERE username=?', (username,))
            return token, 200

    @staticmethod
    def digest(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def session(self, token):
        with self.connection() as db:
            return db.execute('SELECT s.csrf,u.id,u.username FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>?', (self.digest(token),time.time())).fetchone()

    def user_ids(self):
        with self.connection() as db:
            return [r[0] for r in db.execute('SELECT id FROM users ORDER BY id')]

    def access(self, user_id):
        if user_id == 1:
            return {'approved':True,'tabs':list(KINDS),'isAdmin':True}
        with self.connection() as db:
            row=db.execute('SELECT approved,tabs FROM users WHERE id=?',(user_id,)).fetchone()
        if not row:
            return {'approved':False,'tabs':[],'isAdmin':False}
        try:
            stored=json.loads(row[1])
            tabs=[kind for kind in KINDS if isinstance(stored,list) and kind in stored]
        except (ValueError,TypeError):
            tabs=[]
        return {'approved':bool(row[0]),'tabs':tabs if row[0] else [],'isAdmin':False}

    def members(self, actor):
        if actor != 1:
            raise PermissionError('관리자만 회원 권한을 관리할 수 있습니다.')
        with self.connection() as db:
            rows=db.execute('SELECT id,username FROM users ORDER BY id').fetchall()
        return [dict(id=id_,username=name,**self.access(id_)) for id_,name in rows]

    def set_access(self, actor, user_id, approved, tabs):
        if actor != 1:
            raise PermissionError('관리자만 회원 권한을 관리할 수 있습니다.')
        if type(user_id) is not int or user_id <= 1:
            raise ValueError('관리자 본인 권한은 변경할 수 없습니다.')
        if type(approved) is not bool or not isinstance(tabs,list) or len(tabs)>len(KINDS) or any(not isinstance(t,str) or t not in KINDS for t in tabs) or len(tabs)!=len(set(tabs)):
            raise ValueError('승인 여부와 허용 탭을 확인하세요.')
        with self.connection() as db:
            if not db.execute('UPDATE users SET approved=?,tabs=? WHERE id=?',(int(approved),json.dumps([kind for kind in KINDS if kind in tabs]),user_id)).rowcount:
                raise ValueError('회원을 찾을 수 없습니다.')
        return self.access(user_id)
