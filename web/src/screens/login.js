// Log in with phone number and PIN. Friendly, spoken-aloud-able errors; lock-out messages come from the server.
import { t } from '../state/i18n.js';
import { qs } from '../ui/safe-dom.js';
import { settings } from '../state/store.js';
import { signIn } from '../state/account.js';
import { friendlyError } from '../ui/components/friendly.js';
import { speak } from '../audio/speech.js';
import { go } from '../router.js';
import { isLoggedIn } from '../api/auth.js';
import { pinField } from '../ui/components/pin-field.js';

export function render(host) {
  if (isLoggedIn()) { go('/dashboard', { replace: true }); return; }
  host.innerHTML = `
    <div class="page-narrow py-10">
      <h1 class="mb-6">${t('auth.loginTitle')}</h1>
      <form id="form" class="card flex flex-col gap-5" novalidate>
        <label class="flex flex-col gap-2"><span class="field-label">${t('auth.phone')}</span>
          <input class="input" id="phone" type="tel" inputmode="tel" autocomplete="tel" placeholder="${t('auth.phoneHint')}" required></label>
        ${pinField('pin')}
        <p id="error" class="min-h-[1.5em] font-bold text-clay-ink" role="alert"></p>
        <button class="btn btn-primary" id="submit" type="submit">${t('auth.submitLogin')}</button>
        <p class="text-small">${t('auth.noAccount')} <a class="link" href="#/register">${t('nav.register')}</a></p>
      </form>
    </div>`;

  const $ = qs(host);
  $('#form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const err = $('#error');
    err.textContent = '';
    const phone = $('#phone').value.trim();
    const pin = $('#pin').value.trim();
    if (!phone) { err.textContent = t('auth.invalidPhone'); $('#phone').focus(); return; }
    if (!/^\d{4,6}$/.test(pin)) { err.textContent = t('auth.invalidPin'); $('#pin').focus(); return; }
    $('#submit').disabled = true;
    $('#submit').textContent = t('auth.working');
    try {
      const user = await signIn(phone, pin);
      speak(t('auth.welcomeBack', { name: user.name || '' }).replace(' ,', ','), { auto: true });
      go('/dashboard');
    } catch (e2) {
      const pcm = settings.get().language === 'pcm';
      err.textContent = (pcm && e2.detailPcm) || e2.detail || friendlyError(e2);
      $('#submit').disabled = false;
      $('#submit').textContent = t('auth.submitLogin');
    }
  });
  $('#phone').focus();
}
