import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from store import Store, validate
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

if __name__=='__main__':unittest.main()
