// Site shell: top navigation, phone tab bar and footer. The page content renders into <main>.
// Rebuilds when the signed-in state, language or route changes, and marks the current page with aria-current.
import { t, LANGUAGES } from '../state/i18n.js';
import { settings } from '../state/store.js';
import { currentUser, isLoggedIn, onAuthChange } from '../api/auth.js';
import { currentPath, reload } from '../router.js';
import { haptic } from '../device/haptics.js';
import { icons } from './icons/index.js';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const SIZES = [0.85, 1, 1.2, 1.4];

export const inApp = () => isLoggedIn() || settings.get().guest;

export function logoMark(cls = 'h-10 w-10') {
  return `<img class="${cls}" src="/icons/icon.svg" alt="" width="40" height="40">`;
}

const TABS = [
  { to: '/dashboard', icon: 'home', key: 'nav.dashboard' },
  { to: '/check', icon: 'crop', key: 'nav.check' },
  { to: '/chat', icon: 'question', key: 'nav.ask' },
  { to: '/weather', icon: 'weather', key: 'nav.weather' },
  { to: '/guide', icon: 'book', key: 'nav.guide' },
];

/**
 * Phone tab bar. Built once and then only updated in place, so the highlight can slide between tabs with a
 * spring instead of jumping, and the icon of the tab you just chose pops.
 */
function renderTabbar() {
  let bar = document.getElementById('tabbar');
  if (!inApp()) { bar?.remove(); document.body.classList.remove('has-tabbar'); return; }
  const lang = settings.get().language;
  if (!bar) {
    bar = document.createElement('nav');
    bar.id = 'tabbar';
    bar.className = 'tabbar';
    document.body.appendChild(bar);
  }
  if (bar.dataset.lang !== lang) {
    bar.dataset.lang = lang;
    bar.setAttribute('aria-label', t('nav.menu'));
    bar.innerHTML = `<span class="tab-pill" aria-hidden="true"></span>${TABS.map((x) =>
      `<a href="#${x.to}" data-to="${x.to}"><span class="tab-icon">${icons[x.icon]()}</span><span class="tab-label">${esc(t(x.key))}</span></a>`).join('')}`;
    bar.querySelectorAll('a').forEach((a) => a.addEventListener('click', () => haptic('tap')));
  }
  const path = currentPath();
  const idx = TABS.findIndex((x) => x.to === path);
  bar.querySelectorAll('a').forEach((a, i) => {
    if (i === idx) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  });
  bar.classList.toggle('no-active', idx < 0);
  if (idx >= 0) bar.style.setProperty('--idx', String(idx));
  document.body.classList.add('has-tabbar');
}

function renderHeader(el) {
  const path = currentPath();
  const user = currentUser();
  const lang = settings.get().language;
  const dark = document.documentElement.dataset.theme === 'dark';
  const cur = (to) => (path === to ? 'aria-current="page"' : '');

  const mainLinks = inApp() ? TABS : [];
  const navDesktop = mainLinks.map((l) => `<a class="nav-link" href="#${l.to}" ${cur(l.to)}>${t(l.key)}</a>`).join('');
  const navMobile = mainLinks.map((l) =>
    `<a class="menu-row" href="#${l.to}" ${cur(l.to)}><span class="text-[1.5rem]">${icons[l.icon]()}</span>${t(l.key)}</a>`).join('');

  const langToggle = `<div class="seg" role="group" aria-label="${t('nav.language')}">${LANGUAGES.map((l) =>
    `<button type="button" data-lang="${l.code}" aria-pressed="${lang === l.code}">${l.label}</button>`).join('')}</div>`;
  const textSize = `<div class="seg" role="group" aria-label="${t('account.textSize')}">${[['-1', 'A−', t('nav.textSmaller')], ['1', 'A+', t('nav.textLarger')]].map(([step, label, name]) =>
    `<button type="button" data-text-step="${step}" aria-label="${name}" title="${name}">${label}</button>`).join('')}</div>`;
  const themeBtn = `<button type="button" class="chip-btn" data-theme-toggle aria-label="${t('nav.theme')}" aria-pressed="${dark}">${dark ? 'Light' : 'Dark'}</button>`;

  const accountDesktop = inApp()
    ? `<a class="nav-link" href="#/account" ${cur('/account')}>${esc(user?.name?.split(' ')[0] || t('nav.account'))}</a>
       <button type="button" class="btn btn-ghost btn-sm" id="logout">${t('nav.logout')}</button>`
    : `<a class="btn btn-ghost btn-sm" href="#/login">${t('nav.login')}</a><a class="btn btn-primary btn-sm" href="#/register">${t('nav.register')}</a>`;
  const accountMobile = inApp()
    ? `<a class="menu-row" href="#/account" ${cur('/account')}><span class="text-[1.5rem]">${icons.pin()}</span>${esc(user?.name?.split(' ')[0] || t('nav.account'))}</a>
       <button type="button" class="btn btn-ghost" id="logout">${t('nav.logout')}</button>`
    : `<a class="btn btn-ghost" href="#/login">${t('nav.login')}</a><a class="btn btn-primary" href="#/register">${t('nav.register')}</a>`;

  el.innerHTML = `
    <div class="page-wide flex min-h-[4rem] items-center justify-between gap-3 py-2">
      <a class="flex items-center gap-3 no-underline" href="#${inApp() ? '/dashboard' : '/'}" aria-label="AgroAI Advisor">
        ${logoMark('h-9 w-9')}<span class="text-h3 font-bold leading-none">AgroAI <span class="text-leaf-ink">Advisor</span></span>
      </a>

      <details class="relative lg:hidden" id="menu">
        <summary class="btn btn-ghost btn-sm cursor-pointer list-none" aria-label="${t('nav.menu')}">${t('nav.menu')}</summary>
        <div class="menu-panel">
          ${navMobile}
          <div class="flex flex-wrap items-center gap-2 pt-1">${langToggle}${textSize}${themeBtn}</div>
          <div class="flex flex-col gap-2 pt-1">${accountMobile}</div>
        </div>
      </details>

      <div class="hidden shrink-0 items-center gap-1 lg:flex">
        <nav class="flex items-center gap-1" aria-label="${t('nav.menu')}">${navDesktop}</nav>
        <span class="mx-2 h-6 w-px bg-line" aria-hidden="true"></span>
        ${inApp() ? '' : langToggle}
        <details class="relative" id="prefs">
          <summary class="chip-btn cursor-pointer list-none" aria-label="${t('account.display')}" title="${t('account.display')}">Aa</summary>
          <div class="menu-panel">
            ${langToggle}
            <div class="flex flex-wrap items-center gap-2">${textSize}${themeBtn}</div>
            ${inApp() ? `<button type="button" class="btn btn-ghost btn-sm" id="logout">${t('nav.logout')}</button>` : ''}
          </div>
        </details>
        ${inApp() ? `<a class="nav-link" href="#/account" ${cur('/account')}>${esc(user?.name?.split(' ')[0] || t('nav.account'))}</a>` : accountDesktop}
      </div>
    </div>`;

  el.querySelectorAll('[data-lang]').forEach((b) => b.addEventListener('click', () => {
    haptic('tap');
    settings.set({ language: b.dataset.lang });
    renderHeader(el); renderFooter(document.getElementById('site-footer')); renderTabbar(); reload();
  }));
  el.querySelectorAll('[data-text-step]').forEach((b) => b.addEventListener('click', () => {
    haptic('tap');
    const now = settings.get().textScale;
    const i = SIZES.reduce((best, v, k) => (Math.abs(v - now) < Math.abs(SIZES[best] - now) ? k : best), 0);
    settings.set({ textScale: SIZES[Math.max(0, Math.min(SIZES.length - 1, i + Number(b.dataset.textStep)))] });
    renderHeader(el); renderFooter(document.getElementById('site-footer'));
  }));
  el.querySelectorAll('[data-theme-toggle]').forEach((b) => b.addEventListener('click', () => {
    haptic('tap');
    settings.set({ theme: dark ? 'light' : 'dark' });
    renderHeader(el);
  }));
  el.querySelectorAll('#logout').forEach((b) => b.addEventListener('click', async () => {
    const { logout } = await import('../state/account.js');
    logout();
  }));
  // close the phone menu after choosing something, and the display menu when tapping elsewhere
  el.querySelectorAll('#menu a').forEach((a) => a.addEventListener('click', () => { el.querySelector('#menu').open = false; }));
  const closeOutside = (e) => {
    const d = document.getElementById('prefs');
    if (d?.open && !d.contains(e.target)) d.open = false;
  };
  document.removeEventListener('click', renderHeader.__outside);
  renderHeader.__outside = closeOutside;
  document.addEventListener('click', closeOutside);
}

function renderFooter(el) {
  if (!el) return;
  el.className = 'band-dark furrows';
  el.innerHTML = `
    <div class="soil-edge" aria-hidden="true"></div>
    <div class="page flex flex-col gap-3 py-9">
      <p class="flex items-center gap-3 font-bold">${logoMark('h-8 w-8')} AgroAI Advisor</p>
      <p class="font-bold">${t('footer.line')}</p>
      <p class="text-small text-ink-soft">${t('footer.privacy')}</p>
      <p class="text-small text-ink-soft">${t('footer.built')}</p>
      ${inApp() ? `<a class="link text-small self-start" href="#/guide">${t('nav.guide')}</a>` : ''}
    </div>`;
}

export function mountShell() {
  const header = document.getElementById('site-header');
  const footer = document.getElementById('site-footer');
  const refresh = () => { renderHeader(header); renderFooter(footer); renderTabbar(); };
  refresh();
  window.addEventListener('hashchange', () => { renderHeader(header); renderTabbar(); });
  onAuthChange(refresh);
  settings.subscribe((s) => { if (s.guest !== undefined) { renderHeader(header); renderFooter(footer); renderTabbar(); } });
  return refresh;
}
