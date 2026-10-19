"""Local account authentication; credentials never leave the server."""
from contextlib import contextmanager
import hashlib
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
