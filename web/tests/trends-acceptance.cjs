const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
  const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
  try{
    const page=await browser.newPage({acceptDownloads:true});const errors=[];page.on('pageerror',e=>errors.push(e.message));
    let fail=false,liveCount=0;
    await page.route('**/api/**',async route=>{
      if(fail){await route.fulfill({status:503,contentType:'application/json',body:'{}'});return}
      if(route.request().url().endsWith('/live')){
        const response=await route.fetch();const body=await response.json();
        // Synthetic time progression validates presentation, not sensor acquisition.
        body.captured_at=new Date(Date.now()-10000+(liveCount++%2)*5000).toISOString();
        body.sensor_summary.flow.coverage_ratio=null;
        await route.fulfill({response,json:body});
      }else await route.continue();
    });
    await page.goto(process.env.UI_BASE_URL||'http://127.0.0.1:8061/c.html');
    await page.getByLabel('实验访问凭据').fill(process.env.UI_TOKEN||'ui-fixture-only-token-20261121');
    await page.getByRole('button',{name:'连接',exact:true}).click();
    await page.locator('.sensor-grid').waitFor();assert.match(await page.locator('.sensor-card').first().innerText(),/未知/);
    await page.getByRole('button',{name:'数据可视化',exact:true}).click();
    await page.locator('.coverage-chart').waitFor({timeout:15000});
    assert.match(await page.locator('.trend-scope').innerText(),/不会查询服务端历史/);
    const firstRow=page.locator('.latest-evidence tbody tr').first();assert.match(await firstRow.innerText(),/未知/);
    for(const n of [15,30,5]){
      const button=page.getByRole('button',{name:`${n} 分钟`,exact:true});await button.click();assert.equal(await button.getAttribute('aria-pressed'),'true');
    }
    const downloadPromise=page.waitForEvent('download');await page.getByRole('button',{name:'导出趋势数据'}).click();
    const download=await downloadPromise;const content=JSON.parse(fs.readFileSync(await download.path(),'utf8'));
    assert.equal(content.scope,'browser_session');assert.equal(content.time_basis,'snapshot_captured_at');assert(content.snapshots.length>=2);
    const widths=[];for(const width of [1280,768,390]){await page.setViewportSize({width,height:900});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));widths.push(width)}
    fail=true;await page.locator('.interface-state.unavailable').waitFor({timeout:15000});
    assert.equal(await page.locator('.coverage-chart').count(),0);assert.equal(await page.locator('.latest-evidence table').count(),0);
    assert.equal(await page.getByRole('button',{name:'导出趋势数据'}).isDisabled(),true);assert.deepEqual(errors,[]);
    const result={scope:'isolated fixture with synthetic UI clock and missing-value injection',checks:['invalid coverage stays unknown','two snapshots render chart','scope explanation','range selection','JSON export metadata','three viewport widths','503 hides old trend and disables export'],widths,pageErrors:errors};
    if(process.env.UI_RESULT)fs.writeFileSync(process.env.UI_RESULT,JSON.stringify(result,null,2));console.log(JSON.stringify(result));
  }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
