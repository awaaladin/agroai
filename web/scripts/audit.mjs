// Layout audit (design guide section 7): load each route at phone and tablet widths in a real browser, assert no
// horizontal scroll, list offenders, and save screenshots. Run with the dev server up:  npm run audit
import puppeteer from 'puppeteer-core';
import fs from 'node:fs';

const EDGE = process.env.BROWSER || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const BASE = process.env.BASE || 'http://127.0.0.1:5173';
const ROUTES = (process.env.ROUTES || '/,/kitchen-sink').split(',');
const WIDTHS = [320, 375, 414, 768];
const THEMES = (process.env.THEMES || 'light,dark,contrast').split(',');
const OUT = process.env.OUT || 'audit';
fs.mkdirSync(OUT, { recursive: true });

const browser = await puppeteer.launch({ executablePath: EDGE, headless: 'new', args: ['--no-sandbox'] });
let bad = 0;
for (const route of ROUTES) for (const theme of THEMES) for (const w of WIDTHS) {
  const page = await browser.newPage();
  await page.setViewport({ width: w, height: 900, deviceScaleFactor: 1, isMobile: w < 700, hasTouch: w < 700 });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
  await page.evaluateOnNewDocument((th) => { localStorage.setItem('agroai.settings', JSON.stringify({ theme: th, onboarded: true, autoRead: false, town: 'Uyo', lat: 5.04, lon: 7.93, locationSource: 'town', perms: { camera: 'denied' } })); }, theme);
  await page.goto(`${BASE}/#${route}`, { waitUntil: 'networkidle0' });
  await new Promise((r) => setTimeout(r, 900)); // let entrance animations settle
  const res = await page.evaluate(() => {
    const de = document.documentElement;
    const off = [];
    document.querySelectorAll('body *').forEach((el) => {
      const r = el.getBoundingClientRect();
      if (r.width && r.right > de.clientWidth + 1) off.push(`${el.tagName.toLowerCase()}.${String(el.className).slice(0, 40)} right=${Math.round(r.right)}`);
    });
    const small = [...document.querySelectorAll('button, a.btn, .btn, select, input')]
      .filter((el) => { const r = el.getBoundingClientRect(); return r.width && (r.height < 55.5); })
      .map((el) => `${el.tagName.toLowerCase()}#${el.id || ''} h=${Math.round(el.getBoundingClientRect().height)}`);
    return { scroll: de.scrollWidth, client: de.clientWidth, off: off.slice(0, 5), small: small.slice(0, 5) };
  });
  const ok = res.scroll <= res.client && errors.length === 0;
  if (!ok) bad++;
  console.log(`${ok ? 'ok  ' : 'FAIL'} ${route} ${theme} ${w}px scroll=${res.scroll}/${res.client}` +
    (res.off.length ? ` offenders=${res.off.join('; ')}` : '') + (errors.length ? ` errors=${errors.join(' | ').slice(0, 200)}` : '') +
    (res.small.length ? ` (touch targets <56px: ${res.small.join(', ')})` : ''));
  if (w === 375 || w === 320) await page.screenshot({ path: `${OUT}/${route.replace(/\W/g, '') || 'home'}-${theme}-${w}.png`, fullPage: true });
  await page.close();
}
await browser.close();
console.log(bad ? `\n${bad} FAILED` : '\nALL PASSED');
process.exit(bad ? 1 : 0);
