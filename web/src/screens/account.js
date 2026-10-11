// My account: profile, voice and display preferences, privacy controls (delete history, delete account).
import { t } from '../state/i18n.js';
import { qs } from '../ui/safe-dom.js';
import { settings } from '../state/store.js';
import { currentUser, isLoggedIn } from '../api/auth.js';
import { saveProfile, logout } from '../state/account.js';
import { clearMyHistory, deleteMyAccount } from '../api/endpoints.js';
import { TOWNS, detect, placeName } from '../device/location.js';
import { mountVoicePicker } from '../ui/components/voice-picker.js';
import { friendlyError } from '../ui/components/friendly.js';
import { speak } from '../audio/speech.js';
import { go } from '../router.js';
import { clearUser } from '../api/auth.js';
import { setSessionId, clearWork } from '../state/session.js';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const check = (id, label, on) => `
  <label class="flex min-h-tap items-center gap-3"><input id="${id}" type="checkbox" class="h-6 w-6" ${on ? 'checked' : ''}><span>${label}</span></label>`;

export function render(host) {
  const u = currentUser();
  const s = settings.get();
  // Small, Normal, Large, Largest. A size saved by an older version snaps to the nearest one.
  const scales = [[0.85, 'account.tiny'], [1, 'account.small'], [1.2, 'account.medium'], [1.4, 'account.large']];
  const nearest = scales.reduce((a, b) => (Math.abs(b[0] - s.textScale) < Math.abs(a[0] - s.textScale) ? b : a))[0];

  host.innerHTML = `
    <div class="page-narrow flex flex-col gap-6 py-8">
      <h1>${t('account.title')}</h1>

      ${u ? `
      <section class="card flex flex-col gap-4" aria-labelledby="prof-h">
        <h2 id="prof-h">${t('account.profile')}</h2>
        <p><span class="text-ink-soft">${t('account.phone')}:</span> <strong>${esc(u.phone)}</strong></p>
        <label class="flex flex-col gap-2"><span class="field-label">${t('auth.name')}</span><input class="input" id="name" value="${esc(u.name)}" maxlength="80"></label>
        <label class="flex flex-col gap-2"><span class="field-label">${t('auth.town')}</span>
          <select class="input" id="town"><option value="">${t('auth.townPick')}</option>
          ${TOWNS.map((x) => `<option value="${x.name}" ${u.town === x.name ? 'selected' : ''}>${x.name}</option>`).join('')}</select></label>
        <button class="btn btn-ghost" type="button" id="locate">${t('auth.useLocation')}</button>
        <button class="btn btn-primary" type="button" id="save">${t('dash.save')}</button>
        <p id="status" class="min-h-[1.5em] font-bold" role="status" aria-live="polite"></p>
      </section>` : ''}

      <section class="card flex flex-col gap-4" aria-labelledby="disp-h">
        <h2 id="disp-h">${t('account.display')}</h2>
        <fieldset class="flex flex-col gap-2"><legend class="field-label">${t('auth.language')}</legend>
          <div class="flex gap-3">
            ${[['en', 'English'], ['pcm', 'Pidgin']].map(([c, l]) => `<button type="button" class="btn ${s.language === c ? 'btn-primary' : 'btn-ghost'} flex-1" data-lang="${c}" aria-pressed="${s.language === c}">${l}</button>`).join('')}
          </div>
        </fieldset>
        <div id="voice-picker"></div>
        <label class="flex flex-col gap-2"><span class="field-label">${t('speech.speed')}</span>
          <input id="rate" type="range" min="0.6" max="1.3" step="0.05" value="${s.speechRate}" class="min-h-tap w-full"></label>
        ${check('autoRead', t('account.autoRead'), s.autoRead)}
        ${check('sound', t('account.sound'), s.sound)}
        ${check('haptics', t('account.haptics'), s.haptics)}
        ${check('screenReader', t('account.screenReader'), s.screenReader)}
        <fieldset class="flex flex-col gap-2"><legend class="field-label">${t('account.textSize')}</legend>
          <div class="flex flex-wrap gap-3">${scales.map(([v, k]) => `<button type="button" class="btn ${nearest === v ? 'btn-primary' : 'btn-ghost'}" data-scale="${v}" aria-pressed="${nearest === v}">${t(k)}</button>`).join('')}</div>
        </fieldset>
        <fieldset class="flex flex-col gap-2"><legend class="field-label">${t('account.theme')}</legend>
          <div class="flex flex-wrap gap-3">${['light', 'dark', 'contrast'].map((k) => `<button type="button" class="btn ${s.theme === k ? 'btn-primary' : 'btn-ghost'}" data-theme-set="${k}" aria-pressed="${s.theme === k}">${t(`account.${k}`)}</button>`).join('')}</div>
        </fieldset>
        ${check('reduceMotion', t('account.reduceMotion'), s.reduceMotion)}
      </section>

      <section class="card flex flex-col gap-4" aria-labelledby="priv-h">
        <h2 id="priv-h">${t('account.privacy')}</h2>
        <p>${t('account.privacyBody')}</p>
        <button class="btn btn-ghost self-start" type="button" id="promise">${t('account.privacyPromise')}</button>
        ${u ? `
        <div class="leaf-divider"></div>
        <div id="danger" class="flex flex-col gap-3">
          <button class="btn btn-ghost self-start" type="button" id="clear">${t('account.clearHistory')}</button>
          <button class="btn btn-clay self-start" type="button" id="delete">${t('account.deleteAccount')}</button>
        </div>
        <div id="confirm" class="card flex flex-col gap-3 border-clay-ink" role="alertdialog" aria-labelledby="confirm-text" hidden>
          <p id="confirm-text" class="font-bold"></p>
          <div class="flex gap-3"><button class="btn btn-clay" id="yes" type="button">${t('account.confirm')}</button>
            <button class="btn btn-ghost" id="no" type="button">${t('account.cancel')}</button></div>
        </div>` : ''}
      </section>

      <div class="flex gap-3">
        ${isLoggedIn() ? `<button class="btn btn-ghost" type="button" id="logout">${t('nav.logout')}</button>` : `<a class="btn btn-primary" href="#/register">${t('nav.register')}</a>`}
      </div>
    </div>`;

  const $ = qs(host);
  mountVoicePicker($('#voice-picker'));

  host.querySelectorAll('[data-lang]').forEach((b) => b.addEventListener('click', async () => {
    settings.set({ language: b.dataset.lang });
    if (u) { try { await saveProfile({ language: b.dataset.lang }); } catch { /* the choice still applies on this device */ } }
    render(host);
  }));
  host.querySelectorAll('[data-scale]').forEach((b) => b.addEventListener('click', () => { settings.set({ textScale: Number(b.dataset.scale) }); render(host); }));
  host.querySelectorAll('[data-theme-set]').forEach((b) => b.addEventListener('click', () => { settings.set({ theme: b.dataset.themeSet }); render(host); }));
  $('#rate').addEventListener('input', (e) => settings.set({ speechRate: Number(e.target.value) }));
  for (const k of ['autoRead', 'sound', 'haptics', 'screenReader', 'reduceMotion']) {
    $(`#${k}`).addEventListener('change', (e) => settings.set({ [k]: e.target.checked }));
  }
  $('#promise').addEventListener('click', () => speak(t('account.privacySpoken'), { interrupt: true }));
  $('#logout')?.addEventListener('click', logout);

  if (u) {
    const status = (m) => { $('#status').textContent = m; };
    $('#save').addEventListener('click', async () => {
      const town = TOWNS.find((x) => x.name === $('#town').value);
      try {
        await saveProfile({ name: $('#name').value, town: town?.name ?? '', ...(town ? { lat: town.lat, lon: town.lon } : {}) });
        status(t('dash.saved'));
      } catch (e) { status(friendlyError(e)); }
    });
    $('#locate').addEventListener('click', async () => {
      status(t('auth.locating'));
      try {
        const c = await detect();
        const place = await placeName(c); // "Uyo, Akwa Ibom" from the real position, or the nearest known town
        await saveProfile({ town: place, lat: c.lat, lon: c.lon });
        $('#town').value = '';
        status(place ? `${t('auth.located')} ${place}` : t('auth.located'));
      }
      catch { status(t('errors.location')); }
    });

    // Two-step delete: nothing destructive happens on a single tap.
    let pending = null;
    const ask = (text, action) => { pending = action; $('#confirm-text').textContent = text; $('#confirm').hidden = false; $('#yes').focus(); };
    $('#clear').addEventListener('click', () => ask(t('account.clearConfirm'), async () => {
      await clearMyHistory(); status(t('account.cleared')); speak(t('account.cleared'), { auto: true });
    }));
    $('#delete').addEventListener('click', () => ask(t('account.deleteConfirm'), async () => {
      await deleteMyAccount();
      clearUser(); setSessionId(''); clearWork();
      settings.set({ guest: false, town: '', lat: null, lon: null, locationSource: '' });
      speak(t('account.deleted'), { auto: true });
      go('/');
    }));
    $('#no').addEventListener('click', () => { $('#confirm').hidden = true; pending = null; });
    $('#yes').addEventListener('click', async () => {
      $('#confirm').hidden = true;
      try { await pending?.(); } catch (e) { status(friendlyError(e)); }
    });
  }
}
