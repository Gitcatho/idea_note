from contextlib import closing
import json,os,socket,tempfile,time,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from webapp import create_app
from skill_llm import SkillLLM,LLMError,canonical_url,public_excerpt,summary_draft,request_summary,MAX_HTML

TEXT='Synthetic AI skill uses retrieval and evaluation to organize source material. This is test content only.'
URL='https://www.instagram.com/p/SyntheticPost/'
def result(text=TEXT):return {'supported':True,'title':'합성 AI 요약','summary':'검색과 평가 방법을 정리합니다.','points':['출처 확인'],'steps':['작은 합성 자료로 확인'],'cautions':['실제 결과는 별도 확인'],'tags':['AI','평가'],'evidence':text[:65]}

class SkillLLMTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.origin='https://test.example';self.app=create_app(self.temp.name,self.origin,testing=True);self.auth=self.app.extensions['auth'];self.auth.set_password('synthetic-admin-password');self.service=self.app.extensions['skill_llm']
    def tearDown(self):self.temp.cleanup()
    def test_url_allowlist_and_pinned_public_fetch(self):
        self.assertEqual(canonical_url(URL+'?secret=not-forwarded#part'),URL)
        self.assertEqual(canonical_url('https://www.threads.com/@sample/post/Ab123'),'https://www.threads.com/@sample/post/Ab123/')
        for url in ['http://www.instagram.com/p/test/','https://www.instagram.com.evil.test/p/test/','https://www.instagram.com@127.0.0.1/p/test/','https://127.0.0.1/p/test/','https://www.instagram.com:444/p/test/','https://www.instagram.com/accounts/login/','file:///etc/passwd','https://www.threads.com/@sample/post/../private']:
            with self.assertRaises(LLMError):canonical_url(url)
        with patch('skill_llm.socket.getaddrinfo',return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',443))]),patch('skill_llm.PublicHTTPS') as connection:
            with self.assertRaises(LLMError):public_excerpt(URL)
            connection.assert_not_called()
        response=Mock(status=200);response.getheader.side_effect=lambda key,default='':{'Content-Type':'text/html','Content-Encoding':'identity'}.get(key,default);response.read.return_value=('<meta property="og:description" content="'+TEXT+'">').encode()
        connection=Mock();connection.getresponse.return_value=response
        with patch('skill_llm.socket.getaddrinfo',return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',443))]),patch('skill_llm.PublicHTTPS',return_value=connection) as factory:
            self.assertEqual(public_excerpt(URL),TEXT);factory.assert_called_once_with('www.instagram.com','93.184.216.34')
            response.read.return_value=b'x'*(MAX_HTML+1)
            with self.assertRaises(LLMError):public_excerpt(URL)
            response.status=302;response.getheader.side_effect=lambda key,default='':'https://127.0.0.1/private' if key=='Location' else default
            with self.assertRaises(LLMError):public_excerpt(URL)

    def test_dual_stack_uses_ipv4_and_stops_after_bounded_metadata(self):
        response=Mock(status=200);response.getheader.side_effect=lambda key,default='':{'Content-Type':'text/html','Content-Encoding':'identity'}.get(key,default)
        description='개인정보 없는 합성 게시글에서 AI 검색과 평가 기준을 정리하고 근거를 확인하는 학습 방법입니다.'
        prefix=('<meta property="og:description" content="'+description+'">').encode()
        split=prefix.index('개'.encode())+1
        # The unread page tail is larger than the cap; metadata spans UTF-8 chunks.
        response.read.side_effect=[prefix[:split],prefix[split:],b'x'*(MAX_HTML+1)]
        connection=Mock();connection.getresponse.return_value=response
        addresses=[(socket.AF_INET6,socket.SOCK_STREAM,6,'',('2606:4700:4700::1111',443,0,0)),(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',443))]
        with patch('skill_llm.socket.getaddrinfo',return_value=addresses),patch('skill_llm.PublicHTTPS',return_value=connection) as factory:
            self.assertEqual(public_excerpt(URL),description)
            factory.assert_called_once_with('www.instagram.com','93.184.216.34')
            self.assertEqual(response.read.call_count,2)
            self.assertTrue(all(call.args[0]<=8192 for call in response.read.call_args_list))
            connection.close.assert_called_once()

    def test_validation_evidence_and_no_auto_save(self):
        with patch.dict(os.environ,{'OPENAI_MODEL':'synthetic-model','OPENAI_API_KEY':'synthetic-not-a-real-key'},clear=True),patch('skill_llm.request_summary',side_effect=lambda model,key,text,url:result(text)) as request,patch('skill_llm.public_excerpt',return_value=TEXT) as fetch:
            draft=self.service.draft(1,{'url':URL,'body':TEXT,'consent':True});fetch.assert_not_called();self.assertEqual(draft['kind'],'skill')
            self.assertIn('사용자가 붙여넣은 본문',draft['notes']);self.assertEqual(self.app.extensions['store'].list(),[])
            self.service.draft(1,{'url':URL,'consent':True});fetch.assert_called_once_with(URL)
            with self.assertRaises(LLMError):self.service.draft(1,{'url':URL,'body':TEXT,'consent':False})
            with self.assertRaises(LLMError):self.service.draft(1,{'url':URL,'body':'x'*20001,'consent':True})
        invalid=result();invalid['evidence']='invented evidence does not appear in provided text'
        with self.assertRaises(LLMError):summary_draft(invalid,TEXT,URL,'test')
        invalid=result();invalid['supported']=False
        with self.assertRaises(LLMError):summary_draft(invalid,TEXT,URL,'test')
        with patch.dict(os.environ,{},clear=True),patch('skill_llm.public_excerpt') as fetch:
            with self.assertRaises(LLMError) as failure:self.service.draft(1,{'url':URL,'body':TEXT,'consent':True})
            self.assertEqual(failure.exception.status,503);fetch.assert_not_called()

    def test_source_failure_does_not_call_openai_and_quota_persists(self):
        with patch.dict(os.environ,{'OPENAI_MODEL':'synthetic-model','OPENAI_API_KEY':'synthetic-not-a-real-key'},clear=True),patch('skill_llm.public_excerpt',side_effect=LLMError('본문을 붙여넣으세요.')),patch('skill_llm.request_summary') as request:
            with self.assertRaises(LLMError):self.service.draft(2,{'url':URL,'consent':True})
            request.assert_not_called()
        for _ in range(19):self.service.reserve(2)
        restarted=SkillLLM(self.auth)
        with self.assertRaises(LLMError) as failure:restarted.reserve(2)
        self.assertEqual(failure.exception.status,429)
        self.service.lock.acquire()
        try:
            with patch.dict(os.environ,{'OPENAI_MODEL':'synthetic-model','OPENAI_API_KEY':'synthetic-not-a-real-key'},clear=True):
                with self.assertRaises(LLMError) as failure:self.service.draft(1,{'url':URL,'body':TEXT,'consent':True})
                self.assertEqual(failure.exception.status,429)
        finally:self.service.lock.release()

    def test_responses_payload_is_bounded_no_store_and_errors_hide_credentials(self):
        response=Mock(status=200);response.read.return_value=json.dumps({'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(result())}]}]}).encode()
        connection=Mock();connection.getresponse.return_value=response
        with patch('skill_llm.http.client.HTTPSConnection',return_value=connection) as factory:
            self.assertEqual(request_summary('synthetic-model','synthetic-not-a-real-key',TEXT,URL),result())
            self.assertEqual(factory.call_args.args[0],'api.openai.com')
            args=connection.request.call_args;self.assertEqual(args.args[:2],('POST','/v1/responses'))
            payload=json.loads(args.kwargs['body']);self.assertFalse(payload['store']);self.assertEqual(payload['max_output_tokens'],2000);self.assertTrue(payload['text']['format']['strict']);self.assertNotIn('tools',payload)
            quotes=payload['text']['format']['schema']['properties']['evidence']['enum'];self.assertTrue(quotes);self.assertTrue(all(10<=len(quote)<=100 and quote in TEXT for quote in quotes))
            self.assertEqual(set(json.loads(payload['input'])),{'source_url','excerpt'})
            response.status=401
            with self.assertRaises(LLMError) as failure:request_summary('synthetic-model','synthetic-not-a-real-key',TEXT,URL)
            self.assertNotIn('synthetic-not-a-real-key',str(failure.exception))

    def test_api_requires_approved_skill_permission_and_draft_only(self):
        self.auth.register('llm_member','synthetic-member-password','synthetic-member-password');self.auth.set_access(1,2,True,['memo'])
        client=self.app.test_client();response=client.post('/login',base_url=self.origin,headers={'Origin':self.origin},json={'username':'llm_member','password':'synthetic-member-password'});self.assertEqual(response.status_code,200)
        csrf=client.get('/api/session',base_url=self.origin).json['data']['csrf']
        def call(action):return client.post('/api/'+action,base_url=self.origin,headers={'Origin':self.origin,'X-CSRF-Token':csrf},json={'url':URL,'body':TEXT,'consent':True})
        with patch.dict(os.environ,{'OPENAI_MODEL':'synthetic-model','OPENAI_API_KEY':'synthetic-not-a-real-key'},clear=True),patch('skill_llm.request_summary',return_value=result()) as request:
            self.assertEqual(call('llm_draft').status_code,403);self.assertEqual(call('llm_status').status_code,403);request.assert_not_called()
            self.auth.set_access(1,2,True,['skill']);response=call('llm_draft');self.assertEqual(response.status_code,200);self.assertEqual(response.json['data']['kind'],'skill')
            self.assertEqual(client.post('/api/list',base_url=self.origin,headers={'Origin':self.origin,'X-CSRF-Token':csrf},json={}).json['data']['records'],[])
            self.auth.set_access(1,2,False,['skill']);self.assertEqual(call('llm_draft').status_code,403)

if __name__=='__main__':unittest.main()
