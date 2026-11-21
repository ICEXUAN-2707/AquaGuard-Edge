const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{const out=process.argv[2];fs.mkdirSync(out,{recursive:true});const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
let page;const errors=[];try{page=await browser.newPage();page.on('pageerror',e=>errors.push(e.message));
await page.goto(process.env.UI_BASE_URL||'http://127.0.0.1:8061/c.html');await page.getByLabel('实验访问凭据').fill(process.env.UI_TOKEN||'ui-fixture-only-token-20261121');await page.getByRole('button',{name:'连接',exact:true}).click();await page.locator('.sensor-grid').waitFor();
const rows=[];
for(const [name,key] of [['实时总览','overview'],['数据可视化','analytics'],['事件确认','events'],['实验诊断','experiment']]){
await page.getByRole('button',{name,exact:true}).click();
if(key==='events'){await page.locator('.event-card').first().click();await page.getByRole('heading',{name:'事件详情',exact:true}).waitFor();}
if(key==='experiment'){await page.getByRole('button',{name:'查询',exact:true}).click();await page.locator('.trial-name').waitFor();}
for(const width of [1280,768,390]){await page.setViewportSize({width,height:900});await page.evaluate(()=>window.scrollTo(0,0));await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));assert(await page.locator(".skip-link").evaluate(el=>el.getBoundingClientRect().bottom<0));await page.screenshot({path:path.join(out,`${key}-${width}.png`),fullPage:true});rows.push({page:key,width,noOverflow:await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)});}}
fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({scope:'frozen_simulation_visual_fixture',rows,errors},null,2));assert(rows.every(r=>r.noOverflow));assert.equal(errors.length,0);
}catch(e){fs.writeFileSync(path.join(out,'debug.json'),JSON.stringify({errors,url:page?.url(),html:page?await page.content():null},null,2));if(page)await page.evaluate(()=>window.scrollTo(0,0));await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));assert(await page.locator(".skip-link").evaluate(el=>el.getBoundingClientRect().bottom<0));await page.screenshot({path:path.join(out,'debug.png'),fullPage:true});throw e;}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
