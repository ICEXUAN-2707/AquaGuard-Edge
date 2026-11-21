// Run against an isolated local fixture; never writes business data.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
  const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
  const checks=[];
  try {
    const page=await browser.newPage();
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    let mode='pending';let release;
    const gate=new Promise(resolve=>{release=resolve});
    await page.route('**/api/**',async route=>{
      if(mode==='pending')await gate;
      if(mode==='unavailable'||mode==='unauthorized'||(mode==='partial'&&route.request().url().includes('/sync'))){
        await route.fulfill({status:mode==='unauthorized'?401:503,contentType:'application/json',body:'{}'});
      }else await route.continue();
    });
    await page.goto(process.env.UI_BASE_URL||'http://127.0.0.1:8061/c.html');
    assert.equal(await page.locator('.connection-dot.idle').count(),1);
    await page.keyboard.press('Tab');assert.equal(await page.locator('.skip-link').evaluate(el=>el===document.activeElement),true);
    await page.keyboard.press('Enter');assert.equal(await page.locator('main').evaluate(el=>el===document.activeElement),true);
    checks.push('disconnected state and keyboard skip link');
    async function connect(){await page.getByLabel('实验访问凭据').fill(process.env.UI_TOKEN||'ui-fixture-only-token-20261121');await page.getByRole('button',{name:'连接',exact:true}).click();}
    async function disconnect(){await page.getByRole('button',{name:'连接设置',exact:true}).click();await page.getByRole('button',{name:'断开',exact:true}).click();await page.locator('.connection-dot.idle').waitFor();}
    await connect();await page.locator('.interface-state.checking').waitFor();checks.push('credentials wait for API response');mode='available';release();
    await page.locator('.interface-state.available').waitFor();checks.push('all four APIs respond');
    for(const state of ['partial','unavailable','unauthorized']){
      await disconnect();mode=state;await connect();
      await page.locator('.interface-state.'+(state==='partial'?'partial':'unavailable')).waitFor();checks.push(state);
    }
    await disconnect();assert.equal(await page.locator('.interface-state').count(),0);checks.push('disconnect clears availability');
    assert.deepEqual(errors,[]);
    const result={scope:'isolated visual fixture; no experiment acceptance',checks,pageErrors:errors};
    if(process.env.UI_RESULT)fs.writeFileSync(process.env.UI_RESULT,JSON.stringify(result,null,2));
    console.log(JSON.stringify(result));
  }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
