const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('assert'),fs=require('fs'),path=require('path');
const origin='https://pi-home.tail5eceb8.ts.net:8443',publicIP=process.env.FUNNEL_PUBLIC_IP;
if(!publicIP||!/^\d+\.\d+\.\d+\.\d+$/.test(publicIP))throw Error('Set verified public Funnel IPv4');
let browser;
(async()=>{
 browser=await chromium.launch({headless:true,args:[`--host-resolver-rules=MAP pi-home.tail5eceb8.ts.net ${publicIP}`]});
 const page=await browser.newPage({viewport:{width:390,height:844}});
 await page.goto(origin);assert(page.url().endsWith('/login'));assert.equal(await page.title(),'News_idea 로그인');
 const results=await page.evaluate(async()=>{
  const statuses={};
  for(const action of ['list','save','trash','restore','export','import','backup','session'])statuses[action]=(await fetch('/api/'+action,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})).status;
  const files={};for(const name of ['auth.sqlite3','news-idea.sqlite3','backups/test.json','attachments/test','assets/app.js'])files[name]=(await fetch('/'+name)).url.endsWith('/login');
  const health=await fetch('/healthz');
  return {statuses,files,health:health.status};
 });
 for(const status of Object.values(results.statuses))assert.equal(status,401);
 for(const redirected of Object.values(results.files))assert(redirected);
 assert.equal(results.health,200);
 await page.screenshot({path:path.join(__dirname,'../docs/web-public-login.png'),fullPage:true});
 const result={origin,publicIP,route:'public Funnel relay; production container',loginPage:true,...results};
 fs.writeFileSync(path.join(__dirname,'../docs/web-production-public-qa.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();});
