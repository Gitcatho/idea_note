import argparse
import json
import os
from pathlib import Path
import sys
import threading
import webbrowser
from store import Store, now, validate_url

ROOT = Path(__file__).resolve().parent
SOURCES = [
    {'name': '삼성 Careers', 'kind': 'company', 'url': 'https://www.samsungcareers.com/', 'description': '공식 채용 포털 · AI/AX 직무 여부와 지원조건을 직접 확인', 'checked': '2026-10-13T00:10:00+09:00', 'state': '공식 페이지 확인'},
    {'name': 'Hugging Face Learn', 'kind': 'skill', 'url': 'https://huggingface.co/learn', 'description': '공식 학습 자료 · LLM, 에이전트, 모델 과정', 'checked': '2026-10-13T00:10:00+09:00', 'state': '공식 페이지 확인'},
    {'name': 'OpenAI 개발 문서', 'kind': 'skill', 'url': 'https://developers.openai.com/api/docs', 'description': '공식 API·에이전트 개발 문서 · 학습 링크', 'checked': '2026-10-13T00:10:00+09:00', 'state': '공식 페이지 확인'},
    {'name': 'NAVER Careers', 'kind': 'company', 'url': 'https://careers.naver.com/', 'description': '채용 탐색 링크 · 현재 개별 공고 미수집', 'checked': '', 'state': '수집 실패 · 수동 확인 필요'},
    {'name': 'Kakao 영입', 'kind': 'company', 'url': 'https://recruit.kakao.com/', 'description': '채용 탐색 링크 · 현재 개별 공고 미수집', 'checked': '', 'state': '수집 실패 · 수동 확인 필요'},
    {'name': 'AI Factory', 'kind': 'contest', 'url': 'https://www.aifactory.space/', 'description': '대회 운영 플랫폼 · 주최자 공고에서 참가조건 확인', 'checked': '', 'state': '수집 실패 · 수동 확인 필요'},
]

class Bridge:
    def __init__(self, store):
        self.store = store
        self.window = None
    def dispatch(self, action, payload=None):
        try:
            payload = payload or {}
            if action == 'list':
                data = {'records': self.store.list(), 'sources': SOURCES, 'root': str(self.store.root), 'now': now()}
            elif action == 'save':
                data = self.store.save(payload)
            elif action in ('trash', 'restore'):
                self.store.trash(payload['id'], action == 'trash')
                data = True
            elif action == 'backup':
                data = self.store.backup()
            elif action == 'open':
                url = validate_url(payload['url'])
                if not url:
                    raise ValueError('출처가 없습니다.')
                webbrowser.open(url)
                data = True
            elif action == 'export':
                import webview
                chosen = self.window.create_file_dialog(webview.FileDialog.SAVE, save_filename='News_idea-backup.json', file_types=('JSON (*.json)',))
                if not chosen:
                    data = None
                else:
                    target = Path(chosen if isinstance(chosen, str) else chosen[0])
                    target.write_text(json.dumps(self.store.export(), ensure_ascii=False, indent=2), encoding='utf-8')
                    os.chmod(target, 0o600)
                    data = str(target)
            elif action == 'import':
                import webview
                chosen = self.window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=False, file_types=('JSON (*.json)',))
                if not chosen:
                    data = None
                else:
                    target = Path(chosen if isinstance(chosen, str) else chosen[0])
                    if target.stat().st_size > 20_000_000:
                        raise ValueError('백업 파일은 20MB 이하만 지원합니다.')
                    incoming = json.loads(target.read_text(encoding='utf-8'))
                    self.store.backup()
                    data = self.store.merge(incoming)
            else:
                raise ValueError('지원하지 않는 동작입니다.')
            return {'ok': True, 'data': data}
        except ValueError as error:
            return {'ok': False, 'error': str(error)}
        except Exception:
            return {'ok': False, 'error': '파일 또는 저장소 작업에 실패했습니다. 저장 공간과 권한, 백업 형식을 확인하세요.'}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-root', type=Path)
    parser.add_argument('--smoke', type=Path, help='Write native UI smoke evidence and exit')
    args = parser.parse_args()
    import webview
    root = args.data_root or Path.home() / 'Library' / 'Application Support' / 'News_idea'
    fresh = not (root / 'news-idea.sqlite3').exists()
    store = Store(root)
    if fresh:
        from seeds import initialize
        initialize(store)
    store.backup()
    bridge = Bridge(store)
    html = (ROOT / 'static' / 'index.html').read_text(encoding='utf-8')
    html = html.replace('/*APP_CSS*/', (ROOT / 'static' / 'app.css').read_text(encoding='utf-8'))
    html = html.replace('/*RESUME_JS*/', (ROOT / 'static' / 'resume.js').read_text(encoding='utf-8'))
    html = html.replace('/*APP_JS*/', (ROOT / 'static' / 'app.js').read_text(encoding='utf-8'))
    bridge.window = webview.create_window('News_idea · AI 커리어 워크스페이스', html=html, js_api=bridge, width=1320, height=900, min_size=(850, 620), background_color='#f5f7fb')
    if args.smoke:
        def smoke():
            import time
            time.sleep(2)
            try:
                bridge.window.evaluate_js('window.nativeSmoke().then(r => {window.smokeResult=r}).catch(e => {window.smokeResult={error:e.message}}); true')
                result = None
                for _ in range(120):
                    result = bridge.window.evaluate_js('window.smokeResult || null')
                    if result is not None:
                        break
                    time.sleep(0.25)
                if result is None:
                    result = {'error': 'Native smoke timed out'}
                args.smoke.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            finally:
                bridge.window.destroy()
        webview.start(smoke, private_mode=True)
    else:
        webview.start(private_mode=True)

if __name__ == '__main__':
    try:
        main()
    except Exception:
        import webview
        webview.create_window('News_idea 시작 오류', html='<h2>앱을 시작하지 못했습니다.</h2><p>저장 공간과 데이터 폴더 권한을 확인하세요. 기존 데이터를 삭제하지 말고 백업을 보존해 주세요.</p>', width=560, height=260)
        webview.start()
