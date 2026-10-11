// Journey check in a real browser: first visit (splash > language > 3 permissions > home), then a return visit
// that skips straight to Home, plus the skip and denied paths. Needs the dev server running.
import puppeteer from 'puppeteer-core';

const EDGE = process.env.BROWSER || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const BASE = process.env.BASE || 'http://127.0.0.1:5173';
const fails = [];
const ok = (name, cond, extra = '') => {
  console.log(`${cond ? 'ok  ' : 'FAIL'} ${name}${cond ? '' : '  ' + extra}`);
  if (!cond) fails.push(name);
};
const hash = (p) => p.evaluate(() => location.hash);
const text = (p, sel) => p.$eval(sel, (e) => e.textContent.trim()).catch(() => null);
// Direct DOM click: coordinate clicks in headless Edge can land mid-animation; hit-testing is covered by `npm run audit`.
const click = async (p, sel) => { await p.waitForSelector(sel, { visible: true }); await p.$eval(sel, (el) => el.click()); };
const waitScreen = (p, name, timeout = 12000) => p.waitForSelector(`[data-screen="${name}"]`, { visible: true, timeout });
const waitHash = async (p, h, timeout = 12000) => {
  try {
    await p.waitForFunction((x) => location.hash === x, { timeout }, h);
  } catch (e) {
    const st = await p.evaluate(() => ({ hash: location.hash, h1: document.querySelector('h1')?.textContent,
      status: document.querySelector('#status')?.textContent, hidden: document.hidden, vt: !!document.startViewTransition,
      settings: localStorage.getItem('agroai.settings')?.slice(0, 200) }));
    console.log('STALLED waiting for', h, JSON.stringify(st));
    throw e;
  }
};
const settingsOf = (p) => p.evaluate(() => JSON.parse(localStorage.getItem('agroai.settings') || '{}'));

const browser = await puppeteer.launch({
  executablePath: EDGE, headless: 'new',
  args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'],
});

async function newPage(ctx, errors) {
  const p = await ctx.newPage();
  await p.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true });
  p.on('pageerror', (e) => { errors.push(String(e)); console.log('PAGEERROR', String(e).slice(0, 200)); });
  p.on('console', (m) => m.type() === 'error' && !/Failed to load resource/.test(m.text()) && errors.push(m.text()));
  return p;
}

// ---- Journey A: everything allowed (fake camera and microphone, geolocation granted) ----
{
  const ctx = await browser.createBrowserContext();
  await ctx.overridePermissions(BASE, ['geolocation', 'camera', 'microphone']);
  const errors = [];
  const p = await newPage(ctx, errors);
  await p.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' });
  await p.setGeolocation({ latitude: 5.0377, longitude: 7.9128 }); // after load: Edge drops it otherwise
  ok('splash shows the app name', (await text(p, 'h1')) === 'AgroAI Advisor');
  await waitHash(p, '#/language', 4000).catch(() => {});
  ok('splash moves on to language within about 1.2 s', (await hash(p)) === '#/language', await hash(p));
  const labels = await p.$$eval('[data-lang]', (els) => els.map((e) => e.textContent.trim()));
  ok('language screen has English and Pidgin', labels.join() === 'English,Pidgin', labels.join());
  await click(p, '[data-lang="pcm"]');
  await waitHash(p, '#/permissions/camera');
  await waitScreen(p, 'camera');
  ok('language choice saved as pcm', (await settingsOf(p)).language === 'pcm');
  ok('permission screen is in Pidgin', /Make I see your crop/.test(await text(p, 'h1')));
  await click(p, '#allow');
  await waitHash(p, '#/permissions/microphone');
  await waitScreen(p, 'microphone');
  await click(p, '#allow');
  await waitHash(p, '#/permissions/location');
  await waitScreen(p, 'location');
  await click(p, '#allow');
  await waitHash(p, '#/home', 7000);
  const s = await settingsOf(p);
  ok('permissions recorded as granted', s.perms?.camera === 'granted' && s.perms?.microphone === 'granted' && s.perms?.location === 'granted', JSON.stringify(s.perms));
  ok('location saved coarse (2 decimals)', s.lat === 5.04 && s.lon === 7.91 && s.locationSource === 'gps', `${s.lat},${s.lon}`);
  ok('onboarded flag set', s.onboarded === true);
  await p.waitForFunction(() => /Good (morning|afternoon|evening)/.test(document.querySelector('h1')?.textContent || ''), { timeout: 8000 }).catch(() => {});
  ok('home greeting shown', /Good (morning|afternoon|evening)/.test(await text(p, 'h1')));
  const cards = await p.$$eval('[data-to]', (els) => els.map((e) => e.dataset.to));
  ok('three seed-packet cards', cards.join() === '/check,/chat,/weather', cards.join());
  const h = await p.$$eval('[data-to]', (els) => els.map((e) => Math.round(e.getBoundingClientRect().height)));
  ok('cards are oversized (at least 96px)', h.every((x) => x >= 96), h.join());
  await click(p, '[data-to="/weather"]');
  await waitHash(p, '#/weather');
  await p.waitForFunction(() => /Weather for my farm/.test(document.querySelector('h1')?.textContent || ''), { timeout: 8000 }).catch(() => {});
  ok('card opens its screen', /Weather for my farm/.test(await text(p, 'h1')), await text(p, 'h1'));
  const p2 = await newPage(ctx, errors);
  await p2.goto(`${BASE}/`, { waitUntil: 'networkidle0' });
  await waitHash(p2, '#/home', 3000).catch(() => {});
  ok('return visit skips straight to Home', (await hash(p2)) === '#/home', await hash(p2));
  ok('no script errors (journey A)', errors.length === 0, errors.join(' | ').slice(0, 300));
  await ctx.close();
}

// ---- Journey B: everything skipped: typing replaces voice, the town picker replaces location ----
{
  const ctx = await browser.createBrowserContext();
  const errors = [];
  const p = await newPage(ctx, errors);
  await p.goto(`${BASE}/#/language`, { waitUntil: 'networkidle0' });
  await click(p, '[data-lang="en"]');
  await waitScreen(p, 'camera');
  await click(p, '#skip');
  await waitScreen(p, 'microphone');
  await click(p, '#skip');
  await waitScreen(p, 'location');
  await click(p, '#skip');
  await p.waitForSelector('[data-town]', { visible: true });
  const towns = await p.$$eval('[data-town]', (els) => els.map((e) => e.dataset.town));
  ok('town picker lists the required towns', ['Uyo', 'Etinan', 'Eket', 'Ikot Ekpene', 'Oron'].every((x) => towns.includes(x)), towns.join());
  await click(p, '[data-town="Eket"]');
  await waitHash(p, '#/home', 4000);
  const s = await settingsOf(p);
  ok('town saved with coordinates', s.town === 'Eket' && s.locationSource === 'town' && s.lat === 4.64, JSON.stringify(s));
  ok('all permissions skipped, app still usable', s.perms?.camera === 'skipped' && s.perms?.microphone === 'skipped');
  ok('home shows the chosen town', /Eket/.test(await p.evaluate(() => document.body.innerText)));
  ok('no script errors (journey B)', errors.length === 0, errors.join(' | ').slice(0, 300));
  await ctx.close();
}

// ---- Journey C: geolocation denied -> falls back to the town picker ----
{
  const ctx = await browser.createBrowserContext();
  const errors = [];
  const p = await newPage(ctx, errors);
  await p.goto(`${BASE}/#/permissions/location`, { waitUntil: 'networkidle0' });
  await p.evaluate(() => { navigator.geolocation.getCurrentPosition = (_ok, err) => err({ code: 1 }); });
  await click(p, '#allow');
  await p.waitForSelector('[data-town]', { visible: true, timeout: 4000 });
  ok('denied location falls back to the town picker', true);
  ok('denied location is recorded', (await settingsOf(p)).perms?.location === 'denied');
  ok('no script errors (journey C)', errors.length === 0, errors.join(' | ').slice(0, 300));
  await ctx.close();
}

await browser.close();
console.log(fails.length ? `\n${fails.length} FAILED: ${fails.join('; ')}` : '\nALL PASSED');
process.exit(fails.length ? 1 : 0);
