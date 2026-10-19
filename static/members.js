'use strict';
const manageButton=document.createElement('button');manageButton.id='manageMembers';manageButton.textContent='회원 승인 · 탭 권한';manageButton.hidden=true;document.querySelector('.side-bottom').append(manageButton);
const membersDialog=document.createElement('dialog');membersDialog.id='membersDialog';membersDialog.innerHTML='<div class="dialog-head"><div><p class="eyebrow">MEMBER ACCESS</p><h2>회원 승인 · 탭 권한</h2></div><button id="membersClose" aria-label="회원 관리 닫기">✕</button></div><p class="hint">이용을 승인하고 허용할 탭을 선택하세요. 권한을 해제해도 저장된 기록은 삭제되지 않습니다.</p><p data-feedback role="status"></p><div id="memberRows"></div>';document.body.append(membersDialog);
document.getElementById('membersClose').onclick=()=>membersDialog.close();
webReady.then(()=>{manageButton.hidden=!window.webPermissions.isAdmin;}).catch(()=>{});
async function drawMembers(){
 const members=await api('members'),root=document.getElementById('memberRows');root.replaceChildren();
 for(const member of members){
  const row=document.createElement('section');row.className='member-card';row.dataset.memberId=member.id;
  const heading=document.createElement('h3');heading.textContent=member.username;row.append(heading);
  if(member.isAdmin){const note=document.createElement('p');note.className='hint';note.textContent='관리자 · 전체 탭 이용 · 본인 권한 변경 불가';row.append(note);root.append(row);continue;}
  const status=document.createElement('p');status.className='hint';status.textContent=member.approved?'이용 승인됨':'승인 대기 또는 이용 중지';row.append(status);
  const approve=document.createElement('input');approve.type='checkbox';approve.checked=member.approved;approve.dataset.approve='';
  const label=document.createElement('label');label.className='check';label.append(approve,document.createTextNode('이용 승인'));row.append(label);
  const tabs=document.createElement('div');tabs.className='member-tabs';
  for(const [key,definition] of Object.entries(CONFIG)){
   const input=document.createElement('input');input.type='checkbox';input.value=key;input.dataset.tabGrant='';input.checked=member.tabs.includes(key);
   const label=document.createElement('label');label.className='check';label.append(input,document.createTextNode(definition[0]));tabs.append(label);
  }
  row.append(tabs);const save=document.createElement('button');save.className='primary';save.textContent='권한 저장';
  save.onclick=async()=>{save.disabled=true;try{await api('member_access',{userId:member.id,approved:approve.checked,tabs:Array.from(tabs.querySelectorAll('input:checked'),el=>el.value)});await drawMembers();toast('회원 승인과 탭 권한을 저장했습니다.');}catch(error){toast(error.message);}finally{save.disabled=false;}};
  row.append(save);root.append(row);
 }
}
manageButton.onclick=async()=>{membersDialog.showModal();try{await drawMembers();}catch(error){toast(error.message);}};
window.addEventListener('focus',()=>{if(window.webPermissions?.approved)load();});
