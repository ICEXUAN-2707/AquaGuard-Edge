// Run against a fresh, running simulation service. Output contains no token.
const { chromium } = require(process.env.AQUAGUARD_PLAYWRIGHT || 'playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

(async () => {
  const base = process.env.AQUAGUARD_BROWSER_URL;
  const token = process.env.AQUAGUARD_C_TOKEN;
  const trial = process.env.AQUAGUARD_BROWSER_TRIAL || 'demo-trial';
  if (!base || !token) throw new Error('Explicit local URL and test token required');
  const url = new URL(base);
  if (!['127.0.0.1', 'localhost'].includes(url.hostname)) throw new Error('Local service only');
  const output = path.resolve(process.env.AQUAGUARD_BROWSER_EVIDENCE || 'audit/browser-evidence');
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({headless:true, executablePath:process.env.AQUAGUARD_CHROMIUM || undefined});
  const page = await browser.newPage({viewport:{width:1280,height:900}});
  const errors = [], checks = [];
  page.on('pageerror', error => errors.push(error.message));
  const check = name => checks.push(name);
  try {
    await page.goto(base);
    await page.getByRole('heading',{name:'连接本地业务服务'}).waitFor();
    await page.getByLabel('实验访问凭据').fill('invalid-local-token');
    await page.getByRole('button',{name:'连接',exact:true}).click();
    await page.getByText('传感快照：访问凭据无效，请重新连接').waitFor();
    check('invalid credentials are visible');
    await page.getByLabel('实验访问凭据').fill(token);
    await page.getByRole('button',{name:'连接',exact:true}).click();
    await page.getByText('来源：模拟 · 质量：', {exact:false}).waitFor({timeout:45000});
    const snapshot = await page.getByText('来源：模拟 · 质量：', {exact:false}).textContent();
    await page.waitForFunction(old => [...document.querySelectorAll('p')].some(p => p.textContent.includes('来源：模拟 · 质量：') && p.textContent !== old), snapshot, {timeout:15000});
    check('continuous simulation updates overview');
    await page.screenshot({path:path.join(output,'overview.png'),fullPage:true});
    await page.getByRole('button',{name:'事件确认',exact:true}).click();
    await page.getByRole('button',{name:/WATER_CONTACT/}).first().waitFor({timeout:120000});
    await page.getByRole('button',{name:/WATER_CONTACT/}).first().click();
    await page.getByRole('heading',{name:'事件详情'}).waitFor();
    const ack = page.getByRole('button',{name:'我已知晓',exact:true});
    if (await ack.isEnabled()) {
      await page.route('**/api/events/*/ack', route => route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({code:'VERSION_CONFLICT'})}),{times:1});
      await ack.click();
      await page.getByText('版本或操作冲突，已重新查询；核对后再次确认。').waitFor();
      check('ACK conflict prompts requery before retry');
      await ack.click();
      await page.getByText('已确认；物理状态与生命周期由后端单独维护。').waitFor();
      await page.getByText('已确认',{exact:true}).waitFor();
    } else throw new Error('Use a fresh simulation database for ACK verification');
    check('user acknowledgement persists and is shown separately');
    if(process.env.AQUAGUARD_BROWSER_LIFECYCLE==='1') {
      await page.waitForFunction(() => [...document.querySelectorAll('button')].some(b=>b.textContent==='关闭已恢复事件' && !b.disabled),null,{timeout:45000});
      await page.getByRole('button',{name:'关闭已恢复事件',exact:true}).click();
      await page.getByText('事件已关闭；再次发生将创建新的未确认事件。',{exact:true}).waitFor();
      await page.getByText('已关闭',{exact:true}).waitFor();
      check('fresh physical recovery permits explicit close');
      await page.waitForFunction(() => [...document.querySelectorAll('.event-list button')].filter(b=>b.textContent.includes('WATER_CONTACT')).length>=2,null,{timeout:45000});
      check('recurrence creates a separate event in the same MQTT run');
    }
    await page.screenshot({path:path.join(output,'event-ack.png'),fullPage:true});
    await page.getByRole('button',{name:'实验诊断',exact:true}).click();
    await page.getByLabel('实验ID').fill(trial);
    await page.getByRole('button',{name:'查询',exact:true}).click();
    await page.getByText('来源：模拟 · 状态：', {exact:false}).waitFor();
    assert.ok((await page.locator('pre').textContent()).includes(trial));
    check('experiment queries the running trial');
    await page.screenshot({path:path.join(output,'experiment.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});
    for (const tab of ['实时总览','事件确认','实验诊断']) {
      await page.getByRole('button',{name:tab,exact:true}).click();
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),true,tab+' horizontal overflow');
      await page.screenshot({path:path.join(output,`mobile-${['实时总览','事件确认','实验诊断'].indexOf(tab)}.png`),fullPage:true});
    }
    check('three pages fit a 390px viewport');
    await page.route('**/api/devices/*/live', route => route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({code:'STALE'})}));
    await page.getByRole('button',{name:'实时总览',exact:true}).click();
    await page.getByRole('button',{name:'刷新',exact:true}).click();
    await page.getByText('传感快照：不可用或证据已过期').waitFor();
    assert.equal(await page.locator('.grid').count(),0);
    check('unavailable snapshot removes old sensor values');
    await page.getByRole('button',{name:'断开',exact:true}).click();
    await page.getByRole('heading',{name:'连接本地业务服务'}).waitFor();
    assert.equal(await page.locator('pre').count(),0);
    check('disconnect clears displayed experiment data');
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'PASS',checks,errors,at:new Date().toISOString()},null,2));
    console.log(JSON.stringify({status:'PASS',checks}));
  } catch(error) {
    fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'FAIL',checks,error:error.message,errors},null,2));
    await page.screenshot({path:path.join(output,'failure.png'),fullPage:true});
    throw error;
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1});
