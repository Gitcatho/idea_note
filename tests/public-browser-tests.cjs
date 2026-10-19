// Disposable QA container only. Password stays in memory and SSH stdin.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawnSync}=require('child_process');
const crypto=require('crypto'),assert=require('assert'),fs=require('fs'),path=require('path');
const password=crypto.randomBytes(32).toString('base64url');
const origin='https://pi-home.tail5eceb8.ts.net:8443';
const publicIP=process.env.FUNNEL_PUBLIC_IP;
if(!publicIP||!/^\d+\.\d+\.\d+\.\d+$/.test(publicIP))throw Error('Set verified public Funnel IPv4');
const seeded=spawnSync('ssh',['-o','BatchMode=yes','-o','ConnectTimeout=10','-o','IdentitiesOnly=yes','-i','/Users/jinho/.ssh/id_ed25519','jinho@100.84.155.62',"docker exec -i news-idea-qa python -c 'import sys; from webapp import Auth; Auth(\"/data\").set_password(sys.stdin.read())'"],{input:password,encoding:'utf8'});
if(seeded.status!==0)throw Error('QA password setup failed');
let browser;
(async()=>{
 browser=await chromium.launch({headless:true,args:[`--host-resolver-rules=MAP pi-home.tail5eceb8.ts.net ${publicIP}`]});
 const context=await browser.newContext({viewport:{width:390,height:844}}),page=await context.newPage();
 const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
 await page.goto(origin);assert(page.url().endsWith('/login'));
 await page.locator('#username').fill('admin');await page.locator('#password').fill(password);await page.locator('#login button').click();await page.waitForURL(origin+'/');
 await page.waitForFunction(()=>document.querySelector('#dataRoot').textContent.includes('개인 서버'));
 const checks=['public relay TLS and mobile login'];
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 for(const kind of ['job','company','memo','contest','skill']){await page.locator(`[data-tab=${kind}]`).click();assert(await page.locator('#title').textContent());}
 checks.push('five tabs on public HTTPS');
 await page.locator('[data-tab=memo]').click();await page.locator('#add').click();await page.locator('[name=title]').fill('공개 경로 QA 메모');await page.locator('[name=notes]').fill('합성 데이터만 사용');await page.locator('#save').click();await page.waitForFunction(()=>!document.querySelector('#editor').open);
 await page.locator('#search').fill('공개 경로 QA 메모');await page.locator('.record').click();await page.locator('#edit').click();await page.locator('[name=title]').fill('공개 경로 수정 메모');await page.locator('#save').click();await page.waitForFunction(()=>!document.querySelector('#editor').open);
 await page.locator('#search').fill('공개 경로 수정 메모');await page.locator('.record').click();await page.locator('#delete').click();await page.waitForFunction(()=>!document.querySelector('#detail').open);await page.locator('#trashTab').click();await page.locator('.record').click();await page.locator('#edit').click();await page.waitForFunction(()=>!document.querySelector('#detail').open);
 checks.push('public HTTPS create edit search trash restore');
 await page.locator('#settings').click();const download=page.waitForEvent('download');await page.locator('#export').click();const downloaded=await download;assert.equal(downloaded.suggestedFilename(),'News_idea-backup.json');await page.locator('#helpClose').click();
 checks.push('authenticated download');
 const kst=await page.evaluate(()=>kstDay(new Date('2026-10-12T15:00:00Z')));assert.equal(kst,'2026-10-13');checks.push('KST boundary');
 await page.locator('[data-tab=job]').click();await page.screenshot({path:path.join(__dirname,'../docs/web-public-mobile-qa.png'),fullPage:true});
 const cookies=await context.cookies();await page.locator('#logout').click();await page.waitForURL(origin+'/login');await context.addCookies(cookies);
 // Browser fetch uses the pinned public DNS route, rather than APIRequestContext DNS.
 assert.equal(await page.evaluate(async()=> (await fetch('/api/session')).status),401);checks.push('public logout cookie replay rejected');
 assert.deepEqual(errors,[]);
 const result={origin,route:'public Funnel relay pinned independently of MagicDNS',publicIP,passed:checks.length,checks,kst};
 fs.writeFileSync(path.join(__dirname,'../docs/web-public-browser-qa.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();});
