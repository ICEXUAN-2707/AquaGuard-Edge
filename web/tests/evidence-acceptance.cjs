const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict'),fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
 try{
  const page=await browser.newPage();const errors=[],checks=[];page.on('pageerror',e=>errors.push(e.message));
  let eventState='active',evaluationError=false,writes=0;
  await page.route('**/api/**',async route=>{
   const request=route.request(),url=new URL(request.url());
   if(request.method()!=='GET'){writes++;await route.abort();return}
   if(/\/experiments\/[^/]+\/evaluations$/.test(url.pathname)){
    await route.fulfill({status:evaluationError?503:200,contentType:'application/json',body:JSON.stringify(evaluationError?{}:{items:[]})});return
   }
   if(/\/events\/[^/]+$/.test(url.pathname)){
    const response=await route.fetch(),body=await response.json();
    Object.assign(body.event,{lifecycle:eventState==='closed'?'CLOSED':'OPEN',ack_status:eventState==='active'?'UNACKNOWLEDGED':'ACKNOWLEDGED',physical_status:eventState==='active'?'ACTIVE':eventState==='unknown'?'UNKNOWN':'CLEARED'});
    await route.fulfill({response,json:body});return
   }
   await route.continue();
  });
  await page.goto(process.env.UI_BASE_URL||'http://127.0.0.1:8061/c.html');
  await page.getByLabel('实验访问凭据').fill(process.env.UI_TOKEN||'ui-fixture-only-token-20261121');await page.getByRole('button',{name:'连接',exact:true}).click();await page.locator('.sensor-grid').waitFor();
  await page.getByRole('button',{name:'事件确认',exact:true}).click();await page.locator('.event-card').first().click();await page.locator('.operation-guide').waitFor();
  const ack=page.getByRole('button',{name:'我已知晓',exact:true}),close=page.getByRole('button',{name:'关闭已恢复事件',exact:true});
  assert.equal(await ack.isDisabled(),false);assert.equal(await close.isDisabled(),true);assert.match(await page.locator('.operation-guide').innerText(),/需要先确认/);checks.push('active unacknowledged event cannot close');
  async function refresh(state,text){eventState=state;await page.getByRole('button',{name:'刷新事件',exact:true}).click();await page.waitForFunction(text=>document.querySelector('.operation-guide')?.textContent.includes(text),text)}
  await refresh('unknown','等待物理清除候选');assert.equal(await close.isDisabled(),true);checks.push('unknown is not recovery');
  await refresh('cleared','由服务端校验');assert.equal(await ack.isDisabled(),true);assert.equal(await close.isDisabled(),false);checks.push('acknowledged recovered event may request server validation');
  await refresh('closed','事件已关闭，无需');assert.equal(await ack.isDisabled(),true);assert.equal(await close.isDisabled(),true);checks.push('closed event disables both operations');
  await page.locator('.event-timeline details').first().locator('summary').click();assert.match(await page.locator('.event-timeline').innerText(),/证据：/);checks.push('timeline evidence disclosure');
  await page.getByRole('button',{name:'实验诊断',exact:true}).click();await page.getByRole('button',{name:'查询',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.diagnostic-summary')?.textContent.includes('尚无报告'));
  assert.match(await page.locator('.diagnostic-summary').innerText(),/不等于验收通过/);checks.push('run and evidence do not imply evaluation acceptance');
  evaluationError=true;await page.getByRole('button',{name:'查询',exact:true}).click();await page.waitForFunction(()=>document.querySelector('.diagnostic-summary')?.textContent.includes('查询未完成'));checks.push('evaluation failure remains distinct from missing report');
  for(const width of [1280,768,390]){await page.setViewportSize({width,height:900});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth))}
  await page.getByLabel('实验ID',{exact:true}).fill('missing-stage3-trial');assert.equal(await page.locator('.diagnostic-summary').count(),0);checks.push('changed trial clears previous diagnostic summary');
  assert.equal(writes,0);assert.deepEqual(errors,[]);
  const result={scope:'isolated fixture with read-only response overrides; no lifecycle mutation',checks,widths:[1280,768,390],writes,pageErrors:errors};if(process.env.UI_RESULT)fs.writeFileSync(process.env.UI_RESULT,JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
