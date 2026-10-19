"""Local-only records; no credentials or external content execution."""
from contextlib import contextmanager
import datetime as dt
import json
import os
from pathlib import Path
import sqlite3
import threading
import uuid
from resume import validate_resume
from urllib.parse import urlsplit

KINDS = ('job', 'company', 'memo', 'contest', 'skill')
MODES = ('dated', 'rolling', 'unknown')
STATUSES = {'job': ['관심', '준비 중', '지원 완료', '면접', '합격', '종료'], 'company': ['탐색', '지원 예정', '지원 완료', '면접', '보류', '종료'], 'memo': ['정리 중', '확정', '기억할 것'], 'contest': ['관심', '준비 중', '참가 완료', '종료'], 'skill': ['읽을 것', '학습 중', '실습 완료', '보관']}
KST = dt.timezone(dt.timedelta(hours=9))
RESUME_FIELDS = {'resumePersonal': 2000, 'resumeEducation': 10000, 'resumeMilitary': 2000, 'resumeGrades': 4000, 'resumeCareer': 15000, 'resumeCertificates': 6000, 'resumeAwards': 6000, 'resumeActivities': 10000}

def now():
    return dt.datetime.now(KST).isoformat(timespec='seconds')

def validate_url(value):
    if not value:
        return ''
    p = urlsplit(value)
    if p.scheme not in ('https', 'http') or not p.hostname or p.username or p.password or len(value) > 2048:
        raise ValueError('출처는 인증정보 없는 http/https 주소를 입력하세요.')
    return value

def validate(record):
    if not isinstance(record, dict) or record.get('kind') not in KINDS:
        raise ValueError('지원하지 않는 항목 종류입니다.')
    result = {'kind': record['kind']}
    for field, limit in [('title', 200), ('organization', 200), ('url', 2048), ('tags', 500), ('notes', 50000), ('schedules', 4000), ('requirements', 10000), ('benefits', 10000), ('location', 300), ('deadlineTime', 5), ('published', 10), ('deadline', 10), ('checked', 40)]:
        value = record.get(field, '')
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError(f'{field}: 입력 길이/형식을 확인하세요.')
        result[field] = value.strip()
    if not result['title']:
        raise ValueError('제목을 입력하세요.')
    result['url'] = validate_url(result['url'])
    result['mode'] = record.get('mode', 'unknown')
    if result['mode'] not in MODES:
        raise ValueError('기한 유형을 확인하세요.')
    for field in ('deadline', 'published'):
        if result[field]:
            try:
                dt.date.fromisoformat(result[field])
            except ValueError:
                raise ValueError('날짜 형식을 확인하세요.') from None
    if result['mode'] == 'dated' and not result['deadline']:
        raise ValueError('마감일을 입력하세요.')
    if result['mode'] != 'dated':
        result['deadline'] = result['deadlineTime'] = ''
    if result['deadlineTime']:
        try:
            dt.time.fromisoformat(result['deadlineTime'])
        except ValueError:
            raise ValueError('마감 시간 형식을 확인하세요.') from None
    if result['checked']:
        try:
            dt.datetime.fromisoformat(result['checked'])
        except ValueError:
            raise ValueError('확인 시각 형식을 확인하세요.') from None
    for line in result['schedules'].splitlines():
        try:
            date_time, label = line.split('|', 1)
            dt.datetime.strptime(date_time.strip(), '%Y-%m-%d %H:%M')
            if not label.strip():
                raise ValueError()
        except ValueError:
            raise ValueError('추가 일정: YYYY-MM-DD HH:MM | 일정명 형식으로 입력하세요.') from None
    result['status'] = record.get('status', STATUSES[result['kind']][0])
    if result['status'] not in STATUSES[result['kind']]:
        raise ValueError('상태를 확인하세요.')
    if result['kind'] == 'memo':
        result['memoType'] = record.get('memoType', 'resume' if any(record.get(key) for key in RESUME_FIELDS) else 'note')
        if result['memoType'] not in ('note', 'resume'):
            raise ValueError('메모 유형을 확인하세요.')
        for field, limit in RESUME_FIELDS.items():
            value = record.get(field, '')
            if not isinstance(value, str) or len(value) > limit:
                raise ValueError(f'{field}: 입력 길이/형식을 확인하세요.')
            result[field] = value.strip()
        if 'resumeData' in record:
            result['resumeData'] = validate_resume(record['resumeData'])
    return result

class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = threading.RLock()
        self.path = self.root / 'news-idea.sqlite3'
        with self.connection() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, payload TEXT NOT NULL, deleted INTEGER NOT NULL DEFAULT 0, updated TEXT NOT NULL)')
        os.chmod(self.path, 0o600)
    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.path, timeout=15)
        try:
            with conn:
                yield conn
        finally:
            conn.close()
    def list(self):
        with self.lock, self.connection() as conn:
            return [dict(json.loads(payload), id=id_, deleted=bool(deleted), updated=updated) for id_, payload, deleted, updated in conn.execute('SELECT id,payload,deleted,updated FROM records ORDER BY updated DESC,id')]
    def save(self, record):
        payload = validate(record)
        id_ = record.get('id') or str(uuid.uuid4())
        if not isinstance(id_, str) or len(id_) > 100:
            raise ValueError('항목 ID가 올바르지 않습니다.')
        with self.lock, self.connection() as conn:
            existing = conn.execute('SELECT deleted FROM records WHERE id=?', (id_,)).fetchone()
            if record.get('id') and (not existing or existing[0]):
                raise ValueError('항목이 없거나 휴지통에 있습니다. 새로고침하세요.')
            conn.execute('INSERT INTO records VALUES (?,?,0,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,updated=excluded.updated', (id_, json.dumps(payload, ensure_ascii=False), now()))
        return id_
    def trash(self, id_, deleted):
        with self.lock, self.connection() as conn:
            if not conn.execute('UPDATE records SET deleted=?,updated=? WHERE id=?', (int(deleted), now(), id_)).rowcount:
                raise ValueError('항목을 찾을 수 없습니다.')
    def export(self):
        return {'format': 'news-idea', 'version': 1, 'exported': now(), 'records': self.list()}
    def merge(self, data):
        if not isinstance(data, dict) or data.get('format') != 'news-idea' or data.get('version') != 1 or not isinstance(data.get('records'), list) or len(data['records']) > 10000:
            raise ValueError('News_idea v1 JSON 백업 파일이 아닙니다.')
        records = [(r, validate(r)) for r in data['records']]
        ids = [r.get('id') for r, _ in records]
        if any(not isinstance(i, str) or not i or len(i) > 100 for i in ids) or len(ids) != len(set(ids)):
            raise ValueError('백업 ID가 없거나 중복입니다.')
        added = 0
        with self.lock, self.connection() as conn:
            for original, payload in records:
                added += conn.execute('INSERT OR IGNORE INTO records VALUES (?,?,?,?)', (original['id'], json.dumps(payload, ensure_ascii=False), int(bool(original.get('deleted'))), now())).rowcount
        return added
    def backup(self):
        folder = self.root / 'backups'
        folder.mkdir(exist_ok=True, mode=0o700)
        target = folder / ('backup-' + dt.datetime.now(KST).strftime('%Y%m%d-%H%M%S-%f') + '.json')
        target.write_text(json.dumps(self.export(), ensure_ascii=False, indent=2), encoding='utf-8')
        os.chmod(target, 0o600)
        return str(target)
