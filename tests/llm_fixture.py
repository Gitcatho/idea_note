"""Synthetic-only UI fixture. Never imported by production app."""
import os,sys
from unittest.mock import patch
from waitress import serve
from skill_llm import LLMError
from webapp import create_app
def summary(model,key,text,url):
    return {'supported':True,'title':'합성 검색·평가 스킬','summary':'자료를 검색하고 근거를 확인해 평가하는 방법입니다.','points':['원문 근거 확인','평가 기준 기록'],'steps':['작은 합성 자료로 검색하기','근거와 결과를 비교하기'],'cautions':['실제 효과는 별도 검증 필요'],'tags':['검색','평가'],'evidence':text[:50]}
with patch.dict(os.environ,{'OPENAI_MODEL':'synthetic-model','OPENAI_API_KEY':'synthetic-not-a-real-key'},clear=True),patch('skill_llm.request_summary',side_effect=summary),patch('skill_llm.public_excerpt',side_effect=LLMError('공개 본문을 가져오지 못했습니다. 본문을 직접 붙여넣으세요.')):
    app=create_app(sys.argv[1],'http://127.0.0.1:4311')
    app.extensions['auth'].set_password('browser-test-only-12345')
    serve(app,host='127.0.0.1',port=4311)
