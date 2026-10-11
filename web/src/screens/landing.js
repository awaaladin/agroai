// Landing. A field seen from above: furrow lines, red soil, a sun that climbs the horizon as the advisor becomes sure.
// One loop in the hero shows the whole product (look at the leaf, then the answer). All numbers are true statements
// about the product; the example answer is labelled as an illustration.
import { t } from '../state/i18n.js';
import { go } from '../router.js';
import { isLoggedIn } from '../api/auth.js';
import { continueAsGuest } from '../state/account.js';
import { settings } from '../state/store.js';
import { icons } from '../ui/icons/index.js';
import { cropIcon, CROPS } from '../ui/crops.js';
import { gaugeSvg, watchScroll, spotlight } from '../ui/fx.js';
import { qs } from '../ui/safe-dom.js';

const KNOWN = CROPS.filter((c) => c !== 'other');

const leafScene = `
  <svg class="demo-leaf" viewBox="0 0 320 200" fill="none" role="img" aria-label="${'Leaf with pale patches'}">
    <rect width="320" height="200" rx="16" fill="rgb(var(--c-surface-2))"/>
    <path d="M40 170 C 40 70 120 22 262 24 C 262 118 190 176 52 178 Z" fill="rgb(var(--c-leaf))" stroke="rgb(var(--c-ink))" stroke-width="3"/>
    <path d="M52 168 C 110 130 170 90 244 40" stroke="rgb(var(--c-ink))" stroke-opacity=".55" stroke-width="3" stroke-linecap="round"/>
    <path d="M100 138 L 130 96 M138 112 L 176 82 M168 92 L 196 62" stroke="rgb(var(--c-ink))" stroke-opacity=".4" stroke-width="2.5" stroke-linecap="round"/>
    <g fill="rgb(var(--c-sun))" opacity=".9"><ellipse cx="120" cy="120" rx="20" ry="12" transform="rotate(-28 120 120)"/>
      <ellipse cx="190" cy="98" rx="24" ry="14" transform="rotate(-30 190 98)"/><ellipse cx="150" cy="68" rx="14" ry="9" transform="rotate(-25 150 68)"/>
      <ellipse cx="86" cy="152" rx="12" ry="8" transform="rotate(-30 86 152)"/></g>
  </svg>`;

export function render(host) {
  if (isLoggedIn() || settings.get().guest) { go('/dashboard', { replace: true }); return; }
  const $ = qs(host);

  const steps = ['s1', 's2', 's3'].map((k, i) => `
    <li class="sr spot card flex gap-4" style="--i:${i}" data-spot>
      <span class="step-num" aria-hidden="true">${i + 1}</span>
      <div class="flex flex-col gap-1"><h3>${t(`landing.how.${k}.t`)}</h3><p>${t(`landing.how.${k}.b`)}</p></div>
    </li>`).join('');

  const crops = KNOWN.map((c, i) => `
    <li class="sr card spot flex flex-col items-center gap-2 !p-4 text-center" style="--i:${i}" data-spot>
      <span class="flex h-14 w-14 items-center justify-center rounded-leaf bg-surface-2 text-[2.2rem]">${cropIcon[c]}</span>
      <span class="font-bold">${t(`crops.${c}`)}</span>
    </li>`).join('');

  const facts = [
    [KNOWN.length, '', 'landing.facts.crops'],
    [2, '', 'landing.facts.languages'],
    [5, '', 'landing.facts.forecast'],
    [0, '', 'landing.facts.photos'],
  ].map(([n, suffix, key]) => `
    <div class="sr flex flex-col gap-1"><span class="text-h1 font-bold tabular-nums text-leaf-ink" data-count="${n}" data-suffix="${suffix}">0</span>
      <span class="text-small text-ink-soft">${t(key)}</span></div>`).join('');

  host.innerHTML = `
    <section class="band-dark furrows" data-screen="landing">
      <div class="page grid gap-10 py-14 md:grid-cols-2 md:items-center md:py-20">
        <div class="flex flex-col gap-6">
          <p class="eyebrow fade-in">${t('landing.eyebrow')}</p>
          <h1 class="fade-in" style="--d:80ms">${t('landing.title')}</h1>
          <p class="fade-in" style="--d:160ms">${t('landing.lead')}</p>
          <div class="hero-cta fade-in flex flex-col gap-3 sm:flex-row sm:flex-wrap" style="--d:240ms">
            <a class="btn btn-leaf" href="#/register">${t('landing.cta')}</a>
            <button class="btn btn-ghost" id="guest" type="button">${t('landing.guest')}</button>
          </div>
          <p class="fade-in text-small" style="--d:300ms"><a class="link" href="#/login">${t('landing.haveAccount')}</a></p>
        </div>

        <figure class="demo card fade-in" style="--d:200ms" aria-label="${t('landing.example.label')}">
          <div class="demo-layer demo-scan" aria-hidden="true">
            <p class="eyebrow">${t('landing.example.label')}</p>
            ${leafScene}
            <span class="demo-line"></span>
            <p class="text-small text-ink-soft">${t('checking.title')}</p>
          </div>
          <div class="demo-layer demo-answer">
            <p class="eyebrow">${t('landing.example.label')}</p>
            <div class="flex items-center gap-3">
              <span class="flex h-14 w-14 flex-none items-center justify-center rounded-leaf bg-surface-2 text-[2.2rem]">${cropIcon.cassava}</span>
              <p class="text-h3 font-bold">${t('landing.example.problem')}</p>
            </div>
            <div class="mx-auto w-full max-w-[16rem]">${gaugeSvg(t('landing.example.sure'))}
              <p class="-mt-2 text-center font-bold text-leaf-ink">${t('landing.example.sure')}</p></div>
            <p class="rounded-seed bg-surface-2 p-3 text-small"><strong>1.</strong> ${t('landing.example.step')}</p>
            <p class="text-small text-ink-soft">${t('landing.example.note')}</p>
          </div>
        </figure>
      </div>
      <div class="soil-edge" aria-hidden="true"></div>
    </section>

    <section class="page py-14">
      <h2 class="sr mb-6">${t('landing.how.title')}</h2>
      <ol class="grid gap-4 md:grid-cols-3">${steps}</ol>
    </section>

    <section class="bg-surface-2">
      <div class="page flex flex-col gap-6 py-14">
        <div class="sr flex flex-col gap-2"><h2>${t('landing.crops.title')}</h2><p>${t('landing.crops.body')}</p></div>
        <ul class="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-6">${crops}</ul>
      </div>
    </section>

    <section class="page py-12">
      <div class="grid grid-cols-2 gap-6 md:grid-cols-4">${facts}</div>
    </section>

    <section class="page grid gap-6 pb-14 md:grid-cols-2">
      <div class="sr spot card flex flex-col gap-3" data-spot><h2>${t('landing.remember.title')}</h2><p>${t('landing.remember.body')}</p></div>
      <div class="sr spot card flex flex-col gap-3" style="--i:1" data-spot><h2>${t('landing.honest.title')}</h2><p>${t('landing.honest.body')}</p></div>
    </section>

    <section class="band-dark furrows">
      <div class="page flex flex-col items-start gap-5 py-14">
        <h2 class="sr">${t('landing.title')}</h2>
        <div class="hero-cta sr flex flex-col gap-3 sm:flex-row sm:flex-wrap" style="--i:1">
          <a class="btn btn-leaf" href="#/register">${t('landing.cta')}</a>
          <a class="btn btn-ghost" href="#/login">${icons.check()} ${t('landing.haveAccount')}</a>
        </div>
      </div>
    </section>`;

  $('#guest').addEventListener('click', continueAsGuest);
  const stop = watchScroll(host);
  spotlight(host);
  return stop;
}
