"""Private bookmarks and short metadata supplied by official-source review; no scraped body."""
from store import Store

SEEDS = [
 {'id':'official-naver-30005520','kind':'job','title':'NAVER · AI Security 경력 (자격 확인 필요)','organization':'NAVER','url':'https://recruit.navercorp.com/rcrt/view.do?annoId=30005520&lang=ko','mode':'dated','deadline':'2026-10-14','deadlineTime':'17:00','requirements':'각 포지션 경력 3년 이상. 본인 경력과 직무별 자격을 원문에서 확인하세요.','notes':'공식 출처 검토로 등록한 개인용 북마크. 조기 마감 가능. 모집·지원 가능 여부를 보장하지 않습니다. 원문의 시간대는 명시되지 않아 KST로 해석했습니다.','checked':'2026-10-12T15:07:00+00:00'},
 {'id':'official-daker-platform-2026','kind':'contest','title':'AI 플랫폼 개발 챌린지 · 예선','organization':'DAKER','url':'https://daker.ai/public/hackathons/ai-platform-build-challenge-prelims','mode':'dated','deadline':'2026-10-25','deadlineTime':'17:00','schedules':'2026-10-25 23:59 | 기획서 제출','requirements':'누구나 참가 · 개인 또는 1~3인. 상세 자격과 일정은 원문 확인.','notes':'개인용 공식 페이지 북마크와 짧은 사실 메타정보. 시간대 미명시: KST 추정. 실시간 연동 아님. 원문 재확인 필요.','checked':'2026-10-12T15:07:00+00:00'},
 {'id':'official-daker-kic-2026','kind':'contest','title':'KIC AI 에이전트 경진대회','organization':'DAKER','url':'https://daker.ai/public/hackathons/kic-ai-agent-competition','mode':'dated','deadline':'2026-11-12','schedules':'2026-11-12 10:00 | 기획서 제출','requirements':'누구나 참가 · 개인 또는 최대 5인 팀.','notes':'접수 종료일은 11/12, 시각 미명시. 캘린더 계산은 23:59이나 기획서 제출은 10:00이므로 원문 기준 확인. 시간대 미명시: KST 추정. 개인용 북마크, 자동수집 아님.','checked':'2026-10-12T15:07:00+00:00'},
 {'id':'official-dacon-port-236771','kind':'contest','title':'항만 AI 대회 · 참가 자격 확인 필요','organization':'DACON','url':'https://www.dacon.io/competitions/official/236771/overview/description','mode':'dated','deadline':'2026-11-02','deadlineTime':'10:00','schedules':'2026-10-26 10:00 | 팀 병합 마감\n2026-11-01 10:00 | 리더보드 마감','requirements':'학생 또는 졸업 3년 이내 미취업자. 졸업일과 취업 여부에 따라 자격 미충족 가능.','notes':'참가 자격과 복수 일정을 원문에서 재확인. 시간대 미명시: KST 추정. 개인용 공식 페이지 북마크, 실시간 연동 아님.','checked':'2026-10-12T15:07:00+00:00'}
]

def initialize(store):
    store.merge({'format':'news-idea','version':1,'records':SEEDS})
