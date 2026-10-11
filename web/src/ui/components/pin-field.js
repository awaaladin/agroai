// PIN input: numeric keypad on phones, hidden by default, with a Show/Hide toggle (important for people who
// read slowly and need to check what they typed). Returns HTML; the input id is `id`.
import { t } from '../../state/i18n.js';

export function pinField(id, { hint = false } = {}) {
  return `
    <div class="flex flex-col gap-2" data-pin-field>
      <label class="field-label" for="${id}">${t('auth.pin')}</label>
      <div class="flex items-stretch gap-2">
        <input class="input min-w-0 flex-1 tracking-[0.3em]" id="${id}" type="password" inputmode="numeric" pattern="[0-9]*"
               autocomplete="${id === 'pin' ? 'current-password' : 'new-password'}" maxlength="6" ${hint ? `aria-describedby="${id}-hint"` : ''} required>
        <button type="button" class="btn btn-ghost" data-pin-toggle aria-controls="${id}" aria-pressed="false">${t('auth.show')}</button>
      </div>
      ${hint ? `<p id="${id}-hint" class="text-small text-ink-soft">${t('auth.pinHint')}</p>` : ''}
    </div>`;
}

// One delegated listener for every PIN field on every page.
document.addEventListener('click', (e) => {
  const b = e.target.closest?.('[data-pin-toggle]');
  if (!b) return;
  const input = document.getElementById(b.getAttribute('aria-controls'));
  const show = input.type === 'password';
  input.type = show ? 'text' : 'password';
  b.setAttribute('aria-pressed', String(show));
  b.textContent = show ? t('auth.hide') : t('auth.show');
});
