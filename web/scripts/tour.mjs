// Takes screenshots of the real pages (light and dark, phone and desktop) so they can be looked at by eye.
// Registers a throwaway farmer through the real UI. Needs dev server (5173) and backend (8001).
import puppeteer from 'puppeteer-core';
import fs from 'node:fs';
const EDGE = process.env.BROWSER || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const BASE = process.env.BASE || 'http://127.0.0.1:5173';
const OUT = process.env.OUT || 'tour';
fs.mkdirSync(OUT, { recursive: true });
const phone = `0803${String(Math.floor(Math.random() * 9e6) + 1e6)}`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const browser = await puppeteer.launch({ executablePath: EDGE, headless: 'new' });
for (const theme of (process.env.THEMES || 'light,dark').split(',')) {
  for (const [name, w, h] of [['desktop', 1280, 800], ['phone', 390, 844]]) {
    const ctx = await browser.createBrowserContext();
    const p = await ctx.newPage();
    await p.setViewport({ width: w, height: h, isMobile: w < 700, hasTouch: w < 700 });
    await p.evaluateOnNewDocument((th) => localStorage.setItem('agroai.settings', JSON.stringify({ theme: th, autoRead: false })), theme);
    const shot = async (n) => { await sleep(900); await p.screenshot({ path: `${OUT}/${n}-${theme}-${name}.png`, fullPage: true }); };
    await p.goto(`${BASE}/#/`, { waitUntil: 'networkidle0' });
    await shot('1-landing');
    await p.goto(`${BASE}/#/register`, { waitUntil: 'networkidle0' });
    await shot('2-register');
    await p.type('#name', 'Mfon Etim');
    await p.type('#phone', phone);
    await p.type('#newpin', '1234');
    await p.select('#town', 'Uyo');
    await p.$eval('#submit', (b) => b.click());
    await p.waitForFunction(() => location.hash === '#/dashboard', { timeout: 15000 });
    await sleep(2500);
    await shot('3-dashboard');
    for (const [r, n] of [['/check', '4-check'], ['/chat', '5-chat'], ['/weather', '6-weather'], ['/account', '7-account']]) {
      await p.goto(`${BASE}/#${r}`, { waitUntil: 'networkidle0' });
      await sleep(r === '/weather' ? 3500 : 800);
      await shot(n);
    }
    await ctx.close();
  }
}
await browser.close();
console.log('screenshots in', OUT);
