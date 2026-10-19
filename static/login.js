'use strict';
const signup=document.body.dataset.mode==='signup';
if(signup){
 document.title='News_idea 회원가입';
 document.getElementById('formTitle').textContent='회원가입';
 document.getElementById('formDescription').textContent='아이디와 비밀번호로 개인 공간을 만드세요.';
 document.getElementById('confirmationGroup').hidden=false;
 document.getElementById('confirmation').required=true;
 document.getElementById('password').minLength=10;
 document.getElementById('password').autocomplete='new-password';
 document.getElementById('submit').textContent='가입하기';
 document.getElementById('switchText').textContent='이미 계정이 있으신가요?';
 document.getElementById('switchLink').textContent='로그인';
 document.getElementById('switchLink').href='/login';
}
document.getElementById('login').onsubmit=async event=>{
 event.preventDefault();const button=document.getElementById('submit'),error=document.getElementById('error');
 const payload={username:document.getElementById('username').value,password:document.getElementById('password').value};
 if(signup){payload.confirmation=document.getElementById('confirmation').value;if(payload.password!==payload.confirmation){error.textContent='비밀번호 확인이 일치하지 않습니다.';return;}}
 button.disabled=true;error.textContent='';
 try{
  const response=await fetch(signup?'/signup':'/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  if(response.ok){
   if(signup){document.getElementById('login').reset();error.textContent='가입 신청이 완료되었습니다. 관리자 승인 후 로그인할 수 있습니다.';location.replace('/login?pending=1');}
   else location.replace('/');
  }else{
   const result=await response.json();error.textContent=signup?result.error||'가입하지 못했습니다.':response.status===403?result.error:response.status===429?'시도가 너무 많습니다. 15분 후 다시 시도하세요.':'아이디 또는 비밀번호를 확인하세요.';
  }
 }catch(error_){error.textContent='연결을 확인하고 다시 시도하세요.';}finally{button.disabled=false;}
};

if(new URLSearchParams(location.search).has('pending'))document.getElementById('error').textContent='가입 신청이 완료되었습니다. 관리자 승인 후 로그인할 수 있습니다.';
