// Bespoke line-and-fill icons so the interface works for people who read little or nothing.
// 48x48 grid, one stroke weight, colours from tokens only (currentColor for lines, --c-* for fills).
const wrap = (body, label) =>
  `<svg viewBox="0 0 48 48" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" role="${label ? 'img' : 'presentation'}" ${label ? `aria-label="${label}"` : 'aria-hidden="true"'} focusable="false">${body}</svg>`;

const leaf = 'fill="rgb(var(--c-leaf))"';
const sun = 'fill="rgb(var(--c-sun))"';

export const icons = {
  // a leaf with a magnifier: check my crop
  crop: (l) => wrap(`<path d="M8 30 C 8 16 20 8 34 8 C 34 22 26 32 12 32 Z" ${leaf}/><path d="M10 38 L 22 24"/><circle cx="34" cy="34" r="6" fill="rgb(var(--c-surface))"/><path d="M38.5 38.5 L 43 43"/>`, l),
  // a speech bubble with a question mark: ask a question
  question: (l) => wrap(`<path d="M8 10 H 40 V 31 H 24 L 15 39 V 31 H 8 Z" ${sun}/><path d="M20 19 C 20 15 28 15 28 19 C 28 22 24 22 24 25"/><circle cx="24" cy="28.2" r="0.6" fill="currentColor"/>`, l),
  // a sun behind a cloud: weather
  weather: (l) => wrap(`<circle cx="18" cy="17" r="7" ${sun}/><path d="M18 5 V 7 M6 17 H 8 M9.5 8.5 L 11 10 M26.5 8.5 L 25 10"/><path d="M14 38 C 8 38 8 29 14 29 C 15 22 26 21 28 28 C 35 27 37 38 31 38 Z" fill="rgb(var(--c-surface))"/>`, l),
  camera: (l) => wrap(`<path d="M6 16 H 14 L 17 11 H 31 L 34 16 H 42 V 37 H 6 Z" ${leaf}/><circle cx="24" cy="26" r="7" fill="rgb(var(--c-surface))"/><circle cx="24" cy="26" r="2.5" fill="currentColor" stroke="none"/>`, l),
  mic: (l) => wrap(`<rect x="17" y="5" width="14" height="24" rx="7" ${sun}/><path d="M10 23 C 10 33 38 33 38 23 M24 33 V 42 M17 42 H 31"/>`, l),
  pin: (l) => wrap(`<path d="M24 43 C 24 43 10 29 10 19 A 14 14 0 0 1 38 19 C 38 29 24 43 24 43 Z" ${leaf}/><circle cx="24" cy="19" r="5" fill="rgb(var(--c-surface))"/>`, l),
  check: (l) => wrap('<path d="M10 25 L 20 35 L 38 13"/>', l),
  speaker: (l) => wrap('<path d="M8 19 H 15 L 25 10 V 38 L 15 29 H 8 Z" fill="currentColor" stroke="none"/><path d="M31 17 C 35 21 35 27 31 31 M36 12 C 43 19 43 29 36 36"/>', l),
  back: (l) => wrap('<path d="M30 8 L 14 24 L 30 40"/>', l),
  // a small house: home / my farm
  home: (l) => wrap(`<path d="M6 23 L 24 7 L 42 23" /><path d="M11 20 V 40 H 37 V 20" ${leaf}/><path d="M20 40 V 29 H 28 V 40"/>`, l),
  // an open book: how to use
  book: (l) => wrap(`<path d="M24 12 C 19 8 11 8 6 10 V 38 C 11 36 19 36 24 40 C 29 36 37 36 42 38 V 10 C 37 8 29 8 24 12 Z" ${sun}/><path d="M24 12 V 40"/>`, l),
};

/** Big illustrations for permission screens: icon on a soft seed-shaped backdrop. */
export function picture(name, label) {
  return `<span class="picture" style="font-size:7rem">${icons[name](label)}</span>`;
}
