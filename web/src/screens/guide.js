// Guide: what the website does and how to use it, for people who are logged in (or using it as a guest).
// Plain language, short steps, same two languages as the rest of the app. All text lives in the locale files.
import { t, tList } from '../state/i18n.js';
import { icons } from '../ui/icons/index.js';

export function render(host) {
  const steps = ['s1', 's2', 's3', 's4'].map((k, i) => `
    <li class="card reveal flex gap-4" style="--i:${i}">
      <span class="flex h-12 w-12 flex-none items-center justify-center rounded-pod bg-surface-2 font-bold text-h3" aria-hidden="true">${i + 1}</span>
      <div class="flex flex-col gap-1"><h3>${t(`guide.start.${k}.t`)}</h3><p>${t(`guide.start.${k}.b`)}</p></div>
    </li>`).join('');

  const features = [
    { k: 'check', icon: 'crop' },
    { k: 'ask', icon: 'question' },
    { k: 'weather', icon: 'weather' },
    { k: 'farm', icon: 'home' },
    { k: 'account', icon: 'pin' },
    { k: 'language', icon: 'speaker' },
  ].map((f, i) => `
    <li class="card reveal flex flex-col gap-2" style="--i:${i}">
      <span class="flex h-14 w-14 items-center justify-center rounded-leaf bg-surface-2 text-[2.2rem]">${icons[f.icon]()}</span>
      <h3>${t(`guide.features.${f.k}.t`)}</h3><p>${t(`guide.features.${f.k}.b`)}</p>
    </li>`).join('');

  host.innerHTML = `
    <div class="page flex flex-col gap-10 py-8">
      <header class="flex flex-col gap-3">
        <h1 class="reveal">${t('guide.title')}</h1>
        <p class="reveal text-ink-soft" style="--i:1">${t('guide.lead')}</p>
        <div class="reveal flex flex-col gap-3 sm:flex-row" style="--i:2">
          <a class="btn btn-primary" href="#/check">${t('guide.go.check')}</a>
          <a class="btn btn-ghost" href="#/chat">${t('guide.go.ask')}</a>
        </div>
      </header>

      <section aria-labelledby="start-h" class="flex flex-col gap-4">
        <h2 id="start-h">${t('guide.start.title')}</h2>
        <ol class="grid gap-4 md:grid-cols-2">${steps}</ol>
      </section>

      <section aria-labelledby="feat-h" class="flex flex-col gap-4">
        <h2 id="feat-h">${t('guide.features.title')}</h2>
        <ul class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">${features}</ul>
      </section>

      <section aria-labelledby="photo-h" class="grid gap-6 md:grid-cols-2">
        <div class="card flex flex-col gap-3">
          <h2 id="photo-h">${t('guide.photo.title')}</h2>
          <ul class="flex flex-col gap-2">${tList('guide.photo.tips').map((x) => `<li class="flex gap-3"><span class="mt-1 flex-none text-leaf-ink">${icons.check()}</span><span>${x}</span></li>`).join('')}</ul>
        </div>
        <div class="card flex flex-col gap-3">
          <h2>${t('guide.read.title')}</h2><p>${t('guide.read.body')}</p>
        </div>
      </section>

      <section class="grid gap-6 md:grid-cols-2">
        <div class="card flex flex-col gap-3"><h2>${t('guide.limits.title')}</h2><p>${t('guide.limits.body')}</p></div>
        <div class="card flex flex-col gap-3"><h2>${t('guide.privacy.title')}</h2><p>${t('guide.privacy.body')}</p></div>
      </section>
    </div>`;
}
