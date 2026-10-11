import puppeteer from 'puppeteer-core';
const b = await puppeteer.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: 'new' });
const p = await b.newPage();
await p.setViewport({ width: 390, height: 900 });
const errs = []; p.on('pageerror', (e) => errs.push(String(e)));
await p.goto('http://127.0.0.1:5173/#/kitchen-sink', { waitUntil: 'networkidle0' });
for (const [id, wait] of [['api-health', 3000], ['api-weather', 9000], ['api-chat', 40000]]) {
  await p.click('#' + id);
  const t0 = Date.now();
  await p.waitForFunction(() => { const t = document.querySelector('#api-out').textContent; return t && t !== 'Working...' && t !== 'Nothing yet.'; }, { timeout: 60000 });
  const out = await p.$eval('#api-out', (e) => e.textContent);
  console.log(`--- ${id} (${Date.now() - t0}ms)\n${out.slice(0, 700)}`);
}
console.log('page errors:', errs);
const tok = await p.evaluate(() => !!localStorage.getItem('agroai.token'));
console.log('token stored:', tok);
await b.close();
