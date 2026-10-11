// Lists the speech voices the browser has, so we can see what a farmer's device will offer.
import puppeteer from 'puppeteer-core';
const b = await puppeteer.launch({ executablePath: process.env.BROWSER || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: 'new' });
const p = await b.newPage();
await p.goto('http://127.0.0.1:5173/', { waitUntil: 'domcontentloaded' });
const v = await p.evaluate(() => new Promise((res) => {
  const get = () => speechSynthesis.getVoices();
  if (get().length) return res(get().map((x) => `${x.name} | ${x.lang} | ${x.localService ? 'local' : 'online'}`));
  speechSynthesis.addEventListener('voiceschanged', () => res(get().map((x) => `${x.name} | ${x.lang} | ${x.localService ? 'local' : 'online'}`)));
  setTimeout(() => res(get().map((x) => `${x.name} | ${x.lang}`)), 3000);
}));
console.log(v.filter((x) => /\| en/i.test(x)).join('\n') || '(no English voices in headless; run in a normal browser)');
await b.close();
