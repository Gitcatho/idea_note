import tempfile
import unittest
from pathlib import Path
from resume import validate_resume
from store import Store

class ResumeTests(unittest.TestCase):
    def profile(self):
        return {'nameKo':'가상 이름','nameEn':'Sample Name','nameHanja':'合成', 'address':'가상 주소',
                'militaryStatus':'completed','discharge':'만기전역','militaryStart':'2020-01-01','militaryEnd':'2021-01-01',
                'highSchool':'가상 고교','highStart':'2015-03-01','highEnd':'2018-02-01',
                'university':'가상 대학','department':'가상 학과','totalCredits':'130','average':'3.0','averageMax':'4.5','majorCredits':'80','majorAverage':'3.2','majorAverageMax':'4.5',
                'courses':[{'name':'합성 과목','grade':'4.0','maxGrade':'4.5'}],
                'certificates':[{'name':'합성 자격','organization':'가상 기관','date':'2022-01-01'}],
                'careers':[{'company':'가상 회사','department':'연구','position':'개발','start':'2023-01-31','end':'2024-02-29'}],
                'awards':[{'competition':'가상 대회','organization':'가상 기관','award':'합성 상','month':'2024-02'}],
                'activities':[{'organization':'가상 단체','start':'2020-01-01','end':'2020-04-01','description':'합성 활동'}]}

    def test_save_edit_restart_and_backup_roundtrip(self):
        data=self.profile()
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder);store.save({'kind':'memo','title':'합성 이력','memoType':'resume','resumeData':data,'resumeEducation':'기존 자유 입력 보존'})
            row=store.list()[0];row['resumeData']['careers'].append({'company':'추가 가상 회사'})
            store.save(row)
            exported=Store(folder).export();restored=Store(Path(folder)/'restored')
            self.assertEqual(restored.merge(exported),1)
            actual=restored.list()[0]
            self.assertEqual(actual['resumeData'],row['resumeData'])
            self.assertEqual(actual['resumeEducation'],'기존 자유 입력 보존')
            self.assertEqual(restored.merge(exported),0)

    def test_invalid_input_rejected(self):
        changes=[{'militaryEnd':'2019-01-01'}, {'highStart':'2024-02-30'}, {'average':'5'}, {'averageMax':'0'}, {'majorCredits':'999'}, {'militaryStatus':'unknown-type'}, {'nameKo':['bad']}, {'extra':'bad'}, {'courses':[{}]*4}, {'certificates':[{}]*51}, {'average':'NaN'}, {'awards':[{'month':'2024-13'}]}, {'careers':[{'start':'2024-12-01','end':'2024-01-01'}]}, {'certificates':[{'date':'20240101'}]}, {'courses':[{'grade':'3'}]}]
        for change in changes:
            data=self.profile();data.update(change)
            with self.subTest(change=next(iter(change))):
                with self.assertRaises(ValueError):validate_resume(data)
        for bad in (None,[],{'careers':[None]}, {'activities':[{'description':'x'*10001}]}):
            with self.assertRaises(ValueError):validate_resume(bad)

    def test_partial_and_empty_sections(self):
        self.assertEqual(validate_resume({'courses':[{}],'careers':[{}],'nameKo':'  '}),{})
        self.assertEqual(validate_resume({'careers':[{'company':'가상 회사','start':'2024-01-01'}]}),{'careers':[{'company':'가상 회사','start':'2024-01-01'}]})

if __name__=='__main__':unittest.main()
