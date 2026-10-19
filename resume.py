"""Validate optional structured resume data without logging personal contents."""
import datetime as dt
from decimal import Decimal, InvalidOperation
import re

SCALAR_FIELDS = {
    'nameKo':200, 'nameEn':200, 'nameHanja':200, 'address':1000,
    'militaryStatus':30, 'discharge':100, 'militaryStart':10, 'militaryEnd':10,
    'highSchool':200, 'highStart':10, 'highEnd':10,
    'university':200, 'department':200, 'universityStart':10, 'universityEnd':10,
    'totalCredits':10, 'average':10, 'averageMax':10, 'majorCredits':10,
    'majorAverage':10, 'majorAverageMax':10,
}
ROW_FIELDS = {
    'courses': {'name':200, 'grade':10, 'maxGrade':10},
    'certificates': {'name':200, 'organization':200, 'date':10},
    'careers': {'company':200, 'department':200, 'position':200, 'start':10, 'end':10},
    'awards': {'competition':300, 'organization':200, 'award':300, 'month':7},
    'activities': {'organization':200, 'start':10, 'end':10, 'description':10000},
}

def strings(data, fields):
    if not isinstance(data, dict) or set(data)-set(fields):
        raise ValueError('이력 정보 항목 형식을 확인하세요.')
    result={}
    for key, limit in fields.items():
        value=data.get(key,'')
        if not isinstance(value,str) or len(value)>limit:
            raise ValueError(f'{key}: 입력 형식/길이를 확인하세요.')
        value=value.strip()
        if value:
            result[key]=value
    return result

def date(value):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
        raise ValueError('날짜 형식을 확인하세요.')
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        raise ValueError('유효한 날짜를 선택하세요.') from None

def period(data,start,end):
    first=date(data[start]) if data.get(start) else None
    last=date(data[end]) if data.get(end) else None
    if first and last and last<first:
        raise ValueError('종료 날짜는 시작 날짜보다 빠를 수 없습니다.')

def number(value):
    if not re.fullmatch(r'\d+(?:\.\d+)?',value):
        raise ValueError('학점은 0 이상의 숫자로 입력하세요.')
    try:
        result=Decimal(value)
    except InvalidOperation:
        raise ValueError('학점 형식을 확인하세요.') from None
    if not result.is_finite() or result>1000:
        raise ValueError('학점 범위를 확인하세요.')
    return result

def grade(data,key,maximum):
    value=number(data[key]) if data.get(key) else None
    limit=number(data[maximum]) if data.get(maximum) else None
    if limit is not None and limit<=0:
        raise ValueError('최대 학점은 0보다 커야 합니다.')
    if value is not None and limit is None:
        raise ValueError('평점/과목 성적의 최대 학점도 입력하세요.')
    if value is not None and limit is not None and value>limit:
        raise ValueError('평점/성적이 최대 학점보다 큽니다.')

def validate_resume(data):
    if not isinstance(data,dict) or set(data)-set(SCALAR_FIELDS)-set(ROW_FIELDS):
        raise ValueError('이력 정보 형식을 확인하세요.')
    result=strings({k:v for k,v in data.items() if k in SCALAR_FIELDS},SCALAR_FIELDS)
    if result.get('militaryStatus','') not in ('','completed','notCompleted','exempt','serving'):
        raise ValueError('군필 구분을 확인하세요.')
    for start,end in [('militaryStart','militaryEnd'),('highStart','highEnd'),('universityStart','universityEnd')]:
        period(result,start,end)
    for key in ('totalCredits','majorCredits'):
        if result.get(key): number(result[key])
    if result.get('totalCredits') and result.get('majorCredits') and number(result['majorCredits'])>number(result['totalCredits']):
        raise ValueError('전공 학점이 총 학점보다 큽니다.')
    grade(result,'average','averageMax');grade(result,'majorAverage','majorAverageMax')
    for group,fields in ROW_FIELDS.items():
        rows=data.get(group,[])
        if not isinstance(rows,list) or len(rows)>(3 if group=='courses' else 50):
            raise ValueError('과목은 최대 3개, 기타 이력은 항목별 최대 50개입니다.')
        cleaned=[]
        for row in rows:
            entry=strings(row,fields)
            if not entry: continue
            if group=='courses':grade(entry,'grade','maxGrade')
            if group=='certificates' and entry.get('date'):date(entry['date'])
            if group in ('careers','activities'):period(entry,'start','end')
            if group=='awards' and entry.get('month'):
                if not re.fullmatch(r'\d{4}-\d{2}',entry['month']):
                    raise ValueError('수상 년월 형식을 확인하세요.')
                date(entry['month']+'-01')
            cleaned.append(entry)
        if cleaned:result[group]=cleaned
    return result
