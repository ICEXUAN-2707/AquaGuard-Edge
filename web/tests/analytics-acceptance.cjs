const {chromium}=require(process.env.AQUAGUARD_PLAYWRIGHT||'playwright');
const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.AQUAGUARD_CHROMIUM});try{
const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto(process.env.AQUAGUARD_BROWSER_URL);
await page.getByLabel('实验访问凭据').fill(process.env.AQUAGUARD_C_TOKEN);
await page.getByRole('button',{name:'连接',exact:true}).click();
await page.getByRole('button',{name:'数据可视化',exact:true}).click();
await page.getByRole('heading',{name:'三源窗口覆盖趋势'}).waitFor();
await page.locator('.coverage-chart').waitFor({timeout:20000});
await page.getByRole('button',{name:'15 分钟',exact:true}).click();
assert.equal(await page.getByRole('button',{name:'15 分钟',exact:true}).getAttribute('aria-pressed'),'true');
const download=page.waitForEvent('download');await page.getByRole('button',{name:'导出趋势数据'}).click();await download;
await page.setViewportSize({width:390,height:844});
assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
await page.getByRole('button',{name:'连接设置',exact:true}).click();await page.getByRole('button',{name:'断开',exact:true}).click();
assert.equal(await page.locator('.coverage-chart').count(),0);assert.deepEqual(errors,[]);
console.log('PASS: live chart, range, export, mobile width, disconnect, no page errors');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
