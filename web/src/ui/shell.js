// Site shell: top navigation and footer, like a normal website. The page content renders into <main>.
// Rebuilds when the signed-in state, language or route changes, and marks the current page with aria-current.
import { t, LANGUAGES } from '../state/i18n.js';
import { settings } from '../state/store.js';
import { currentUser, isLoggedIn, onAuthChange } from '../api/auth.js';
import { currentPath, go, reload } from '../router.js';
import { icons } from './icons/index.js';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

export const inApp = () => isLoggedIn() || settings.get().guest;

export function logoMark(cls = 'h-10 w-10') {
  return `<img class="${cls}" src="/icons/icon.svg" alt="" width="40" height="40">`;
}

function links() {
  if (!inApp()) return [];
  return [
    { to: '/dashboard', label: t('nav.dashboard') },
    { to: '/check', label: t('nav.check') },
    { to: '/chat', label: t('nav.ask') },
    { to: '/weather', label: t('nav.weather') },
  ];
}

function renderHeader(el) {
  const path = currentPath();
  const user = currentUser();
  const lang = settings.get().language;
  const dark = document.documentElement.dataset.theme === 'dark';
  const nav = links().map((l) =>
    `<a class="btn btn-ghost !border-transparent" href="#${l.to}" ${path === l.to ? 'aria-current="page"' : ''}>${l.label}</a>`).join('');
  const langToggle = LANGUAGES.map((l) =>
    `<button type="button" class="btn ${lang === l.code ? 'btn-primary' : 'btn-ghost'} !min-w-0 !px-3" data-lang="${l.code}" aria-pressed="${lang === l.code}">${l.label}</button>`).join('');
  const account = inApp()
    ? `<a class="btn btn-ghost !border-transparent" href="#/account" ${path === '/account' ? 'aria-current="page"' : ''}>${esc(user?.name?.split(' ')[0] || t('nav.account'))}</a>
       <button type="button" class="btn btn-ghost" id="logout">${t('nav.logout')}</button>`
    : `<a class="btn btn-ghost" href="#/login">${t('nav.login')}</a><a class="btn btn-primary" href="#/register">${t('nav.register')}</a>`;

  el.innerHTML = `
    <div class="page flex min-h-[4.5rem] flex-wrap items-center justify-between gap-3 py-2">
      <a class="flex items-center gap-3 no-underline" href="#${inApp() ? '/dashboard' : '/'}" aria-label="AgroAI Advisor">
        ${logoMark()}<span class="text-h3 font-bold">AgroAI <span class="text-leaf-ink">Advisor</span></span>
      </a>
      <details class="relative md:hidden" id="menu">
        <summary class="btn btn-ghost cursor-pointer list-none" aria-label="${t('nav.menu')}">${t('nav.menu')}</summary>
        <div class="absolute right-0 z-20 mt-2 flex w-72 flex-col gap-2 rounded-seed border border-line bg-surface p-3 shadow-lg">
          ${nav}<div class="flex gap-2">${langToggle}</div>${account}
        </div>
      </details>
      <div class="hidden flex-wrap items-center gap-2 md:flex">
        ${nav}<div class="flex gap-1" role="group" aria-label="${t('nav.language')}">${langToggle}</div>
        <button type="button" class="btn btn-ghost" id="theme" aria-label="${t('nav.theme')}" aria-pressed="${dark}">${dark ? 'Light' : 'Dark'}</button>
        ${account}
      </div>
    </div>`;

  el.querySelectorAll('[data-lang]').forEach((b) => b.addEventListener('click', () => {
    settings.set({ language: b.dataset.lang });
    renderHeader(el); renderFooter(document.getElementById('site-footer')); reload();
  }));
  el.querySelector('#theme')?.addEventListener('click', () => {
    settings.set({ theme: dark ? 'light' : 'dark' });
    renderHeader(el);
  });
  el.querySelectorAll('#logout').forEach((b) => b.addEventListener('click', async () => {
    const { logout } = await import('../state/account.js');
    logout();
  }));
  // close the mobile menu after choosing something
  el.querySelectorAll('#menu a').forEach((a) => a.addEventListener('click', () => { el.querySelector('#menu').open = false; }));
}

function renderFooter(el) {
  if (!el) return;
  el.innerHTML = `
    <div class="page flex flex-col gap-2 py-8 text-small text-ink-soft">
      <p class="font-bold text-ink">${t('footer.line')}</p>
      <p>${t('footer.privacy')}</p>
      <p>${t('footer.built')}</p>
    </div>`;
}

export function mountShell() {
  const header = document.getElementById('site-header');
  const footer = document.getElementById('site-footer');
  const refresh = () => { renderHeader(header); renderFooter(footer); };
  refresh();
  window.addEventListener('hashchange', () => renderHeader(header));
  onAuthChange(refresh);
  settings.subscribe((s) => { if (s.guest !== undefined) renderHeader(header); });
  return refresh;
}
