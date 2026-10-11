// End-to-end check of the three main features against the REAL backend (and so the real AI and weather):
// Check my crop (photo -> analyzing -> result), Ask a question (chat with context), Weather for my farm.
// Needs: dev server on 5173, backend on 8001. Costs two AI calls. Usage: PHOTO=path/to/leaf.jpg npm run features
import puppeteer from 'puppeteer-core';

const EDGE = process.env.BROWSER || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const BASE = process.env.BASE || 'http://127.0.0.1:5173';
const PHOTO = process.env.PHOTO;
if (!PHOTO) { console.error('Set PHOTO to a leaf photo path'); process.exit(2); }
const fails = [];
const ok = (name, cond, extra = '') => { console.log(`${cond ? 'ok  ' : 'FAIL'} ${name}${cond ? '' : '  ' + String(extra).slice(0, 300)}`); if (!cond) fails.push(name); };
const text = (p, sel) => p.$eval(sel, (e) => e.textContent.trim()).catch(() => null);
const click = async (p, sel) => { await p.waitForSelector(sel, { visible: true }); await p.$eval(sel, (el) => el.click()); };
const waitHash = (p, h, timeout = 90000) => p.waitForFunction((x) => location.hash === x, { timeout }, h);

const browser = await puppeteer.launch({ executablePath: EDGE, headless: 'new', args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] });
const ctx = await browser.createBrowserContext();
await ctx.overridePermissions(BASE, ['camera', 'microphone', 'geolocation']);
const errors = [];
const p = await ctx.newPage();
await p.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true });
p.on('pageerror', (e) => errors.push(e.stack || String(e)));
p.on('requestfailed', (r) => errors.push(`requestfailed ${r.url()}`));
await p.evaluateOnNewDocument(() => {
  localStorage.setItem('agroai.settings', JSON.stringify({ language: 'en', onboarded: true, autoRead: false, theme: 'light',
    town: 'Uyo', lat: 5.04, lon: 7.93, locationSource: 'town', perms: { camera: 'granted' } }));
});

// ---- Weather ----
await p.goto(`${BASE}/#/home`, { waitUntil: 'networkidle0' });
await click(p, '[data-to="/weather"]');
await waitHash(p, '#/weather');
await p.waitForSelector('ol li', { timeout: 30000 });
const days = await p.$$eval('ol li', (els) => els.length);
ok('weather: five-day strip', days === 5, days);
ok('weather: current temperature shown', /\d+°C/.test(await p.evaluate(() => document.body.innerText)));
ok('weather: animated icons present', (await p.$$eval('svg.wx', (e) => e.length)) >= 6);
ok('weather: meaning card with rules', /What this means for your farm today/.test(await p.evaluate(() => document.body.innerText)));
ok('weather: hear button', !!(await p.$('#hear')));

// ---- Check my crop (gallery upload of a real photo) ----
await p.goto(`${BASE}/#/home`, { waitUntil: 'networkidle0' });
await click(p, '[data-to="/check"]');
await waitHash(p, '#/check');
await p.waitForSelector('#gallery', { timeout: 10000 });
const crops = await p.$$eval('[data-crop]', (e) => e.map((x) => x.dataset.crop));
ok('crop picker has seven crops', crops.join() === 'cassava,yam,maize,plantain,cocoyam,pepper,other', crops.join());
await click(p, '[data-crop="cassava"]');
ok('crop selection marked', (await p.$eval('[data-crop="cassava"]', (e) => e.getAttribute('aria-pressed'))) === 'true');
await p.evaluate(() => { document.querySelector('#symptoms').value = 'leaves are yellow and curling'; });
const input = await p.$('#gallery');
await input.uploadFile(PHOTO);
await waitHash(p, '#/analyzing', 20000);
ok('goes to analyzing', true);
ok('analyzing shows skeleton and message (or already finished)', !!(await p.$('.skeleton')) || !!(await text(p, '#msg')) || (await p.evaluate(() => location.hash)) === '#/result');
await waitHash(p, '#/result', 120000);
await p.waitForSelector('.meter', { timeout: 10000 });
ok('result: likely problem heading', (await text(p, 'h1'))?.length > 3, await text(p, 'h1'));
ok('result: confidence meter with words', /(Sure|Fairly sure|Not sure) \(\d+%\)/.test(await text(p, '[aria-label="How sure I am"]')), await text(p, '[aria-label="How sure I am"]'));
const steps = await p.$$eval('[data-done]', (e) => e.length);
ok('result: numbered action cards', steps >= 2, steps);
ok('result: officer button always present', !!(await p.$('#officer')));
ok('result: delete my data link', !!(await p.$('#delete')));
ok('result: what I see and why', /What I see/.test(await p.evaluate(() => document.body.innerText)) && /Why I think so/.test(await p.evaluate(() => document.body.innerText)));
await click(p, '[data-done]');
ok('action step checks off', (await p.$eval('[data-done]', (e) => e.getAttribute('aria-pressed'))) === 'true');
const sentImage = await p.evaluate(() => performance.getEntriesByType('resource').filter((r) => r.name.includes('/v1/diagnose')).map((r) => r.transferSize));
ok('photo was sent to the API', sentImage.length >= 1);

// ---- Officer share card (no Web Share in headless: falls back to WhatsApp link or copy) ----
await p.evaluate(() => { window.open = () => null; });
await click(p, '#officer');
await p.waitForFunction(() => document.querySelector('#share-status').textContent.length > 0, { timeout: 20000 });
ok('officer message prepared', true);

// ---- Chat with context ----
await click(p, '#ask');
await waitHash(p, '#/chat');
await p.waitForSelector('#text');
const bubbles0 = await p.$$eval('#log li', (e) => e.length);
ok('chat opens with context bubble', bubbles0 >= 1);
await p.type('#text', 'Can I spray today?');
await click(p, '#send');
await p.waitForFunction(() => { const li = [...document.querySelectorAll('#log li')]; const last = li[li.length - 1]; return li.length >= 3 && last && !/Thinking/.test(last.textContent); }, { timeout: 90000 });
const reply = await p.$$eval('#log li', (e) => e[e.length - 1].textContent);
ok('chat: answer shown', reply.length > 20 && !/Thinking/.test(reply), reply);
ok('chat: follow-up chips', (await p.$$eval('#chips button', (e) => e.length)) >= 1);
ok('chat: session carried over', !!(await p.evaluate(() => sessionStorage.getItem('agroai.sessionId'))));

// ---- Delete my data ----
await p.goto(`${BASE}/#/result`, { waitUntil: 'networkidle0' }).catch(() => {});
ok('no script errors', errors.length === 0, errors.join(' | '));
await browser.close();
console.log(fails.length ? `\n${fails.length} FAILED: ${fails.join('; ')}` : '\nALL PASSED');
process.exit(fails.length ? 1 : 0);
