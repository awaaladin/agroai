// Result: the spoken answer plays automatically (auto-read), with a plant-growth confidence meter, the reasoning,
// numbered action cards, prevention, questions to check on the farm, the officer hand-off and "Delete my data".
import { t } from '../state/i18n.js';
import { qs } from '../ui/safe-dom.js';
import { gaugeSvg, runGauge } from '../ui/fx.js';
import { speak, stop, pause, resume } from '../audio/speech.js';
import { earcon } from '../audio/earcons.js';
import { haptic } from '../device/haptics.js';
import { shareCard, deleteSession, deleteMyCheck } from '../api/endpoints.js';
import { shareText, whatsappLink, officerText } from '../device/share.js';
import { icons } from '../ui/icons/index.js';
import { cropIcon } from '../ui/crops.js';
import { friendlyError } from '../ui/components/friendly.js';
import { work, clearWork, getSessionId, setSessionId } from '../state/session.js';
import { go } from '../router.js';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

export const confidenceWord = (c) => (c >= 0.8 ? 'sure' : c >= 0.6 ? 'fairly' : 'notSure');

const WHEN_ICON = {
  today: '<circle cx="24" cy="24" r="9" fill="rgb(var(--c-sun))"/><path d="M24 6 V 11 M24 37 V 42 M6 24 H 11 M37 24 H 42 M11 11 L 15 15 M33 33 L 37 37 M11 37 L 15 33 M33 15 L 37 11"/>',
  this_week: '<rect x="8" y="10" width="32" height="30" rx="5" fill="rgb(var(--c-surface))"/><path d="M8 19 H 40 M16 6 V 13 M32 6 V 13"/><circle cx="24" cy="29" r="3.5" fill="rgb(var(--c-leaf))" stroke="none"/>',
  next_season: '<path d="M24 42 V 22" /><path d="M24 26 C 14 26 10 18 10 12 C 18 12 24 18 24 26 Z" fill="rgb(var(--c-leaf))"/><path d="M24 22 C 32 22 38 16 38 8 C 30 8 24 14 24 22 Z" fill="rgb(var(--c-leaf))"/>',
};
const whenIcon = (w) => `<svg viewBox="0 0 48 48" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${WHEN_ICON[w] || WHEN_ICON.this_week}</svg>`;

export function render(host) {
  const r = work.result;
  if (!r || !r.assessment) { go('/check', { replace: true }); return; }
  const a = r.assessment;
  const pct = Math.round(a.confidence * 100);
  const word = t(`result.${confidenceWord(a.confidence)}`);
  const low = a.confidence < 0.6;

  host.innerHTML = `
    <div class="page-narrow flex flex-col gap-6 py-6">
      <a class="btn btn-ghost -ml-3 self-start" href="#/dashboard">${icons.back()} ${t('common.back')}</a>

      <header class="flex items-center gap-4">
        ${work.photoUrl ? `<img class="photo-target h-24 w-24 flex-none rounded-leaf border-2 border-ink object-cover" src="${work.photoUrl}" alt="">` : ''}
        <div class="min-w-0">
          <p class="flex items-center gap-2 text-small font-bold text-ink-soft"><span class="text-[1.6rem]">${cropIcon[r.crop?.name] || ''}</span>${esc(r.crop?.name || '')}</p>
          <h1 class="morph-target break-words">${esc(a.likely_problem)}</h1>
        </div>
      </header>

      <section class="card flex flex-col gap-3 ${low ? 'gauge-low' : ''}" aria-label="${t('result.confidence')}">
        <div class="flex items-baseline justify-between gap-3">
          <h2>${t('result.confidence')}</h2><span class="text-h3 font-bold ${low ? 'text-clay-ink' : 'text-leaf-ink'}">${word} (<span id="pct" class="tabular-nums">${pct}</span>%)</span>
        </div>
        <div class="mx-auto w-full max-w-[19rem]" role="meter" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${pct}" aria-valuetext="${word}">
          ${gaugeSvg(word)}
        </div>
        ${a.alternatives?.length ? `<p class="text-small text-ink-soft">${t('result.alternatives')}: ${a.alternatives.map((x) => esc(x.name)).join(', ')}</p>` : ''}
      </section>

      ${r.escalate?.recommended ? `
      <section class="card flex flex-col gap-3 border-clay-ink" role="note">
        <h2 class="text-clay-ink">${t('result.escalate')}</h2>
        ${r.escalate.reason ? `<p>${esc(r.escalate.reason)}</p>` : ''}
      </section>` : ''}

      <div class="flex flex-wrap gap-3" role="group" aria-label="Audio">
        <button class="btn btn-sun" id="repeat" type="button">${icons.speaker()} ${t('common.repeat')}</button>
        <button class="btn btn-ghost" id="pause" type="button">${t('common.pause')}</button>
      </div>

      <section class="card flex flex-col gap-3"><h2>${t('result.see')}</h2><p>${esc(a.what_i_see)}</p></section>
      <section class="card flex flex-col gap-3"><h2>${t('result.why')}</h2><p>${esc(a.why_i_think_so)}</p>
        <p class="text-small text-ink-soft"><strong>${t('result.change')}:</strong> ${esc(a.what_could_change_my_mind)}</p></section>

      ${r.weather_note ? `<section class="card flex flex-col gap-2"><h2>${t('result.weatherNote')}</h2><p>${esc(r.weather_note)}</p></section>` : ''}

      <section class="flex flex-col gap-4"><h2>${t('result.actions')}</h2>
        <ol class="flex flex-col gap-4">
          ${r.actions.map((x, i) => `
          <li class="card reveal flex gap-4" style="--i:${i}">
            <span class="flex h-14 w-14 flex-none items-center justify-center rounded-leaf bg-surface-2 text-[2.2rem]">${whenIcon(x.when)}</span>
            <div class="flex min-w-0 flex-1 flex-col gap-2">
              <div class="flex flex-wrap items-center gap-2"><span class="chip">${x.step}</span><span class="chip">${t(`result.${x.when}`)}</span></div>
              <p class="font-bold">${esc(x.what)}</p><p class="text-small text-ink-soft">${esc(x.why)}</p>
              <button type="button" class="btn btn-ghost self-start" data-done aria-pressed="false">
                <svg class="tick" viewBox="0 0 48 48" width="1.4em" height="1.4em" fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path pathLength="1" d="M10 25 L 20 35 L 38 13"/></svg>
                <span>${t('result.done')}</span>
              </button>
            </div>
          </li>`).join('')}
        </ol>
      </section>

      ${r.prevention?.length ? `<section class="card flex flex-col gap-3"><h2>${t('result.prevention')}</h2>
        <ul class="flex list-none flex-col gap-2">${r.prevention.map((p) => `<li class="flex gap-3"><span class="text-[1.4rem] text-leaf-ink">${icons.check()}</span><span>${esc(p)}</span></li>`).join('')}</ul></section>` : ''}

      ${r.farmer_questions?.length ? `<section class="card flex flex-col gap-3"><h2>${t('result.questions')}</h2>
        <ul class="flex list-none flex-col gap-2">${r.farmer_questions.map((q) => `<li class="flex gap-3"><span class="text-[1.4rem]">${icons.question()}</span><span>${esc(q)}</span></li>`).join('')}</ul></section>` : ''}

      <div class="leaf-divider" role="presentation"></div>
      <div class="flex flex-col gap-4">
        <button class="btn ${r.escalate?.recommended ? 'btn-clay' : 'btn-leaf'}" id="officer" type="button">${t('result.send')}</button>
        <p id="share-status" class="min-h-[1.5em] text-center font-bold" role="status" aria-live="polite"></p>
        <button class="btn btn-primary" id="ask" type="button">${icons.question()} ${t('result.askAbout')}</button>
        <button class="btn btn-ghost" id="again" type="button">${icons.camera()} ${t('result.newPhoto')}</button>
      </div>
      <p class="text-center text-small text-ink-soft">${t('result.privacy')}</p>
      <button class="mx-auto underline" id="delete" type="button">${work.savedId ? t('history.deleteOne') : t('result.deleteData')}</button>
    </div>`;

  const $ = qs(host);
  earcon('ready');
  // The sun climbs from the horizon to how sure the advisor is.
  const stopGauge = runGauge(host.querySelector('.gauge'), a.confidence, {
    onValue: (v) => { $('#pct').textContent = String(Math.round(v * 100)); },
  });

  // The answer is read aloud automatically (auto-read setting), and again on Repeat.
  const intro = setTimeout(() => speak(r.spoken_text, { auto: true }), 500);
  $('#repeat').addEventListener('click', () => speak(r.spoken_text, { interrupt: true }));
  let paused = false;
  $('#pause').addEventListener('click', (e) => {
    paused = !paused;
    paused ? pause() : resume();
    e.currentTarget.textContent = paused ? t('common.listen') : t('common.pause');
  });

  host.querySelectorAll('[data-done]').forEach((b) => b.addEventListener('click', () => {
    const on = b.getAttribute('aria-pressed') !== 'true';
    b.setAttribute('aria-pressed', String(on));
    b.closest('li').classList.toggle('done', on);
    haptic('tap');
  }));

  $('#officer').addEventListener('click', async () => {
    const status = $('#share-status');
    status.textContent = t('result.preparing');
    try {
      let text;
      try { text = work.savedId ? null : (await shareCard(r.session_id || getSessionId())).text; } catch { text = null; }
      // Saved checks (and expired sessions) are summarised on the device from the stored answer.
      if (!text) text = officerText(r, work.savedAt);
      const how = await shareText(text);
      status.textContent = how === 'copied' ? t('result.copied') : '';
      if (how === 'whatsapp') status.innerHTML = `<a class="underline" href="${whatsappLink(text)}" target="_blank" rel="noopener">WhatsApp</a>`;
    } catch (e) {
      status.textContent = friendlyError(e);
    }
  });

  $('#ask').addEventListener('click', () => go('/chat'));
  $('#again').addEventListener('click', () => { stop(); clearWork(); go('/check'); });
  $('#delete').addEventListener('click', async () => {
    stop();
    try {
      if (work.savedId) await deleteMyCheck(work.savedId);
      else await deleteSession(r.session_id || getSessionId());
    } catch { /* it may already have expired: still clear here */ }
    setSessionId(''); clearWork();
    speak(t('result.deleted'), { interrupt: true, auto: true });
    go('/dashboard');
  });

  return () => { clearTimeout(intro); stop(); stopGauge(); };
}
