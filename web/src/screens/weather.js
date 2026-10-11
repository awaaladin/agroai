// Weather: current conditions, a 5-day strip with animated icons and words, and a "What this means for your farm
// today" card built from the backend's deterministic rules, read aloud on tap. The page background shifts gently
// with the weather and the time of day.
import { t } from '../state/i18n.js';
import { qs } from '../ui/safe-dom.js';
import { settings } from '../state/store.js';
import { speak, stop } from '../audio/speech.js';
import { earcon } from '../audio/earcons.js';
import { weatherAdvice } from '../api/endpoints.js';
import { weatherIcon, kindOf } from '../ui/weather-icons.js';
import { icons } from '../ui/icons/index.js';
import { friendlyError, errorBox } from '../ui/components/friendly.js';
import { getLocation } from '../device/location.js';
import { work } from '../state/session.js';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function dayName(iso, index, lang) {
  if (index === 0) return t('result.today');
  const d = new Date(`${iso}T12:00:00`);
  return new Intl.DateTimeFormat(lang === 'pcm' ? 'en-NG' : 'en', { weekday: 'short' }).format(d);
}

export function render(host) {
  const loc = getLocation();
  const lang = settings.get().language;
  const hour = new Date().getHours();
  host.innerHTML = `
    <div class="wx-page page-narrow flex flex-col gap-5 py-6" id="page" data-daypart="${hour >= 6 && hour < 18 ? 'day' : 'night'}">
      <a class="btn btn-ghost -ml-3 self-start" href="#/dashboard">${icons.back()} ${t('common.back')}</a>
      <h1 class="morph-target">${t('weather.title')}</h1>
      <div id="body" class="flex flex-col gap-5">
        <div class="skeleton h-40"></div><div class="skeleton h-32"></div><div class="skeleton h-40"></div>
      </div>
    </div>`;
  const $ = qs(host);
  const ctl = new AbortController();

  if (!loc) {
    $('#body').innerHTML = `<div class="card flex flex-col gap-4 text-center">
      <p class="text-h3">${t('weather.noLocation')}</p>
      <a class="btn btn-primary" href="#/account">${icons.pin()} ${t('weather.pickTown')}</a></div>`;
    return () => {};
  }

  async function load() {
    $('#body').innerHTML = `<div class="skeleton h-40"></div><div class="skeleton h-32"></div><div class="skeleton h-40"></div>`;
    try {
      const w = await weatherAdvice(loc.lat, loc.lon, work.result?.crop?.name || work.crop || undefined, ctl.signal);
      earcon('ready');
      draw(w);
    } catch (e) {
      if (ctl.signal.aborted) return;
      earcon('error');
      const msg = friendlyError(e);
      $('#body').replaceChildren(errorBox(msg, load));
      speak(msg, { auto: true });
    }
  }

  function draw(w) {
    const kind = kindOf(w.current.condition_code);
    $('#page').dataset.wx = kind; // CSS shifts the background with the weather
    const word = (c) => t(`weather.cond.${kindOf(c)}`);
    const advice = w.advice || [];
    const meaning = advice.map((a) => (lang === 'pcm' ? a.message_pcm : a.message));
    const spoken = meaning.join(' ');

    $('#body').innerHTML = `
      <section class="card flex items-center gap-5" aria-label="${t('weather.now')}">
        <span class="text-[5rem]">${weatherIcon(w.current.condition_code)}</span>
        <div>
          <p class="text-small font-bold text-ink-soft">${loc.town ? t('weather.updated', { town: esc(loc.town) }) : t('weather.now')}</p>
          <p class="text-h1">${Math.round(w.current.temp_c)}°C</p>
          <p class="text-h3 font-bold">${word(w.current.condition_code)}</p>
        </div>
      </section>

      <section aria-label="${t('weather.forecast')}">
        <h2 class="mb-3">${t('weather.forecast')}</h2>
        <ol class="grid grid-cols-5 gap-2">
          ${w.days.map((d, i) => `
            <li class="reveal flex flex-col items-center gap-1 rounded-2xl bg-surface p-2 text-center" style="--i:${i}">
              <span class="text-small font-bold">${dayName(d.date, i, lang)}</span>
              <span class="text-[2.6rem]">${weatherIcon(d.condition_code)}</span>
              <span class="text-small font-bold leading-tight">${word(d.condition_code)}</span>
              <span class="text-small">${Math.round(d.high_c)}° / ${Math.round(d.low_c)}°</span>
              <span class="text-small text-ink-soft">${d.rain_chance_pct}%</span>
            </li>`).join('')}
        </ol>
      </section>

      <section class="card flex flex-col gap-3" aria-labelledby="meaning-h">
        <h2 id="meaning-h">${t('weather.meaning')}</h2>
        ${advice.length ? `<ul class="flex list-none flex-col gap-3">
          ${advice.map((a, i) => `<li class="flex gap-3"><span class="mt-1 flex-none rounded-pod px-2 text-small font-bold ${a.severity === 'warning' ? 'bg-clay-ink text-bg' : a.severity === 'good' ? 'bg-leaf text-ink' : 'bg-surface-2'}">${
            a.severity === 'warning' ? '!' : a.severity === 'good' ? '&#10003;' : 'i'}</span><span>${esc(meaning[i])}</span></li>`).join('')}</ul>` : `<p>${t('weather.cond.clear')}</p>`}
        <button type="button" class="btn btn-sun self-start" id="hear">${icons.speaker()} ${t('weather.hear')}</button>
      </section>`;

    $('#hear').addEventListener('click', () => speak(spoken || word(w.current.condition_code), { interrupt: true }));
    // Read aloud when the farmer taps the card, as well as on the button.
    $('#body').querySelector('[aria-labelledby="meaning-h"]').addEventListener('click', (e) => {
      if (e.target.closest('button, a')) return;
      speak(spoken, { interrupt: true });
    });
  }

  load();
  return () => { ctl.abort(); stop(); };
}
