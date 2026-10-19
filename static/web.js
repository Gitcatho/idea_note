'use strict';
// Adapt the existing desktop bridge to authenticated same-origin HTTP.
let webCSRF='';
const webReady=(async()=>{
 const response=await fetch('/api/session');
 if(response.status===401){location.replace('/login');throw Error('로그인이 필요합니다.');}
 const result=await response.json();webCSRF=result.data.csrf;
 const identity=document.getElementById('memberIdentity');if(identity)identity.textContent=result.data.username+' 님의 개인 공간';
})();
window.pywebview={api:{dispatch:async(action,payload={})=>{
 await webReady;
 if(action==='open'){
  const url=new URL(payload.url);
  if(!['http:','https:'].includes(url.protocol)||url.username||url.password)throw Error('출처 주소를 확인하세요.');
  window.open(url.href,'_blank','noopener,noreferrer');return {ok:true,data:true};
 }
 if(action==='import'){
  const file=await new Promise(resolve=>{const input=document.createElement('input');input.type='file';input.accept='.json,application/json';input.onchange=()=>resolve(input.files[0]||null);input.oncancel=()=>resolve(null);input.click();});
  if(!file)return {ok:true,data:null};
  if(file.size>20000000)throw Error('20MB 이하 파일만 지원합니다.');
  payload=JSON.parse(await file.text());
 }
 const response=await fetch('/api/'+action,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':webCSRF},body:JSON.stringify(payload)});
 if(response.status===401){location.replace('/login');throw Error('세션이 만료되었습니다.');}
 const result=await response.json();
 if(action==='export'&&result.ok){
  const url=URL.createObjectURL(new Blob([JSON.stringify(result.data,null,2)],{type:'application/json'}));
  const link=document.createElement('a');link.href=url;link.download='News_idea-backup.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);result.data='다운로드';
 }
 return result;
}}};
document.getElementById('logout').onclick=async()=>{
 await webReady;
 const response=await fetch('/logout',{method:'POST',headers:{'X-CSRF-Token':webCSRF}});
 if(response.ok||response.status===401)location.replace('/login');
 else alert('로그아웃에 실패했습니다. 연결을 확인하고 다시 시도하세요.');
};
window.addEventListener('pageshow',event=>{if(event.persisted)location.reload();});
