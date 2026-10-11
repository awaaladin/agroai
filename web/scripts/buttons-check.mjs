// Every-button check in a real browser. Needs: dev server (5173) and backend (8001) running; real AI + weather are used.
//   1. Guest: landing buttons, then every link/button on every screen is hit-tested (is it reachable, not covered?)
//      and clicked (does anything happen? any page error or failed API call?).
//   2. Account: register through the form, repeat the crawl at phone and desktop width, then the real flows:
//      crop photo -> result -> ask about it -> chat, weather, account settings, log out, log in, delete history, delete account.
// Usage: npm run buttons          (BASE, BROWSER, QUICK=1 to skip the AI flows)
import puppeteer from 'puppeteer-core';

const EDGE = process.env.BROWSER || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const BASE = process.env.BASE || 'http://127.0.0.1:5173';
const QUICK = !!process.env.QUICK;
const ROUTES = ['/dashboard', '/check', '/chat', '/weather', '/guide', '/account'];
const DESTRUCTIVE = /delete|log ?out|clear|remove|×|&times;/i;

const fails = [];
const warns = [];
let step = 'start';
const ok = (name, cond, extra = '') => {
  console.log(`${cond ? 'ok  ' : 'FAIL'} ${name}${cond ? '' : '  ' + String(extra).slice(0, 300)}`);
  if (!cond) fails.push(`${name} ${extra}`);
};
const warn = (m) => { console.log(`warn ${m}`); warns.push(m); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await puppeteer.launch({
  executablePath: EDGE, headless: 'new',
  args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream', '--no-sandbox', '--mute-audio'],
});

async function newPage(viewport) {
  const ctx = await browser.createBrowserContext();
  await ctx.overridePermissions(BASE, ['camera', 'microphone', 'geolocation']);
  const p = await ctx.newPage();
  await p.setViewport(viewport);
  await p.setGeolocation({ latitude: 5.04, longitude: 7.93 });
  // Silence the app's read-aloud voice (speechSynthesis uses the real speakers even in headless mode).
  await p.evaluateOnNewDocument(() => {
    try {
      const s = window.speechSynthesis;
      if (s) { s.speak = () => {}; s.getVoices = () => []; }
      window.SpeechSynthesisUtterance = window.SpeechSynthesisUtterance || function () {};
    } catch { /* ignore */ }
  });
  p.__reqs = 0;
  p.on('request', (r) => { if (/\/v1\//.test(r.url())) p.__reqs += 1; });
  p.on('pageerror', (e) => ok(`no page error [${step}]`, false, String(e).slice(0, 200)));
  p.on('console', (m) => {
    if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) ok(`no console error [${step}]`, false, m.text());
  });
  p.on('response', (r) => {
    if (r.status() >= 400 && /\/v1\//.test(r.url())) ok(`API ok [${step}]`, false, `${r.status()} ${r.request().method()} ${r.url()}`);
  });
  return { ctx, p };
}

const hash = (p) => p.evaluate(() => location.hash);
const go = async (p, route) => {
  await p.goto(`${BASE}/#${route}`, { waitUntil: 'domcontentloaded' });
  await p.evaluate((r) => { if (location.hash !== `#${r}`) location.hash = r; }, route);
  await sleep(700);
};
const settle = (p, ms = 700) => sleep(ms);

// ---- generic crawler -------------------------------------------------------------------------------------
const COLLECT = () => {
  // 'main': the page with the phone menu closed. 'menu': only the items inside the opened phone menu.
  const menu = document.querySelector('#menu');
  const prefs = document.querySelector('#prefs');
  const mode = window.__mode || 'main';
  if (menu) menu.open = mode === 'menu';
  if (prefs) prefs.open = mode === 'prefs';
  const sel = mode === 'menu'
    ? '#menu a, #menu button'
    : mode === 'prefs'
      ? '#prefs a, #prefs button'
      : 'header a, header button, header summary, main a, main button, main summary, main [role="button"], main label.btn, #tabbar a, footer a';
  const out = [];
  document.querySelectorAll(sel).forEach((el) => {
    if (mode === 'main' && el.closest('#menu, #prefs') && el.tagName !== 'SUMMARY') return;
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    if (!r.width || !r.height || cs.visibility === 'hidden' || cs.display === 'none') return;
    if (el.closest('[hidden]')) return;
    out.push(el);
  });
  return out;
};

async function describe(p, i, mode = 'main') {
  return p.evaluate((idx, collectSrc, m) => {
    window.__mode = m;
    const els = (new Function(`return (${collectSrc})`))()();
    const el = els[idx];
    if (!el) return null;
    el.scrollIntoView({ block: 'center', behavior: 'instant' }); // the page has smooth scrolling; measure after the jump
    const r = el.getBoundingClientRect();
    const cx = r.left + r.width / 2; const cy = r.top + r.height / 2;
    const top = document.elementFromPoint(cx, cy);
    const hit = !!top && (el === top || el.contains(top) || top.contains(el));
    const label = (el.getAttribute('aria-label') || el.textContent || el.id || el.tagName).trim().replace(/\s+/g, ' ').slice(0, 40);
    return {
      total: els.length, label, tag: el.tagName.toLowerCase(), id: el.id || '', href: el.getAttribute('href') || '',
      forAttr: el.getAttribute('for') || '', cx, cy, w: r.width, h: r.height, hit,
      covered: hit ? '' : `${top?.tagName?.toLowerCase()}${top?.id ? '#' + top.id : ''}.${String(top?.className || '').split(' ').slice(0, 3).join('.')}`,
      disabled: el.disabled === true || el.getAttribute('aria-disabled') === 'true',
      hasName: !!(el.getAttribute('aria-label') || el.textContent.trim() || el.querySelector('img[alt]')?.alt),
    };
  }, i, COLLECT.toString(), mode);
}

async function crawl(p, route, who) {
  await crawlMode(p, route, who, 'main');
  const has = await p.evaluate(() => ({
    menu: !!document.querySelector('#menu summary')?.getBoundingClientRect().width,
    prefs: !!document.querySelector('#prefs summary')?.getBoundingClientRect().width,
  }));
  if (has.menu) await crawlMode(p, route, who, 'menu');
  if (has.prefs) await crawlMode(p, route, who, 'prefs');
}

async function crawlMode(p, route, who, mode) {
  step = `${who} ${route}${mode === 'menu' ? ' (menu)' : ''}`;
  await go(p, route);
  const first = await describe(p, 0, mode);
  if (!first) { warn(`${step}: nothing clickable found`); return; }
  const total = first.total;
  let clicked = 0;
  for (let i = 0; i < total; i += 1) {
    if (i > 0) { await go(p, route); }
    const d = await describe(p, i, mode);
    if (!d) continue;
    const name = `${step} "${d.label || d.id || d.tag}"`;
    ok(`${name} is reachable (not covered)`, d.hit, `covered by ${d.covered}`);
    ok(`${name} has an accessible name`, d.hasName);
    if (d.h < 40 || d.w < 40) warn(`${name} is small: ${Math.round(d.w)}x${Math.round(d.h)}px`);
    if (d.disabled || DESTRUCTIVE.test(d.label) || d.forAttr || /^https?:/.test(d.href) || /^(mailto|tel):/.test(d.href)) continue;
    const before = await p.evaluate(() => {
      window.__mut = 0;
      window.__mo?.disconnect();
      window.__mo = new MutationObserver((m) => { window.__mut += m.length; });
      window.__mo.observe(document.body, { subtree: true, childList: true, attributes: true, characterData: true });
      return location.hash;
    });
    const reqs0 = p.__reqs;
    await p.mouse.click(d.cx, d.cy);
    await sleep(700);
    const after = await p.evaluate(() => ({ hash: location.hash, mut: window.__mut, theme: document.documentElement.dataset.theme }));
    clicked += 1;
    const effect = after.hash !== before || after.mut > 0 || p.__reqs > reqs0;
    if (!effect) warn(`${name} did nothing visible`);
  }
  console.log(`     ${step}: ${total} controls, ${clicked} clicked`);
}

// ---- 1. guest --------------------------------------------------------------------------------------------
{
  const { ctx, p } = await newPage({ width: 390, height: 844, isMobile: true, hasTouch: true });
  step = 'landing';
  await go(p, '/');
  ok('landing shows a heading', !!(await p.$('h1')));
  const lang = await p.$$eval('header [data-lang]', (b) => b.length);
  ok('language buttons exist', lang >= 2 || (await p.$$eval('#menu [data-lang]', (b) => b.length)) >= 2);
  // Create account and Log in links
  await p.$eval('a[href="#/register"]', (a) => a.click()); await settle(p);
  ok('landing "Create account" opens the form', (await hash(p)) === '#/register');
  await go(p, '/'); await p.$eval('a[href="#/login"]', (a) => a.click()); await settle(p);
  ok('landing "Log in" opens the form', (await hash(p)) === '#/login');
  await go(p, '/'); await p.waitForSelector('#guest', { visible: true });
  await p.click('#guest'); await settle(p, 1200);
  ok('"Try without an account" opens the dashboard', (await hash(p)) === '#/dashboard');
  for (const r of ROUTES) await crawl(p, r, 'guest/phone');
  await ctx.close();
}

// ---- 2. account ------------------------------------------------------------------------------------------
const phone = `0803${String(Math.floor(1000000 + Math.random() * 8999999))}`;
const PIN = '4821';
{
  const { ctx, p } = await newPage({ width: 390, height: 844, isMobile: true, hasTouch: true });
  step = 'register';
  await go(p, '/register');
  // English first: changing language re-renders the form (and clears the PIN), so do it before typing.
  await p.$eval('input[name="lang"][value="en"]', (r) => r.click());
  await sleep(300);
  await p.type('#name', 'Check Farmer');
  await p.type('#phone', phone);
  await p.type('#newpin', PIN);
  await p.select('#town', 'Uyo');
  await p.click('#submit');
  await p.waitForFunction(() => location.hash === '#/dashboard', { timeout: 20000 }).catch(() => {});
  ok('register creates the account and opens the dashboard', (await hash(p)) === '#/dashboard', await p.$eval('#error', (e) => e.textContent).catch(() => ''));
  ok('signed-in user is stored', await p.evaluate(() => !!localStorage.getItem('agroai.user')));

  for (const r of ROUTES) await crawl(p, r, 'account/phone');

  // desktop width
  await p.setViewport({ width: 1280, height: 800 });
  for (const r of ROUTES) await crawl(p, r, 'account/desktop');
  await p.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true });

  // ---- real flows ----
  step = 'dashboard farm';
  await go(p, '/dashboard');
  await p.waitForSelector('#add-crop', { visible: true, timeout: 15000 }).catch(() => {});
  await p.select('#add-crop', 'cassava').catch(() => {});
  await sleep(1500);
  ok('adding a crop shows a chip', (await p.$$eval('#crop-chips .chip', (c) => c.length)) >= 1);
  await p.$eval('#notes', (n) => { n.value = 'Sandy soil near the river'; });
  await p.click('#save-farm'); await sleep(1500);
  ok('saving farm notes confirms', /saved/i.test(await p.$eval('#farm-status', (e) => e.textContent).catch(() => '')));

  step = 'weather';
  await go(p, '/weather'); await sleep(4000);
  const wx = await p.$eval('main', (m) => m.innerText.length);
  ok('weather screen has content', wx > 120, `chars=${wx}`);

  if (!QUICK) {
    step = 'check crop';
    await go(p, '/check'); await sleep(1500);
    await p.evaluate(async () => {
      const c = document.createElement('canvas'); c.width = 800; c.height = 600;
      const x = c.getContext('2d');
      x.fillStyle = '#4c8a2b'; x.fillRect(0, 0, 800, 600);
      x.fillStyle = '#b7b21f'; for (let i = 0; i < 30; i += 1) { x.beginPath(); x.arc(80 + (i * 97) % 640, 60 + (i * 53) % 480, 14 + (i % 5) * 6, 0, 7); x.fill(); }
      const blob = await new Promise((r) => c.toBlob(r, 'image/jpeg', 0.85));
      const dt = new DataTransfer(); dt.items.add(new File([blob], 'leaf.jpg', { type: 'image/jpeg' }));
      const input = document.querySelector('#gallery'); input.files = dt.files;
      input.dispatchEvent(new Event('change', { bubbles: true }));
    });
    await sleep(2000);
    await p.$eval('[data-crop="cassava"]', (b) => b.click()).catch(() => {});
    await p.type('#symptoms', 'leaves are turning yellow').catch(() => {});
    const send = await p.$$('button');
    for (const b of send) { const tx = await b.evaluate((e) => e.textContent.trim()); if (/check this photo/i.test(tx)) { await b.click(); break; } }
    await p.waitForFunction(() => location.hash === '#/result', { timeout: 120000 }).catch(() => {});
    ok('photo check reaches the result screen', (await hash(p)) === '#/result');
    if ((await hash(p)) === '#/result') {
      await sleep(1500);
      ok('result shows a heading and "ask about this"', !!(await p.$('h1')) && !!(await p.$('#ask')));
      await p.click('#ask'); await sleep(1500);
      ok('"Ask about this" opens the chat', (await hash(p)) === '#/chat');
    }
    step = 'chat';
    await go(p, '/chat'); await sleep(1000);
    await p.type('#text', 'Can I spray my crop today?');
    await p.click('#send');
    await p.waitForFunction(() => document.querySelectorAll('#log li').length >= 2, { timeout: 90000 }).catch(() => {});
    ok('chat answers a typed question', (await p.$$eval('#log li', (l) => l.length)) >= 2);
  }

  // settings, logout, login, delete
  step = 'account settings';
  await go(p, '/account'); await sleep(1000);
  await p.$eval('[data-theme-set="dark"]', (b) => b.click()); await sleep(300);
  ok('theme button switches to dark', await p.evaluate(() => document.documentElement.dataset.theme === 'dark'));
  await p.$eval('[data-theme-set="light"]', (b) => b.click());
  await p.$eval('[data-scale]:last-of-type', (b) => b.click()).catch(() => {});
  await p.$eval('[data-lang="pcm"]', (b) => b.click()); await sleep(500);
  ok('Pidgin button switches language', await p.evaluate(() => JSON.parse(localStorage.getItem('agroai.settings') || '{}').language === 'pcm'));
  await p.$eval('[data-lang="en"]', (b) => b.click()); await sleep(500);
  await p.$eval('#name', (n) => { n.value = 'Check Farmer Two'; });
  await p.click('#save'); await sleep(1500);
  ok('profile save confirms', (await p.$eval('#status', (e) => e.textContent).catch(() => '')).length > 0);

  step = 'logout and login';
  await p.$eval('#logout', (b) => b.click()); await sleep(1500);
  ok('log out returns to the landing page', !(await p.evaluate(() => !!localStorage.getItem('agroai.user'))));
  await go(p, '/login');
  await p.type('#phone', phone); await p.type('#pin', PIN); await p.click('#submit');
  await p.waitForFunction(() => location.hash === '#/dashboard', { timeout: 20000 }).catch(() => {});
  ok('log in works with the same phone and PIN', (await hash(p)) === '#/dashboard');

  step = 'delete history';
  await go(p, '/account'); await sleep(800);
  await p.click('#clear'); await sleep(400);
  ok('"Delete my history" asks for confirmation', await p.$eval('#confirm', (e) => !e.hidden));
  await p.click('#no'); await sleep(300);
  ok('"Cancel" hides the confirmation', await p.$eval('#confirm', (e) => e.hidden));
  await p.click('#clear'); await p.click('#yes'); await sleep(1500);

  step = 'delete account';
  await p.click('#delete'); await sleep(300); await p.click('#yes');
  await sleep(2500);
  ok('"Delete my account" signs out', !(await p.evaluate(() => !!localStorage.getItem('agroai.user'))));
  await go(p, '/login');
  await p.type('#phone', phone); await p.type('#pin', PIN); await p.click('#submit'); await sleep(2000);
  ok('deleted account can no longer log in', (await hash(p)) !== '#/dashboard');
  await ctx.close();
}

await browser.close();
console.log(`\n${fails.length ? 'FAILED' : 'PASSED'}: ${fails.length} failures, ${warns.length} warnings`);
fails.slice(0, 40).forEach((f) => console.log('  FAIL', f));
process.exit(fails.length ? 1 : 0);
