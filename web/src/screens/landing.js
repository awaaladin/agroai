// Landing: what the service is, how it works, what it will not do. Plain language, one example answer clearly
// labelled as an illustration (no invented numbers or testimonials), two calls to action.
import { t } from '../state/i18n.js';
import { go } from '../router.js';
import { isLoggedIn } from '../api/auth.js';
import { continueAsGuest } from '../state/account.js';
import { settings } from '../state/store.js';
import { icons } from '../ui/icons/index.js';
import { cropIcon, CROPS } from '../ui/crops.js';

export function render(host) {
  if (isLoggedIn() || settings.get().guest) { go('/dashboard', { replace: true }); return; }

  const steps = ['s1', 's2', 's3'].map((k, i) => `
    <li class="card reveal flex flex-col gap-3" style="--i:${i}">
      <span class="flex h-12 w-12 items-center justify-center rounded-pod bg-surface-2 font-bold text-h3">${i + 1}</span>
      <h3>${t(`landing.how.${k}.t`)}</h3><p>${t(`landing.how.${k}.b`)}</p>
    </li>`).join('');

  host.innerHTML = `
    <section class="band-dark">
      <div class="page grid gap-10 py-14 md:grid-cols-2 md:items-center md:py-20">
        <div class="flex flex-col gap-6">
          <p class="eyebrow fade-in">${t('landing.eyebrow')}</p>
          <h1 class="fade-in" style="--d:80ms">${t('landing.title')}</h1>
          <p class="fade-in text-body" style="--d:160ms">${t('landing.lead')}</p>
          <div class="fade-in flex flex-col gap-3 sm:flex-row" style="--d:240ms">
            <a class="btn btn-leaf" href="#/register">${t('landing.cta')}</a>
            <button class="btn btn-ghost" id="guest" type="button">${t('landing.guest')}</button>
          </div>
          <p class="fade-in text-small"><a class="link" href="#/login">${t('landing.haveAccount')}</a></p>
        </div>
        <figure class="card reveal flex flex-col gap-4 bg-surface" style="--i:3" aria-label="${t('landing.example.label')}">
          <figcaption class="eyebrow">${t('landing.example.label')}</figcaption>
          <div class="flex items-center gap-4">
            <span class="flex h-16 w-16 flex-none items-center justify-center rounded-leaf bg-surface-2 text-[2.6rem]">${cropIcon.cassava}</span>
            <div><p class="text-h3 font-bold">${t('landing.example.problem')}</p><p class="text-leaf-ink font-bold">${t('landing.example.sure')}</p></div>
          </div>
          <p>${t('landing.example.see')}</p>
          <p class="rounded-seed bg-surface-2 p-4"><strong>1.</strong> ${t('landing.example.step')}</p>
          <p class="text-small text-ink-soft">${t('landing.example.note')}</p>
        </figure>
      </div>
    </section>

    <section class="page py-14">
      <h2 class="mb-6">${t('landing.how.title')}</h2>
      <ol class="grid gap-5 md:grid-cols-3">${steps}</ol>
    </section>

    <section class="bg-surface-2">
      <div class="page grid gap-8 py-14 md:grid-cols-2">
        <div class="flex flex-col gap-3">
          <h2>${t('landing.crops.title')}</h2><p>${t('landing.crops.body')}</p>
          <div class="mt-2 flex flex-wrap gap-3" aria-hidden="true">
            ${CROPS.filter((c) => c !== 'other').map((c) => `<span class="flex h-14 w-14 items-center justify-center rounded-leaf bg-surface text-[2.2rem]">${cropIcon[c]}</span>`).join('')}
          </div>
        </div>
        <div class="flex flex-col gap-3">
          <h2>${t('landing.remember.title')}</h2><p>${t('landing.remember.body')}</p>
        </div>
      </div>
    </section>

    <section class="page py-14">
      <div class="card flex flex-col gap-3">
        <h2>${t('landing.honest.title')}</h2><p>${t('landing.honest.body')}</p>
        <div class="mt-2 flex flex-col gap-3 sm:flex-row">
          <a class="btn btn-primary" href="#/register">${t('landing.cta')}</a>
          <a class="btn btn-ghost" href="#/login">${icons.check()} ${t('landing.haveAccount')}</a>
        </div>
      </div>
    </section>`;

  host.querySelector('#guest').addEventListener('click', continueAsGuest);
}
