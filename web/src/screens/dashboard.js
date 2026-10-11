// Dashboard: the farmer's home. Greeting, the three things to do, today's weather, recent crop checks (accounts),
// and "About your farm" (the crops and notes the advisor uses to personalise its advice).
import { t } from '../state/i18n.js';
import { settings } from '../state/store.js';
import { currentUser, isLoggedIn } from '../api/auth.js';
import { myChecks, myCheck, weatherAdvice } from '../api/endpoints.js';
import { refreshProfile, saveProfile } from '../state/account.js';
import { getLocation, TOWNS } from '../device/location.js';
import { icons } from '../ui/icons/index.js';
import { cropIcon, CROPS } from '../ui/crops.js';
import { weatherIcon, kindOf } from '../ui/weather-icons.js';
import { friendlyError } from '../ui/components/friendly.js';
import { confidenceWord } from './result.js';
import { work, clearWork } from '../state/session.js';
import { go } from '../router.js';
import { speak } from '../audio/speech.js';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const greetingKey = (h = new Date().getHours()) => (h < 12 ? 'morning' : h < 17 ? 'afternoon' : 'evening');
const fmtDate = (iso) => new Intl.DateTimeFormat(settings.get().language === 'pcm' ? 'en-NG' : 'en', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(iso));

export function render(host) {
  const user = currentUser();
  const loc = getLocation();
  const greeting = t(`home.greeting.${greetingKey()}`);
  const first = (user?.name || '').split(' ')[0];

  const actions = [
    { to: '/check', icon: 'crop', key: 'check', hint: t('dash.sub') },
    { to: '/chat', icon: 'question', key: 'question' },
    { to: '/weather', icon: 'weather', key: 'weather' },
  ];

  host.innerHTML = `
    <div class="page flex flex-col gap-8 py-8">
      <header class="flex flex-col gap-1">
        <h1 class="reveal">${first ? t('dash.hello', { greeting, name: esc(first) }) : t('dash.helloGuest', { greeting })}</h1>
        <p class="reveal text-ink-soft" style="--i:1">${loc?.town ? `${esc(loc.town)} · ` : ''}${t('dash.sub')}</p>
      </header>

      <nav class="grid gap-4 md:grid-cols-3" aria-label="${t('dash.title')}">
        ${actions.map((a, i) => `
          <a class="action-card reveal flex items-center gap-4" style="--i:${i + 2}" href="#${a.to}" data-to="${a.to}">
            <span class="flex h-16 w-16 flex-none items-center justify-center rounded-leaf bg-surface-2 text-[2.6rem]">${icons[a.icon]()}</span>
            <span class="text-h3 font-bold">${t(`home.${a.key}`)}</span>
          </a>`).join('')}
      </nav>

      <div class="grid gap-6 lg:grid-cols-3">
        <section class="card flex flex-col gap-4 lg:col-span-2" aria-labelledby="recent-h">
          <div class="flex items-center justify-between gap-3"><h2 id="recent-h">${t('dash.recent')}</h2></div>
          <div id="history">${isLoggedIn() ? '<div class="skeleton h-24"></div>' : ''}</div>
        </section>

        <div class="flex flex-col gap-6">
          <section class="card flex flex-col gap-3" aria-labelledby="wx-h"><h2 id="wx-h">${t('dash.weatherToday')}</h2><div id="wx">${loc ? '<div class="skeleton h-20"></div>' : `<a class="btn btn-ghost" href="#/account">${icons.pin()} ${t('weather.pickTown')}</a>`}</div></section>
          <section class="card flex flex-col gap-4" aria-labelledby="farm-h" id="farm"></section>
        </div>
      </div>
    </div>`;

  const $ = (s) => host.querySelector(s);

  // ---- Weather today (real forecast, first rule as the headline) ----
  if (loc) {
    weatherAdvice(loc.lat, loc.lon, user?.crops?.[0]).then((w) => {
      const lang = settings.get().language;
      const top = w.advice?.[0];
      $('#wx').innerHTML = `
        <div class="flex items-center gap-4"><span class="text-[3.2rem]">${weatherIcon(w.current.condition_code)}</span>
          <div><p class="text-h2 font-bold">${Math.round(w.current.temp_c)}°C</p><p class="font-bold">${t(`weather.cond.${kindOf(w.current.condition_code)}`)}</p></div></div>
        ${top ? `<p>${esc(lang === 'pcm' ? top.message_pcm : top.message)}</p>` : ''}
        <a class="link text-small" href="#/weather">${t('dash.viewAll')}</a>`;
    }).catch((e) => { $('#wx').textContent = friendlyError(e); });
  }

  // ---- Saved checks (accounts only) ----
  async function loadHistory() {
    if (!isLoggedIn()) {
      $('#history').innerHTML = `<div class="flex flex-col gap-3"><h3>${t('dash.guestTitle')}</h3><p>${t('dash.guestBody')}</p>
        <div class="flex flex-col gap-3 sm:flex-row"><a class="btn btn-primary" href="#/register">${t('nav.register')}</a><a class="btn btn-ghost" href="#/login">${t('nav.login')}</a></div></div>`;
      return;
    }
    try {
      const rows = await myChecks(8);
      if (!rows.length) { $('#history').innerHTML = `<p>${t('dash.none')}</p>`; return; }
      $('#history').innerHTML = `
        <div class="table-wrap"><table>
          <thead><tr><th>${t('dash.date')}</th><th>${t('dash.crop')}</th><th>${t('dash.problem')}</th><th>${t('dash.sure')}</th><th>${t('dash.officer')}</th></tr></thead>
          <tbody>${rows.map((r) => `
            <tr tabindex="0" data-id="${r.id}" role="link" aria-label="${t('dash.open')}: ${esc(r.problem)}">
              <td class="whitespace-nowrap">${fmtDate(r.created_at)}</td>
              <td><span class="flex items-center gap-2"><span class="text-[1.6rem]">${cropIcon[r.crop] || ''}</span>${esc(t(`crops.${r.crop}`) !== `crops.${r.crop}` ? t(`crops.${r.crop}`) : r.crop)}</span></td>
              <td class="font-bold">${esc(r.problem)}</td>
              <td class="whitespace-nowrap">${t(`result.${confidenceWord(r.confidence)}`)}</td>
              <td>${r.escalate ? `<span class="chip">${t('dash.yes')}</span>` : ''}</td>
            </tr>`).join('')}</tbody></table></div>`;
      $('#history').querySelectorAll('tbody tr').forEach((tr) => {
        const open = async () => {
          const saved = await myCheck(tr.dataset.id);
          clearWork(); work.result = saved.result; work.savedId = saved.id; work.savedAt = saved.created_at;
          go('/result');
        };
        tr.addEventListener('click', open);
        tr.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });
      });
    } catch (e) {
      $('#history').textContent = friendlyError(e);
    }
  }

  // ---- About your farm: what the advisor uses ----
  function drawFarm() {
    const u = currentUser();
    const box = $('#farm');
    if (!u) {
      box.innerHTML = `<h2 id="farm-h">${t('dash.farm')}</h2><p>${t('dash.guestBody')}</p>`;
      return;
    }
    box.innerHTML = `
      <h2 id="farm-h">${t('dash.farm')}</h2>
      <p class="text-small text-ink-soft">${t('dash.farmSub')}</p>
      <div class="flex flex-wrap gap-2" id="crop-chips">${(u.crops || []).map((c) => `
        <span class="chip"><span class="text-[1.4rem]">${cropIcon[c] || ''}</span>${esc(t(`crops.${c}`) !== `crops.${c}` ? t(`crops.${c}`) : c)}
          <button type="button" class="px-1" data-remove="${esc(c)}" aria-label="${t('common.delete')} ${esc(c)}">&times;</button></span>`).join('')}</div>
      <label class="flex flex-col gap-2"><span class="field-label">${t('dash.addCrop')}</span>
        <select class="input" id="add-crop"><option value="">${t('dash.addCrop')}</option>
          ${CROPS.filter((c) => c !== 'other' && !(u.crops || []).includes(c)).map((c) => `<option value="${c}">${t(`crops.${c}`)}</option>`).join('')}</select></label>
      <label class="flex flex-col gap-2"><span class="field-label">${t('dash.notes')}</span>
        <textarea class="input min-h-[7rem]" id="notes" maxlength="500" placeholder="${t('dash.notesHint')}">${esc(u.notes)}</textarea></label>
      <button class="btn btn-primary" type="button" id="save-farm">${t('dash.save')}</button>
      <p id="farm-status" class="min-h-[1.5em] font-bold" role="status" aria-live="polite"></p>
      <div class="leaf-divider"></div>
      <h3>${t('dash.remembers')}</h3>
      <p class="text-small">${t('dash.remembersBody', { count: u.checks_count || 0 })}</p>`;
    const status = (m) => { $('#farm-status').textContent = m; };
    const save = async (patch) => {
      try { await saveProfile(patch); drawFarm(); $('#farm-status').textContent = t('dash.saved'); }
      catch (e) { status(friendlyError(e)); }
    };
    box.querySelectorAll('[data-remove]').forEach((b) => b.addEventListener('click', () =>
      save({ crops: (u.crops || []).filter((c) => c !== b.dataset.remove) })));
    box.querySelector('#add-crop').addEventListener('change', (e) => { if (e.target.value) save({ crops: [...(u.crops || []), e.target.value] }); });
    box.querySelector('#save-farm').addEventListener('click', () => save({ notes: box.querySelector('#notes').value }));
  }

  drawFarm();
  loadHistory();
  if (isLoggedIn()) refreshProfile().then(drawFarm).catch(() => {});
  // A short, quiet greeting by voice when auto-read is on.
  speak(first ? `${greeting}, ${first}.` : `${greeting}.`, { auto: true });
}
