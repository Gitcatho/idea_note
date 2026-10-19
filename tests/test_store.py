import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from store import Store, validate, RESUME_FIELDS
from desktop import Bridge
from seeds import initialize

class StoreTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(); self.store=Store(self.temp.name)
 def tearDown(self):self.temp.cleanup()
 def record(self,kind='job',**kw):return dict(kind=kind,title='테스트',mode='unknown',**kw)
 def test_crud_all_tabs_restart_restore(self):
  for kind in ('job','company','memo','contest','skill'):
   id_=self.store.save(self.record(kind,notes='한글 개인 메모'))
   r=next(r for r in self.store.list() if r['id']==id_);r['title']='수정';self.store.save(r)
   self.store.trash(id_,True);self.assertTrue(next(r for r in self.store.list() if r['id']==id_)['deleted'])
   self.store.trash(id_,False)
  self.assertEqual(len(Store(self.temp.name).list()),5)
  self.assertTrue(all(r['title']=='수정' and not r['deleted'] for r in self.store.list()))
 def test_validation(self):
  for changes in ({'title':''},{'url':'javascript:alert(1)'},{'deadline':'2026-02-30','mode':'dated'},{'mode':'dated'},{'status':'made-up'},{'schedules':'bad line'},{'deadlineTime':'25:00','deadline':'2026-10-13','mode':'dated'}):
   r=self.record();r.update(changes)
   with self.assertRaises(ValueError):self.store.save(r)
 def test_rolling_drops_stale_date(self):
  r=self.record();r.update(mode='rolling',deadline='2026-01-01',deadlineTime='12:00');self.assertEqual(validate(r)['deadline'],'')
 def test_atomic_import_dedup(self):
  self.store.save(self.record());data=self.store.export();self.assertEqual(self.store.merge(data),0)
  bad=dict(data);bad['records']=data['records']+[{'id':'bad','kind':'job','title':''}]
  with self.assertRaises(ValueError):self.store.merge(bad)
  self.assertEqual(len(self.store.list()),1)
 def test_backup_export_roundtrip(self):
  self.store.save(self.record());backup=self.store.backup();data=json.loads(Path(backup).read_text());second=Store(Path(self.temp.name)/'second');self.assertEqual(second.merge(data),1)
 def test_deleted_edit_rejected(self):
  id_=self.store.save(self.record());r=self.store.list()[0];self.store.trash(id_,True)
  with self.assertRaises(ValueError):self.store.save(r)
 def test_bridge_error_safe(self):
  bridge=Bridge(self.store);self.assertFalse(bridge.dispatch('save',{'kind':'memo','title':''})['ok']);self.assertFalse(bridge.dispatch('invalid')['ok'])
 def test_official_seed_idempotence_multiple_deadlines(self):
  initialize(self.store);initialize(self.store);self.assertEqual(len(self.store.list()),4);self.assertTrue(any(r['schedules'] for r in self.store.list()))
 def test_empty_title_no_row(self):
  self.assertFalse(Bridge(self.store).dispatch('save',dict(kind='job',title=''))['ok'])
 def test_resume_fields_edit_backup_restore(self):
  fields={key:'합성 이력서 정보 '+key for key in RESUME_FIELDS}
  id_=self.store.save(self.record('memo',notes='기존 자유 메모',**fields))
  row=self.store.list()[0];row['title']='편집';self.store.save(row)
  self.assertEqual(self.store.list()[0]['notes'],'기존 자유 메모')
  data=json.loads(Path(self.store.backup()).read_text())
  restored=Store(Path(self.temp.name)/'restored');self.assertEqual(restored.merge(data),1)
  actual=Store(restored.root).list()[0]
  for key,value in fields.items():self.assertEqual(actual[key],value)
  self.assertEqual(actual['id'],id_);self.assertEqual(restored.merge(data),0)
 def test_resume_fields_validation_and_legacy(self):
  self.assertEqual(validate(self.record('memo',memoType='resume'))['memoType'],'resume')
  with self.assertRaises(ValueError):validate(self.record('memo',memoType='invalid'))
  legacy=self.record('memo',notes='일반 메모');self.store.save(legacy)
  self.assertEqual(self.store.list()[0]['notes'],'일반 메모')
  for key,limit in RESUME_FIELDS.items():
   for invalid in ([],None,'x'*(limit+1)):
    with self.assertRaises(ValueError):validate(self.record('memo',**{key:invalid}))
  self.assertNotIn('resumeEducation',validate(self.record('job',resumeEducation='다른 탭')))

if __name__=='__main__':unittest.main()
