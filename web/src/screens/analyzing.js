// Analyzing: the logo mark breathes while friendly messages rotate (spoken and written) and a skeleton of
// the result card waits to fill. An unusable photo gets its spoken advice and a one-tap retake.
import { t, tList } from '../state/i18n.js';
import { settings } from '../state/store.js';
import { speak, stop } from '../audio/speech.js';
import { earcon } from '../audio/earcons.js';
import { haptic } from '../device/haptics.js';
import { diagnose } from '../api/endpoints.js';
import { friendlyError, errorBox } from '../ui/components/friendly.js';
import { work, setSessionId } from '../state/session.js';
import { getLocation } from '../device/location.js';
import { go } from '../router.js';

export function render(host) {
  if (!work.photoBlob) { go('/check', { replace: true }); return; }

  host.innerHTML = `
    <div class="page-narrow flex flex-col gap-6 py-8">
      <h1 class="text-center">${t('checking.title')}</h1>
      <img class="photo-target mx-auto h-40 w-40 rounded-leaf border border-line object-cover" src="${work.photoUrl}" alt="">
      <img class="mark-loader mx-auto h-14 w-14" src="/icons/icon.svg" alt="">
      <p id="msg" class="min-h-[3.5em] text-center text-h3 font-bold" role="status" aria-live="polite"></p>
      <div id="panel" class="flex flex-col gap-3" aria-hidden="true">
        <div class="skeleton h-10 w-3/4"></div><div class="skeleton h-6 w-full"></div>
        <div class="skeleton h-28"></div><div class="skeleton h-28"></div>
      </div>
    </div>`;

  const $ = (s) => host.querySelector(s);
  const ctl = new AbortController();
  const messages = tList('analyzing');
  let i = 0;
  let timer = null;

  const showMessage = () => {
    const m = messages[i++ % messages.length];
    $('#msg').textContent = m;
    speak(m, { auto: true });
  };

  async function run() {
    $('#panel').replaceChildren(...[...Array(4)].map((_, k) => {
      const d = document.createElement('div'); d.className = `skeleton ${['h-10 w-3/4', 'h-6 w-full', 'h-28', 'h-28'][k]}`; return d;
    }));
    i = 0; showMessage();
    clearInterval(timer);
    timer = setInterval(showMessage, 4500);
    const slow = setTimeout(() => { $('#msg').textContent = t('checking.slow'); }, 3000 + 4500 * 2);

    if (navigator.onLine === false) { fail(t('errors2.offlineCheck')); clearTimeout(slow); return; }
    const loc = getLocation();
    try {
      const res = await diagnose(work.photoBlob, {
        language: settings.get().language, crop: work.crop || undefined, symptoms: work.symptoms || undefined,
        lat: loc?.lat, lon: loc?.lon,
      }, ctl.signal);
      clearTimeout(slow); clearInterval(timer); stop();
      if (!res.image_quality.usable) return unusable(res);
      work.result = res;
      setSessionId(res.session_id);
      earcon('ready'); haptic('success');
      go('/result', { replace: true });
    } catch (e) {
      clearTimeout(slow);
      if (ctl.signal.aborted) return;
      fail(friendlyError(e));
    }
  }

  function unusable(res) {
    earcon('error'); haptic('error');
    const advice = res.image_quality.advice || res.spoken_text;
    $('#msg').textContent = '';
    $('#panel').removeAttribute('aria-hidden');
    $('#panel').innerHTML = `
      <div class="card flex flex-col gap-4 text-center" role="alert">
        <h2>${t('checking.retakeTitle')}</h2>
        <p class="mx-auto text-h3">${advice}</p>
        <button class="btn btn-primary" id="retake" type="button">${t('check.retake')}</button>
      </div>`;
    speak(advice, { interrupt: true });
    $('#retake').addEventListener('click', () => go('/check'));
    $('#retake').focus();
  }

  function fail(message) {
    clearInterval(timer); stop();
    earcon('error'); haptic('error');
    $('#msg').textContent = '';
    $('#panel').removeAttribute('aria-hidden');
    $('#panel').replaceChildren(errorBox(message, run));
    speak(message, { interrupt: true, auto: true });
  }

  run();
  return () => { ctl.abort(); clearInterval(timer); stop(); };
}
