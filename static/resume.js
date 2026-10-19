'use strict';
window.Resume=(()=>{
 const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const field=(key,label,type='text',max=200)=>({key,label,type,max});
 const sections=[
  ['이름·주소',[field('nameKo','한글 이름'),field('nameEn','영문 이름'),field('nameHanja','한자 이름'),field('address','주소','textarea',1000)]],
  ['병역',[field('militaryStatus','군필 구분','military'),field('discharge','전역 구분 (예: 만기전역)','text',100),field('militaryStart','복무 시작일','date'),field('militaryEnd','복무 종료일','date')]],
  ['고등학교',[field('highSchool','고등학교명'),field('highStart','입학일','date'),field('highEnd','졸업일','date')]],
  ['대학교',[field('university','대학교명'),field('department','학과'),field('universityStart','입학일','date'),field('universityEnd','졸업일','date'),field('totalCredits','총 이수 학점','number'),field('average','평균 학점','number'),field('averageMax','전체 평점 만점','number'),field('majorCredits','전공 이수 학점','number'),field('majorAverage','전공 평균 학점','number'),field('majorAverageMax','전공 평점 만점','number')]],
 ];
 const groups={
  courses:{label:'성적이 가장 좋은 과목 3가지',fields:[field('name','과목명'),field('grade','본인 학점','number'),field('maxGrade','최대 학점','number')]},
  certificates:{label:'자격증',fields:[field('name','자격증명'),field('organization','기관명'),field('date','취득일','date')]},
  careers:{label:'경력사항',fields:[field('company','기업명'),field('department','부서명'),field('position','직책'),field('start','시작일','date'),field('end','종료일','date')]},
  awards:{label:'수상기록',fields:[field('competition','대회명'),field('organization','기관명'),field('award','수상명'),field('month','수상 년월','month')]},
  activities:{label:'대외활동',fields:[field('organization','단체명'),field('start','시작일','date'),field('end','종료일','date'),field('description','활동내용','textarea',10000)]},
 };
 const military={'':'미지정',completed:'군필',notCompleted:'미필',exempt:'면제',serving:'복무 중'};
 let root,baseline='{}',enabled=false;
 function input(f,value='',prefix=''){
  const id='resume_'+prefix+f.key,attrs=`name="${id}" data-field="${f.key}" aria-label="${f.label}"`;
  let control;
  if(f.type==='textarea')control=`<textarea ${attrs} maxlength="${f.max}" rows="3">${esc(value)}</textarea>`;
  else if(f.type==='military')control=`<select ${attrs}>${Object.entries(military).map(([v,l])=>`<option value="${v}" ${v===value?'selected':''}>${l}</option>`).join('')}</select>`;
  else control=`<input ${attrs} type="${f.type}" value="${esc(value)}" ${f.type==='number'?'min="0" max="1000" step="0.01"':`maxlength="${f.max}"`}>`;
  return `<label class="${f.type==='textarea'?'wide':''}">${f.label}${control}</label>`;
 }
 function period(start,end){
  if(!start||!end)return '시작일·종료일을 선택하면 기간을 계산합니다.';
  const a=new Date(start+'T00:00:00Z'),b=new Date(end+'T00:00:00Z');
  if(!Number.isFinite(+a)||!Number.isFinite(+b)||b<a)return '종료일이 시작일보다 빠릅니다.';
  const anchor=months=>{const year=a.getUTCFullYear(),month=a.getUTCMonth()+months;return new Date(Date.UTC(year,month,Math.min(a.getUTCDate(),new Date(Date.UTC(year,month+1,0)).getUTCDate())));};
  let months=(b.getUTCFullYear()-a.getUTCFullYear())*12+b.getUTCMonth()-a.getUTCMonth();
  if(anchor(months)>b)months--;
  const days=Math.round((b-anchor(months))/86400000),total=Math.round((b-a)/86400000);
  return `${Math.floor(months/12)}년 ${months%12}개월 ${days}일 · 총 ${total}일 (종료일−시작일)`;
 }
 function row(group,values={}){
  const definition=groups[group],wrapper=document.createElement('div');wrapper.className='resume-row';wrapper.dataset.row=group;
  const index=root.querySelectorAll(`[data-row="${group}"]`).length;
  wrapper.innerHTML=`<div class="form-grid">${definition.fields.map(f=>input(f,values[f.key]||'',group+'_'+index+'_')).join('')}</div>${['careers','activities'].includes(group)?'<p class="resume-duration" role="status"></p>':''}${group!=='courses'?`<button type="button" class="resume-remove" aria-label="${definition.label} 항목 삭제">항목 삭제</button>`:''}`;
  root.querySelector(`[data-group="${group}"]`).append(wrapper);
  const remove=wrapper.querySelector('.resume-remove');if(remove)remove.onclick=()=>wrapper.remove();
  wrapper.oninput=()=>{const out=wrapper.querySelector('.resume-duration');if(out)out.textContent=period(wrapper.querySelector('[data-field=start]').value,wrapper.querySelector('[data-field=end]').value);};
  wrapper.oninput();
 }
 function load(data={},active=false,legacy=false){
  if(!root){root=document.createElement('div');root.id='structuredResume';document.getElementById('resumeFields').append(root);}
  enabled=active;root.hidden=!active;
  document.querySelector('#resumeFields > .form-grid').hidden=!legacy;
  root.innerHTML=sections.map(([label,fields])=>`<section class="resume-section"><h3>${label}</h3><div class="form-grid">${fields.map(f=>input(f,data[f.key]||'')).join('')}</div></section>`).join('')+Object.entries(groups).map(([key,g])=>`<section class="resume-section"><h3>${g.label}</h3><div data-group="${key}"></div>${key==='courses'?'':`<button type="button" data-add="${key}">＋ ${g.label} 추가</button>`}</section>`).join('');
  for(const group of Object.keys(groups)){
   const rows=data[group]||[];
   for(let i=0;i<(group==='courses'?3:Math.max(1,rows.length));i++)row(group,rows[i]||{});
  }
  root.querySelectorAll('[data-add]').forEach(button=>button.onclick=()=>{
   const group=button.dataset.add;if(root.querySelectorAll(`[data-row="${group}"]`).length>=50){alert('항목별 최대 50개입니다.');return;}row(group);
  });
  root.querySelectorAll('input,select,textarea,button').forEach(el=>el.disabled=!active);
  baseline=JSON.stringify(read());
 }
 function read(){
  const data={};if(!enabled)return data;
  for(const [,fields] of sections)for(const f of fields){const v=root.querySelector(`[name="resume_${f.key}"]`).value.trim();if(v)data[f.key]=v;}
  for(const group of Object.keys(groups)){
   const rows=Array.from(root.querySelectorAll(`[data-row="${group}"]`),el=>Object.fromEntries(Array.from(el.querySelectorAll('[data-field]'),input=>[input.dataset.field,input.value.trim()]).filter(([,v])=>v)));
   const filled=rows.filter(r=>Object.keys(r).length);if(filled.length)data[group]=filled;
  }
  return data;
 }
 function view(data){
  if(!data||!Object.keys(data).length)return '';
  const item=(f,value)=>value?`<div class="resume-value"><dt>${f.label}</dt><dd>${esc(f.type==='military'?military[value]||value:value)}</dd></div>`:'';
  const fixed=sections.map(([label,fields])=>{const values=fields.map(f=>item(f,data[f.key])).join('');return values?`<section class="resume-summary"><h3>${label}</h3><dl>${values}</dl></section>`:'';}).join('');
  const repeated=Object.entries(groups).map(([key,g])=>{const rows=data[key]||[];return rows.length?`<section class="resume-summary"><h3>${g.label}</h3>${rows.map(r=>`<article><dl>${g.fields.map(f=>item(f,r[f.key])).join('')}</dl>${['careers','activities'].includes(key)?`<p class="resume-duration">${esc(period(r.start,r.end))}</p>`:''}</article>`).join('')}</section>`:'';}).join('');
  return `<div class="resume-overview">${fixed}${repeated}</div>`;
 }
 return {load,read,dirty:()=>enabled&&JSON.stringify(read())!==baseline,view,period};
})();
