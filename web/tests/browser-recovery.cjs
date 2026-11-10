// Real backend expiry/recovery only: no route interception or fabricated replies.
const {chromium}=require(process.env.AQUAGUARD_PLAYWRIGHT || 'playwright');
const fs=require('node:fs');
const path=require('node:path');
(async()=>{
  const base=process.env.AQUAGUARD_BROWSER_URL;
  if(!base || !['127.0.0.1','localhost'].includes(new URL(base).hostname)) throw Error('local URL required');
  const out=process.env.AQUAGUARD_BROWSER_EVIDENCE;
  fs.mkdirSync(out,{recursive:true});
  const browser=await chromium.launch({headless:true,executablePath:process.env.AQUAGUARD_CHROMIUM});
  const page=await browser.newPage({viewport:{width:1280,height:900}});
  const checks=[],errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  try {
    await page.goto(base);
    await page.getByLabel('实验访问凭据').fill(process.env.AQUAGUARD_C_TOKEN);
    await page.getByRole('button',{name:'连接',exact:true}).click();
    await page.locator('.grid').waitFor({timeout:60000});
    checks.push('MQTT overview initially available');
    await page.screenshot({path:path.join(out,'initial.png'),fullPage:true});
    await page.getByText('传感快照：不可用或证据已过期',{exact:true}).waitFor({timeout:60000});
    if(await page.locator('.grid').count()) throw Error('stale values still visible');
    checks.push('real stopped input expires and hides sensor values');
    await page.screenshot({path:path.join(out,'expired.png'),fullPage:true});
    await page.locator('.grid').waitFor({timeout:90000});
    checks.push('same browser recovers after consumer restart and new MQTT boot');
    await page.screenshot({path:path.join(out,'recovered.png'),fullPage:true});
    if(errors.length) throw Error('browser errors');
    fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({status:'PASS',checks,errors},null,2));
  } catch(error) {
    fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({status:'FAIL',checks,errors,error:error.message},null,2));
    await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});
    throw error;
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
