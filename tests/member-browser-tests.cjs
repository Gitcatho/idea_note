const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('child_process');
const fs=require('fs'),os=require('os'),path=require('path'),assert=require('assert');
const root=path.resolve(__dirname,'..'),data=fs.mkdtempSync(path.join(os.tmpdir(),'news-members-test-'));
const url='http://127.0.0.1:4311';let server,browser;
async function start(){server=spawn(path.join(root,'.venv-web/bin/python'),['tests/web_fixture.py',data],{cwd:root,env:{...process.env,PYTHONPATH:root},stdio:['ignore','ignore','pipe']});server.stderr.on('data',b=>process.stderr.write(b));for(let i=0;i<100;i++){try{if((await fetch(url+'/healthz')).ok)return;}catch(e){}await new Promise(r=>setTimeout(r,100));}throw Error('fixture unavailable');}
async function stop(){if(server&&server.exitCode===null)await new Promise(resolve=>{server.once('exit',resolve);server.kill();});}
(async()=>{
 await start();browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 const checks=[];
 await page.goto(url+'/login');assert.equal(await page.locator('#formTitle').textContent(),'로그인');
 await page.screenshot({path:path.join(root,'docs/member-login-mobile.png'),fullPage:true});
 await page.setViewportSize({width:1320,height:900});await page.screenshot({path:path.join(root,'docs/member-login-desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});
 const signup=async username=>{await page.goto(url+'/signup');await page.locator('#username').fill(username);await page.locator('#password').fill('synthetic-browser-password');await page.locator('#confirmation').fill('synthetic-browser-password');await page.locator('#submit').click();await page.waitForURL(url+'/login');};
 const login=async username=>{await page.locator('#username').fill(username);await page.locator('#password').fill('synthetic-browser-password');await page.locator('#submit').click();await page.waitForURL(url+'/');await page.waitForFunction(()=>document.querySelector('#dataRoot').textContent.includes('개인 서버'));};
 await page.locator('#switchLink').click();await page.waitForURL(url+'/signup');assert(await page.locator('#confirmationGroup').isVisible());
 await page.locator('#username').fill('browser_member_a');await page.locator('#password').fill('synthetic-browser-password');await page.locator('#confirmation').fill('wrong-password');await page.locator('#submit').click();assert((await page.locator('#error').textContent()).includes('일치하지'));
 await page.screenshot({path:path.join(root,'docs/member-signup-mobile.png'),fullPage:true});checks.push('mobile signup confirmation validation');
 await signup('browser_member_a');await login('BROWSER_MEMBER_A');checks.push('signup and case-insensitive ID login');
 await page.locator('[data-tab=memo]').click();await page.locator('#resumeAdd').click();await page.locator('[name=title]').fill('합성 회원 A 이력');await page.locator('[name=resume_university]').fill('가상 대학교');await page.locator('#save').click();await page.waitForFunction(()=>!document.querySelector('#editor').open);
 await page.reload();await page.locator('[data-tab=memo]').click();assert.equal(await page.locator('.record').count(),1);checks.push('member resume persistence');
 await page.locator('#logout').click();await page.waitForURL(url+'/login');await signup('browser_member_b');await login('browser_member_b');await page.locator('[data-tab=memo]').click();assert.equal(await page.locator('.record').count(),0);checks.push('member B cannot see A records');
 await page.locator('#settings').click();const download=page.waitForEvent('download');await page.locator('#export').click();const exported=await download;const file=path.join(data,'b-export.json');await exported.saveAs(file);assert.equal(JSON.parse(fs.readFileSync(file)).records.length,0);await page.locator('#helpClose').click();checks.push('member export contains only own records');
 await stop();await start();await page.reload();await page.waitForFunction(()=>document.querySelector('#dataRoot').textContent.includes('개인 서버'));await page.locator('[data-tab=memo]').click();assert.equal(await page.locator('.record').count(),0);checks.push('member B session and isolation survive restart');
 await page.locator('#logout').click();await page.waitForURL(url+'/login');await login('browser_member_a');await page.locator('[data-tab=memo]').click();assert.equal(await page.locator('.record').count(),1);await page.locator('.record').click();assert((await page.locator('#detailBody').textContent()).includes('가상 대학교'));await page.locator('#detailClose').click();checks.push('member A data remains intact');
 await page.locator('#logout').click();await page.waitForURL(url+'/login');await page.setViewportSize({width:320,height:740});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.goto(url+'/signup');assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));checks.push('320px login and signup no overflow');
 assert.deepEqual(errors,[]);fs.writeFileSync(path.join(root,'docs/member-browser-qa.json'),JSON.stringify({passed:checks.length,checks},null,2));console.log(JSON.stringify({passed:checks.length,checks}));
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();await stop();fs.rmSync(data,{recursive:true,force:true});});
