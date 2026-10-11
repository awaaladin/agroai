// Create an account: phone number and PIN, plus the few things that make advice personal (language, town).
// Location is optional and coarse; a town can be picked instead. Everything is editable later in My account.
import { t } from '../state/i18n.js';
import { settings } from '../state/store.js';
import { signUp } from '../state/account.js';
import { friendlyError } from '../ui/components/friendly.js';
import { speak } from '../audio/speech.js';
import { go } from '../router.js';
import { isLoggedIn } from '../api/auth.js';
import { pinField } from '../ui/components/pin-field.js';
import { TOWNS, detect } from '../device/location.js';
import { LANGUAGES } from '../state/i18n.js';

export function render(host) {
  if (isLoggedIn()) { go('/dashboard', { replace: true }); return; }
  const s = settings.get();
  let coords = s.lat != null ? { lat: s.lat, lon: s.lon } : null;

  host.innerHTML = `
    <div class="page-narrow py-10">
      <h1 class="mb-6">${t('auth.registerTitle')}</h1>
      <form id="form" class="card flex flex-col gap-5" novalidate>
        <label class="flex flex-col gap-2"><span class="field-label">${t('auth.name')}</span>
          <input class="input" id="name" autocomplete="given-name" maxlength="80"></label>
        <label class="flex flex-col gap-2"><span class="field-label">${t('auth.phone')}</span>
          <input class="input" id="phone" type="tel" inputmode="tel" autocomplete="tel" placeholder="${t('auth.phoneHint')}" required></label>
        ${pinField('newpin', { hint: true })}
        <p class="text-small text-ink-soft">${t('auth.pinNote')}</p>
        <fieldset class="flex flex-col gap-2"><legend class="field-label">${t('auth.language')}</legend>
          <div class="flex gap-3">${LANGUAGES.map((l) => `<label class="btn ${s.language === l.code ? 'btn-primary' : 'btn-ghost'} flex-1">
            <input class="sr-only" type="radio" name="lang" value="${l.code}" ${s.language === l.code ? 'checked' : ''}>${l.label}</label>`).join('')}</div>
        </fieldset>
        <label class="flex flex-col gap-2"><span class="field-label">${t('auth.town')}</span>
          <select class="input" id="town"><option value="">${t('auth.townPick')}</option>
            ${TOWNS.map((x) => `<option value="${x.name}" ${s.town === x.name ? 'selected' : ''}>${x.name}</option>`).join('')}</select></label>
        <button type="button" class="btn btn-ghost" id="locate">${t('auth.useLocation')}</button>
        <p id="locate-status" class="min-h-[1.5em] text-small font-bold" role="status" aria-live="polite"></p>
        <p id="error" class="min-h-[1.5em] font-bold text-clay-ink" role="alert"></p>
        <button class="btn btn-primary" id="submit" type="submit">${t('auth.submitRegister')}</button>
        <p class="text-small">${t('auth.hasAccount')} <a class="link" href="#/login">${t('nav.login')}</a></p>
      </form>
    </div>`;

  const $ = (q) => host.querySelector(q);
  host.querySelectorAll('input[name="lang"]').forEach((r) => r.addEventListener('change', () => {
    settings.set({ language: r.value });
    // re-render in the new language, keeping what was typed
    const keep = { name: $('#name').value, phone: $('#phone').value, town: $('#town').value };
    render(host);
    host.querySelector('#name').value = keep.name; host.querySelector('#phone').value = keep.phone; host.querySelector('#town').value = keep.town;
  }));

  $('#locate').addEventListener('click', async () => {
    $('#locate-status').textContent = t('auth.locating');
    try {
      coords = await detect();
      $('#town').value = '';
      $('#locate-status').textContent = t('auth.located');
    } catch {
      $('#locate-status').textContent = t('errors.location');
    }
  });
  $('#town').addEventListener('change', () => {
    const tw = TOWNS.find((x) => x.name === $('#town').value);
    coords = tw ? { lat: tw.lat, lon: tw.lon } : coords;
  });

  $('#form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const err = $('#error');
    err.textContent = '';
    const phone = $('#phone').value.trim();
    const pin = $('#newpin').value.trim();
    if (!phone) { err.textContent = t('auth.invalidPhone'); $('#phone').focus(); return; }
    if (!/^\d{4,6}$/.test(pin)) { err.textContent = t('auth.invalidPin'); $('#newpin').focus(); return; }
    const lang = host.querySelector('input[name="lang"]:checked')?.value || 'en';
    $('#submit').disabled = true;
    $('#submit').textContent = t('auth.working');
    try {
      const user = await signUp({
        phone, pin, name: $('#name').value.trim(), language: lang, town: $('#town').value,
        lat: coords?.lat, lon: coords?.lon,
      });
      speak(t('auth.welcome', { name: user.name || '' }).replace(' ,', ','), { auto: true });
      go('/dashboard');
    } catch (e2) {
      const pcm = settings.get().language === 'pcm';
      err.textContent = (pcm && e2.detailPcm) || e2.detail || friendlyError(e2);
      $('#submit').disabled = false;
      $('#submit').textContent = t('auth.submitRegister');
    }
  });
  $('#name').focus();
}
