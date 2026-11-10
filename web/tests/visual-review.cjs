// Capture the built workbench against an existing local simulation service.
const {chromium}=require(process.env.AQUAGUARD_PLAYWRIGHT || 'playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
  const base=process.env.AQUAGUARD_BROWSER_URL, token=process.env.AQUAGUARD_C_TOKEN;
  if(!base || !token || !['localhost','127.0.0.1'].includes(new URL(base).hostname))throw new Error('Local URL and test token required');
  const output=path.resolve(process.env.AQUAGUARD_BROWSER_EVIDENCE || 'audit/visual-review');
  fs.mkdirSync(output,{recursive:true});
  const browser=await chromium.launch({headless:true,executablePath:process.env.AQUAGUARD_CHROMIUM || undefined});
  const page=await browser.newPage();
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  try{
    await page.goto(base);
    await page.getByLabel('实验访问凭据').fill(token);
    await page.getByRole('button',{name:'连接',exact:true}).click();
    await page.locator('.sensor-grid').waitFor({timeout:45000});
    for(const width of [1280,768,390]){
      await page.setViewportSize({width,height:900});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
      await page.screenshot({path:path.join(output,`overview-${width}.png`),fullPage:true});
    }
    await page.setViewportSize({width:1280,height:900});
    await page.route('**/api/devices/*/live',route=>route.fulfill({status:503,contentType:'application/json',body:'{"code":"STALE"}'}));
    await page.getByRole('button',{name:'刷新',exact:true}).click();
    await page.getByText('传感快照：不可用或证据已过期').waitFor();
    assert.equal(await page.locator('.sensor-grid').count(),0);
    await page.screenshot({path:path.join(output,'overview-unavailable.png'),fullPage:true});
    await page.getByRole('button',{name:'连接设置',exact:true}).click();
    await page.getByRole('button',{name:'断开',exact:true}).click();
    await page.getByRole('heading',{name:'连接本地业务服务'}).waitFor();
    assert.equal(await page.locator('.sensor-grid').count(),0);
    await page.screenshot({path:path.join(output,'disconnected.png'),fullPage:true});
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'PASS',viewports:[1280,768,390],errors,at:new Date().toISOString()},null,2));
    console.log('PASS: final viewport, unavailable and disconnected review');
  }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
