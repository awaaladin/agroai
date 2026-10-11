// Check my crop: rear camera in a leaf-shaped frame, an optional crop picker with big pictures, spoken tips,
// a giant shutter, and a gallery fallback. The photo is compressed and re-encoded on the device (1280 px, JPEG 85),
// which also strips EXIF and GPS, then sent for checking on the Analyzing screen.
import { t, tList } from '../state/i18n.js';
import { settings } from '../state/store.js';
import { speak, stop } from '../audio/speech.js';
import { earcon } from '../audio/earcons.js';
import { haptic } from '../device/haptics.js';
import { startCamera, stopCamera, compress, cameraSupported } from '../device/camera.js';
import { CROPS, cropIcon } from '../ui/crops.js';
import { icons } from '../ui/icons/index.js';
import { go } from '../router.js';
import { work, setPhoto, clearWork } from '../state/session.js';

export function render(host) {
  clearWork();
  host.innerHTML = `
    <div class="page-narrow flex flex-col gap-5 py-6">
      <a class="btn btn-ghost -ml-3 self-start" href="#/dashboard">${icons.back()} ${t('common.back')}</a>
      <h1 class="morph-target">${t('check.title')}</h1>

      <div class="relative mx-auto w-full max-w-md overflow-hidden bg-surface-2 photo-frame" id="frame" style="aspect-ratio:3/4;border-radius:1rem;border:var(--border-w) solid rgb(var(--c-ink))">
        <video id="video" class="h-full w-full object-cover" playsinline muted aria-label="Camera preview"></video>
        <div id="flash" class="pointer-events-none absolute inset-0 bg-bg opacity-0" aria-hidden="true"></div>
        <div id="nocam" class="absolute inset-0 flex flex-col items-center justify-center gap-3 p-8 text-center" hidden>
          <span class="text-[4rem]">${icons.camera()}</span><p id="nocam-text"></p>
        </div>
      </div>
      <p id="tip" class="text-center text-h3 font-bold" role="status" aria-live="polite"></p>

      <div class="flex items-center justify-center gap-5">
        <label class="btn btn-ghost" for="gallery">${t('check.gallery')}</label>
        <input id="gallery" class="sr-only" type="file" accept="image/*">
        <button id="shutter" type="button" class="btn btn-sun h-24 w-24 rounded-full p-0" aria-label="${t('check.shutter')}" disabled>
          <span class="h-14 w-14 rounded-full border-4 border-ink bg-sun" aria-hidden="true"></span>
        </button>
        <label class="btn btn-ghost" id="cap-label" for="capture" hidden>${icons.camera()} ${t('check.openCamera')}</label>
        <input id="capture" class="sr-only" type="file" accept="image/*" capture="environment">
      </div>

      <section class="flex flex-col gap-3">
        <h2>${t('check.pickCrop')}</h2>
        <p class="text-small text-ink-soft">${t('check.optional')}</p>
        <div class="grid grid-cols-3 gap-3 sm:grid-cols-4" role="group" aria-label="${t('check.pickCrop')}">
          ${CROPS.map((c) => `
            <button type="button" class="action-card flex flex-col items-center gap-1 !p-3 text-center" data-crop="${c}" aria-pressed="false">
              <span class="text-[3rem]">${cropIcon[c]}</span><span class="text-small font-bold">${t(`crops.${c}`)}</span>
            </button>`).join('')}
        </div>
      </section>

      <label class="flex flex-col gap-2"><span class="font-bold">${t('check.symptoms')}</span>
        <input id="symptoms" class="input" maxlength="500" placeholder="${t('check.symptomsHint')}" autocomplete="off">
      </label>
    </div>`;

  const $ = (s) => host.querySelector(s);
  const video = $('#video');
  const shutter = $('#shutter');
  const tips = tList('check.tips');
  let tipIndex = 0;
  let tipTimer = null;
  let firstTip = null;
  let busy = false;

  // --- crop picker (optional, one at a time, tap again to clear) ---
  host.querySelectorAll('[data-crop]').forEach((b) => b.addEventListener('click', () => {
    const on = b.getAttribute('aria-pressed') !== 'true';
    host.querySelectorAll('[data-crop]').forEach((x) => x.setAttribute('aria-pressed', 'false'));
    b.setAttribute('aria-pressed', String(on));
    work.crop = on && b.dataset.crop !== 'other' ? b.dataset.crop : '';
    host.querySelectorAll('[data-crop]').forEach((x) => { x.style.background = x.getAttribute('aria-pressed') === 'true' ? 'rgb(var(--c-leaf) / 0.35)' : ''; });
    haptic('tap');
    speak(t(`crops.${b.dataset.crop}`), { interrupt: true, auto: true });
  }));

  // --- spoken tips, one every few seconds while the camera is open ---
  function nextTip() {
    if (!host.isConnected || !$('#tip')) return; // the farmer already left this screen
    const tip = tips[tipIndex++ % tips.length];
    $('#tip').textContent = tip;
    speak(tip, { auto: true });
  }

  function cameraOff(reason) {
    $('#nocam').hidden = false;
    $('#nocam-text').textContent = reason;
    $('#cap-label').hidden = false;
    clearInterval(tipTimer);
    $('#tip').textContent = '';
  }

  async function open() {
    if (!cameraSupported() || settings.get().perms?.camera === 'denied') return cameraOff(t('check.noCamera'));
    try {
      await startCamera(video);
      shutter.disabled = false;
      tipTimer = setInterval(nextTip, 7000);
      firstTip = setTimeout(nextTip, 600);
    } catch {
      earcon('error');
      cameraOff(t('errors.camera'));
    }
  }

  // --- capture ---
  async function finish(source) {
    if (busy) return;
    busy = true;
    clearInterval(tipTimer); clearTimeout(firstTip);
    stop();
    work.symptoms = $('#symptoms').value.trim();
    try {
      const { blob } = await compress(source);
      setPhoto(blob);
      stopCamera();
      $('#frame').style.viewTransitionName = 'photo';
      go('/analyzing');
    } catch {
      busy = false;
      earcon('error');
      $('#tip').textContent = t('check.badFile');
    }
  }

  shutter.addEventListener('click', async () => {
    if (!video.videoWidth) return;
    haptic('capture'); earcon('captured');
    const flash = $('#flash');
    flash.animate([{ opacity: 0.85 }, { opacity: 0 }], { duration: 260, easing: 'ease-out' });
    await finish(video);
  });
  const fromFile = (e) => { const f = e.target.files?.[0]; if (f) { haptic('capture'); earcon('captured'); finish(f); } };
  $('#gallery').addEventListener('change', fromFile);
  $('#capture').addEventListener('change', fromFile);

  open();
  return () => { clearInterval(tipTimer); clearTimeout(firstTip); stopCamera(); stop(); };
}
