// Voice picker: choose Woman / Man / Any, optionally pick one exact voice, and hear it. The list comes from the
// device (Web Speech API), so it differs between phones and browsers. Used on Home and in Settings.
import { settings } from '../../state/store.js';
import { t } from '../../state/i18n.js';
import { listVoices, voiceGender, speak, speechSupported } from '../../audio/speech.js';

const GENDERS = ['female', 'male', 'any'];

/** @param {HTMLElement} host */
export function mountVoicePicker(host) {
  if (!speechSupported) {
    host.innerHTML = `<p>${t('voice.none')}</p>`;
    return () => {};
  }
  const draw = async () => {
    const s = settings.get();
    const voices = await listVoices(s.voiceGender);
    const sample = () => speak(t('voice.sample'), { interrupt: true });
    host.innerHTML = `
      <div class="flex flex-col gap-4">
        <div class="flex flex-wrap gap-3" role="radiogroup" aria-label="${t('voice.title')}">
          ${GENDERS.map((g) => `<button type="button" class="btn ${s.voiceGender === g ? 'btn-primary' : 'btn-ghost'}"
              role="radio" aria-checked="${s.voiceGender === g}" data-gender="${g}">${t(`voice.${g}`)}</button>`).join('')}
        </div>
        ${voices.length ? `
        <label class="flex flex-col gap-2"><span class="font-bold">${t('voice.title')}</span>
          <select class="input" id="voice-select">
            <option value="">${t('voice.best')}${voices[0] ? ` (${voices[0].name.replace(/^Microsoft /, '').split(' - ')[0]})` : ''}</option>
            ${voices.map((v) => `<option value="${v.voiceURI}" ${s.voiceURI === v.voiceURI ? 'selected' : ''}>${
              v.name.replace(/^Microsoft /, '')} ${voiceGender(v) === 'female' ? '(' + t('voice.female') + ')' : voiceGender(v) === 'male' ? '(' + t('voice.male') + ')' : ''}</option>`).join('')}
          </select>
        </label>
        <button type="button" class="btn btn-sun" id="voice-hear">${t('voice.hear')}</button>` : `<p>${t('voice.none')}</p>`}
        <p class="text-small text-ink-soft">${t('voice.note')}</p>
      </div>`;
    host.querySelectorAll('[data-gender]').forEach((b) => b.addEventListener('click', () => {
      settings.set({ voiceGender: b.dataset.gender, voiceURI: '' }); // a new gender choice clears an exact voice
      draw().then(sample);
    }));
    host.querySelector('#voice-select')?.addEventListener('change', (e) => { settings.set({ voiceURI: e.target.value }); sample(); });
    host.querySelector('#voice-hear')?.addEventListener('click', sample);
  };
  draw();
  return () => {};
}
